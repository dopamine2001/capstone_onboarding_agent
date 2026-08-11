"""
Connector Generator.
Takes a structured spec (from agent.py) and fills the matching template
(from templates.py) to produce final, ready-to-use Python connector code.
"""
from templates import TEMPLATES, TEMPLATE_VERSION

ENV_VAR_MAP = {
    "postgresql": ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"],
    "mysql": ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"],
    "sqlserver": ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"],
    "rest_api": ["API_BASE_URL", "API_AUTH_TYPE", "API_CREDENTIAL"],
}


def _class_name(source_name):
    parts = [p.capitalize() for p in source_name.split("_") if p]
    return "".join(parts) + "Connector" if parts else "GeneratedConnector"


def generate_connector_code(spec):
    """
    Generate Python connector source code from a spec dict.
    Returns (code_string, error) — error is None on success.
    """
    source_type = spec.get("source_type")
    template = TEMPLATES.get(source_type)

    if not template:
        return None, f"No template available for source type '{source_type}'."

    class_name = _class_name(spec.get("source_name", "source"))

    try:
        code = template.format(
            template_version=TEMPLATE_VERSION,
            class_name=class_name,
            source_name=spec.get("source_name"),
            host=spec.get("host") or "localhost",
            port=spec.get("port") or 0,
            database=spec.get("database"),
            user=spec.get("user"),
        )
    except KeyError as e:
        return None, f"Missing field for template: {e}"

    return code, None


def generate_env_example(spec):
    """Produces a .env.example listing the env vars this connector expects,
    for the 'placeholder environment variable mappings' requirement."""
    source_type = spec.get("source_type")
    var_names = ENV_VAR_MAP.get(source_type, [])
    lines = [f"# Environment variables for '{spec.get('source_name')}' ({source_type})"]
    lines.extend(f"{name}=" for name in var_names)
    return "\n".join(lines) + "\n"