"""
Real Connection Tester.
Actually attempts to connect to the live data source using the credentials
the user provides in the UI (not stored anywhere — used once, then discarded).

Each function imports its driver lazily so the backend still runs fine even
if you haven't installed every driver (e.g. you only need psycopg2 if you're
only testing PostgreSQL sources).

Every result includes a "field" key (may be None) pointing at the specific
input field most likely responsible, so the frontend can highlight it.
"""
from validator import map_connection_error_to_field


def _failure(message, field=None):
    return {
        "status": "failed",
        "message": message,
        "field": field or map_connection_error_to_field(message),
    }


def _error(message):
    return {"status": "error", "message": message, "field": None}


def _success(message):
    return {"status": "success", "message": message, "field": None}


def test_postgresql(config):
    try:
        import psycopg2
    except ImportError:
        return _error("psycopg2-binary is not installed. Run: pip install psycopg2-binary")

    try:
        conn = psycopg2.connect(
            host=config.get("host"),
            port=int(config.get("port") or 5432),
            dbname=config.get("database"),
            user=config.get("user"),
            password=config.get("password"),
            connect_timeout=5,
        )
        conn.close()
        return _success("Connected to PostgreSQL successfully.")
    except Exception as e:
        return _failure(str(e))


def test_mysql(config):
    try:
        import mysql.connector
    except ImportError:
        return _error("mysql-connector-python is not installed. Run: pip install mysql-connector-python")

    try:
        conn = mysql.connector.connect(
            host=config.get("host"),
            port=int(config.get("port") or 3306),
            database=config.get("database"),
            user=config.get("user"),
            password=config.get("password"),
            connection_timeout=5,
        )
        conn.close()
        return _success("Connected to MySQL successfully.")
    except Exception as e:
        return _failure(str(e))


def test_sqlserver(config):
    try:
        import pyodbc
    except ImportError:
        return _error("pyodbc is not installed (also needs the system ODBC driver). See README.")

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.get('host')},{config.get('port') or 1433};"
            f"DATABASE={config.get('database')};"
            f"UID={config.get('user')};PWD={config.get('password')}"
        )
        conn = pyodbc.connect(conn_str, timeout=5)
        conn.close()
        return _success("Connected to SQL Server successfully.")
    except Exception as e:
        return _failure(str(e))


def test_rest_api(config):
    try:
        import requests
    except ImportError:
        return _error("requests is not installed. Run: pip install requests")

    auth_type = config.get("auth_type", "none")
    api_key = config.get("api_key")

    if auth_type in ("api_key", "bearer_token") and not api_key:
        return _failure(
            f"Auth type is '{auth_type}' but no API key/token was provided.",
            field="api_key",
        )

    headers = {}
    if auth_type == "api_key" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_type == "bearer_token" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(config.get("host"), headers=headers, timeout=5)
        if response.status_code in (401, 403):
            return _failure(
                f"API rejected the credentials. HTTP status: {response.status_code}",
                field="api_key",
            )
        if response.status_code < 500:
            return _success(f"Reached the API. HTTP status: {response.status_code}")
        return _failure(f"API returned server error. HTTP status: {response.status_code}", field="host")
    except Exception as e:
        return _failure(str(e), field="host")


TESTERS = {
    "postgresql": test_postgresql,
    "mysql": test_mysql,
    "sqlserver": test_sqlserver,
    "rest_api": test_rest_api,
}


def test_real_connection(source_type, config):
    tester = TESTERS.get(source_type)
    if not tester:
        return _error(f"Unsupported source type: {source_type}")
    return tester(config)