"""
Validator.
Checks generated code for valid Python syntax and simulates a connection
test (since real credentials usually aren't available at generation time).
"""
import ast


def validate_syntax(code):
    """Return (is_valid, error_message)."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e}"


def test_connection(spec):
    """
    Simulated connection test.

    A real implementation would actually import and run the generated
    connector's test_connection() with real credentials. Here we simulate
    a basic check based on whether required config fields are present,
    so the project can run end-to-end without live databases.
    """
    required_fields = ["source_type", "host"]
    missing = [f for f in required_fields if not spec.get(f)]

    if spec.get("source_type") == "unknown":
        return {
            "status": "failed",
            "message": "Could not determine source type from the request.",
        }

    if missing:
        return {
            "status": "failed",
            "message": f"Missing required fields: {', '.join(missing)}",
        }

    return {
        "status": "simulated_success",
        "message": (
            "Syntax and config look valid. This is a simulated connection "
            "test — plug in real credentials and run the generated file "
            "directly to test against a live source."
        ),
    }


def validate(code, spec):
    """Run all validation checks and return a combined report."""
    syntax_ok, syntax_error = validate_syntax(code)
    connection_result = test_connection(spec)

    return {
        "syntax_valid": syntax_ok,
        "syntax_error": syntax_error,
        "connection_test": connection_result,
    }
