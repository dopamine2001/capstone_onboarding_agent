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
