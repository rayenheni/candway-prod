from datetime import UTC, datetime
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    Interview,
    InterviewFeedback,
    InterviewParticipant,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger

from . import router


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class FeedbackCreate(BaseModel):
    technical_rating: Optional[int] = None
    communication_rating: Optional[int] = None
    culture_fit_rating: Optional[int] = None
    problem_solving_rating: Optional[int] = None
    overall_rating: int
    strengths: Optional[str] = None
    concerns: Optional[str] = None
    additional_notes: Optional[str] = None
    recommendation: str

    @field_validator(
        "overall_rating",
        "technical_rating",
        "communication_rating",
        "culture_fit_rating",
        "problem_solving_rating",
    )
    @classmethod
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v):
        allowed = ["strong_yes", "yes", "maybe", "no", "strong_no"]
        if v not in allowed:
            raise ValueError(f"Recommendation must be one of: {', '.join(allowed)}")
        return v


def format_feedback(feedback: InterviewFeedback, db: Session) -> dict:
    interviewer = db.query(User).filter(User.id == feedback.interviewer_id).first()
    return {
        "id": feedback.id,
        "interviewer_name": interviewer.name if interviewer else "Unknown",
        "interviewer_email": interviewer.email if interviewer else None,
        "technical_rating": feedback.technical_rating,
        "communication_rating": feedback.communication_rating,
        "culture_fit_rating": feedback.culture_fit_rating,
        "problem_solving_rating": feedback.problem_solving_rating,
        "overall_rating": feedback.overall_rating,
        "strengths": feedback.strengths,
        "concerns": feedback.concerns,
        "additional_notes": feedback.additional_notes,
        "recommendation": feedback.recommendation,
        "created_at": feedback.created_at,
    }


def send_interview_notifications(
    interview_id: int,
    candidate_email: str,
    candidate_name: str,
    interviewer_ids: List[int],
    company_id: int = None,
):
    from backend.database import Interview, SessionLocal
    from backend.email_utils import send_email

    db = SessionLocal()
    try:
        interview = (
            db.query(Interview)
            .filter(
                Interview.id == interview_id,
                Interview.company_id == company_id,
            )
            .first()
        )
        if not interview:
            return

        time_str = interview.scheduled_time.strftime("%B %d, %Y at %I:%M %p")

        candidate_subject = f"Interview Scheduled - {time_str}"
        candidate_body = f"""
        <h2>Interview Scheduled</h2>
        <p>Dear {candidate_name},</p>
        <p>Your interview has been scheduled for <strong>{time_str}</strong>.</p>
        <p><strong>Type:</strong> {interview.type.title()}</p>
        <p><strong>Duration:</strong> {interview.duration_minutes} minutes</p>
        {f'<p><strong>Meeting Link:</strong> <a href="{interview.meeting_link}">{interview.meeting_link}</a></p>' if interview.meeting_link else ""}
        {f"<p><strong>Location:</strong> {interview.location}</p>" if interview.location else ""}
        {f"<p><strong>Agenda:</strong><br>{interview.agenda}</p>" if interview.agenda else ""}
        <p>Good luck!</p>
        """
        send_email(candidate_email, candidate_subject, candidate_body)

        from backend.database import User

        for interviewer_id in interviewer_ids:
            interviewer = db.query(User).filter(User.id == interviewer_id).first()
            if interviewer and interviewer.email:
                interviewer_subject = f"Interview Assignment - {candidate_name}"
                interviewer_body = f"""
                <h2>Interview Assignment</h2>
                <p>You have been assigned to interview <strong>{candidate_name}</strong>.</p>
                <p><strong>Time:</strong> {time_str}</p>
                <p><strong>Type:</strong> {interview.type.title()}</p>
                {f'<p><strong>Meeting Link:</strong> <a href="{interview.meeting_link}">{interview.meeting_link}</a></p>' if interview.meeting_link else ""}
                <p>Please log in to Candway to view details and submit feedback after the interview.</p>
                """
                send_email(interviewer.email, interviewer_subject, interviewer_body)

        logger.info(f"Interview notifications sent for interview {interview_id}")
    finally:
        db.close()


def send_interview_update_notifications(
    interview_id: int,
    candidate_email: str,
    interviewer_ids: List[int],
    company_id: int = None,
):
    from backend.database import Interview, SessionLocal, User
    from backend.email_utils import send_email

    db = SessionLocal()
    try:
        interview = (
            db.query(Interview)
            .filter(
                Interview.id == interview_id,
                Interview.company_id == company_id,
            )
            .first()
        )
        if not interview:
            return

        time_str = interview.scheduled_time.strftime("%B %d, %Y at %I:%M %p")

        subject = "Interview Rescheduled"
        body = f"""
        <h2>Interview Rescheduled</h2>
        <p>Your interview has been rescheduled to <strong>{time_str}</strong>.</p>
        <p>Please update your calendar accordingly.</p>
        """
        send_email(candidate_email, subject, body)

        for interviewer_id in interviewer_ids:
            interviewer = db.query(User).filter(User.id == interviewer_id).first()
            if interviewer and interviewer.email:
                send_email(interviewer.email, subject, body)

        logger.info(f"Update notifications sent for interview {interview_id}")
    finally:
        db.close()


@router.post("/{interview_id}/feedback")
def submit_interview_feedback(
    interview_id: int,
    feedback: FeedbackCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(
            Interview.id == interview_id,
            Interview.company_id == getattr(recruiter, "_company_id", None),
        )
        .first()
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    participant = (
        db.query(InterviewParticipant)
        .filter(
            and_(
                InterviewParticipant.interview_id == interview_id,
                InterviewParticipant.user_id == recruiter.id,
            )
        )
        .first()
    )

    if not participant and recruiter.role != "admin":
        raise HTTPException(
            status_code=403, detail="Only interview participants can submit feedback"
        )

    if interview.scheduled_time > _utcnow() and recruiter.role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Cannot submit feedback before the interview takes place",
        )

    existing = (
        db.query(InterviewFeedback)
        .filter(
            and_(
                InterviewFeedback.interview_id == interview_id,
                InterviewFeedback.interviewer_id == recruiter.id,
            )
        )
        .first()
    )

    if existing:
        for key, value in feedback.model_dump().items():
            setattr(existing, key, value)
        existing.updated_at = _utcnow()
        db.commit()
        logger.info(
            f"Feedback updated for interview {interview_id} by {recruiter.email}"
        )
    else:
        fb = InterviewFeedback(
            interview_id=interview_id,
            interviewer_id=recruiter.id,
            company_id=interview.company_id,
            **feedback.model_dump(),
        )
        db.add(fb)
        db.commit()
        logger.info(
            f"Feedback submitted for interview {interview_id} by {recruiter.email}"
        )

    if interview.status in ("scheduled", "rescheduled"):
        interview.status = "completed"
        interview.completed_at = _utcnow()

    app = (
        db.query(Application).filter(Application.id == interview.application_id).first()
    )
    feedback_count = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id == interview_id)
        .count()
    )

    if feedback_count <= 1:
        if feedback.recommendation in ["strong_yes", "yes"]:
            if app.status not in ("offer", "hired"):
                app.status = "offer"
        elif feedback.recommendation in ["strong_no", "no"]:
            if app.status not in ("rejected", "hired"):
                app.status = "rejected"

    db.commit()

    return {"success": True, "message": "Feedback submitted successfully"}


@router.get("/{interview_id}/feedback")
def get_interview_feedback(
    interview_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    from .management import check_interview_access as _check_access

    _check_access(interview, recruiter, db)

    feedback_list = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id == interview_id)
        .all()
    )

    return [format_feedback(f, db) for f in feedback_list]
