"""
One-shot backfill: lift the four top-level analysis keys
(strengths, weaknesses, final_score_breakdown, score) out of
analysis_json and into the new dedicated columns.

Run with::

    python -m backend.migrations.analysis_columns_backfill

Idempotent: re-running is a no-op because the helper short-
circuits when the column is already populated.
"""

import json
import logging
import sys

from backend.analysis_columns import write_analysis_columns
from backend.database import Application, SessionLocal
from backend.logger import logger


def backfill() -> None:
    db = SessionLocal()
    moved = 0
    skipped = 0
    errors = 0
    try:
        apps = db.query(Application).filter(Application.analysis_json.isnot(None)).all()
        logger.info(
            f"[ANALYSIS-BACKFILL] Scanning {len(apps)} applications with analysis_json"
        )

        for app in apps:
            try:
                if isinstance(app.analysis_json, str):
                    bag = json.loads(app.analysis_json)
                else:
                    bag = app.analysis_json or {}
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"[ANALYSIS-BACKFILL] Cannot parse bag for app {app.id}: {e}"
                )
                skipped += 1
                continue

            if not isinstance(bag, dict):
                skipped += 1
                continue

            strengths = bag.get("strengths")
            weaknesses = bag.get("weaknesses") or bag.get("missing_skills")
            score_breakdown = bag.get("final_score_breakdown")
            score = (
                bag.get("score") or bag.get("match_score") or bag.get("current_score")
            )

            # Skip rows that are already populated AND have
            # nothing new in the bag to lift.
            if (
                app.analysis_strengths is not None
                and app.analysis_weaknesses is not None
                and app.analysis_score_breakdown is not None
                and app.analysis_score is not None
            ):
                skipped += 1
                continue

            try:
                write_analysis_columns(
                    db,
                    app,
                    strengths=strengths,
                    weaknesses=weaknesses,
                    score_breakdown=score_breakdown,
                    score=score,
                    also_write_bag=False,  # don't change the bag during backfill
                )
                moved += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[ANALYSIS-BACKFILL] App {app.id} failed: {e}")
                errors += 1

        db.commit()
        logger.info(
            f"[ANALYSIS-BACKFILL] Done. moved={moved} skipped={skipped} errors={errors}"
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error(f"[ANALYSIS-BACKFILL] FAILED: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill()
