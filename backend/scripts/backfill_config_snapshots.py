"""One-shot backfill: create EvaluationConfigSnapshot for existing evaluation sessions.

Prerequisites:
  - Alembic migration ac4f530aebb2 must be applied first
    (creates evaluation_config_snapshots table + FK column).

Usage:
    python -m backend.scripts.backfill_config_snapshots          # dry run
    python -m backend.scripts.backfill_config_snapshots --commit  # actual write

Scans EvaluationSession rows where evaluation_config_snapshot_id IS NULL.
For each match:
  1. Collect rubric, job, campaign data from live tables
  2. Create an EvaluationConfigSnapshot via ConfigurationResolver
  3. Link session.evaluation_config_snapshot_id
"""

import logging
import sys

from sqlalchemy.orm import Session

from backend.database import EvaluationSession, Job, SessionLocal
from backend.database import Rubric as RubricDB
from backend.models.evaluation.config_snapshot import EntryPoint
from backend.rubric.config_resolver import ConfigurationResolver

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
logger = logging.getLogger(__name__)


def backfill_config_snapshots(dry_run: bool = True) -> int:
    db: Session = SessionLocal()
    created = 0
    errors = 0

    try:
        sessions = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.evaluation_config_snapshot_id.is_(None))
            .all()
        )

        logger.info("Found %d session(s) needing a config snapshot", len(sessions))

        for session in sessions:
            rubric_record = None
            if session.rubric_id is not None:
                rubric_record = (
                    db.query(RubricDB).filter(RubricDB.id == session.rubric_id).first()
                )

            job = None
            if session.application_id is not None:
                from backend.database import Application

                app = (
                    db.query(Application)
                    .filter(Application.id == session.application_id)
                    .first()
                )
                if app and app.job_id:
                    job = db.query(Job).filter(Job.id == app.job_id).first()

            if dry_run:
                logger.info(
                    "[DRY RUN] Would create snapshot for session %s "
                    "(rubric_id=%s, app_id=%s)",
                    session.id,
                    session.rubric_id,
                    session.application_id,
                )
                created += 1
                continue

            try:
                entry_point = EntryPoint(
                    source_type=session.source or "job_apply",
                    source_id=session.context_id
                    or (
                        str(session.application_id) if session.application_id else None
                    ),
                    application_id=session.application_id,
                )
                snapshot = ConfigurationResolver.resolve(
                    db,
                    entry_point,
                    company_id=session.company_id,
                    rubric_record=rubric_record,
                    job=job,
                )
                session.evaluation_config_snapshot_id = snapshot.id
                db.flush()
                logger.info(
                    "Created snapshot %s for session %s (app_id=%s)",
                    snapshot.id,
                    session.id,
                    session.application_id,
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
    total = backfill_config_snapshots(dry_run=dry_run)
    if total < 0:
        sys.exit(1)
    logger.info("Done -- processed %d session(s).", total)
