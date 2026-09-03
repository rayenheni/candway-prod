"""
Migration: Rename jobs.company -> jobs.company_name
"""

import os

import pymysql


def run_migration():
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "candway_db"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE jobs")
            cols = {row[0] for row in cursor.fetchall()}

            if "company" in cols and "company_name" not in cols:
                cursor.execute(
                    "ALTER TABLE jobs CHANGE COLUMN company company_name VARCHAR(255)"
                )
                print("[OK] Renamed jobs.company -> jobs.company_name")
            elif "company_name" in cols:
                print("[SKIP] jobs.company_name already exists")
            else:
                print("[SKIP] Neither company nor company_name found")
        connection.commit()
        print("[DONE] Migration complete")
    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
