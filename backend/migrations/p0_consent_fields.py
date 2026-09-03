"""
Migration: P0 Beta — Add consent fields to batch_jobs and applications tables.

Adds:
  batch_jobs:
    - cv_processing_consent_confirmed  TINYINT(1) DEFAULT 0
    - cv_processing_consent_confirmed_at  DATETIME NULL
    - cv_processing_consent_confirmed_by  INT NULL (FK users.id)

  applications:
    - consent_accepted  TINYINT(1) DEFAULT 0
    - consent_at  DATETIME NULL
    - consent_source  VARCHAR(100) NULL

Safe to run multiple times (idempotent column checks).
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def run_migration():
    import pymysql

    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "candway_db"),
    )

    try:
        with connection.cursor() as cursor:
            # ── 1. batch_jobs consent columns ──────────────────────────────
            cursor.execute("DESCRIBE batch_jobs")
            batch_cols = {row[0] for row in cursor.fetchall()}

            batch_new = []
            if "cv_processing_consent_confirmed" not in batch_cols:
                batch_new.append(
                    "ADD COLUMN cv_processing_consent_confirmed TINYINT(1) NOT NULL DEFAULT 0"
                )
            if "cv_processing_consent_confirmed_at" not in batch_cols:
                batch_new.append(
                    "ADD COLUMN cv_processing_consent_confirmed_at DATETIME NULL"
                )
            if "cv_processing_consent_confirmed_by" not in batch_cols:
                batch_new.append(
                    "ADD COLUMN cv_processing_consent_confirmed_by INT NULL"
                )

            if batch_new:
                cursor.execute(
                    f"ALTER TABLE batch_jobs {', '.join(batch_new)}"
                )
                print(
                    f"[OK] Added {len(batch_new)} consent column(s) to batch_jobs"
                )
            else:
                print("[SKIP] batch_jobs consent columns already exist")

            # ── 2. applications consent columns ────────────────────────────
            cursor.execute("DESCRIBE applications")
            app_cols = {row[0] for row in cursor.fetchall()}

            app_new = []
            if "consent_accepted" not in app_cols:
                app_new.append(
                    "ADD COLUMN consent_accepted TINYINT(1) NOT NULL DEFAULT 0"
                )
            if "consent_at" not in app_cols:
                app_new.append("ADD COLUMN consent_at DATETIME NULL")
            if "consent_source" not in app_cols:
                app_new.append(
                    "ADD COLUMN consent_source VARCHAR(100) NULL"
                )

            if app_new:
                cursor.execute(
                    f"ALTER TABLE applications {', '.join(app_new)}"
                )
                print(
                    f"[OK] Added {len(app_new)} consent column(s) to applications"
                )
            else:
                print("[SKIP] applications consent columns already exist")

            connection.commit()
            print("[OK] Migration p0_consent_fields completed successfully!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
