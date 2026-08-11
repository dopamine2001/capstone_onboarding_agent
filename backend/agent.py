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


CHAT_SYSTEM_PROMPT = """You are a friendly data engineering onboarding assistant
having a conversation to gather what's needed to onboard a new data source
connector.

You need to eventually know:
- source_type: one of "postgresql", "mysql", "sqlserver", "rest_api"
- auth_method: one of "username_password", "api_key", "oauth", "none"
- source_name: a short snake_case name for the source
- host: hostname or base URL, if the user has mentioned one (optional)

Rules:
- If the user's message is genuinely ambiguous about source_type (e.g. "a SQL
  database" without saying which engine, or just "an API"), do NOT guess.
  Ask ONE short, polite clarifying question instead, e.g.: "Could you tell me
  which SQL database you mean — PostgreSQL, MySQL, or SQL Server?"
- If source_type is already clear (including from typos/abbreviations like
  "pg" or "mssql") but auth_method or source_name is still unknown, ask a
  single short, natural follow-up question for the most important missing
  piece.
- If the user explicitly says things like "just generate it", "use
  defaults", "dummy data", or "I don't have real details yet" — treat that as
  a request to fill in any missing fields with sensible placeholders and
  proceed.
- Once source_type and auth_method are both known (or defaulted), mark the
  spec ready. Do not ask more questions than necessary.

Always respond with ONLY a JSON object (no markdown, no extra text):
{
  "status": "clarify" | "need_info" | "ready",
  "message": "<a short, natural chat reply — a question, or a confirmation>",
  "spec": {"source_name": "...", "source_type": "...", "auth_method": "...", "host": "..."}
}
Only include spec keys you're actually confident about; omit unknown ones.
"""


def converse(session_id, user_message, dummy_mode=False):
    """
    Multi-turn conversational entry point. Keeps context across calls using
    session_id, asks clarifying/follow-up questions when needed, and only
    returns a final spec once (status == "ready").
    """
    session = session_store.get_session(session_id)

    # Deterministic fuzzy/synonym backstop — catches typos and abbreviations
    # ("pg", "postge", "mssql") reliably even if the LLM's own read is off,
    # and flags genuinely ambiguous phrasing so we don't silently guess.
    resolved_type, is_ambiguous = source_resolver.resolve_source_type(user_message)

    llm_user_message = user_message
    if dummy_mode:
        llm_user_message += (
            "\n\n(The user wants to proceed with dummy/placeholder values "
            "for anything still missing — do not ask further questions.)"
        )
    llm_user_message += f"\n\nInformation already gathered so far: {json.dumps(session['spec'])}"

    session["messages"].append({"role": "user", "content": user_message})

    conversation_for_llm = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    conversation_for_llm.extend(session["messages"][-8:-1])  # prior turns, for context
    conversation_for_llm.append({"role": "user", "content": llm_user_message})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=conversation_for_llm,
        )
        parsed = _extract_json(response.choices[0].message.content)
    except Exception as e:
        print(f"Conversational parsing failed: {e}")
        parsed = {
            "status": "need_info",
            "message": "Sorry, I had trouble understanding that — could you rephrase?",
            "spec": {},
        }

    spec_update = parsed.get("spec", {}) or {}

    # If the LLM missed an obvious typo/abbreviation, use our deterministic match.
    if resolved_type and not spec_update.get("source_type"):
        spec_update["source_type"] = resolved_type

    # If phrasing was clearly ambiguous and nothing resolved it, force a clarify.
    if is_ambiguous and not spec_update.get("source_type") and not session["spec"].get("source_type"):
        parsed["status"] = "clarify"
        if not parsed.get("message"):
            parsed["message"] = (
                "Could you tell me which specific database or API you mean? "
                "We currently support PostgreSQL, MySQL, SQL Server, and REST APIs."
            )

    session["spec"].update({k: v for k, v in spec_update.items() if v})

    if dummy_mode:
        session["spec"].setdefault("source_type", "postgresql")
        session["spec"].setdefault("auth_method", "username_password")
        session["spec"].setdefault("source_name", "new_source")
        session["spec"].setdefault("host", "localhost")
        parsed["status"] = "ready"
        if not parsed.get("message"):
            parsed["message"] = "Got it — generating with placeholder/dummy values."

    session["messages"].append({"role": "assistant", "content": parsed.get("message", "")})

    final_spec = None
    if parsed.get("status") == "ready":
        st = session["spec"].get("source_type", "unknown")
        source_name = session["spec"].get("source_name", "new_source")
        final_spec = {
            "source_name": source_name,
            "source_type": st,
            "auth_method": session["spec"].get("auth_method", "username_password"),
            "host": session["spec"].get("host", "localhost"),
            "port": default_port(st),
            "database": source_name,
            "user": "your_username",
            "raw_request": user_message,
        }

    return {
        "session_id": session_id,
        "status": parsed.get("status", "need_info"),
        "message": parsed.get("message", ""),
        "spec": final_spec,
    }