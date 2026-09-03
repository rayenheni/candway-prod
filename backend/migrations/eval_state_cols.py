"""
Migration: Add evaluation state machine columns to applications table

Added columns:
- fraud_reported_by (was added earlier, ensuring exists)
- evaluation_state
- evaluation_started_at
- evaluation_completed_at
- evaluation_source
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
            # Check if columns exist first
            cursor.execute("DESCRIBE applications")
            columns = {row[0] for row in cursor.fetchall()}

            migrations = []

            # fraud_reported_by (often missing)
            if "fraud_reported_by" not in columns:
                migrations.append("ADD COLUMN fraud_reported_by INT NULL")
                print("+ fraud_reported_by")

            if "fraud_reported_at" not in columns:
                migrations.append("ADD COLUMN fraud_reported_at DATETIME NULL")
                print("+ fraud_reported_at")

            # Evaluation state machine columns
            if "evaluation_state" not in columns:
                migrations.append(
                    "ADD COLUMN evaluation_state VARCHAR(20) DEFAULT 'pending'"
                )
                print("+ evaluation_state")

            if "evaluation_started_at" not in columns:
                migrations.append("ADD COLUMN evaluation_started_at DATETIME NULL")
                print("+ evaluation_started_at")

            if "evaluation_completed_at" not in columns:
                migrations.append("ADD COLUMN evaluation_completed_at DATETIME NULL")
                print("+ evaluation_completed_at")

            if "evaluation_source" not in columns:
                migrations.append("ADD COLUMN evaluation_source VARCHAR(20) NULL")
                print("+ evaluation_source")

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
