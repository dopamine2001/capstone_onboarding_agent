"""
Real Connection Tester.
Actually attempts to connect to the live data source using the credentials
the user provides in the UI (not stored anywhere — used once, then discarded).

Each function imports its driver lazily so the backend still runs fine even
if you haven't installed every driver (e.g. you only need psycopg2 if you're
only testing PostgreSQL sources).
"""


def test_postgresql(config):
    try:
        import psycopg2
    except ImportError:
        return {"status": "error", "message": "psycopg2-binary is not installed. Run: pip install psycopg2-binary"}

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
        return {"status": "success", "message": "Connected to PostgreSQL successfully."}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


def test_mysql(config):
    try:
        import mysql.connector
    except ImportError:
        return {"status": "error", "message": "mysql-connector-python is not installed. Run: pip install mysql-connector-python"}

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
        return {"status": "success", "message": "Connected to MySQL successfully."}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


def test_sqlserver(config):
    try:
        import pyodbc
    except ImportError:
        return {"status": "error", "message": "pyodbc is not installed (also needs the system ODBC driver). See README."}

    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={config.get('host')},{config.get('port') or 1433};"
            f"DATABASE={config.get('database')};"
            f"UID={config.get('user')};PWD={config.get('password')}"
        )
        conn = pyodbc.connect(conn_str, timeout=5)
        conn.close()
        return {"status": "success", "message": "Connected to SQL Server successfully."}
    except Exception as e:
        return {"status": "failed", "message": str(e)}


def test_rest_api(config):
    try:
        import requests
    except ImportError:
        return {"status": "error", "message": "requests is not installed. Run: pip install requests"}

    try:
        headers = {}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        response = requests.get(config.get("host"), headers=headers, timeout=5)
        if response.status_code < 500:
            return {
                "status": "success",
                "message": f"Reached the API. HTTP status: {response.status_code}",
            }
        return {
            "status": "failed",
            "message": f"API returned server error. HTTP status: {response.status_code}",
        }
    except Exception as e:
        return {"status": "failed", "message": str(e)}


TESTERS = {
    "postgresql": test_postgresql,
    "mysql": test_mysql,
    "sqlserver": test_sqlserver,
    "rest_api": test_rest_api,
}


def test_real_connection(source_type, config):
    tester = TESTERS.get(source_type)
    if not tester:
        return {"status": "error", "message": f"Unsupported source type: {source_type}"}
    return tester(config)
