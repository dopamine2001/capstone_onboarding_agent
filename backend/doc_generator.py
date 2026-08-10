"""
Documentation Generator.

Primary path: ask the Groq LLM to write the onboarding documentation, a
plain-English explanation of the generated code, and setup/dependency
instructions, based on the actual generated connector code and spec.

Fallback path: if the LLM call fails for any reason (no API key, network
issue, rate limit, bad response), fall back to the original template-based
generator so the app never breaks because of the LLM being unavailable.
"""
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

DEPENDENCIES = {
    "postgresql": ["psycopg2-binary"],
    "mysql": ["mysql-connector-python"],
    "sqlserver": ["pyodbc"],
    "rest_api": ["requests"],
}

EXPLANATIONS = {
    "postgresql": (
        "This connector uses psycopg2 to open a connection to a PostgreSQL "
        "database. It exposes connect(), test_connection(), fetch_schema() "
        "(lists tables), and close()."
    ),
    "mysql": (
        "This connector uses mysql-connector-python to open a connection to "
        "a MySQL database. It exposes connect(), test_connection(), "
        "fetch_schema() (lists tables), and close()."
    ),
    "sqlserver": (
        "This connector uses pyodbc with the 'ODBC Driver 17 for SQL Server' "
        "to connect to a SQL Server database. It exposes connect(), "
        "test_connection(), fetch_schema() (lists tables), and close()."
    ),
    "rest_api": (
        "This connector uses the requests library to call a REST API, "
        "optionally authenticating with an API key or bearer token. It "
        "exposes connect(), test_connection(), fetch_schema() (sample "
        "response), and close()."
    ),
}


def generate_documentation_template(spec, code):
    """Original fixed-template generator. Used as a fallback."""
    source_type = spec.get("source_type")
    source_name = spec.get("source_name")
    deps = DEPENDENCIES.get(source_type, [])
    explanation = EXPLANATIONS.get(source_type, "No explanation available.")

    doc = f"""# Onboarding Documentation: {source_name}

## Overview
- **Source type:** {source_type}
- **Auth method:** {spec.get('auth_method')}
- **Host:** {spec.get('host')}
- **Database/Base URL:** {spec.get('database')}

## What this connector does
{explanation}

## Dependencies
Install the following before using this connector:

```
pip install {' '.join(deps)}
```

## Configuration
Before running, replace the placeholder credentials in the generated file
with your real values (host, port, user, password/API key).

## How to test it
Run the generated Python file directly:

```
python {source_name}_connector.py
```

It will print whether the connection succeeded.

## Original request
> {spec.get('raw_request')}
"""
    return doc


def generate_documentation_llm(spec, code):
    """Ask the LLM to write documentation based on the real generated code
    and spec. Raises on failure — caller is expected to catch and fall
    back to the template version."""
    prompt = f"""You are a technical writer for a data engineering team.
Write onboarding documentation in Markdown for the following auto-generated
Python connector.

Source spec:
- source_name: {spec.get('source_name')}
- source_type: {spec.get('source_type')}
- auth_method: {spec.get('auth_method')}
- host: {spec.get('host')}
- database: {spec.get('database')}

Generated connector code:
```python
{code}
```

Write the documentation with these sections, in Markdown:
1. "## Overview" — what this connector is for, in one or two sentences.
2. "## What this connector does" — a plain-English explanation of the code
   (what each main method does).
3. "## Dependencies" — the pip install command for whatever library the
   code imports.
4. "## Configuration" — what the user needs to fill in before using it
   (host, credentials, etc.) — don't repeat real credential values.
5. "## How to test it" — how to run the file directly.

Respond with ONLY the Markdown documentation, no preamble or commentary
outside of it.
"""
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def generate_documentation(spec, code):
    """Try the LLM first; fall back to the template on any failure."""
    try:
        return generate_documentation_llm(spec, code)
    except Exception as e:
        print(f"LLM documentation generation failed, using template fallback: {e}")
        return generate_documentation_template(spec, code)