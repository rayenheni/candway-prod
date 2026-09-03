"""Phase 3: Backfill Application deprecated columns → EvaluationSession.

Run this BEFORE the m16 migration that drops the deprecated columns.
Idempotent — safe to run multiple times.

Backfill rules:
  - Application without any EvaluationSession → create one with legacy data.
  - Application with EvaluationSession(s) but NULL fields → fill NULLs only.
  - Application with EvaluationSession(s) and non-NULL fields → skip (ES is source of truth).

IMPORTANT: Uses SQLAlchemy ORM for reads so that EncryptedText columns are
automatically decrypted.  Raw SQL (text()) is only used for metadata checks.
"""

import json as json_mod
import logging
import sys
from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from backend.database import Application, EvaluationSession

logger = logging.getLogger(__name__)

# Application attribute → EvaluationSession attribute
ATTR_MAP = {
    "interview_state": "interview_state",
    "interview_progress": "interview_progress",
    "interview_time_left": "interview_time_left",
    "interview_last_saved": "interview_last_saved",
    "interview_log": "interview_log",
    "interview_questions": "interview_questions",
    "interview_turn_seq": "interview_turn_seq",
    "interview_reset_count": "interview_reset_count",
    "interview_last_reset_at": "interview_last_reset_at",
    "calibration_json": "calibration_json",
    "video_file_path": "video_file_path",
}

# Columns that store JSON strings in Application but expect JSON in ES
_JSON_COLS = {"interview_log", "interview_questions", "calibration_json"}

# Default values that indicate "no meaningful data"
_DEFAULTS = {
    "interview_state": "not_started",
    "interview_progress": 0,
    "interview_time_left": 1800,
    "interview_log": None,  # None (after ORM load if column was NULL/"[]")
    "interview_questions": None,
    "interview_turn_seq": 0,
    "interview_reset_count": 0,
    "interview_last_reset_at": None,
    "calibration_json": None,
    "video_file_path": None,
}


def _has_data(app: Application, attr: str) -> bool:
    """Check if the Application has non-default data in the deprecated attribute."""
    val = getattr(app, attr, None)
    default = _DEFAULTS.get(attr)

    if attr in _JSON_COLS:
        # EncryptedText stores JSON strings.  After ORM decryption:
        # - NULL / "[]" → treat as "no data"
        # - non-empty JSON array/object → has data
        if val is None:
            return False
        if isinstance(val, str):
            normalized = val.strip()
            if normalized in ("[]", "{}", ""):
                return False
            return True
        # If already a Python list/dict (possible if previously migrated), treat as data
        return bool(val)

    # Scalar / date columns
    if val is None:
        return False
    return val != default


def _normalize_for_es(attr: str, val):
    """Convert Application value to the type ES expects."""
    if attr in _JSON_COLS and isinstance(val, str):
        try:
            return json_mod.loads(val)
        except (json_mod.JSONDecodeError, TypeError):
            return val
    return val


def backfill(app_db_url: str, dry_run: bool = True):
    engine = create_engine(app_db_url)

    # Check which columns still exist (some may have been dropped by m11)
    existing_cols = set()
    try:
        insp = inspect(engine)
        app_cols = {c["name"] for c in insp.get_columns("applications")}
        for app_col in ATTR_MAP:
            if app_col in app_cols:
                existing_cols.add(app_col)
    except Exception:
        logger.warning("Could not inspect table columns; assuming all exist.")
        existing_cols = set(ATTR_MAP.keys())

    if not existing_cols:
        logger.info("No deprecated columns found — nothing to backfill.")
        return

    logger.info("Found existing columns: %s", sorted(existing_cols))

    with Session(engine) as db:
        # Use ORM so that EncryptedText is automatically decrypted
        apps = db.query(Application).all()
        logger.info("Found %d applications to process.", len(apps))

        created = updated = skipped = 0
        for app in apps:
            es_count = (
                db.query(EvaluationSession.id)
                .filter(EvaluationSession.application_id == app.id)
                .count()
            )

            values = {}
            for app_attr in existing_cols:
                if _has_data(app, app_attr):
                    raw = getattr(app, app_attr)
                    values[ATTR_MAP[app_attr]] = _normalize_for_es(app_attr, raw)

            if not values:
                skipped += 1
                continue

            if es_count == 0:
                values["application_id"] = app.id
                values["company_id"] = app.company_id
                values["status"] = (
                    "completed"
                    if values.get("interview_state") == "completed"
                    else "created"
                )
                values["created_at"] = datetime.utcnow()

                if not dry_run:
                    cols = ", ".join(values.keys())
                    placeholders = ", ".join(f":{k}" for k in values)
                    db.execute(
                        text(
                            f"INSERT INTO evaluation_sessions ({cols}) VALUES ({placeholders})"
                        ),
                        values,
                    )
                created += 1
                logger.info(
                    "  [CREATE] App %d → new ES (%d fields)", app.id, len(values)
                )
            else:
                es_id = (
                    db.query(EvaluationSession.id)
                    .filter(EvaluationSession.application_id == app.id)
                    .order_by(EvaluationSession.id.desc())
                    .limit(1)
                    .scalar()
                )
                updates = {}
                for es_col, val in values.items():
                    existing = db.execute(
                        text(
                            f"SELECT {es_col} FROM evaluation_sessions WHERE id = :eid"
                        ),
                        {"eid": es_id},
                    ).scalar()
                    if existing is None:
                        updates[es_col] = val

                if updates and not dry_run:
                    set_clause = ", ".join(f"{c} = :{c}" for c in updates)
                    updates["eid"] = es_id
                    db.execute(
                        text(
                            f"UPDATE evaluation_sessions SET {set_clause} WHERE id = :eid"
                        ),
                        updates,
                    )
                    updated += 1
                    logger.info(
                        "  [UPDATE] App %d → ES %d (%d fields)",
                        app.id,
                        es_id,
                        len(updates),
                    )
                else:
                    skipped += 1

        if not dry_run:
            db.commit()

        logger.info(
            "Backfill complete. Created=%d Updated=%d Skipped=%d (dry_run=%s)",
            created,
            updated,
            skipped,
            dry_run,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    url = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///candway.db"
    dry = "--dry-run" in sys.argv or len(sys.argv) < 2
    backfill(url, dry_run=dry)
