from datetime import UTC, datetime
from typing import Optional

from fastapi import BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import Application, Interview, InterviewParticipant, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger

from . import router


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def check_interview_access(interview: Interview, user: User, db: Session):
    get_application_for_recruiter(interview.application_id, user, db)


class InterviewUpdate(BaseModel):
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    type: Optional[str] = None
    meeting_link: Optional[str] = None
    location: Optional[str] = None
    agenda: Optional[str] = None
    internal_notes: Optional[str] = None
    status: Optional[str] = None


@router.get("/{interview_id}")
def get_interview_details(
    interview_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    from backend.database import InterviewFeedback

    from .feedback import format_feedback
    from .scheduling import format_interview_response

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    check_interview_access(interview, recruiter, db)

    feedback_list = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id == interview_id)
        .all()
    )

    return {
        **format_interview_response(interview, db),
        "internal_notes": interview.internal_notes,
        "feedback": [format_feedback(f, db) for f in feedback_list],
    }


@router.put("/{interview_id}")
def update_interview(
    interview_id: int,
    data: InterviewUpdate,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    check_interview_access(interview, recruiter, db)

    time_changed = False

    if data.scheduled_time and data.scheduled_time != interview.scheduled_time:
        interview.scheduled_time = data.scheduled_time
        interview.status = "rescheduled"
        time_changed = True

    if data.duration_minutes:
        interview.duration_minutes = data.duration_minutes

    if data.type:
        interview.type = data.type

    if data.meeting_link is not None:
        interview.meeting_link = data.meeting_link

    if data.location is not None:
        interview.location = data.location

    if data.agenda is not None:
        interview.agenda = data.agenda

    if data.internal_notes is not None:
        interview.internal_notes = data.internal_notes

    if data.status:
        interview.status = data.status
        if data.status == "cancelled":
            interview.cancelled_at = _utcnow()
        elif data.status == "completed":
            interview.completed_at = _utcnow()

    interview.updated_at = _utcnow()
    db.commit()

    if time_changed:
        app = (
            db.query(Application)
            .filter(Application.id == interview.application_id)
            .first()
        )
        participants = (
            db.query(InterviewParticipant)
            .filter(InterviewParticipant.interview_id == interview_id)
            .all()
        )

        from .feedback import send_interview_update_notifications

        background_tasks.add_task(
            send_interview_update_notifications,
            interview.id,
            app.email,
            [p.user_id for p in participants],
            interview.company_id,
        )

    logger.info(f"Interview {interview_id} updated by {recruiter.email}")

    return {"success": True, "message": "Interview updated successfully"}


@router.delete("/{interview_id}")
def cancel_interview(
    interview_id: int,
    reason: Optional[str] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    check_interview_access(interview, recruiter, db)

    interview.status = "cancelled"
    interview.cancelled_at = _utcnow()
    if reason:
        interview.internal_notes = (
            f"{interview.internal_notes or ''}\n\nCancellation reason: {reason}"
        )

    db.commit()

    logger.info(f"Interview {interview_id} cancelled by {recruiter.email}")

    return {"success": True, "message": "Interview cancelled"}
