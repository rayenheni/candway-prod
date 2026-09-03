"""
A/B Experiment Engine — compares two AI model versions side-by-side.

Usage:
    experiment = get_active_experiment(company_id)
    if experiment:
        arm = assign_arm(experiment, application_id)
        if arm == "A":
            result = await call_model_a(...)
        else:
            result = await call_model_b(...)
        record_result(experiment, application_id, arm, score)
        conclude_experiment(experiment)
"""

import hashlib
from datetime import UTC, datetime
from typing import Optional

from backend.database import ABExperiment, SessionLocal
from backend.logger import logger


def get_active_experiment(company_id: Optional[int] = None) -> Optional[ABExperiment]:
    """Return the first active experiment for a company, if any."""
    try:
        with SessionLocal() as db:
            q = db.query(ABExperiment).filter(ABExperiment.is_active)
            if company_id:
                q = q.filter(ABExperiment.company_id == company_id)
            return q.order_by(ABExperiment.started_at.desc()).first()
    except Exception as e:
        logger.warning(f"[AB] Failed to get active experiment: {e}")
        return None


def assign_arm(experiment: ABExperiment, application_id: int) -> str:
    """Deterministically assign an application to arm A or B based on hash.

    Uses application_id as salt so the same app always gets the same arm,
    enabling reproducible assignments.
    """
    seed = hashlib.sha256(f"{experiment.id}:{application_id}".encode()).hexdigest()
    arm = "A" if int(seed[:8], 16) % 2 == 0 else "B"
    return arm


def record_result(
    experiment: ABExperiment,
    application_id: int,
    arm: str,
    score: float,
):
    """Record a scored result into the experiment's running averages atomically."""
    try:
        with SessionLocal() as db:
            exp = (
                db.query(ABExperiment).filter(ABExperiment.id == experiment.id).first()
            )
            if not exp:
                return

            if arm == "A":
                old_count = exp.sample_size_a or 0
                old_avg = exp.avg_score_a or 0.0
                new_count = old_count + 1
                new_avg = (
                    (old_avg * old_count + score) / new_count
                    if old_count > 0
                    else score
                )
                exp.sample_size_a = new_count
                exp.avg_score_a = new_avg
            else:
                old_count = exp.sample_size_b or 0
                old_avg = exp.avg_score_b or 0.0
                new_count = old_count + 1
                new_avg = (
                    (old_avg * old_count + score) / new_count
                    if old_count > 0
                    else score
                )
                exp.sample_size_b = new_count
                exp.avg_score_b = new_avg

            db.commit()
    except Exception as e:
        logger.warning(f"[AB] Failed to record result: {e}")


def conclude_experiment(experiment: ABExperiment, min_sample: int = 50) -> bool:
    """Auto-conclude an experiment once both arms have sufficient samples.

    Returns True if the experiment was concluded.
    """
    try:
        with SessionLocal() as db:
            exp = (
                db.query(ABExperiment).filter(ABExperiment.id == experiment.id).first()
            )
            if not exp or not exp.is_active:
                return False
            if exp.sample_size_a < min_sample or exp.sample_size_b < min_sample:
                return False
            exp.is_active = False
            exp.ended_at = datetime.now(UTC).replace(tzinfo=None)
            if exp.avg_score_a is not None and exp.avg_score_b is not None:
                diff = exp.avg_score_a - exp.avg_score_b
                if abs(diff) < 0.02:
                    exp.conclusion = "No significant difference detected"
                elif diff > 0:
                    exp.conclusion = f"Model A leads by {diff:.3f} points"
                else:
                    exp.conclusion = f"Model B leads by {abs(diff):.3f} points"
            db.commit()
            logger.info(f"[AB] Experiment {exp.id} concluded: {exp.conclusion}")
            return True
    except Exception as e:
        logger.warning(f"[AB] Failed to conclude experiment: {e}")
        return False


def get_experiment_summary(experiment_id: int) -> Optional[dict]:
    """Return a summary of an experiment for reporting."""
    try:
        with SessionLocal() as db:
            exp = (
                db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
            )
            if not exp:
                return None
            return {
                "id": exp.id,
                "name": exp.name,
                "model_a": exp.model_a,
                "model_b": exp.model_b,
                "sample_size_a": exp.sample_size_a,
                "sample_size_b": exp.sample_size_b,
                "avg_score_a": exp.avg_score_a,
                "avg_score_b": exp.avg_score_b,
                "is_active": exp.is_active,
                "conclusion": exp.conclusion,
                "started_at": exp.started_at.isoformat() if exp.started_at else None,
                "ended_at": exp.ended_at.isoformat() if exp.ended_at else None,
            }
    except Exception as e:
        logger.warning(f"[AB] Failed to get summary: {e}")
        return None
