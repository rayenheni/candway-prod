import json
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.config import get_settings
from backend.database import (
    ActivityLog,
    InterviewFeedback,
    ScorecardSubmission,
    UndoAction,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.email_service import email_service
from backend.logger import logger
from backend.profile_helpers import get_user_name
from backend.routers.recruiter_candidates.applications import (
    ALLOWED_APPLICATION_STATUSES,
)

router = APIRouter(tags=["Recruiter Enhancements - Quick Actions"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class QuickActionRequest(BaseModel):
    action: str  # invite, shortlist, reject, archive
    app_id: int
    message: Optional[str] = None


class UndoResponse(BaseModel):
    undo_id: int
    action_type: str
    target_type: str
    target_id: int
    expires_in_seconds: float
    can_undo: bool


@router.post("/quick-action")
async def quick_action(
    data: QuickActionRequest,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """One-click action on pipeline card: invite, shortlist, reject, archive"""
    app = get_application_for_recruiter(data.app_id, recruiter, db)

    # Save undo state before action
    previous_state = {
        "status": app.status,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }

    if data.action == "invite":
        app.status = "invited"
        app.invited_at = _utcnow()
        background_tasks.add_task(
            _send_quick_invite_email,
            app.id,
            app.full_name,
            app.email,
            recruiter.id,
            data.message,
        )
    elif data.action == "shortlist":
        app.status = "interviewing"
    elif data.action == "reject":
        app.status = "rejected"
    elif data.action == "archive":
        app.status = "archived"
        app.deleted_at = _utcnow()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {data.action}")

    if app.status not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Action '{data.action}' is not supported: '{app.status}' is not a valid application status",
        )

    # Create undo record (10 second window)
    undo = UndoAction(
        user_id=recruiter.id,
        company_id=app.company_id,
        action_type=data.action,
        target_type="application",
        target_id=app.id,
        previous_state_json=json.dumps(previous_state),
        new_state_json=json.dumps({"status": app.status}),
        expires_at=_utcnow() + timedelta(seconds=10),
    )
    db.add(undo)

    # Log activity
    log = ActivityLog(
        user_id=recruiter.id,
        company_id=app.company_id,
        action=f"quick_{data.action}",
        application_id=app.id,
        details=json.dumps({"action": data.action, "message": data.message}),
    )
    db.add(log)

    db.commit()

    return {
        "success": True,
        "action": data.action,
        "app_id": app.id,
        "new_status": app.status,
        "undo_id": undo.id,
        "undo_expires_in": 10,
    }


@router.post("/undo/{undo_id}")
def undo_action(
    undo_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Undo a recent action within the 10-second window"""
    undo = (
        db.query(UndoAction)
        .filter(UndoAction.id == undo_id, UndoAction.user_id == recruiter.id)
        .first()
    )
    if not undo:
        raise HTTPException(status_code=404, detail="Undo record not found")

    if undo.is_executed:
        raise HTTPException(status_code=400, detail="Action already undone")

    if undo.expires_at < _utcnow():
        undo.is_expired = True
        db.commit()
        raise HTTPException(status_code=400, detail="Undo window expired")

    # Rollback
    previous = json.loads(undo.previous_state_json)
    if undo.target_type == "application":
        try:
            app = get_application_for_recruiter(undo.target_id, recruiter, db)
            app.status = previous.get("status", app.status)
            if app.status != "archived":
                app.deleted_at = None
        except HTTPException:
            raise HTTPException(status_code=404, detail="Application not found")

    undo.is_executed = True
    db.commit()

    logger.info(
        f"Undo executed by {recruiter.email}: {undo.action_type} on {undo.target_type} {undo.target_id}"
    )
    return {"success": True, "message": f"Undone {undo.action_type}"}


@router.get("/undo/pending")
def get_pending_undos(
    recruiter: User = Depends(require_recruiter), db: Session = Depends(get_db)
):
    """Get all pending undo actions for the current user"""
    now = _utcnow()
    undos = (
        db.query(UndoAction)
        .filter(
            UndoAction.user_id == recruiter.id,
            not UndoAction.is_executed,
            not UndoAction.is_expired,
            UndoAction.expires_at > now,
        )
        .order_by(desc(UndoAction.created_at))
        .all()
    )

    return [
        {
            "undo_id": u.id,
            "action_type": u.action_type,
            "target_type": u.target_type,
            "target_id": u.target_id,
            "expires_in_seconds": max(0, (u.expires_at - now).total_seconds()),
            "created_at": u.created_at.isoformat(),
        }
        for u in undos
    ]


@router.post("/debrief/{interview_id}")
async def generate_interview_debrief(
    interview_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Auto-generate interview debrief summary from feedback + AI analysis"""
    from backend.authz import get_interview_for_recruiter as _get_interview

    interview = _get_interview(interview_id, recruiter, db)
    app = get_application_for_recruiter(interview.application_id, recruiter, db)

    # Get all feedback
    feedback_list = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id == interview_id)
        .all()
    )

    # Get scorecard submissions
    scorecards = (
        db.query(ScorecardSubmission)
        .filter(ScorecardSubmission.application_id == app.id)
        .all()
    )

    # Build debrief data
    _es_actions = app.evaluation_sessions or []
    _er_actions = (
        _es_actions[0].evaluation_result
        if _es_actions and _es_actions[0].evaluation_result
        else None
    )
    debrief = {
        "candidate_name": app.full_name,
        "role": app.declared_role,
        "interview_type": interview.type,
        "interview_date": interview.scheduled_time.isoformat()
        if interview.scheduled_time
        else None,
        "overall_score": (_er_actions.final_score if _er_actions else None) or 0,
        "cv_score": (_er_actions.cv_score if _er_actions else None) or 0,
        "interview_feedback": [],
        "scorecard_results": [],
        "strengths": [],
        "concerns": [],
        "recommendations": [],
        "consensus": None,
    }

    for fb in feedback_list:
        interviewer = db.query(User).filter(User.id == fb.interviewer_id).first()
        debrief["interview_feedback"].append(
            {
                "interviewer": interviewer.name if interviewer else "Unknown",
                "overall_rating": fb.overall_rating,
                "recommendation": fb.recommendation,
                "strengths": fb.strengths,
                "concerns": fb.concerns,
            }
        )
        if fb.strengths:
            debrief["strengths"].append(fb.strengths)
        if fb.concerns:
            debrief["concerns"].append(fb.concerns)
        if fb.recommendation:
            debrief["recommendations"].append(fb.recommendation)

    for sc in scorecards:
        evaluator = db.query(User).filter(User.id == sc.evaluator_id).first()
        debrief["scorecard_results"].append(
            {
                "evaluator": evaluator.name if evaluator else "Unknown",
                "scorecard": sc.scorecard.name,
                "overall_score": sc.overall_score,
                "recommendation": sc.recommendation,
            }
        )

    # Calculate consensus
    recs = [r for r in debrief["recommendations"] if r]
    if recs:
        yes_count = sum(1 for r in recs if r in ("strong_yes", "yes"))
        no_count = sum(1 for r in recs if r in ("strong_no", "no"))
        if yes_count > no_count:
            debrief["consensus"] = "Hire"
        elif no_count > yes_count:
            debrief["consensus"] = "No Hire"
        else:
            debrief["consensus"] = "Split Decision"

    # Generate AI summary if available
    credit_tx = None
    try:
        from backend.ai.llm import call_groq_cascade
        from backend.credit_service import consume_credits_or_402, rollback_credits

        system_prompt = """You are an expert HR assistant. Generate a concise interview debrief summary.
        Format as HTML with sections: Overview, Key Strengths, Areas of Concern, Recommendation."""

        user_prompt = f"""Candidate: {debrief["candidate_name"]}
        Role: {debrief["role"]}
        Overall Score: {debrief["overall_score"]}/100
        Interview Type: {debrief["interview_type"]}
        Feedback Points: {json.dumps(debrief["interview_feedback"][:3])}
        Consensus: {debrief["consensus"]}"""

        credit_tx = consume_credits_or_402(
            db,
            recruiter,
            1,
            "debrief_summary",
            reference_type="interview",
            reference_id=interview_id,
        )
        ai_summary = await call_groq_cascade(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        debrief["ai_summary"] = ai_summary
    except HTTPException:
        raise
    except Exception as e:
        if credit_tx is not None:
            try:
                rollback_credits(db, credit_tx)
            except Exception:
                pass
        logger.error(f"AI debrief generation failed: {e}")
        debrief["ai_summary"] = None

    return debrief


async def _send_quick_invite_email(
    app_id: int,
    full_name: str,
    email: str,
    recruiter_id: int,
    custom_message: Optional[str],
):
    """Background task to send quick invite email"""
    from backend.database import SessionLocal

    with SessionLocal() as db:
        recruiter = db.query(User).filter(User.id == recruiter_id).first()
        if not recruiter:
            return

        get_settings()
        subject = f"AI Interview Invitation — {get_user_name(recruiter) or 'Our Team'}"

        body = (
            custom_message
            or f"""
        <p>Dear {full_name or "Candidate"},</p>
        <p>You've been invited to complete an AI-powered interview.</p>
        <p>Please log in to your candidate portal to begin.</p>
        """
        )

        if email and "@" not in email:
            return

        email_service.send_email(email, subject, body)
        logger.info(f"Quick invite email sent to {email}")
