"""
Migration: Add missing columns to applications table
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

    # Columns that the code expects to exist

    try:
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE applications")
            columns = {row[0] for row in cursor.fetchall()}

            migrations = []

            if "interview_turn_seq" not in columns:
                migrations.append("ADD COLUMN interview_turn_seq INT DEFAULT 0")

            if "final_eval_done" not in columns:
                migrations.append("ADD COLUMN final_eval_done BOOLEAN DEFAULT FALSE")

            if "final_eval_timestamp" not in columns:
                migrations.append("ADD COLUMN final_eval_timestamp DATETIME NULL")

            if "cv_text_anonymized" not in columns:
                migrations.append("ADD COLUMN cv_text_anonymized TEXT")

            if "cv_embedding" not in columns:
                migrations.append("ADD COLUMN cv_embedding LONGTEXT")

            if "interview_log" not in columns:
                migrations.append("ADD COLUMN interview_log LONGTEXT DEFAULT '[]'")

            if "interview_questions" not in columns:
                migrations.append(
                    "ADD COLUMN interview_questions LONGTEXT DEFAULT '[]'"
                )

            if "proctoring_violations" not in columns:
                migrations.append(
                    "ADD COLUMN proctoring_violations LONGTEXT DEFAULT '[]'"
                )

            if "interview_qa_structured" not in columns:
                migrations.append(
                    "ADD COLUMN interview_qa_structured LONGTEXT DEFAULT '[]'"
                )

            if migrations:
                sql = f"ALTER TABLE applications {', '.join(migrations)}"
                cursor.execute(sql)
                connection.commit()
                print(f"Applied: {migrations}")
            else:
                print("All columns already exist")

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
