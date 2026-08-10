"""
Documentation Generator.
Produces onboarding documentation, a plain-English explanation of the
generated code, and setup/dependency instructions.
"""

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
        "optionally authenticating with a bearer token. It exposes "
        "connect(), test_connection(), fetch_schema() (sample response), "
        "and close()."
    ),
}


def generate_documentation(spec, code):
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
