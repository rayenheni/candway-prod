"""
Migration: Add photo_url column to candidates table
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
            cursor.execute("DESCRIBE candidates")
            columns = {row[0] for row in cursor.fetchall()}

            if "photo_url" not in columns:
                cursor.execute(
                    "ALTER TABLE candidates ADD COLUMN photo_url VARCHAR(512) NULL"
                )
                print("[OK] Added photo_url column to candidates table")
            else:
                print("[SKIP] candidates.photo_url already exists")

        connection.commit()
        print("[DONE] Migration complete")
    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
