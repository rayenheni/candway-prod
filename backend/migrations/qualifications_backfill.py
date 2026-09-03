"""
One-shot backfill: lift qualifications out of analysis_json and
into the new ``qualifications`` table.

Run with::

    python -m backend.migrations.qualifications_backfill

The script is idempotent — re-running it is safe; the
``(user_id, title, category)`` unique constraint will deduplicate.

After backfill, the analysis_json entry is **left in place** so we
can roll back if needed. A separate cron (or manual run of
``backend/migrations/qualifications_json_drop.py``) will strip it
once we've confirmed parity in production.
"""

import logging
import sys

from sqlalchemy.exc import IntegrityError

from backend.database import Application, Qualification, SessionLocal
from backend.logger import logger

try:
    from backend.routers.candidate.common import safe_load_json
except Exception:
    # Standalone run — provide a tiny shim
    import json

    def safe_load_json(raw):  # type: ignore[no-redef]
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}


def backfill() -> None:
    db = SessionLocal()
    moved = 0
    skipped = 0
    errors = 0
    try:
        apps = db.query(Application).filter(Application.analysis_json.isnot(None)).all()
        logger.info(
            f"[QUAL-BACKFILL] Scanning {len(apps)} applications with analysis_json"
        )

        for app in apps:
            meta = safe_load_json(app.analysis_json) or {}
            qual_list = meta.get("qualifications") or []
            if not qual_list:
                continue

            for q in qual_list:
                if not isinstance(q, dict):
                    continue
                title = (q.get("title") or "").strip()
                category = (q.get("category") or "other").strip()
                if not title:
                    skipped += 1
                    continue

                # Preserve the legacy id if it's a short hex; mint
                # a new one if not. This keeps any saved bookmarks
                # working.
                legacy_id = q.get("id")
                if (
                    isinstance(legacy_id, str)
                    and 4 <= len(legacy_id) <= 16
                    and legacy_id.isalnum()
                ):
                    new_id = legacy_id
                else:
                    import uuid as _uuid

                    new_id = _uuid.uuid4().hex[:8]

                # Check for an existing row to avoid clobbering
                # anything the user has uploaded since the script
                # was first drafted.
                existing = (
                    db.query(Qualification).filter(Qualification.id == new_id).first()
                )
                if existing:
                    skipped += 1
                    continue

                uploaded_at = q.get("uploaded_at")
                if uploaded_at:
                    try:
                        from datetime import datetime

                        uploaded_dt = datetime.fromisoformat(
                            uploaded_at.replace("Z", "+00:00")
                        )
                    except Exception:
                        from datetime import UTC, datetime

                        uploaded_dt = datetime.now(UTC)
                else:
                    from datetime import UTC, datetime

                    uploaded_dt = datetime.now(UTC)

                new_row = Qualification(
                    id=new_id,
                    user_id=app.user_id,
                    application_id=app.id,
                    title=title,
                    category=category,
                    filename=q.get("filename") or "",
                    file_url=q.get("file_url") or "",
                    file_size=int(q.get("file_size") or 0),
                    mime_type=q.get("mime_type") or "application/octet-stream",
                    verified=bool(q.get("verified", False)),
                    uploaded_at=uploaded_dt,
                )
                db.add(new_row)
                try:
                    db.flush()
                    moved += 1
                except IntegrityError as e:
                    db.rollback()
                    skipped += 1
                    logger.debug(
                        f"[QUAL-BACKFILL] Skip duplicate for app {app.id}: {e}"
                    )

        db.commit()
        logger.info(
            f"[QUAL-BACKFILL] Done. moved={moved} skipped={skipped} errors={errors}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[QUAL-BACKFILL] FAILED: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill()
