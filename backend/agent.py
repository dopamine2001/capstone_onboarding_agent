"""
AI Agent (LLM-powered via Groq Cloud).

Understands a natural language onboarding request and turns it into a
structured spec: source type, auth method, and connection config.

Requires the GROQ_API_KEY environment variable to be set. Get a free key at
https://console.groq.com/keys — never hardcode it directly in this file.

This reads it from a .env file in the backend/ folder (see .env.example).
"""
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

import session_store
import source_resolver
import field_schemas

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a data engineering assistant that extracts structured
connection information from a natural language data source onboarding request.

Respond with ONLY a valid JSON object (no markdown, no explanation) with exactly
these keys:
- "source_name": short lowercase snake_case name for the source, e.g. "sales_db"
- "source_type": one of "postgresql", "mysql", "sqlserver", "rest_api", or "unknown"
- "auth_method": one of "username_password", "api_key", "oauth"
- "host": the hostname, URL, or "localhost" if not mentioned

Example input: "Connect to our PostgreSQL sales database at db.company.com using
username and password authentication"
Example output:
{"source_name": "sales_db", "source_type": "postgresql", "auth_method": "username_password", "host": "db.company.com"}
"""


def default_port(source_type):
    return {
        "postgresql": 5432,
        "mysql": 3306,
        "sqlserver": 1433,
        "rest_api": None,
    }.get(source_type, None)


def _extract_json(text):
    """Pull a JSON object out of the model's reply, even if it wraps it in
    markdown code fences or adds stray text around it."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))


def parse_request(request_text):
    """
    Parse a natural language onboarding request into a structured spec
    using the Groq LLM API. Returns a dict spec used by the connector
    generator. Falls back to a safe "unknown" spec if the API call or
    JSON parsing fails, so the app doesn't crash on a bad response.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request_text},
            ],
        )
        content = response.choices[0].message.content
        parsed = _extract_json(content)
    except Exception as e:
        print(f"LLM parsing failed, falling back to 'unknown' spec: {e}")
        parsed = {
            "source_name": "new_source",
            "source_type": "unknown",
            "auth_method": "username_password",
            "host": "localhost",
        }

    source_type = parsed.get("source_type", "unknown")
    source_name = parsed.get("source_name", "new_source")

    spec = {
        "source_name": source_name,
        "source_type": source_type,
        "auth_method": parsed.get("auth_method", "username_password"),
        "host": parsed.get("host", "localhost"),
        "port": default_port(source_type),
        "database": source_name,
        "user": "your_username",
        "raw_request": request_text,
    }
    return spec


EXTRACTION_SYSTEM_PROMPT = """Extract any of the following fields that the
user's message actually mentions. Only include a field if it's genuinely
present in the message — omit anything not mentioned. Respond with ONLY a
JSON object, no other text.

Fields:
- source_name: short snake_case name for the source, if given or implied
- source_type: one of "postgresql", "mysql", "sqlserver", "rest_api"
  (map obvious synonyms/typos: "pg"/"postge"/"postgres" -> "postgresql",
  "mssql"/"ms sql" -> "sqlserver")
- auth_method: one of "username_password", "api_key", "oauth", "none"
- auth_type: for REST APIs only — one of "none", "api_key", "bearer_token"
- host: hostname, IP address, or base URL
- port: port number (as an integer)
- database: database name
- user: username
- password: password
- api_key: API key or token value
"""


def _extract_fields_from_message(message):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        )
        return _extract_json(response.choices[0].message.content)
    except Exception as e:
        print(f"Field extraction failed: {e}")
        return {}


def _missing_fields(spec):
    """Deterministically compute which required fields are still missing,
    using field_schemas.py as the single source of truth — the same schema
    that used to drive the (now-removed) credentials form."""
    missing = []

    if not spec.get("source_name"):
        missing.append({"name": "source_name", "label": "a name for this source"})

    source_type = spec.get("source_type")
    if not source_type or source_type == "unknown":
        return missing  # can't know connection fields until source_type is known

    for field in field_schemas.get_field_schema(source_type):
        name = field["name"]
        if source_type == "rest_api" and name == "api_key":
            auth_type = spec.get("auth_type", "none")
            if auth_type in ("api_key", "bearer_token") and not spec.get("api_key"):
                missing.append(field)
            continue
        if field.get("required") and not spec.get(name):
            missing.append(field)

    return missing


def _ask_for_missing(missing_fields):
    names = [f["name"] for f in missing_fields]
    labels = [f.get("label", f["name"]) for f in missing_fields]

    if names == ["source_name"]:
        return "What would you like to name this source?"

    if "source_name" in names:
        labels[names.index("source_name")] = "a name for this source"

    if len(labels) == 1:
        return f"Got it! Now I just need the {labels[0]}."
    return "Got it! I still need: " + ", ".join(labels[:-1]) + f", and {labels[-1]}."


def _finalize_spec(spec, raw_request):
    source_type = spec.get("source_type", "unknown")
    return {
        "source_name": spec.get("source_name", "new_source"),
        "source_type": source_type,
        "auth_method": spec.get("auth_method", "username_password"),
        "host": spec.get("host", "localhost"),
        "port": spec.get("port") or default_port(source_type),
        "database": spec.get("database") or spec.get("source_name", "new_source"),
        "user": spec.get("user", "your_username"),
        "password": spec.get("password"),
        "auth_type": spec.get("auth_type", "none"),
        "api_key": spec.get("api_key"),
        "raw_request": raw_request,
    }


def converse(session_id, user_message, dummy_mode=False):
    """
    Multi-turn conversational entry point. Keeps context across calls using
    session_id. Field extraction/tracking is deterministic (Python, backed
    by field_schemas.py) rather than trusting the LLM to remember state
    across turns — the LLM is only used to pull whatever fields appear in
    THIS message. Only returns status "ready" once every required field
    for the detected source type has actually been gathered (or dummy_mode
    was requested).
    """
    session = session_store.get_session(session_id)
    session["messages"].append({"role": "user", "content": user_message})

    if dummy_mode:
        session["dummy_mode"] = True

    # Deterministic fuzzy/synonym backstop for source_type — catches typos
    # and abbreviations ("pg", "postge", "mssql") reliably.
    resolved_type, is_ambiguous = source_resolver.resolve_source_type(user_message)

    # LLM extracts whatever fields are mentioned in THIS message only.
    extracted = _extract_fields_from_message(user_message)
    if resolved_type and not extracted.get("source_type"):
        extracted["source_type"] = resolved_type

    # Merge into the running spec (never overwrite a known value with a blank).
    for key, value in extracted.items():
        if value in (None, ""):
            continue
        if key == "port":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        session["spec"][key] = value

    spec = session["spec"]

    # Ambiguity check — only matters while source_type is still unknown.
    if (not spec.get("source_type") or spec.get("source_type") == "unknown") and is_ambiguous:
        message = (
            "Could you tell me which specific database or API you mean? "
            "We currently support PostgreSQL, MySQL, SQL Server, and REST APIs."
        )
        session["messages"].append({"role": "assistant", "content": message})
        return {"session_id": session_id, "status": "clarify", "message": message, "spec": None}

    # Dummy mode: fill in anything still missing and go straight to ready.
    if session.get("dummy_mode"):
        spec.setdefault("source_type", "postgresql")
        spec.setdefault("source_name", "new_source")
        spec.setdefault("auth_method", "username_password")
        spec.setdefault("host", "localhost")
        message = "Got it — generating with placeholder/dummy values."
        session["messages"].append({"role": "assistant", "content": message})
        return {
            "session_id": session_id,
            "status": "ready",
            "message": message,
            "spec": _finalize_spec(spec, user_message),
            "dry_run": True,
        }

    # Ask for whatever's still missing, remembering everything gathered so far.
    missing = _missing_fields(spec)
    if missing:
        message = _ask_for_missing(missing)
        session["messages"].append({"role": "assistant", "content": message})
        return {"session_id": session_id, "status": "need_info", "message": message, "spec": None}

    # Everything required is present — ready to generate automatically.
    message = f"{spec.get('source_type', 'source').capitalize()} connection spec is complete. Generating your connector now..."
    session["messages"].append({"role": "assistant", "content": message})
    return {
        "session_id": session_id,
        "status": "ready",
        "message": message,
        "spec": _finalize_spec(spec, user_message),
        "dry_run": False,
    }