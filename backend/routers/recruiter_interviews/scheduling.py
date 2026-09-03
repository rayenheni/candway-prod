from datetime import UTC, datetime
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from backend.authz import get_application_for_recruiter
from backend.database import (
    Application,
    Interview,
    InterviewFeedback,
    InterviewParticipant,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name, get_user_tier

from . import router


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class InterviewCreate(BaseModel):
    application_id: int
    scheduled_time: datetime
    duration_minutes: int = 60
    type: str
    meeting_link: Optional[str] = None
    location: Optional[str] = None
    agenda: Optional[str] = None
    internal_notes: Optional[str] = None
    interviewer_ids: List[int] = []

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        allowed = ["phone", "video", "onsite", "technical", "behavioral", "panel"]
        if v not in allowed:
            raise ValueError(f"Interview type must be one of: {', '.join(allowed)}")
        return v

    @field_validator("scheduled_time")
    @classmethod
    def validate_future_time(cls, v):
        if v < _utcnow():
            raise ValueError("Interview must be scheduled in the future")
        return v


class InterviewResponse(BaseModel):
    id: int
    application_id: int
    candidate_name: str
    candidate_email: str
    job_title: str
    scheduled_time: datetime
    duration_minutes: int
    type: str
    meeting_link: Optional[str]
    location: Optional[str]
    status: str
    agenda: Optional[str]
    interviewers: List[dict]
    video_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


InterviewResponse.model_rebuild()


def format_interview_response(interview: Interview, db: Session) -> dict:
    app = interview.application
    if not app:
        app = (
            db.query(Application)
            .filter(Application.id == interview.application_id)
            .first()
        )

    job_title = "General Application"
    if app.job:
        job_title = app.job.title
    elif app.batch_job:
        job_title = app.batch_job.title
    elif app.declared_role:
        job_title = app.declared_role

    participants = (
        db.query(InterviewParticipant)
        .options(joinedload(InterviewParticipant.user))
        .filter(InterviewParticipant.interview_id == interview.id)
        .all()
    )

    interviewers = []
    for p in participants:
        user = p.user
        if user:
            interviewers.append(
                {
                    "id": user.id,
                    "name": get_user_name(user),
                    "email": get_user_email(user),
                    "role": p.role,
                    "status": p.attendance_status,
                }
            )

    feedback_count = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id == interview.id)
        .count()
    )

    _es_sched = app.evaluation_sessions or []
    _er_sched = (
        _es_sched[0].evaluation_result
        if _es_sched and _es_sched[0].evaluation_result
        else None
    )
    _owner_user = app.owner if hasattr(app, "owner") else None
    photo_url = None
    if _owner_user is not None:
        photo_url = getattr(
            getattr(_owner_user, "candidate_profile", None), "avatar_url", None
        )
    if not photo_url:
        photo_url = getattr(getattr(app, "candidate", None), "photo_url", None)
    return {
        "id": interview.id,
        "application_id": interview.application_id,
        "candidate_name": app.full_name,
        "candidate_email": app.email,
        "photo_url": photo_url,
        "job_title": job_title,
        "scheduled_time": interview.scheduled_time,
        "duration_minutes": interview.duration_minutes,
        "type": interview.type,
        "meeting_link": interview.meeting_link,
        "location": interview.location,
        "status": interview.status,
        "agenda": interview.agenda,
        "interviewers": interviewers,
        "video_url": app.video_file_path
        if hasattr(app, "video_file_path") and app.video_file_path
        else None,
        "feedback_collected": feedback_count > 0,
        "ai_score": round(_er_sched.final_score)
        if _er_sched and _er_sched.final_score
        else None,
        "cv_score": round(_er_sched.cv_score)
        if _er_sched and _er_sched.cv_score
        else None,
        "application_status": app.status,
        "created_at": interview.created_at,
    }


@router.post("/schedule", status_code=status.HTTP_201_CREATED)
async def schedule_interview(
    data: InterviewCreate,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(data.application_id, recruiter, db)

    interview = Interview(
        company_id=app.company_id,
        application_id=data.application_id,
        scheduled_by=recruiter.id,
        scheduled_time=data.scheduled_time,
        duration_minutes=data.duration_minutes,
        type=data.type,
        meeting_link=data.meeting_link,
        location=data.location,
        agenda=data.agenda,
        internal_notes=data.internal_notes,
    )
    db.add(interview)
    db.flush()

    for interviewer_id in data.interviewer_ids:
        interviewer = db.query(User).filter(User.id == interviewer_id).first()
        if not interviewer:
            logger.warning(f"Interviewer {interviewer_id} not found, skipping")
            continue

        participant = InterviewParticipant(
            interview_id=interview.id,
            user_id=interviewer_id,
            role="interviewer",
            company_id=app.company_id,
        )
        db.add(participant)

    if app.status not in ["interviewing", "offer", "hired"]:
        app.status = "interviewing"

    db.commit()
    db.refresh(interview)

    from .feedback import send_interview_notifications

    background_tasks.add_task(
        send_interview_notifications,
        interview.id,
        app.email,
        app.full_name,
        [i for i in data.interviewer_ids],
        app.company_id,
    )

    try:
        import asyncio

        from backend.webhook_dispatcher import dispatch_webhook

        asyncio.create_task(
            dispatch_webhook(
                "interview_scheduled",
                {
                    "interview_id": interview.id,
                    "application_id": app.id,
                    "candidate_name": app.full_name,
                    "interview_type": data.type,
                    "scheduled_time": data.scheduled_time.isoformat(),
                    "scheduled_by": get_user_email(recruiter),
                },
                app.company_id,
            )
        )
    except Exception as e:
        logger.warning(f"Failed to dispatch interview webhook: {e}")

    logger.info(
        f"Interview {interview.id} scheduled by {get_user_email(recruiter)} for app {app.id}"
    )

    return {
        "success": True,
        "interview_id": interview.id,
        "message": "Interview scheduled successfully",
    }


@router.get("/upcoming", response_model=List[InterviewResponse])
def get_upcoming_interviews(
    limit: int = 50,
    offset: int = 0,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    from backend.security import mask_candidate_data

    company_id = getattr(recruiter, "_company_id", None)
    interviews = (
        db.query(Interview)
        .join(Application)
        .options(
            joinedload(Interview.application).joinedload(Application.job),
            joinedload(Interview.application).joinedload(Application.batch_job),
            joinedload(Interview.participants).joinedload(InterviewParticipant.user),
        )
        .filter(
            and_(
                Interview.scheduled_time >= _utcnow(),
                Interview.status.in_(["scheduled", "rescheduled"]),
                Application.company_id == company_id,
            )
        )
        .order_by(Interview.scheduled_time)
        .offset(offset)
        .limit(limit)
        .all()
    )

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    return [
        mask_candidate_data(format_interview_response(i, db), is_pro)
        for i in interviews
    ]


@router.get("/past", response_model=List[InterviewResponse])
def get_past_interviews(
    limit: int = 50,
    offset: int = 0,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    from backend.security import mask_candidate_data

    company_id = getattr(recruiter, "_company_id", None)
    interviews = (
        db.query(Interview)
        .join(Application)
        .options(
            joinedload(Interview.application).joinedload(Application.job),
            joinedload(Interview.application).joinedload(Application.batch_job),
            joinedload(Interview.participants).joinedload(InterviewParticipant.user),
        )
        .filter(
            and_(
                or_(
                    Interview.scheduled_time < _utcnow(),
                    Interview.status.in_(["completed", "cancelled", "no_show"]),
                ),
                Application.company_id == company_id,
            )
        )
        .order_by(Interview.scheduled_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    return [
        mask_candidate_data(format_interview_response(i, db), is_pro)
        for i in interviews
    ]


@router.get("/application/{app_id}")
def get_interviews_by_application(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    _app = get_application_for_recruiter(app_id, recruiter, db)

    from backend.security import mask_candidate_data

    app_ids = [app_id]
    if _app.user_id:
        same_candidate = (
            db.query(Application.id)
            .filter(
                Application.user_id == _app.user_id,
                Application.company_id == _app.company_id,
            )
            .all()
        )
        app_ids = [a[0] for a in same_candidate] or app_ids

    interviews = (
        db.query(Interview)
        .options(
            joinedload(Interview.application).joinedload(Application.job),
            joinedload(Interview.application).joinedload(Application.batch_job),
            joinedload(Interview.participants).joinedload(InterviewParticipant.user),
        )
        .filter(Interview.application_id.in_(app_ids))
        .order_by(Interview.scheduled_time.desc())
        .all()
    )

    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    return [
        mask_candidate_data(format_interview_response(i, db), is_pro)
        for i in interviews
    ]
