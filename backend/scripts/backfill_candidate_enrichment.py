"""
backfill_candidate_enrichment.py — Populate Candidate enrichment fields.

Copies headline, bio, skills, location from CandidateProfile (via User
join) into the Candidate table for candidates that are missing them.

Usage:
    python -m backend.scripts.backfill_candidate_enrichment

Safety:
    - Single transaction — rolls back on error.
    - Idempotent — skips candidates that already have data.
    - Never deletes CandidateProfile or User data.
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.logger import logger

FIELDS = ["headline", "bio", "skills", "location"]


def backfill(db: Session, batch_size: int = 500) -> int:
    """Return count of Candidate rows updated."""
    set_clause = ", ".join(f"c.{f} = COALESCE(c.{f}, cp.{f})" for f in FIELDS)
    sql = text(f"""
        UPDATE candidates c
        JOIN applications a ON a.candidate_id = c.id AND a.deleted_at IS NULL
        JOIN users u ON u.id = a.user_id AND u.deleted_at IS NULL
        JOIN candidate_profiles cp ON cp.user_id = u.id
        SET {set_clause}
        WHERE (
            {" OR ".join(f"cp.{f} IS NOT NULL" for f in FIELDS)}
        )
        AND (
            {" OR ".join(f"c.{f} IS NULL" for f in FIELDS)}
        )
    """)
    result = db.execute(sql)
    db.commit()
    count = result.rowcount
    logger.info("Updated %d Candidate rows with enrichment data", count)
    return count


def verify(db: Session) -> None:
    """Check how many candidates still lack enrichment."""
    for field in FIELDS:
        row = db.execute(
            text(
                f"SELECT COUNT(*) FROM candidates WHERE {field} IS NULL AND deleted_at IS NULL"
            )
        ).scalar()
        if row:
            logger.info("Candidates missing %s: %d", field, row)


def main():
    logger.info("Starting Candidate enrichment backfill")
    db = SessionLocal()
    try:
        count = backfill(db)
        verify(db)
        logger.info("Backfill complete: %d rows updated", count)
    except Exception:
        logger.exception("Backfill failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
