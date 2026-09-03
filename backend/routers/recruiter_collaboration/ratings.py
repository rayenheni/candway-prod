import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import (
    ActivityLog,
    CandidateRating,
    User,
)
from backend.dependencies import (
    get_db,
    require_recruiter,
)
from backend.logger import logger
from backend.profile_helpers import get_user_name
from backend.repository.metrics_repository import MetricsRepository

router = APIRouter(tags=["Recruiter Collaboration - Ratings"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    application_id: int = None,
    details: dict = None,
    company_id: int = None,
):
    try:
        activity = ActivityLog(
            user_id=user_id,
            application_id=application_id,
            company_id=company_id,
            action=action,
            details=json.dumps(details) if details else None,
        )
        db.add(activity)
        db.flush()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


class RatingCreate(BaseModel):
    application_id: int
    rating: int
    category: Optional[str] = None
    note: Optional[str] = None


class RatingResponse(BaseModel):
    id: int
    application_id: int
    user_name: str
    rating: int
    category: Optional[str]
    note: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def format_rating(rating: CandidateRating, db: Session) -> dict:
    user = db.query(User).filter(User.id == rating.user_id).first()

    return {
        "id": rating.id,
        "application_id": rating.application_id,
        "user_name": get_user_name(user) if user else "Unknown",
        "rating": rating.rating,
        "category": rating.category,
        "note": rating.note,
        "created_at": rating.created_at,
    }


@router.post("/ratings", status_code=status.HTTP_201_CREATED)
def add_rating(
    data: RatingCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    app = get_application_for_recruiter(data.application_id, recruiter, db)

    existing = (
        db.query(CandidateRating)
        .filter(
            and_(
                CandidateRating.application_id == data.application_id,
                CandidateRating.user_id == recruiter.id,
                CandidateRating.category == data.category,
            )
        )
        .first()
    )

    if existing:
        existing.rating = data.rating
        existing.note = data.note
        existing.updated_at = _utcnow()
        db.commit()
        rating_id = existing.id
        action = "rating_updated"
    else:
        rating = CandidateRating(
            application_id=data.application_id,
            user_id=recruiter.id,
            company_id=app.company_id,
            rating=data.rating,
            category=data.category,
            note=data.note,
        )
        db.add(rating)
        db.commit()
        db.refresh(rating)
        rating_id = rating.id
        action = "rating_added"

    log_activity(
        db,
        recruiter.id,
        action,
        data.application_id,
        {"rating": data.rating, "category": data.category},
        company_id=app.company_id,
    )

    logger.info(
        f"Rating {action} by {recruiter.email} on application {data.application_id}"
    )

    return {"success": True, "rating_id": rating_id}


@router.get("/ratings/{application_id}", response_model=List[RatingResponse])
def get_ratings(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    get_application_for_recruiter(application_id, recruiter, db)

    ratings = (
        db.query(CandidateRating)
        .filter(CandidateRating.application_id == application_id)
        .order_by(CandidateRating.created_at.desc())
        .all()
    )

    return [format_rating(r, db) for r in ratings]


@router.get("/ratings/{application_id}/average")
def get_average_rating(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    get_application_for_recruiter(application_id, recruiter, db)

    return MetricsRepository(db).get_rating_stats(application_id)
