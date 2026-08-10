"""
Connector Generator.
Takes a structured spec (from agent.py) and fills the matching template
(from templates.py) to produce final, ready-to-use Python connector code.
"""
from templates import TEMPLATES, TEMPLATE_VERSION


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
