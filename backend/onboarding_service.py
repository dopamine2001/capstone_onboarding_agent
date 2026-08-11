"""
Shared connector-generation logic.

Used by both the manual /api/onboard endpoint and the automatic in-chat
generation flow (once agent.converse() decides all fields are gathered),
so there's exactly one place that does: validate -> test connection ->
generate code -> generate docs -> save.
"""
import generator
import validator
import doc_generator
import storage
import real_connectors
from agent import default_port


def run_onboarding(spec, dry_run=False):
    """
    Returns (record, error).
    - On success: (saved_record_dict, None)
    - On failure: (None, {"message": "...", "field_errors": {...}})
    """
    spec = dict(spec)  # don't mutate the caller's dict

    if not spec.get("port"):
        spec["port"] = default_port(spec.get("source_type"))
    if not spec.get("database"):
        spec["database"] = spec.get("source_name")
    if not spec.get("user"):
        spec["user"] = "your_username"

    if dry_run:
        spec["host"] = spec.get("host") or "localhost"
        spec["user"] = spec.get("user") or "test_user"
        spec["password"] = spec.get("password") or "dummy_password"
        spec["api_key"] = spec.get("api_key") or "dummy_api_key"
        spec["auth_type"] = spec.get("auth_type") or "none"

    if not dry_run:
        field_errors = validator.validate_fields(spec)
        if field_errors:
            return None, {"message": "Please fix the highlighted fields.", "field_errors": field_errors}

    if dry_run:
        connection_result = {
            "status": "dry_run",
            "message": (
                "Dry-run mode: no live connection was attempted. Syntax and "
                "class interface were validated; replace the placeholder "
                "values before using this against a real source."
            ),
            "field": None,
        }
    else:
        connection_result = real_connectors.test_real_connection(
            spec["source_type"],
            {
                "host": spec.get("host"),
                "port": spec.get("port"),
                "database": spec.get("database"),
                "user": spec.get("user"),
                "password": spec.get("password"),
                "auth_type": spec.get("auth_type"),
                "api_key": spec.get("api_key"),
            },
        )
        if connection_result["status"] != "success":
            field = connection_result.get("field")
            return None, {
                "message": f"Connection {connection_result['status']}: {connection_result['message']}",
                "field_errors": {field: connection_result["message"]} if field else {},
            }

    code, gen_error = generator.generate_connector_code(spec)
    if gen_error:
        return None, {"message": gen_error, "field_errors": {}}

    syntax_valid, syntax_error = validator.validate_syntax(code)

    validation_report = {
        "syntax_valid": syntax_valid,
        "syntax_error": syntax_error,
        "connection_test": connection_result,
    }

    documentation = doc_generator.generate_documentation(spec, code, dry_run=dry_run)
    env_example = generator.generate_env_example(spec)

    stored_spec = {k: v for k, v in spec.items() if k not in ("password", "api_key")}
    record = storage.save_connector({
        "spec": stored_spec,
        "code": code,
        "env_example": env_example,
        "validation": validation_report,
        "documentation": documentation,
    })

    return record, None