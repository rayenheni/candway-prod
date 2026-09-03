"""CI helper: run the test suite against MySQL.

Usage:
    CANDWAY_TEST_DATABASE_URL=mysql+pymysql://root:@localhost/candway_test \\
        python scripts/run_tests_mysql.py

Drops and recreates ``candway_test`` first, then runs the full
``backend/tests/`` + ``tests/`` suite. The MySQL config must be
reachable from the runner and the user must have ``DROP DATABASE``
permission.

This is a thin wrapper around ``pytest`` — it does not modify
any application code. The conftest at ``tests/conftest.py``
honours ``CANDWAY_TEST_DATABASE_URL`` to switch off the SQLite
fallback.

Exit code matches pytest's: 0 = all green, 1 = at least one
test failed.
"""
import os
import subprocess
import sys


def main() -> int:
    db_url = os.environ.get("CANDWAY_TEST_DATABASE_URL")
    if not db_url:
        print(
            "ERROR: CANDWAY_TEST_DATABASE_URL is not set. Refusing to "
            "run — that would clobber the production DB.",
            file=sys.stderr,
        )
        return 2

    if "test" not in db_url.lower() and "_test" not in db_url.lower():
        print(
            "ERROR: CANDWAY_TEST_DATABASE_URL does not contain 'test'. "
            "Refusing to run against a non-test database.",
            file=sys.stderr,
        )
        return 2

    # Wipe + recreate the test schema before the run. The conftest
    # fixture will then ``create_all`` over the empty DB.
    try:
        import pymysql

        parsed = _parse_mysql_url(db_url)
        conn = pymysql.connect(
            host=parsed["host"],
            port=parsed["port"],
            user=parsed["user"],
            password=parsed["password"],
        )
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{parsed['db']}`")
            cur.execute(
                f"CREATE DATABASE `{parsed['db']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        conn.close()
        print(f"MySQL test database reset: {parsed['db']}")
    except ImportError:
        print(
            "WARNING: pymysql is not installed; skipping the "
            "DROP/CREATE step. The conftest will create_all() "
            "over the existing schema, which may fail if the "
            "schema is stale."
        )
    except Exception as e:
        print(f"ERROR: could not reset MySQL test DB: {e}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "backend/tests/",
        "tests/",
        "-q",
        "--tb=line",
    ]
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    return subprocess.call(cmd, env=env)


def _parse_mysql_url(url: str) -> dict:
    """Tiny MySQL URL parser. We don't need the full sqlalchemy
    machinery here."""
    # mysql+pymysql://user:pass@host:port/db
    from urllib.parse import urlparse

    # Strip the driver prefix
    if "://" in url:
        url = url.split("://", 1)[1]
    parsed = urlparse(f"mysql://{url}")
    db = (parsed.path or "/").lstrip("/") or "candway_test"
    return {
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "db": db,
    }


if __name__ == "__main__":
    sys.exit(main())
