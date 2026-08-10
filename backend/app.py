"""
Data Source Onboarding & Connector Generation Agent — Backend API (FastAPI).

Two-step flow:
    1. POST /api/parse    -> agent reads the NL request, returns extracted spec
                              (source type, auth method, guessed name) — no code
                              generated yet.
    2. POST /api/onboard  -> user has filled in REAL connection details; this
                              validates those fields, runs a REAL connection
                              test, and (only on success) generates the
                              connector code + LLM-written documentation.

Other endpoints:
    GET  /api/fields/{source_type}        -> which input fields this source type needs
    GET  /api/connectors                  -> list all previously generated connectors
    GET  /api/connectors/{id}             -> get one connector's full details
    POST /api/connectors/{id}/test-live   -> re-test a saved connector with credentials
    GET  /api/connectors/{id}/download/code -> download the generated .py file
    GET  /api/connectors/{id}/download/docs -> download the generated .md file

Run with:
    uvicorn app:app --reload --port 5001
"""
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import agent
import generator
import validator
import doc_generator
import storage
import real_connectors
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


class GenerateRequest(BaseModel):
    """Sent once the user has filled in their REAL connection details."""
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


@app.get("/api/fields/{source_type}")
def fields_for_source_type(source_type: str):
    """CHANGE 1: which input fields this source type needs. The frontend
    calls this to render a source-specific form instead of a fixed one."""
    if source_type not in FIELD_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Unknown source type: {source_type}")
    return {"source_type": source_type, "fields": get_field_schema(source_type)}


@app.post("/api/onboard", status_code=201)
def onboard(body: GenerateRequest):
    """Step 2: user has entered real credentials. Validate fields, run a
    REAL connection test, and (only on success) generate connector code +
    LLM-written documentation."""
    spec = body.model_dump()

    # Fill in sensible defaults for anything left blank.
    if not spec.get("port"):
        spec["port"] = agent.default_port(spec["source_type"])
    if not spec.get("database"):
        spec["database"] = spec["source_name"]
    if not spec.get("user"):
        spec["user"] = "your_username"

    # CHANGE 2 (part 1): field-level validation BEFORE attempting a
    # connection, so obviously-missing fields get an immediate,
    # per-field error instead of a vague connection failure.
    field_errors = validator.validate_fields(spec)
    if field_errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Please fix the highlighted fields.", "field_errors": field_errors},
        )

    # REAL connection test — don't generate anything unless this succeeds.
    connection_result = real_connectors.test_real_connection(
        spec["source_type"],
        {
            "host": spec.get("host"),
            "port": spec.get("port"),
            "database": spec.get("database"),
            "user": spec.get("user"),
            "password": spec.get("password"),
            "auth_type": spec.get("auth_type"),
            "api_key": spec.get("api_key"),
        },
    )

    if connection_result["status"] != "success":
        # CHANGE 2 (part 2): attach the specific field the real connection
        # error points to (e.g. "password", "host"), determined in
        # real_connectors.py / validator.map_connection_error_to_field.
        field = connection_result.get("field")
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Connection {connection_result['status']}: {connection_result['message']}",
                "field_errors": {field: connection_result["message"]} if field else {},
            },
        )

    # Generate connector code (only reached if the connection worked)
    code, gen_error = generator.generate_connector_code(spec)
    if gen_error:
        raise HTTPException(status_code=400, detail={"message": gen_error, "field_errors": {}})

    syntax_valid, syntax_error = validator.validate_syntax(code)

    validation_report = {
        "syntax_valid": syntax_valid,
        "syntax_error": syntax_error,
        "connection_test": connection_result,
    }

    # CHANGE 3: documentation now comes from the LLM (doc_generator tries
    # Groq first, falls back to the template internally on failure).
    documentation = doc_generator.generate_documentation(spec, code)

    # Save (never store the raw password/api_key)
    stored_spec = {k: v for k, v in spec.items() if k not in ("password", "api_key")}
    record = storage.save_connector({
        "spec": stored_spec,
        "code": code,
        "validation": validation_report,
        "documentation": documentation,
    })

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


# CHANGE 4: downloadable files alongside the JSON response.
# The frontend gets everything as JSON from /api/onboard already; these two
# endpoints let the user click a real download link/button for the same
# code and documentation as standalone files.

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
    record = storage.get_by_id(connector_id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    filename = f"{record['spec']['source_name']}_documentation.md"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(record["documentation"], headers=headers, media_type="text/markdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5001, reload=True)