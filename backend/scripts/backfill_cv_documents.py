"""
backfill_cv_documents.py — Populate CvDocument from Application deprecated columns.

For each Application that lacks a CvDocument row, creates one and copies
the 8 deprecated columns (declared_role, detected_role, cv_text_anonymized,
cv_file_path, analysis_json, cv_embedding, roadmap_json, cv_review_json)
into the new CvDocument row.

Usage:
    python -m backend.scripts.backfill_cv_documents

Safety:
    - Single transaction — rolls back on error.
    - Idempotent — skips applications that already have a CvDocument.
    - Never deletes Application data.
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.logger import logger

APPLICATION_FIELDS = [
    "declared_role",
    "detected_role",
    "cv_text_anonymized",
    "cv_file_path",
    "analysis_json",
    "cv_embedding",
    "roadmap_json",
    "cv_review_json",
]

CVDOCUMENT_FIELDS = [
    "declared_role",
    "detected_role",
    "cv_text_anonymized",
    "cv_file_path",
    "analysis_json",
    "cv_embedding",
    "roadmap_json",
    "cv_review_json",
]


def get_field_mapping():
    return dict(zip(APPLICATION_FIELDS, CVDOCUMENT_FIELDS))


def backfill(app: Session, batch_size: int = 500) -> int:
    """Return count of CvDocument rows created."""
    cv_table = "cv_documents"
    app_table = "applications"
    app_cols = ", ".join(f'a."{f}"' for f in APPLICATION_FIELDS)
    cv_cols = ", ".join(f'"{f}"' for f in CVDOCUMENT_FIELDS)

    sql = text(f"""
        INSERT INTO {cv_table} (application_id, company_id, {cv_cols}, created_at, updated_at)
        SELECT a.id, a.company_id, {app_cols}, NOW(), NOW()
        FROM {app_table} a
        WHERE NOT EXISTS (
            SELECT 1 FROM {cv_table} c WHERE c.application_id = a.id
        )
        AND a.id IS NOT NULL
    """)

    result = app.execute(sql)
    app.commit()
    count = result.rowcount
    logger.info("Created %d CvDocument rows from Application columns", count)
    return count


def verify(app: Session) -> None:
    """Check that all applications have a CvDocument."""
    row = app.execute(
        text("""
        SELECT COUNT(*) FROM applications a
        WHERE NOT EXISTS (
            SELECT 1 FROM cv_documents c WHERE c.application_id = a.id
        )
    """)
    ).scalar()
    if row:
        logger.warning("%d applications still lack a CvDocument", row)
    else:
        logger.info("All applications have a CvDocument")


def main():
    logger.info("Starting CvDocument backfill")
    db = SessionLocal()
    try:
        count = backfill(db)
        verify(db)
        logger.info("Backfill complete: %d rows created", count)
    except Exception:
        logger.exception("Backfill failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
