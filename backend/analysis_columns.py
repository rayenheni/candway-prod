"""
Read/write helpers for the structured analysis columns added in
Bug B-31.

The audit's analysis_json column on ``Application`` had 18+
top-level keys; the most-read four (strengths, weaknesses,
final_score_breakdown, score) now live in dedicated columns
that are cheap to index and don't require JSON parsing on
the list path.

The new columns are the source of truth. The bag continues to
be written by the AI analysis pipeline; this helper just makes
sure both stay in sync and that readers can fall back to the
bag if the column is NULL.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database import Application
from backend.entity_writer import sync_cv_document

logger = logging.getLogger(__name__)


def _safe_load(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


def write_analysis_columns(
    db: Session,
    application: Application,
    *,
    strengths: Optional[List[str]] = None,
    weaknesses: Optional[List[str]] = None,
    score_breakdown: Optional[Dict[str, Any]] = None,
    score: Optional[float] = None,
    also_write_bag: bool = True,
) -> None:
    """Mirror values into the new columns. Optionally mirrors
    them into ``analysis_json`` too, so legacy readers (the JS
    dashboard, recruiter previews) keep working."""
    if strengths is not None:
        application.analysis_strengths = list(strengths)
    if weaknesses is not None:
        application.analysis_weaknesses = list(weaknesses)
    if score_breakdown is not None:
        application.analysis_score_breakdown = dict(score_breakdown)
    if score is not None:
        try:
            application.analysis_score = float(score)
        except (TypeError, ValueError):
            logger.warning(
                f"[ANALYSIS-COLS] Could not coerce score {score!r} to float "
                f"for app {application.id}"
            )

    # NOTE: analysis_score is a legacy mirror column.
    # The canonical score is EvaluationResult.final_score written via
    # ScoringService.compute_final_score().  This column exists only for
    # backward compatibility during the v3 migration and will be removed.
    # New code MUST NOT read analysis_score directly.

    if also_write_bag and any(
        v is not None for v in (strengths, weaknesses, score_breakdown, score)
    ):
        try:
            bag = _safe_load(application.analysis_json)
            if strengths is not None:
                bag["strengths"] = list(strengths)
            if weaknesses is not None:
                bag["weaknesses"] = list(weaknesses)
            if score_breakdown is not None:
                bag["final_score_breakdown"] = dict(score_breakdown)
            if score is not None:
                bag["score"] = float(score)
            sync_cv_document(db, application, analysis_json=json.dumps(bag))
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"[ANALYSIS-COLS] Could not mirror to analysis_json bag for "
                f"app {application.id}: {e}"
            )

    db.flush()


def read_analysis(
    application: Application,
    *,
    include_bag_fallback: bool = True,
) -> Dict[str, Any]:
    """Return a normalised dict with the four canonical keys.

    Reads the dedicated columns first; falls back to the JSON
    bag if the column is NULL.
    """
    out: Dict[str, Any] = {
        "strengths": None,
        "weaknesses": None,
        "score_breakdown": None,
        "score": None,
    }

    out["strengths"] = application.analysis_strengths
    out["weaknesses"] = application.analysis_weaknesses
    out["score_breakdown"] = application.analysis_score_breakdown
    out["analysis_score"] = application.analysis_score

    if not include_bag_fallback:
        return out

    bag = _safe_load(application.analysis_json)
    if out["strengths"] is None and "strengths" in bag:
        out["strengths"] = bag["strengths"]
    if out["weaknesses"] is None:
        out["weaknesses"] = bag.get("weaknesses") or bag.get("missing_skills") or []
    if out["score_breakdown"] is None and "final_score_breakdown" in bag:
        out["score_breakdown"] = bag["final_score_breakdown"]
    if out["analysis_score"] is None:
        out["analysis_score"] = (
            bag.get("score") or bag.get("match_score") or bag.get("current_score")
        )

    return out
