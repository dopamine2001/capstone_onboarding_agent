"""
Data Source Onboarding & Connector Generation Agent — Backend API (FastAPI).

Two-step flow:
    1. POST /api/parse    -> agent reads the NL request, returns extracted spec
                              (source type, auth method, guessed name) — no code
                              generated yet.
    2. POST /api/onboard  -> user has filled in REAL connection details; this
                              generates the connector code, runs a REAL
                              connection test with those credentials, and
                              generates documentation — all in one step.

Other endpoints:
    GET  /api/connectors                  -> list all previously generated connectors
    GET  /api/connectors/{id}             -> get one connector's full details
    POST /api/connectors/{id}/test-live   -> re-test a saved connector with credentials

Run with:
    uvicorn app:app --reload --port 5001
"""
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import agent
import generator
import validator
import doc_generator
import storage
import real_connectors

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
    auth_method: str
    host: str
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    raw_request: Optional[str] = None


class LiveTestRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
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


@app.post("/api/onboard", status_code=201)
def onboard(body: GenerateRequest):
    """Step 2: user has entered real credentials. Generate the connector,
    run a REAL connection test with those credentials, and generate docs."""
    spec = body.model_dump()

    # Fill in sensible defaults for anything left blank.
    if not spec.get("port"):
        spec["port"] = agent.default_port(spec["source_type"])
    if not spec.get("database"):
        spec["database"] = spec["source_name"]
    if not spec.get("user"):
        spec["user"] = "your_username"

    # 1. REAL connection test FIRST — don't generate anything unless this
    #    actually succeeds.
    connection_result = real_connectors.test_real_connection(
        spec["source_type"],
        {
            "host": spec.get("host"),
            "port": spec.get("port"),
            "database": spec.get("database"),
            "user": spec.get("user"),
            "password": spec.get("password"),
            "api_key": spec.get("api_key"),
        },
    )

    if connection_result["status"] != "success":
        raise HTTPException(
            status_code=400,
            detail=f"Connection {connection_result['status']}: {connection_result['message']}",
        )

    # 2. Generate connector code (only reached if the connection worked)
    code, gen_error = generator.generate_connector_code(spec)
    if gen_error:
        raise HTTPException(status_code=400, detail=gen_error)

    # 3. Syntax check
    syntax_valid, syntax_error = validator.validate_syntax(code)

    validation_report = {
        "syntax_valid": syntax_valid,
        "syntax_error": syntax_error,
        "connection_test": connection_result,
    }

    # 4. Generate documentation
    documentation = doc_generator.generate_documentation(spec, code)

    # 5. Save (never store the raw password/api_key)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=5001, reload=True)