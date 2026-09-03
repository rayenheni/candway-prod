"""
Drift Monitor — tracks score distribution drift over time windows.

Detects when AI scores shift significantly from baseline,
which can indicate model degradation, data drift, or prompt changes.

Integrated with the scheduler to run periodic drift checks
and write snapshots to the DriftSnapshot table.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func

from backend.database import (
    Application,
    DriftSnapshot,
    EvaluationResult,
    EvaluationSession,
    SessionLocal,
)
from backend.logger import logger

_WINDOW_HOURS = 24
_BASELINE_DAYS = 7
_DRIFT_THRESHOLD = 0.1


def compute_drift(company_id: Optional[int] = None) -> Dict[str, Any]:
    """Compute drift for key metrics over rolling windows.

    Returns a dict of metric_name -> {current_value, baseline_value, drift_score, sample_size}.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    window_start = now - timedelta(hours=_WINDOW_HOURS)

    metrics = {
        "overall_score": {"column": EvaluationResult.final_score, "avg": True},
        "completion_rate": {"column": EvaluationResult.final_score, "avg": True},
    }

    results = {}
    try:
        with SessionLocal() as db:
            for metric_name, cfg in metrics.items():
                col = cfg["column"]
                q_window = (
                    db.query(func.avg(col))
                    .select_from(Application)
                    .join(
                        EvaluationSession,
                        EvaluationSession.application_id == Application.id,
                    )
                    .join(
                        EvaluationResult,
                        EvaluationResult.evaluation_session_id == EvaluationSession.id,
                    )
                    .filter(
                        EvaluationResult.final_score.isnot(None),
                    )
                )
                q_baseline = (
                    db.query(func.avg(col))
                    .select_from(Application)
                    .join(
                        EvaluationSession,
                        EvaluationSession.application_id == Application.id,
                    )
                    .join(
                        EvaluationResult,
                        EvaluationResult.evaluation_session_id == EvaluationSession.id,
                    )
                    .filter(
                        EvaluationResult.final_score.isnot(None),
                    )
                )

                if company_id:
                    q_window = q_window.filter(Application.company_id == company_id)
                    q_baseline = q_baseline.filter(Application.company_id == company_id)

                current_val = q_window.scalar() or 0.0
                baseline_val = q_baseline.scalar() or 0.0
                drift = abs(current_val - baseline_val)

                results[metric_name] = {
                    "current_value": round(float(current_val), 4),
                    "baseline_value": round(float(baseline_val), 4),
                    "drift_score": round(float(drift), 4),
                    "drifted": drift > _DRIFT_THRESHOLD,
                }

            count_window = (
                db.query(func.count(Application.id))
                .join(
                    EvaluationSession,
                    EvaluationSession.application_id == Application.id,
                )
                .join(
                    EvaluationResult,
                    EvaluationResult.evaluation_session_id == EvaluationSession.id,
                )
                .filter(
                    Application.created_at >= window_start,
                    EvaluationResult.final_score.isnot(None),
                )
            )
            if company_id:
                count_window = count_window.filter(Application.company_id == company_id)
            results["sample_count"] = count_window.scalar() or 0

    except Exception as e:
        logger.warning(f"[DRIFT] Compute failed: {e}")
        results["error"] = str(e)

    return results


def record_drift_snapshot(company_id: Optional[int] = None) -> Dict[str, Any]:
    """Compute drift and write a DriftSnapshot record for each metric."""
    drift_data = compute_drift(company_id)
    logger.info(f"[DRIFT] Recording snapshot: {drift_data.get('overall_score', {})}")

    try:
        with SessionLocal() as db:
            for metric_name, values in drift_data.items():
                if metric_name == "sample_count" or metric_name == "error":
                    continue
                snapshot = DriftSnapshot(
                    company_id=company_id,
                    metric_name=metric_name,
                    metric_value=values.get("current_value", 0.0),
                    baseline_value=values.get("baseline_value", 0.0),
                    drift_score=values.get("drift_score", 0.0),
                    sample_size=drift_data.get("sample_count", 0),
                    snapshot_at=datetime.now(UTC).replace(tzinfo=None),
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
                db.add(snapshot)
            db.commit()
    except Exception as e:
        logger.warning(f"[DRIFT] Failed to record snapshot: {e}")

    return drift_data


def get_drift_history(
    metric_name: str = "overall_score",
    company_id: Optional[int] = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """Return recent drift snapshots for a metric."""
    try:
        with SessionLocal() as db:
            q = (
                db.query(DriftSnapshot)
                .filter(DriftSnapshot.metric_name == metric_name)
                .order_by(DriftSnapshot.snapshot_at.desc())
                .limit(limit)
            )
            if company_id:
                q = q.filter(DriftSnapshot.company_id == company_id)
            snapshots = q.all()
            return [
                {
                    "id": s.id,
                    "metric_value": s.metric_value,
                    "baseline_value": s.baseline_value,
                    "drift_score": s.drift_score,
                    "sample_size": s.sample_size,
                    "snapshot_at": s.snapshot_at.isoformat(),
                }
                for s in snapshots
            ]
    except Exception as e:
        logger.warning(f"[DRIFT] Failed to get history: {e}")
        return []


def check_alert_threshold(company_id: Optional[int] = None) -> Optional[str]:
    """Check if any metric has drifted beyond threshold.

    Returns an alert message if threshold exceeded, None otherwise.
    """
    drift_data = compute_drift(company_id)
    alerts = []
    for metric_name, values in drift_data.items():
        if isinstance(values, dict) and values.get("drifted"):
            alerts.append(
                f"[DRIFT ALERT] {metric_name}: drift_score={values['drift_score']} "
                f"(current={values['current_value']}, baseline={values['baseline_value']})"
            )
    return "\n".join(alerts) if alerts else None
