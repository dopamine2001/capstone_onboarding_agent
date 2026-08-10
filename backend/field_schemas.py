"""
Declarative input field definitions per source type.

Adding a new source type later just means adding a new entry here — no
frontend form logic needs to change, since the form renders whatever this
returns.

Each field has:
    name        - key used in the request body / spec
    label       - human-readable label shown in the UI
    type        - "text" | "password" | "number" | "select"
    required    - whether it must be filled in
    options     - only for type "select": list of {value, label}
"""

FIELD_SCHEMAS = {
    "postgresql": [
        {"name": "host", "label": "Host", "type": "text", "required": True},
        {"name": "port", "label": "Port", "type": "number", "required": True},
        {"name": "database", "label": "Database", "type": "text", "required": True},
        {"name": "user", "label": "Username", "type": "text", "required": True},
        {"name": "password", "label": "Password", "type": "password", "required": True},
    ],
    "mysql": [
        {"name": "host", "label": "Host", "type": "text", "required": True},
        {"name": "port", "label": "Port", "type": "number", "required": True},
        {"name": "database", "label": "Database", "type": "text", "required": True},
        {"name": "user", "label": "Username", "type": "text", "required": True},
        {"name": "password", "label": "Password", "type": "password", "required": True},
    ],
    "sqlserver": [
        {"name": "host", "label": "Host", "type": "text", "required": True},
        {"name": "port", "label": "Port", "type": "number", "required": True},
        {"name": "database", "label": "Database", "type": "text", "required": True},
        {"name": "user", "label": "Username", "type": "text", "required": True},
        {"name": "password", "label": "Password", "type": "password", "required": True},
    ],
    "rest_api": [
        {"name": "host", "label": "Base URL", "type": "text", "required": True},
        {
            "name": "auth_type",
            "label": "Auth Type",
            "type": "select",
            "required": True,
            "options": [
                {"value": "none", "label": "No auth"},
                {"value": "api_key", "label": "API Key"},
                {"value": "bearer_token", "label": "Bearer Token"},
            ],
        },
        # credential field is conditionally required depending on auth_type -
        # enforced in validator.py, not here, since it depends on another field's value
        {"name": "api_key", "label": "API Key / Token", "type": "password", "required": False},
    ],
}


def get_field_schema(source_type):
    return FIELD_SCHEMAS.get(source_type, [])