"""
Migration: Add all missing columns to applications table
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

            def add_col(name, col_type, default=None):
                if name not in columns:
                    if default:
                        migrations.append(
                            f"ADD COLUMN {name} {col_type} DEFAULT {default}"
                        )
                    else:
                        migrations.append(f"ADD COLUMN {name} {col_type}")

            add_col("cv_text_anonymized", "LONGTEXT", "'[]'")
            add_col("cv_embedding", "LONGTEXT", "'[]'")
            add_col("interview_log", "LONGTEXT", "'[]'")
            add_col("interview_questions", "LONGTEXT", "'[]'")
            add_col("proctoring_violations", "LONGTEXT", "'[]'")
            add_col("interview_qa_structured", "LONGTEXT", "'[]'")
            add_col("generated_questions", "LONGTEXT", "NULL")
            add_col("video_file_path", "VARCHAR(512)", "NULL")
            add_col("video_transcript", "LONGTEXT", "NULL")
            add_col("video_analysis_json", "LONGTEXT", "NULL")
            add_col("roadmap_json", "LONGTEXT", "NULL")
            add_col("cv_review_json", "LONGTEXT", "NULL")
            add_col("detected_role", "VARCHAR(255)", "NULL")
            add_col("cv_file_path", "VARCHAR(255)", "NULL")
            add_col("assigned_to", "INT", "NULL")
            add_col("assigned_at", "DATETIME", "NULL")
            add_col("interview_turn_seq", "INT DEFAULT 0")
            add_col("final_eval_done", "BOOLEAN DEFAULT FALSE")
            add_col("final_eval_timestamp", "DATETIME", "NULL")
            add_col("fraud_reported_by", "INT", "NULL")
            add_col("fraud_reported_at", "DATETIME", "NULL")
            add_col("evaluation_state", "VARCHAR(20) DEFAULT 'pending'")
            add_col("evaluation_started_at", "DATETIME", "NULL")
            add_col("evaluation_completed_at", "DATETIME", "NULL")
            add_col("evaluation_source", "VARCHAR(20)", "NULL")

            if migrations:
                sql = f"ALTER TABLE applications {', '.join(migrations)}"
                cursor.execute(sql)
                connection.commit()
                print(f"Applied {len(migrations)} columns")
                for m in migrations:
                    print(f"  + {m}")
            else:
                print("All columns already exist")

    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
