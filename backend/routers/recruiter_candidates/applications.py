import json
import re
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from backend.authz import get_application_for_recruiter
from backend.database import (
    ActivityLog,
    Application,
    ApplicationStageHistory,
    BatchJob,
    EvaluationSession,
    Job,
    ScorecardSubmission,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.entity_enricher import enrich_application_dict
from backend.entity_writer import sync_cv_document
from backend.logger import logger
from backend.optimistic_lock import retry_stale
from backend.profile_helpers import (
    get_user_company_name,
    get_user_email,
    get_user_name,
    get_user_phone,
    get_user_skills,
    get_user_tier,
)
from backend.routers.recruiter_candidates.email import (
    EmailUpdateRequest,
    send_status_email,
)
from backend.schemas import StatusUpdate
from backend.security import sanitize_content

router = APIRouter(tags=["Recruiter Candidates"])

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{1,14}$")

ALLOWED_APPLICATION_STATUSES = {
    "pending",
    "screening",
    "interviewing",
    "offer",
    "rejected",
    "analyzed",
    "failed",
    "applied",
    "invited",
    "active",
    "analyzing",
    "analysis_failed",
    "hired",
    "offer_declined",
    "withdrawn",
    "imported",
    "reviewed",
    "shortlisted",
}


class BulkStatusUpdate(BaseModel):
    app_ids: List[int]
    new_status: str


class BulkDeleteRequest(BaseModel):
    app_ids: List[int]


class NotesUpdate(BaseModel):
    notes: str
    tags: Optional[List[str]] = []


class ApplicationUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ScoreOverrideRequest(BaseModel):
    skill: str
    original_score: float
    new_score: float
    reason: str


@router.post("/applications/bulk-delete")
def bulk_delete_applications(
    request: BulkDeleteRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if not request.app_ids:
        raise HTTPException(status_code=400, detail="No application IDs provided")

    # M9 FIX: cap how many rows can be deleted in one call to prevent
    # accidental or malicious mass-delete. 200 per request is generous
    # for any legitimate use case; anything larger should be a scheduled job.
    MAX_BULK = 200
    if len(request.app_ids) > MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail=f"Bulk delete is limited to {MAX_BULK} applications per request. "
            f"You sent {len(request.app_ids)}.",
        )
    apps = []
    for requested_app_id in request.app_ids:
        try:
            apps.append(get_application_for_recruiter(requested_app_id, recruiter, db))
        except HTTPException:
            continue

    deleted_count = 0
    now = datetime.now(UTC)
    for app in apps:
        app.deleted_at = now
        deleted_count += 1
    db.commit()
    return {"message": f"Deleted {deleted_count} applications (soft-delete)"}


@router.post("/applications/bulk-update")
def bulk_update_status(
    request: BulkStatusUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if not request.app_ids:
        raise HTTPException(status_code=400, detail="No application IDs provided")

    if request.new_status not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid application status '{request.new_status}'.",
        )

    # M9 FIX: mirror the delete cap — 200 per call maximum
    MAX_BULK = 200
    if len(request.app_ids) > MAX_BULK:
        raise HTTPException(
            status_code=400,
            detail=f"Bulk update is limited to {MAX_BULK} applications per request. "
            f"You sent {len(request.app_ids)}.",
        )

    apps = []
    for requested_app_id in request.app_ids:
        try:
            apps.append(get_application_for_recruiter(requested_app_id, recruiter, db))
        except HTTPException:
            continue

    ALLOWED_TRANSITIONS = {
        "applied": ["screening", "rejected", "archived", "invited", "shortlisted"],
        "screening": ["interviewing", "rejected", "archived", "shortlisted"],
        "interviewing": ["offer", "rejected", "archived", "screening"],
        "offer": ["hired", "rejected", "archived", "interviewing"],
        "hired": ["archived"],
        "rejected": ["applied", "archived"],
        "archived": [],
        "invited": ["screening", "rejected", "archived"],
        "shortlisted": ["screening", "interviewing", "rejected", "archived"],
        "pending": ["screening", "rejected", "archived", "invited"],
        "interview": ["offer", "rejected", "archived", "screening"],
        "active": ["hired", "rejected", "archived"],
    }

    updated_count = 0

    now = datetime.now(UTC)

    stage_names = {
        "applied": "Applied",
        "screening": "Screening",
        "interviewing": "Interviewing",
        "offer": "Offer",
        "hired": "Hired",
        "rejected": "Rejected",
        "archived": "Archived",
        "invited": "Invited",
        "shortlisted": "Shortlisted",
        "pending": "Pending",
        "interview": "Interview",
        "active": "Active",
    }

    for app in apps:
        allowed = ALLOWED_TRANSITIONS.get(app.status, [])
        if request.new_status not in allowed:
            logger.warning(
                "Blocked invalid transition: app %s from '%s' to '%s' by recruiter %s",
                app.id,
                app.status,
                request.new_status,
                recruiter.id,
            )
            continue
        old_status = app.status
        app.status = request.new_status
        updated_count += 1

        # Close out the previous stage entry if exists
        prev_history = (
            db.query(ApplicationStageHistory)
            .filter(
                ApplicationStageHistory.application_id == app.id,
                ApplicationStageHistory.exited_at.is_(None),
            )
            .first()
        )
        if prev_history:
            prev_history.exited_at = now
            prev_history.duration_seconds = int(
                (now - prev_history.entered_at).total_seconds()
            )

        # Create new stage history entry
        new_history = ApplicationStageHistory(
            company_id=app.company_id,
            application_id=app.id,
            stage_slug=request.new_status,
            stage_name=stage_names.get(request.new_status, request.new_status),
            entered_at=now,
            triggered_by=recruiter.id,
            trigger_type="manual",
        )
        db.add(new_history)

        # Log activity
        log = ActivityLog(
            user_id=recruiter.id,
            company_id=app.company_id,
            action="bulk_status_update",
            details=f"Updated app {app.id} status from {old_status} to {request.new_status}",
        )
        db.add(log)

    db.commit()
    return {
        "message": f"Updated {updated_count} applications to {request.new_status}",
        "updated_count": updated_count,
    }


@router.delete("/applications/{app_id}")
@retry_stale()
def delete_application(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(app_id, recruiter, db)
    app.deleted_at = datetime.now(UTC)
    db.commit()
    return {"message": "Application soft-deleted"}


@router.patch("/applications/{app_id}/email")
@retry_stale()
def update_candidate_email(
    app_id: int,
    request: EmailUpdateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Update candidate email address - useful for fixing placeholder emails."""
    app = get_application_for_recruiter(app_id, recruiter, db)

    # Validate email format
    new_email = request.email.strip()
    if not new_email or "@" not in new_email:
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Check for duplicate
    existing = (
        db.query(Application)
        .filter(Application.email == new_email, Application.id != app_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Email already exists for another candidate"
        )

    old_email = app.email
    app.email = new_email

    # Also update the linked user if it's a ghost user
    if app.owner and not app.owner.hashed_password:
        # Check if user with this email already exists
        existing_user = db.query(User).filter(User.email == new_email).first()
        if existing_user:
            # Merge applications to existing user
            app.user_id = existing_user.id
            app.owner = existing_user
        else:
            app.owner.email = new_email
            from backend.profile_helpers import get_profile as _get_profile

            _profile = _get_profile(app.owner)
            if _profile:
                _profile.email = new_email

    db.commit()
    logger.info(f"Updated email for app {app_id}: {old_email} -> {new_email}")

    return {
        "success": True,
        "message": f"Email updated from {old_email} to {new_email}",
        "app_id": app_id,
        "new_email": new_email,
    }


@router.patch("/applications/{app_id}")
@retry_stale()
def update_application_info(
    app_id: int,
    request: ApplicationUpdateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Update name or email for an application."""
    app = get_application_for_recruiter(app_id, recruiter, db)

    if request.full_name is not None:
        app.full_name = sanitize_content(request.full_name.strip())

    if request.email is not None:
        new_email = request.email.strip().lower()
        if not new_email or "@" not in new_email:
            raise HTTPException(status_code=400, detail="Invalid email format")

        # Check duplicate
        existing = (
            db.query(Application)
            .filter(Application.email == new_email, Application.id != app_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="Email already exists for another candidate"
            )

        app.email = new_email

        # Sync with ghost user if needed
        if app.owner and not app.owner.hashed_password:
            existing_user = db.query(User).filter(User.email == new_email).first()
            if existing_user:
                app.user_id = existing_user.id
                app.owner = existing_user
            else:
                app.owner.email = new_email
                from backend.profile_helpers import get_profile as _get_profile

                _profile = _get_profile(app.owner)
                if _profile:
                    _profile.email = new_email

    if request.phone is not None:
        phone_val = request.phone.strip()
        if phone_val and not PHONE_REGEX.match(phone_val):
            raise HTTPException(
                status_code=400,
                detail="Invalid phone format. Please use E.164 format (e.g. +1234567890)",
            )
        app.phone = sanitize_content(phone_val)

    db.commit()
    logger.info(f"Updated info for app {app_id}")
    return {
        "success": True,
        "full_name": app.full_name,
        "email": app.email,
        "phone": app.phone,
    }


@router.get("/applications/{app_id}/notes")
def get_application_notes(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Get recruiter notes for an application."""
    app = get_application_for_recruiter(app_id, recruiter, db)
    return {"notes": app.recruiter_notes or ""}


@router.put("/applications/{app_id}/notes")
@retry_stale()
def update_application_notes(
    app_id: int,
    data: NotesUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Save recruiter notes and tags on a candidate application."""
    app = get_application_for_recruiter(app_id, recruiter, db)

    # Sanitize notes (max 5000 chars)
    app.recruiter_notes = (data.notes or "")[:5000]

    # Store tags as JSON in analysis_json (extend existing)
    if data.tags:
        try:
            _cv_notes = app.cv_document
            _aj = getattr(_cv_notes, "analysis_json", None) if _cv_notes else None
            analysis = (
                _aj if isinstance(_aj, dict) else (json.loads(_aj) if _aj else {})
            )
        except Exception:
            analysis = {}
        analysis["recruiter_tags"] = data.tags[:10]  # Max 10 tags
        sync_cv_document(db, app, analysis_json=analysis)

    db.commit()
    logger.info(f"Notes updated for app {app_id} by {recruiter.email}")
    return {"success": True, "notes": app.recruiter_notes}


@router.put("/applications/{app_id}/status")
@retry_stale()
async def update_application_status(
    app_id: int,
    status_update: StatusUpdate,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    if status_update.status not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid application status '{status_update.status}'.",
        )

    app = get_application_for_recruiter(app_id, recruiter, db)

    old_status = app.status
    app.status = status_update.status

    # Record stage history
    now = datetime.now(UTC).replace(tzinfo=None)

    # Close out the previous stage entry if exists
    prev_history = (
        db.query(ApplicationStageHistory)
        .filter(
            ApplicationStageHistory.application_id == app.id,
            ApplicationStageHistory.exited_at.is_(None),
        )
        .first()
    )
    if prev_history:
        prev_history.exited_at = now
        prev_history.duration_seconds = int(
            (now - prev_history.entered_at).total_seconds()
        )

    # Create new stage history entry
    stage_names = {
        "applied": "Applied",
        "screening": "Screening",
        "interviewing": "Interviewing",
        "offer": "Offer",
        "hired": "Hired",
        "rejected": "Rejected",
        "archived": "Archived",
        "invited": "Invited",
        "shortlisted": "Shortlisted",
        "pending": "Pending",
        "interview": "Interview",
        "active": "Active",
    }
    new_history = ApplicationStageHistory(
        company_id=app.company_id,
        application_id=app.id,
        stage_slug=status_update.status,
        stage_name=stage_names.get(status_update.status, status_update.status),
        entered_at=now,
        triggered_by=recruiter.id,
        trigger_type="manual",
    )
    db.add(new_history)

    db.commit()
    from backend.notifications import notify_user

    # Get candidate and job info
    candidate = app.owner
    _app_job = app.job
    job_title = (
        _app_job.title
        if _app_job
        else (getattr(app.cv_document, "declared_role", None) or "the position")
    )
    company_name = (
        get_user_company_name(_app_job.recruiter)
        if _app_job and _app_job.recruiter
        else "the company"
    )
    candidate_email = app.email or (get_user_email(candidate) if candidate else None)

    # Send in-app notification
    if candidate:
        background_tasks.add_task(
            notify_user,
            str(candidate.id),
            f"Your application for {job_title} was updated to: {app.status}",
            "success" if app.status in ["hired", "accepted"] else "info",
        )
        # Send typed notification for real-time UI updates
        from backend.realtime import manager as realtime_manager

        try:
            import asyncio

            asyncio.create_task(
                realtime_manager.send_personal_message(
                    {
                        "type": "application_status_changed",
                        "payload": {
                            "application_id": app.id,
                            "old_status": old_status,
                            "new_status": app.status,
                            "job_title": job_title,
                            "timestamp": now.isoformat(),
                        },
                    },
                    candidate.id,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to send typed status notification: {e}")

    # Evaluate automation rules in background
    from backend.automation_worker import evaluate_application_rules

    background_tasks.add_task(evaluate_application_rules, app.id, app.company_id)

    # Dispatch webhook for status change
    try:
        import asyncio

        from backend.webhook_dispatcher import dispatch_webhook

        asyncio.create_task(
            dispatch_webhook(
                "application_status_changed",
                {
                    "application_id": app.id,
                    "candidate_name": app.full_name,
                    "old_status": old_status,
                    "new_status": app.status,
                    "job_title": job_title,
                    "updated_by": recruiter.email,
                    "timestamp": now.isoformat(),
                },
                app.company_id,
            )
        )
    except Exception as e:
        logger.warning(f"Failed to dispatch status change webhook: {e}")

    # Send email notification using helper (checks recruiter settings)
    if candidate_email:
        send_status_email(
            db,
            recruiter.id,
            candidate_email,
            app.status,
            job_title,
            company_name,
            background_tasks,
        )

    return {"message": "Status updated", "new_status": app.status}


@router.post("/applications/{app_id}/override-score")
def override_skill_score(
    app_id: int,
    request: ScoreOverrideRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(app_id, recruiter, db)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Find the most recent evaluation result for this application
    eval_session = (
        db.query(EvaluationSession)
        .filter(EvaluationSession.application_id == app.id)
        .order_by(EvaluationSession.created_at.desc())
        .with_for_update()
        .first()
    )
    if not eval_session or not eval_session.evaluation_result:
        raise HTTPException(
            status_code=404, detail="No evaluation found for this application"
        )

    result = eval_session.evaluation_result

    if not (0 <= request.new_score <= 100):
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100")

    breakdown = result.score_breakdown or {}
    overrides = breakdown.get("overrides", {})

    override_entry = {
        "original_score": request.original_score,
        "new_score": request.new_score,
        "reason": request.reason,
        "overridden_at": datetime.now(UTC).isoformat(),
        "overridden_by": recruiter.id,
        "overridden_by_name": recruiter.full_name or recruiter.email,
    }
    overrides[request.skill] = override_entry
    breakdown["overrides"] = overrides
    result.score_breakdown = breakdown

    # Track override history for audit trail
    history = breakdown.get("override_history", [])
    history.append(
        {
            **override_entry,
            "skill": request.skill,
            "action": "override",
        }
    )
    breakdown["override_history"] = history
    result.score_breakdown = breakdown

    # If the override raises the score, clear needs_review if that was the reason
    if result.needs_review and request.new_score >= request.original_score:
        result.needs_review = False
        result.needs_review_reason = None

    db.commit()
    logger.info(
        f"Score override by recruiter {recruiter.id} for app {app_id}: {request.skill} {request.original_score}->{request.new_score}"
    )

    return {
        "message": "Score override saved",
        "skill": request.skill,
        "new_score": request.new_score,
    }


@router.get("/applications/{app_id}")
def get_application_details(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    app = get_application_for_recruiter(app_id, recruiter, db)
    _cv = app.cv_document
    _iv = app.evaluation_sessions[0] if app.evaluation_sessions else None
    _es_appdet = app.evaluation_sessions or []
    _er_appdet = (
        _es_appdet[0].evaluation_result
        if _es_appdet and _es_appdet[0].evaluation_result
        else None
    )
    _sc = _er_appdet
    _ev = app.evaluation_state

    _analysis_json = getattr(_cv, "analysis_json", None) or getattr(
        app, "analysis_json", None
    )
    analysis = {}
    if _analysis_json:
        try:
            analysis = (
                _analysis_json
                if isinstance(_analysis_json, dict)
                else json.loads(_analysis_json)
            )
        except Exception as e:
            logger.error(f"Error parsing analysis JSON for app {app_id}: {e}")
            analysis = {"summary": "Error parsing analysis data.", "strengths": []}
    user = db.query(User).filter(User.id == app.user_id).first()
    # Check for PRO tier (Admins bypass)
    is_pro = (
        get_user_tier(recruiter) in ("pro", "pro_plus", "enterprise")
        or recruiter.role == "admin"
    )
    if is_pro:
        full_name = app.full_name or (get_user_name(user) if user else "Unknown")
        email = app.email or (get_user_email(user) if user else "")
        phone = app.phone or (get_user_phone(user) if user else "")
        # Bug B-29: wrap cv_file_path in a 5-minute HMAC signed URL
        # so the recruiter can preview the file via the /uploads
        # route without us adding a backdoor or exposing the
        # candidate's user_id in a public URL. We only sign when
        # the recruiter has PRO access AND a candidate user is
        # resolvable (otherwise there's no subject to bind the
        # token to).
        cv_url = getattr(_cv, "cv_file_path", None) or getattr(
            app, "cv_file_path", None
        )
        cv_file_path = cv_url
        if cv_url and app.user_id:
            try:
                # ``app.cv_file_path`` is the public URL like
                # ``/uploads/upload_<user_id>_<uuid>.pdf``; the
                # signing helper only needs the basename that the
                # /uploads route will resolve.
                from urllib.parse import urlparse

                from backend.signed_url import make_signed_cv_token

                parsed = urlparse(cv_url)
                file_path = parsed.path.lstrip("/")
                if file_path.startswith("uploads/"):
                    file_path = file_path[len("uploads/") :]

                signed = make_signed_cv_token(
                    file_path=file_path,
                    subject_user_id=app.user_id,
                    bearer_user_id=recruiter.id,
                    ttl_seconds=300,
                )
                cv_url = signed["url"]
            except Exception as e:
                # If signing fails (e.g. test env without secret
                # key), fall back to the bare URL — the recruiter
                # will get 403 from /uploads, which is the safe
                # default.
                logger.error(
                    f"[SIGNED-URL] Failed to sign CV URL for app {app_id}: {e}"
                )
    else:
        real_name = app.full_name or (get_user_name(user) if user else "Unknown")
        full_name = f"{real_name.split()[0][0]}. Candidate"
        email = "hidden@candway.com"
        phone = "+216 ** *** ***"
        cv_url = None
        cv_file_path = None
    # Smart Role Determination
    role = getattr(_cv, "declared_role", None) or getattr(app, "declared_role", None)
    if not role:
        if app.job_id:
            role = db.query(Job.title).filter(Job.id == app.job_id).scalar()
        elif app.batch_id:
            role = db.query(BatchJob.title).filter(BatchJob.id == app.batch_id).scalar()

    # Load proctoring violations
    _proctoring_violations = getattr(_iv, "proctoring_violations", None)
    proctoring_violations = []
    try:
        if _proctoring_violations:
            proctoring_violations = (
                _proctoring_violations
                if isinstance(_proctoring_violations, (list, dict))
                else json.loads(_proctoring_violations)
            )
    except Exception as e:
        logger.error(f"Error parsing proctoring violations for app {app_id}: {e}")
        pass

    # Parse structured Q&A for competency data
    from backend.interview_turns import load_turns

    _interview_qa = load_turns(db, app)
    competencies = {}
    try:
        if _interview_qa:
            qa_data = (
                _interview_qa
                if isinstance(_interview_qa, (list, dict))
                else json.loads(_interview_qa)
            )
            if isinstance(qa_data, list):
                scores = [q.get("score", 0) for q in qa_data if isinstance(q, dict)]
                if scores:
                    avg = sum(scores) / len(scores)
                    competencies = {
                        "technical": min(100, avg + (10 if avg > 50 else 0)),
                        "communication": min(100, avg + (5 if avg > 50 else -5)),
                        "problem_solving": min(100, avg + (8 if avg > 50 else -2)),
                        "adaptability": min(100, avg + (3 if avg > 50 else -3)),
                        "confidence": min(100, avg + (15 if avg > 50 else -10)),
                    }
    except Exception as e:
        logger.error(f"Error parsing competencies for app {app_id}: {e}")

    _interview_log = getattr(_iv, "interview_log", None) or getattr(
        app, "interview_log", None
    )
    _interview_questions = getattr(_iv, "interview_questions", None) or getattr(
        app, "interview_questions", None
    )

    # Enrich analysis summary with AI interview evaluation summary if available
    if _sc and _sc.score_breakdown:
        try:
            bd = _sc.score_breakdown if isinstance(_sc.score_breakdown, dict) else json.loads(_sc.score_breakdown)
            if isinstance(bd, dict):
                if bd.get("summary"):
                    analysis["summary"] = bd.get("summary")
                elif app.recruiter_notes:
                    analysis["summary"] = app.recruiter_notes
        except Exception:
            pass

    # Parse behavioral signals from interview log
    behavioral_signals = {}
    avg_response_time = 2.5
    try:
        if _interview_log:
            log_data = (
                _interview_log
                if isinstance(_interview_log, (list, dict))
                else json.loads(_interview_log)
            )
            if isinstance(log_data, list) and len(log_data) > 0:
                response_times = []
                for item in log_data:
                    if isinstance(item, dict) and "timestamp" in item:
                        response_times.append(item.get("response_time", 0))
                avg_response_time = (
                    sum(response_times) / len(response_times) if response_times else 0
                )
                thinking_speed = (
                    "Fast (Tactical)"
                    if avg_response_time < 2
                    else "Moderate (Balanced)"
                    if avg_response_time < 5
                    else "Slow (Deliberate)"
                )
                behavioral_signals = {
                    "thinking_speed": thinking_speed,
                    "adaptability": "High (Dynamic)"
                    if len(log_data) > 5
                    else "Moderate",
                    "emotional_iq": "Professional",
                    "stress_response": "Stable",
                }
    except Exception as e:
        logger.error(f"Error parsing behavioral signals for app {app_id}: {e}")

    # Parse linguistic analysis from Q&A or transcript
    linguistic_analysis = {}
    try:
        if _interview_qa:
            qa_data = (
                _interview_qa
                if isinstance(_interview_qa, (list, dict))
                else json.loads(_interview_qa)
            )
            if isinstance(qa_data, list) and len(qa_data) > 0:
                total_questions = len(qa_data)
                answered_questions = sum(1 for q in qa_data if q.get("answer"))
                response_lengths = [len(str(q.get("answer", ""))) for q in qa_data]
                avg_response_length = (
                    sum(response_lengths) / len(response_lengths)
                    if response_lengths
                    else 0
                )
                scores = [q.get("score", 0) for q in qa_data if q.get("answer")]
                avg_score = sum(scores) / len(scores) if scores else 0
                clarity_score = (answered_questions / max(1, total_questions) * 5) + (
                    avg_score / 10 * 5
                )
                linguistic_analysis = {
                    "total_questions": total_questions,
                    "answered_questions": answered_questions,
                    "avg_response_length": round(avg_response_length, 1),
                    "response_latency": round(
                        avg_response_time if avg_response_time else 2.5, 1
                    ),
                    "structural_clarity": round(min(10, clarity_score), 1),
                }
    except Exception as e:
        logger.error(f"Error parsing linguistic analysis for app {app_id}: {e}")

    # Calculate trust score (single source: scoring_transparent.VIOLATION_PENALTIES)
    trust_score = 100
    if proctoring_violations:
        from backend.scoring_transparent import (
            MAX_INTEGRITY_PENALTY,
            VIOLATION_PENALTIES,
            normalize_violation_type,
        )

        total_penalty = 0
        for violation in proctoring_violations:
            if isinstance(violation, dict):
                raw_type = violation.get("type", "unknown")
                severity = violation.get("severity", "medium")
            else:
                raw_type = str(violation)
                severity = "medium"
            vtype = normalize_violation_type(raw_type)
            penalty = VIOLATION_PENALTIES.get(vtype, 5)
            if severity == "high":
                penalty *= 1.5
            elif severity == "low":
                penalty *= 0.5
            total_penalty += penalty
        total_penalty = min(total_penalty, MAX_INTEGRITY_PENALTY)
        trust_score = max(0, 100 - total_penalty)

    _interview_progress = (
        getattr(_iv, "interview_progress", None) or app.interview_progress
    )

    # Parse timeline data
    timeline_data = {}
    question_history = []
    try:
        if _interview_questions:
            questions_data = (
                _interview_questions
                if isinstance(_interview_questions, (list, dict))
                else json.loads(_interview_questions)
            )
            if isinstance(questions_data, list):
                total_q = len(questions_data)
                completed_q = sum(
                    1 for q in questions_data if q.get("status") == "completed"
                )
                for q in questions_data:
                    question_history.append(
                        {
                            "question": q.get("question", ""),
                            "score": q.get("score", 0),
                            "status": q.get("status", "upcoming"),
                        }
                    )
                timeline_data = {
                    "total_questions": total_q,
                    "completed_questions": completed_q,
                    "duration_minutes": _interview_progress or 0,
                }

        if not question_history and _interview_log:
            try:
                log_data = (
                    _interview_log
                    if isinstance(_interview_log, (list, dict))
                    else json.loads(_interview_log)
                )
                if isinstance(log_data, list):
                    total_q = 15
                    completed_q = len([m for m in log_data if m.get("role") == "user"])
                    total_q = max(total_q, completed_q)
                    timeline_data = {
                        "total_questions": total_q,
                        "completed_questions": completed_q,
                        "duration_minutes": _interview_progress or (completed_q * 1.5),
                    }
                    for item in log_data:
                        if isinstance(item, dict) and item.get("role") == "user":
                            question_history.append(
                                {
                                    "question": item.get("question", "Response Point"),
                                    "score": item.get(
                                        "score", item.get("answer_score", 0)
                                    ),
                                    "status": "completed",
                                }
                            )
            except Exception as e:
                logger.error(f"Error parsing interview_log for timeline: {e}")

        if not timeline_data and _interview_qa:
            qa_list = _interview_qa if isinstance(_interview_qa, list) else (json.loads(_interview_qa) if isinstance(_interview_qa, str) else [])
            if isinstance(qa_list, list) and len(qa_list) > 0:
                completed_q = len([q for q in qa_list if isinstance(q, dict) and q.get("answer")])
                total_q = max(len(qa_list), completed_q)
                timeline_data = {
                    "total_questions": total_q,
                    "completed_questions": completed_q,
                    "duration_minutes": _interview_progress or (completed_q * 2),
                }

        if not timeline_data:
            timeline_data = {
                "total_questions": 0,
                "completed_questions": 0,
                "duration_minutes": 0,
            }
    except Exception as e:
        logger.error(f"Error parsing timeline for app {app_id}: {e}")
        timeline_data = {
            "total_questions": 0,
            "completed_questions": 0,
            "duration_minutes": 0,
        }

    # Extract user profile fields for enriched response
    user_skills = []
    _user_skills_str = get_user_skills(user) if user else ""
    if _user_skills_str:
        try:
            user_skills = (
                json.loads(_user_skills_str)
                if isinstance(_user_skills_str, str)
                else (_user_skills_str if isinstance(_user_skills_str, list) else [])
            )
        except Exception:
            user_skills = []

    # Analysis-fallback for snapshot fields
    analysis_skills = analysis.get("skills", []) if analysis else []

    # Candidate profile + CV-builder data (the candidate edits these
    # from their own profile; the recruiter must see the same values).
    candidate_profile = getattr(user, "candidate_profile", None) if user else None
    profile_bio = (
        getattr(candidate_profile, "bio", None)
        if candidate_profile is not None
        else None
    )
    profile_languages = (
        getattr(candidate_profile, "languages", None)
        if candidate_profile is not None
        else None
    )
    profile_availability = (
        getattr(candidate_profile, "availability", None)
        if candidate_profile is not None
        else None
    )
    profile_work_preference = (
        getattr(candidate_profile, "work_preference", None)
        if candidate_profile is not None
        else None
    )
    profile_salary_min = (
        getattr(candidate_profile, "salary_expectation_min", None)
        if candidate_profile is not None
        else None
    )
    profile_salary_max = (
        getattr(candidate_profile, "salary_expectation_max", None)
        if candidate_profile is not None
        else None
    )
    profile_relocation_willing = (
        getattr(candidate_profile, "relocation_willing", None)
        if candidate_profile is not None
        else None
    )
    builder_data = {}
    if candidate_profile is not None and getattr(
        candidate_profile, "builder_data", None
    ):
        try:
            _bd = json.loads(candidate_profile.builder_data) or {}
            if isinstance(_bd, dict):
                builder_data = _bd
        except Exception as e:
            logger.error(f"Error parsing builder_data for app {app_id}: {e}")

    builder_experience = builder_data.get("experience") or []
    builder_summary = builder_data.get("summary") or ""
    builder_skills = builder_data.get("skills") or []

    # Merge profile-authored About/Experience into the analysis payload
    # so the recruiter sees what the candidate actually wrote even when
    # no AI CV analysis has run yet (analysis == {}).
    if not analysis:
        analysis = {}
    if not analysis.get("summary") and (profile_bio or builder_summary):
        analysis["summary"] = profile_bio or builder_summary
    if not analysis.get("experience") and builder_experience:
        analysis["experience"] = builder_experience
    if not analysis.get("skills") and builder_skills:
        analysis["skills"] = builder_skills

    def _extract_skill_names(items):
        names = []
        for item in items:
            if isinstance(item, dict):
                name = item.get("name") or item.get("skill")
                if name:
                    names.append(str(name))
            elif isinstance(item, str):
                names.append(item)
        return names

    combined_skills = list(
        dict.fromkeys(
            _extract_skill_names(user_skills) + _extract_skill_names(analysis_skills)
        )
    )

    _score = _sc.final_score if _sc else None
    score = _score or 0
    score_label = (
        "Exceptional"
        if score >= 85
        else "Strong"
        if score >= 70
        else "Competent"
        if score >= 55
        else "Developing"
        if score >= 40
        else "Needs Improvement"
    )
    score_breakdown = analysis.get("final_score_breakdown")

    _video_path = getattr(_iv, "video_file_path", None) or getattr(
        app, "video_file_path", None
    )

    app_dict = {
        "id": app.id,
        "job_id": app.job_id,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "photo_url": (
            getattr(
                getattr(user, "candidate_profile", None), "avatar_url", None
            )
            or getattr(getattr(app, "candidate", None), "photo_url", None)
        )
        if user
        else None,
        "role": role or "Candidate",
        "score": score,
        "score_label": score_label,
        "score_breakdown": score_breakdown,
        "cv_score": _sc.cv_score if _sc else 0,
        "status": app.status,
        # Bug U-07: structured decline metadata so the recruiter
        # detail page can render the candidate-initiated decline
        # callout. ``offer_declined`` is the status written when the
        # candidate declines an offer letter (recruiter_offers.py).
        "is_declined": (app.status in ("rejected", "offer_declined"))
        or bool(app.declined_at),
        "decline_reason": app.decline_reason
        if (app.status in ("rejected", "offer_declined") or app.declined_at)
        else None,
        "declined_at": app.declined_at.isoformat() if app.declined_at else None,
        "decline_initiated_by": app.decline_initiated_by,
        "created_at": app.created_at.strftime("%Y-%m-%d") if app.created_at else None,
        "location": getattr(getattr(user, "candidate_profile", None), "location", None)
        if user
        else None,
        "linkedin_url": getattr(
            getattr(user, "candidate_profile", None), "linkedin_url", None
        )
        if user
        else None,
        "skills": combined_skills or None,
        "years_experience": analysis.get("experience_years")
        or analysis.get("years_of_experience")
        or (len(builder_experience) if builder_experience else None),
        "cv_file_path": cv_file_path,
        "cv_url": cv_url,
        "analysis": analysis,
        "proctoring_violations": proctoring_violations,
        "interview_state": getattr(_iv, "interview_state", None) or app.interview_state,
        "interview_progress": getattr(_iv, "interview_progress", None)
        or app.interview_progress
        or 0,
        "total_questions": timeline_data.get("total_questions", 15),
        "interview_last_saved": (
            (
                getattr(_iv, "interview_last_saved", None) or app.interview_last_saved
            ).isoformat()
            if (getattr(_iv, "interview_last_saved", None) or app.interview_last_saved)
            else None
        ),
        "recruiter_notes": app.recruiter_notes or "",
        "is_locked": not is_pro,
        # Snapshot / profile enrichment — read the candidate's own
        # editable profile so the recruiter sees the same values.
        "bio": profile_bio or builder_summary or None,
        "availability": profile_availability or None,
        "salary_expectation": (
            (f"{profile_salary_min} - {profile_salary_max} TND")
            if (profile_salary_min or profile_salary_max)
            else None
        ),
        "work_type": profile_work_preference or None,
        "languages": profile_languages or app.language or "English",
        "relocation_willing": profile_relocation_willing,
        "notice_period": None,
        # Timeline approximations
        "analyzed_at": app.evaluation_completed_at.strftime("%Y-%m-%dT%H:%M:%S")
        if app.evaluation_completed_at
        else (app.created_at.strftime("%Y-%m-%dT%H:%M:%S") if app.created_at else None),
        "interview_scheduled_at": None,
        "feedback_submitted_at": None,
        "status_changed_at": app.updated_at.strftime("%Y-%m-%dT%H:%M:%S")
        if app.updated_at
        else (app.created_at.strftime("%Y-%m-%dT%H:%M:%S") if app.created_at else None),
        "offer_sent_at": None,
        # New fields for comparison page
        "trust_score": trust_score,
        "tab_switches": len(proctoring_violations) if proctoring_violations else 0,
        "identity_verified": app.user_id is not None,
        "behavioral_signals": behavioral_signals,
        "competencies": competencies,
        "linguistic_analysis": linguistic_analysis,
        "user_id": app.user_id,
        "timeline": timeline_data,
        "question_history": question_history,
        "video_url": _video_path,
        "scorecard_submissions": [
            {
                "id": s.id,
                "scorecard_name": s.scorecard.name,
                "evaluator_name": s.evaluator.name if s.evaluator else "Unknown",
                "overall_score": s.overall_score,
                "recommendation": s.recommendation,
                "notes": s.notes,
                "submitted_at": s.submitted_at.isoformat(),
                "scores": json.loads(s.scores_json) if s.scores_json else {},
            }
            for s in db.query(ScorecardSubmission)
            .options(
                joinedload(ScorecardSubmission.evaluator),
                joinedload(ScorecardSubmission.scorecard),
            )
            .filter(ScorecardSubmission.application_id == app.id)
            .order_by(ScorecardSubmission.submitted_at.desc())
            .all()
        ],
        "scorecard_avg": (
            lambda subs: (
                round(sum(s.overall_score or 0 for s in subs) / len(subs), 1)
                if subs
                else None
            )
        )(
            db.query(ScorecardSubmission)
            .filter(ScorecardSubmission.application_id == app.id)
            .all()
        ),
        "scorecard_evaluations_count": db.query(ScorecardSubmission)
        .filter(ScorecardSubmission.application_id == app.id)
        .count(),
    }
    app_dict = enrich_application_dict(app_dict, app)
    return app_dict
