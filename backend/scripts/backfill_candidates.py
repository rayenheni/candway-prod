"""
backfill_candidates.py — Populate Candidate table from Application records.

For each company, groups Application records by email and creates one
Candidate row per unique email.  Then backfills candidate_id on every
Application row.

Usage:
    python -m alembic upgrade m24          # apply m24 first
    python -m alembic upgrade m25          # run migration (adds columns)
    python -m backend.scripts.backfill_candidates   # populate + backfill
    python -m alembic upgrade m25          # re-run (no-op, already applied)

Safety:
    - Wraps everything in a single transaction.
    - Rolls back on any error.
    - Preserves existing data — never deletes Application rows.
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import Application, Company, SessionLocal
from backend.logger import logger
from backend.models.ats.candidate import Candidate


def backfill_candidates(db: Session) -> int:
    """Create Candidate rows and backfill candidate_id on Application.

    Returns the number of Candidate rows created.
    """
    companies = db.query(Company.id).all()
    total_created = 0

    for (cid,) in companies:
        # Find all distinct emails for this company
        rows = (
            db.query(
                Application.email,
                Application.full_name,
                Application.phone,
            )
            .filter(
                Application.company_id == cid,
                Application.email.isnot(None),
                Application.email != "",
                Application.deleted_at.is_(None),
            )
            .distinct()
            .all()
        )

        if not rows:
            continue

        # Create Candidate rows (skip if already exists for this company)
        candidate_map = {}  # email → candidate_id
        for email, full_name, phone in rows:
            existing = (
                db.query(Candidate.id)
                .filter(
                    Candidate.company_id == cid,
                    Candidate.email == email,
                )
                .first()
            )
            if existing:
                candidate_map[email] = existing[0]
                continue
            candidate = Candidate(
                company_id=cid,
                email=email,
                full_name=full_name,
                phone=phone,
            )
            db.add(candidate)
            db.flush()
            candidate_map[email] = candidate.id
            total_created += 1

        # Backfill candidate_id on applications (only where missing)
        for email, cand_id in candidate_map.items():
            db.execute(
                text(
                    "UPDATE applications SET candidate_id = :cand_id "
                    "WHERE company_id = :cid AND email = :email "
                    "AND candidate_id IS NULL AND deleted_at IS NULL"
                ),
                {"cand_id": cand_id, "cid": cid, "email": email},
            )
            db.execute(
                text(
                    "UPDATE applications SET candidate_id = :cand_id "
                    "WHERE company_id = :cid AND email = :email "
                    "AND candidate_id != :cand_id AND deleted_at IS NULL"
                ),
                {"cand_id": cand_id, "cid": cid, "email": email},
            )

        db.flush()

    return total_created


def main():
    db = SessionLocal()
    try:
        created = backfill_candidates(db)
        db.commit()
        logger.info("Backfill complete: created %d Candidate rows", created)
    except Exception:
        db.rollback()
        logger.exception("Backfill failed — rolling back")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
