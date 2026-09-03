"""One-shot backfill: create RubricSnapshot for existing EvaluationSession rows.

Prerequisites:
  - Alembic migration m18_add_rubric_snapshot_table must be applied first
    (creates rubric_snapshots table + rubric_snapshot_id FK columns).

Usage:
    python -m backend.scripts.backfill_rubric_snapshots          # dry run
    python -m backend.scripts.backfill_rubric_snapshots --commit  # actual write

Scans EvaluationSession rows where rubric_id IS NOT NULL AND
rubric_snapshot_id IS NULL.  For each match:
  1. Create a RubricSnapshot from the linked Rubric record
  2. Link session.rubric_snapshot_id
  3. Link EvaluationResult.rubric_snapshot_id if one exists
"""

import logging
import sys

from sqlalchemy.orm import Session

from backend.database import EvaluationResult, EvaluationSession, SessionLocal
from backend.database import Rubric as RubricDB
from backend.rubric.rubric_snapshotter import RubricSnapshotter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
logger = logging.getLogger(__name__)


def backfill_rubric_snapshots(dry_run: bool = True) -> int:
    db: Session = SessionLocal()
    created = 0
    skipped_no_rubric = 0
    errors = 0

    try:
        sessions = (
            db.query(EvaluationSession)
            .filter(
                EvaluationSession.rubric_id.isnot(None),
                EvaluationSession.rubric_snapshot_id.is_(None),
            )
            .all()
        )

        logger.info("Found %d session(s) needing a RubricSnapshot", len(sessions))

        for session in sessions:
            rubric_record = (
                db.query(RubricDB).filter(RubricDB.id == session.rubric_id).first()
            )
            if rubric_record is None:
                logger.warning(
                    "Session %s: rubric_id=%s not found in rubrics table, skipping",
                    session.id,
                    session.rubric_id,
                )
                skipped_no_rubric += 1
                continue

            if dry_run:
                logger.info(
                    "[DRY RUN] Would create snapshot for session %s (rubric_id=%s, app_id=%s)",
                    session.id,
                    session.rubric_id,
                    session.application_id,
                )
                created += 1
                continue

            try:
                snapshot = RubricSnapshotter.create_from_rubric_record(
                    db, rubric_record
                )
                session.rubric_snapshot_id = snapshot.id

                result = (
                    db.query(EvaluationResult)
                    .filter(EvaluationResult.evaluation_session_id == session.id)
                    .first()
                )
                if result is not None:
                    result.rubric_snapshot_id = snapshot.id

                db.flush()
                logger.info(
                    "Created snapshot %s for session %s (app_id=%s, rubric=%s v%s)",
                    snapshot.id,
                    session.id,
                    session.application_id,
                    rubric_record.id,
                    snapshot.version,
                )
                created += 1
            except Exception as exc:
                logger.error(
                    "Error processing session %s: %s",
                    session.id,
                    exc,
                )
                errors += 1

        if not dry_run:
            db.commit()
            logger.info("Committed %d snapshot(s)", created)
        else:
            logger.info(
                "[DRY RUN] Would create %d snapshot(s). Pass --commit to execute.",
                created,
            )

        if skipped_no_rubric:
            logger.info(
                "Skipped %d session(s) (rubric record missing)", skipped_no_rubric
            )
        if errors:
            logger.warning("Encountered %d error(s)", errors)

        return created

    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        db.rollback()
        return -1
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--commit" not in sys.argv
    total = backfill_rubric_snapshots(dry_run=dry_run)
    if total < 0:
        sys.exit(1)
    logger.info("Done — processed %d session(s).", total)
