"""
Data Source Onboarding & Connector Generation Agent — Backend API (FastAPI).

Conversational flow:
    1. POST /api/chat      -> multi-turn chat with session memory. The agent
                               asks clarifying/follow-up questions until it
                               has enough info, then returns status "ready"
                               with a spec.
    2. POST /api/onboard   -> user has filled in REAL connection details (or
                               requested dry-run/dummy mode); this validates
                               those fields, runs a REAL connection test (or
                               skips it in dry-run mode), and generates the
                               connector code + LLM-written documentation.

Other endpoints:
    GET  /api/fields/{source_type}          -> which input fields this source type needs
    GET  /api/connectors                    -> list all previously generated connectors
    GET  /api/connectors/{id}               -> get one connector's full details
    POST /api/connectors/{id}/test-live     -> re-test a saved connector with credentials
    GET  /api/connectors/{id}/download/code -> download the generated .py file
    GET  /api/connectors/{id}/download/docs -> download the documentation as a PDF
    GET  /api/connectors/{id}/download/bundle -> download .py + .pdf + .env.example as a .zip

Legacy (kept, no longer used by the chat UI):
    POST /api/parse -> original one-shot NL parser

Run with:
    uvicorn app:app --reload --port 5001
"""
import io
import uuid
import zipfile
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

import agent
import generator
import validator
import doc_generator
import storage
import real_connectors
import pdf_generator
import session_store
import onboarding_service
import templates
from field_schemas import get_field_schema, FIELD_SCHEMAS

app = FastAPI(title="Data Source Onboarding & Connector Generation Agent")

# Allow the React dev server (http://localhost:3000) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    request: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    dummy_mode: Optional[bool] = False


class GenerateRequest(BaseModel):
    """Sent once the user has filled in their REAL connection details
    (or requested dry-run/dummy-data mode)."""
    source_name: str
    source_type: str
    auth_method: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    auth_type: Optional[str] = None   # rest_api only: "none" | "api_key" | "bearer_token"
    api_key: Optional[str] = None
    raw_request: Optional[str] = None
    dry_run: Optional[bool] = False   # skip the real connection test, use placeholders


class LiveTestRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    auth_type: Optional[str] = None
    api_key: Optional[str] = None


@app.post("/api/parse")
def parse(body: ParseRequest):
    """Step 1: understand the natural language request. Does NOT generate
    code yet — just returns the extracted spec so the frontend can show a
    form for the user's real connection details."""
    nl_request = body.request.strip()
    if not nl_request:
        raise HTTPException(status_code=400, detail="Field 'request' is required.")

    spec = agent.parse_request(nl_request)
    return spec


@app.post("/api/chat")
def chat(body: ChatRequest):
    """Multi-turn conversational endpoint. The frontend keeps session_id
    across turns; the agent asks clarifying/follow-up questions, remembering
    everything gathered so far, and once status is "ready" this endpoint
    AUTOMATICALLY runs the connection test + code generation + PDF docs and
    returns the result inline — no separate form/endpoint needed."""
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Field 'message' is required.")

    session_id = body.session_id or str(uuid.uuid4())
    turn = agent.converse(session_id, message, dummy_mode=bool(body.dummy_mode))

    response = {
        "session_id": session_id,
        "status": turn["status"],
        "message": turn["message"],
        "result": None,
    }

    if turn["status"] == "ready" and turn.get("spec"):
        record, error = onboarding_service.run_onboarding(
            turn["spec"], dry_run=bool(turn.get("dry_run"))
        )

        if error:
            # Turn a generation failure into a natural chat message instead
            # of an HTTP error, so the conversation can continue — and clear
            # the offending field(s) from session memory so the user's next
            # message is treated as a correction, not a duplicate.
            field_errors = error.get("field_errors") or {}
            session = session_store.get_session(session_id)
            for field_name in field_errors:
                session["spec"].pop(field_name, None)

            if field_errors:
                fix_list = ", ".join(field_errors.values())
                response["message"] = f"{error['message']} Could you provide a corrected value? ({fix_list})"
            else:
                response["message"] = error["message"]
            response["status"] = "need_info"
        else:
            response["result"] = record
            response["message"] = turn["message"] + " Your connector is ready below."

    return response


@app.post("/api/chat/{session_id}/reset")
def chat_reset(session_id: str):
    session_store.reset_session(session_id)
    return {"reset": True}


@app.get("/api/fields/{source_type}")
def fields_for_source_type(source_type: str):
    """CHANGE 1: which input fields this source type needs. The frontend
    calls this to render a source-specific form instead of a fixed one."""
    if source_type not in FIELD_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Unknown source type: {source_type}")
    return {"source_type": source_type, "fields": get_field_schema(source_type)}


@app.get("/api/templates/{source_type}/versions")
def template_versions(source_type: str):
    """Governance/versioning visibility: the current version of the
    connector template for this source type, plus its full changelog —
    so it's possible to see what changed between versions, not just a
    string baked into generated code."""
    if source_type not in FIELD_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Unknown source type: {source_type}")
    return {
        "source_type": source_type,
        "current_version": templates.get_template_version(source_type),
        "changelog": templates.get_template_changelog(source_type),
    }


@app.post("/api/onboard", status_code=201)
def onboard(body: GenerateRequest):
    """Manual/legacy path — kept for direct API use. The chat flow no
    longer calls this; it runs onboarding_service.run_onboarding()
    automatically once enough fields are gathered in conversation."""
    spec = body.model_dump()
    dry_run = bool(spec.pop("dry_run", False))

    record, error = onboarding_service.run_onboarding(spec, dry_run=dry_run)
    if error:
        status_code = 422 if error["message"].startswith("Please fix") else 400
        raise HTTPException(status_code=status_code, detail=error)

    return record


@app.get("/api/connectors")
def list_connectors():
    return storage.get_all()


@app.get("/api/connectors/{connector_id}")
def get_connector(connector_id: int):
    record = storage.get_by_id(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")
    return record


@app.post("/api/connectors/{connector_id}/test-live")
def test_live_connection(connector_id: int, body: LiveTestRequest):
    """Re-test a previously generated connector with (possibly updated)
    real credentials."""
    record = storage.get_by_id(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    source_type = record["spec"]["source_type"]
    config = body.model_dump(exclude_none=True)

    result = real_connectors.test_real_connection(source_type, config)
    return result


# Downloadable files alongside the chat/JSON response: the frontend gets
# everything as JSON from /api/onboard already; these endpoints let the
# user click a real download link/button for the code, documentation
# (as PDF), or a single .zip bundle of everything.

@app.get("/api/connectors/{connector_id}/download/code")
def download_code(connector_id: int):
    record = storage.get_by_id(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    filename = f"{record['spec']['source_name']}_connector.py"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(record["code"], headers=headers, media_type="text/x-python")


@app.get("/api/connectors/{connector_id}/download/docs")
def download_docs(connector_id: int):
    """Documentation is delivered as a PDF, generated on the fly from the
    saved Markdown."""
    record = storage.get_by_id(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    pdf_bytes = pdf_generator.markdown_to_pdf_bytes(record["documentation"])
    filename = f"{record['spec']['source_name']}_documentation.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, headers=headers, media_type="application/pdf")


@app.get("/api/connectors/{connector_id}/download/bundle")
def download_bundle(connector_id: int):
    """A single .zip containing the connector code, documentation PDF, and
    a .env.example — everything needed to start using the connector."""
    record = storage.get_by_id(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    pdf_bytes = pdf_generator.markdown_to_pdf_bytes(record["documentation"])
    source_name = record["spec"]["source_name"]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{source_name}_connector.py", record["code"])
        zf.writestr(f"{source_name}_documentation.pdf", pdf_bytes)
        zf.writestr(".env.example", record.get("env_example", ""))
    buffer.seek(0)

    filename = f"{source_name}_bundle.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=buffer.getvalue(), headers=headers, media_type="application/zip")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5001, reload=True)