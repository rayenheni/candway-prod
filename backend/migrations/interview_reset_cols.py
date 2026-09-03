"""
Migration: Add interview reset tracking columns to applications table.

Lifts ``_reset_count`` and ``_last_reset`` out of the analysis_json
JSON-bag (Bug B-09 in the Candidate Experience Audit). The previous
design stored these in analysis_json, which is overwritten on every
CV reanalysis — silently resetting the per-application reset quota
and letting candidates burn through unlimited interview retries.

For Alembic environments run ``alembic upgrade head`` instead. This
script exists for deployments that still use the legacy
``backend/migrations/*.py`` ad-hoc path.
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
            cursor.execute("DESCRIBE applications")
            columns = {row[0] for row in cursor.fetchall()}

            migrations = []

            if "interview_reset_count" not in columns:
                migrations.append(
                    "ADD COLUMN interview_reset_count INT NOT NULL DEFAULT 0"
                )
                print("+ interview_reset_count")

            if "interview_last_reset_at" not in columns:
                migrations.append("ADD COLUMN interview_last_reset_at DATETIME NULL")
                print("+ interview_last_reset_at")

            if migrations:
                sql = f"ALTER TABLE applications {', '.join(migrations)}"
                cursor.execute(sql)
                connection.commit()
                print(f"Applied {len(migrations)} migrations")
            else:
                print("All columns already exist")

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
