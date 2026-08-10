"""
Validator.
- validate_syntax(): checks generated Python code compiles.
- validate_fields(): checks the submitted connection-details form against
  that source type's field schema and returns SPECIFIC errors per field
  (not just one generic message), so the frontend can show each error next
  to the exact input that caused it.
"""
import ast

from field_schemas import get_field_schema, FIELD_SCHEMAS


def validate_syntax(code):
    """Return (is_valid, error_message)."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e}"


def validate_fields(spec):
    """
    Validate the submitted spec against its source type's field schema.

    Returns a dict of {field_name: "error message"} for every field that's
    missing or invalid. An empty dict means everything required is present.
    """
    errors = {}
    source_type = spec.get("source_type")

    if source_type not in FIELD_SCHEMAS:
        errors["source_type"] = f"Unsupported or unrecognized source type: '{source_type}'"
        return errors

    schema = get_field_schema(source_type)

    for field in schema:
        name = field["name"]
        value = spec.get(name)

        # REST API's credential field is conditionally required based on auth_type
        if source_type == "rest_api" and name == "api_key":
            auth_type = spec.get("auth_type", "none")
            if auth_type in ("api_key", "bearer_token") and not value:
                errors[name] = f"{field['label']} is required when auth type is '{auth_type}'."
            continue

        if field["required"] and (value is None or value == ""):
            errors[name] = f"{field['label']} is required."
            continue

        if field["type"] == "number" and value not in (None, ""):
            try:
                int(value)
            except (TypeError, ValueError):
                errors[name] = f"{field['label']} must be a number."

    return errors


def map_connection_error_to_field(message):
    """
    Best-effort mapping of a real driver error message to the field most
    likely responsible, so the frontend can highlight the right input even
    for errors that only show up once we actually try to connect (as
    opposed to missing-field errors, which validate_fields() already caught).
    """
    lowered = message.lower()

    if "password" in lowered or "authentication failed" in lowered:
        return "password"
    if "could not translate host" in lowered or "name or service not known" in lowered or "getaddrinfo" in lowered:
        return "host"
    if "connection refused" in lowered or "timed out" in lowered or "timeout" in lowered:
        return "host"
    if "database" in lowered and ("does not exist" in lowered or "unknown database" in lowered):
        return "database"
    if "role" in lowered and "does not exist" in lowered:
        return "user"
    if "access denied" in lowered:
        return "user"
    return None