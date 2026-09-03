"""
Migration: Add Campaign Templates and Enhanced Campaign Features
"""

import io
import os
import sys

import pymysql

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def run_migration():
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "candway_db"),
    )

    try:
        with connection.cursor() as cursor:
            # 1. Create campaign_templates table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaign_templates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    recruiter_id INT,
                    name VARCHAR(255) NOT NULL,
                    role VARCHAR(255),
                    description TEXT,
                    subject_template VARCHAR(500),
                    body_template TEXT,
                    is_default BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (recruiter_id) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_recruiter_id (recruiter_id),
                    INDEX idx_is_default (is_default)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("[OK] Created campaign_templates table")

            # 2. Add columns to batch_jobs table
            cursor.execute("DESCRIBE batch_jobs")
            columns = {row[0] for row in cursor.fetchall()}

            new_cols = []

            if "template_id" not in columns:
                new_cols.append("ADD COLUMN template_id INT DEFAULT NULL")
            if "email_sequence_enabled" not in columns:
                new_cols.append(
                    "ADD COLUMN email_sequence_enabled BOOLEAN DEFAULT FALSE"
                )
            if "email_sequence_days" not in columns:
                new_cols.append("ADD COLUMN email_sequence_days TEXT DEFAULT NULL")
            if "emails_sent" not in columns:
                new_cols.append("ADD COLUMN emails_sent INT DEFAULT 0")
            if "emails_opened" not in columns:
                new_cols.append("ADD COLUMN emails_opened INT DEFAULT 0")
            if "emails_clicked" not in columns:
                new_cols.append("ADD COLUMN emails_clicked INT DEFAULT 0")
            if "responses_received" not in columns:
                new_cols.append("ADD COLUMN responses_received INT DEFAULT 0")

            if new_cols:
                alter_query = f"ALTER TABLE batch_jobs {', '.join(new_cols)}"
                cursor.execute(alter_query)
                print(f"[OK] Added {len(new_cols)} new columns to batch_jobs")

            connection.commit()
            print("[OK] Migration completed successfully!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        connection.rollback()
    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
