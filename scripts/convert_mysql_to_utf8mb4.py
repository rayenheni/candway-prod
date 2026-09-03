"""Convert every table in the MySQL database to utf8mb4 / utf8mb4_unicode_ci.

Run this ONCE against an existing deployment whose tables were created with the
MySQL 8 default collation (or the legacy latin1/utf8mb3), so that the database
matches the utf8mb4 server configuration in docker-compose.yml.

Idempotent: tables already on utf8mb4 / utf8mb4_unicode_ci are skipped.

Usage::

    python scripts/convert_mysql_to_utf8mb4.py

Requires DATABASE_URL in backend/.env (mysql+pymysql://...). Back up first:
    python scripts/db_backup.py
"""

import os
import sys
from dotenv import load_dotenv

_CHARSET = "utf8mb4"
_COLLATION = "utf8mb4_unicode_ci"


def _get_url():
    backend_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", ".env")
    load_dotenv(backend_env)
    url = os.getenv("DATABASE_URL")
    if not url or not url.startswith("mysql"):
        print("DATABASE_URL must point to MySQL (mysql+pymysql://...) in backend/.env")
        sys.exit(1)
    return url


def convert_all():
    url = _get_url()
    try:
        import pymysql
    except ImportError:
        print("pymysql is required: pip install pymysql")
        sys.exit(1)

    # Strip any SQLAlchemy prefix (mysql+pymysql://) and query params (?charset=...)
    driver_prefix = "://"
    if "+" in url.split("://")[0]:
        driver_prefix = "+" + driver_prefix
    conn_url = url.split("?")[0].replace(driver_prefix, "://", 1)
    # Normalize any query params so pymysql does not choke on charset=...
    conn_url = conn_url.split("?")[0]

    print(f"Connecting to {conn_url}")
    conn = pymysql.connect(host=_host(conn_url), user=_user(conn_url),
                           password=_password(conn_url), database=_db(conn_url))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s", (db_name,))
            tables = [row[0] for row in cursor.fetchall()]
        if not tables:
            print("No tables found.")
            return

        converted = skipped = failed = 0
        for table in sorted(tables):
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT TABLE_COLLATION FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                        (db_name, table))
                    row = cursor.fetchone()
                    if row and row[0] == _COLLATION:
                        skipped += 1
                        continue
                    cursor.execute(
                        "ALTER TABLE `%s` CONVERT TO CHARACTER SET %s COLLATE %s"
                        % (table, _CHARSET, _COLLATION))
                conn.commit()
                converted += 1
                print(f"  converted: {table}")
            except Exception as e:
                conn.rollback()
                failed += 1
                print(f"  FAILED:    {table} — {e}")
        print(f"\nDone. converted={converted} skipped={skipped} failed={failed}")
        if failed:
            sys.exit(2)
    finally:
        conn.close()


def _host(url):
    return url.split("://")[1].split("@")[-1].split("/")[0].split(":")[0]


def _user(url):
    return url.split("://")[1].split("@")[0].split(":")[0]


def _password(url):
    up = url.split("://")[1].split("@")[0]
    if ":" in up:
        return up.split(":", 1)[1]
    return ""


def _db(url):
    return url.split("://")[1].split("/")[-1].split("?")[0]


if __name__ == "__main__":
    convert_all()
