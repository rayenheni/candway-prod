import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_db, require_recruiter

router = APIRouter(prefix="/recruiter", tags=["Scoring Weights"])

DEFAULT_WEIGHTS = {
    "weight_cv": 0.25,
    "weight_interview": 0.50,
    "weight_rubric": 0.50,
    "weight_human": 0.0,
}


class ScoringWeightsUpdate(BaseModel):
    weight_cv: Optional[float] = None
    weight_interview: Optional[float] = None
    weight_rubric: Optional[float] = None
    weight_human: Optional[float] = None


def _get_weights(user: User) -> dict:
    from backend.profile_helpers import get_user_email_settings

    raw = get_user_email_settings(user) or "{}"
    try:
        settings = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        settings = {}
    stored = settings.get("scoring_weights", {})
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(stored)
    return weights


def _set_weights(user: User, weights: dict, db: Session):
    from backend.models.evaluation.profile import RecruiterProfile

    profile = (
        db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user.id).first()
    )
    if not profile:
        return
    try:
        raw = getattr(profile, "email_settings", None) or "{}"
        settings = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        settings = {}
    settings["scoring_weights"] = weights
    profile.email_settings = json.dumps(settings)
    db.commit()


@router.get("/scoring-weights")
def get_scoring_weights(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    return _get_weights(recruiter)


@router.put("/scoring-weights")
def update_scoring_weights(
    req: ScoringWeightsUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    current = _get_weights(recruiter)
    for key in ["weight_cv", "weight_interview", "weight_rubric", "weight_human"]:
        val = getattr(req, key, None)
        if val is not None:
            current[key] = max(0.0, min(1.0, val))
    total = sum(current.values())
    if abs(total - 1.0) > 0.01:
        current = {k: v / total for k, v in current.items()}
    _set_weights(recruiter, current, db)
    return current
