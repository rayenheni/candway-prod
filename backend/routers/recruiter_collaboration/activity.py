import json
from datetime import UTC, datetime
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import (
    ActivityLog,
    Application,
    User,
)
from backend.dependencies import (
    get_db,
    require_recruiter,
)
from backend.logger import logger
from backend.profile_helpers import get_user_name
from backend.tenant import get_current_company_id

router = APIRouter(tags=["Recruiter Collaboration - Activity"])


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


class ActivityResponse(BaseModel):
    id: int
    user_name: str
    action: str
    details: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def format_activity(activity: ActivityLog, db: Session) -> dict:
    user = db.query(User).filter(User.id == activity.user_id).first()

    try:
        details = json.loads(activity.details) if activity.details else {}
    except Exception:
        details = {}

    return {
        "id": activity.id,
        "user_name": get_user_name(user) if user else "Unknown",
        "action": activity.action,
        "details": details,
        "created_at": activity.created_at,
    }


@router.get("/activity/{application_id}", response_model=List[ActivityResponse])
def get_activity_feed(
    application_id: int,
    limit: int = 50,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    get_application_for_recruiter(application_id, recruiter, db)
    activities = (
        db.query(ActivityLog)
        .filter(ActivityLog.application_id == application_id)
        .order_by(desc(ActivityLog.created_at))
        .limit(limit)
        .all()
    )

    return [format_activity(a, db) for a in activities]


@router.get("/activity/recent")
def get_recent_activity(
    limit: int = 20,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    activities = (
        db.query(ActivityLog)
        .join(Application)
        .outerjoin(Application.job)
        .outerjoin(Application.batch_job)
        .filter(
            (Application.job.has(company_id=company_id))
            | (Application.batch_job.has(company_id=company_id))
        )
        .order_by(desc(ActivityLog.created_at))
        .limit(limit)
        .all()
    )

    return [format_activity(a, db) for a in activities]
