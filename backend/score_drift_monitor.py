"""EvaluationResult health check — verifies canonical score consistency.

The mirror migration is complete so there is no divergence to detect.
This monitor now reports EvaluationResult population health only.
"""

import logging
from datetime import UTC, datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import Application, EvaluationResult, SessionLocal

logger = logging.getLogger(__name__)


def find_divergent_scores(db: Session, limit: int = 1000) -> List[Dict]:
    """Legacy function — mirror columns removed, always returns empty."""
    return []


def check_population_health(db: Session) -> Dict:
    """Return EvaluationResult population health stats."""
    total_apps = db.query(func.count(Application.id)).scalar() or 0
    total_with_eval_result = db.query(func.count(EvaluationResult.id)).scalar() or 0

    return {
        "total_applications": total_apps,
        "has_evaluation_result": total_with_eval_result,
        "pct_scored": round((total_with_eval_result / max(total_apps, 1)) * 100, 1),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def run_drift_check(company_id: Optional[int] = None) -> Dict:
    """Entrypoint for scheduler. Opens its own session."""
    with SessionLocal() as db:
        try:
            health = check_population_health(db)
            logger.info(
                "[SCORE HEALTH] %d/%d applications have EvaluationResult (%.1f%%)",
                health["has_evaluation_result"],
                health["total_applications"],
                health["pct_scored"],
            )
            return {"status": "ok", "health": health, "divergent_samples": []}
        except Exception as exc:
            logger.error("[SCORE HEALTH] Check failed: %s", exc)
            return {"status": "error", "error": str(exc)}
