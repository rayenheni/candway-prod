import asyncio
import csv
import html
import io
import json
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, selectinload, undefer

from backend.authz import get_application_for_recruiter, get_batch_for_recruiter
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.models.core.batch_job import batch_counters
from backend.profile_helpers import get_user_name

from . import router

from math import ceil


class CampaignCandidate(BaseModel):
    id: int
    full_name: str
    email: str
    status: str
    source: Optional[str] = None
    is_registered: bool = False
    cv_score: Optional[float]
    interview_score: Optional[float]
    delta: Optional[float]
    opened_at: Optional[str] = None
    clicked_at: Optional[str] = None
    interview_state: Optional[str] = None
    interview_progress: Optional[int] = None
    phone: Optional[str] = None
    rubric_match: Optional[dict] = None
    can_invite: bool = False
    recommendation: Optional[str] = None
    cv_rubric_weighted: Optional[bool] = None
    cv_scoring_method: Optional[str] = None
    cv_coverage_pct: Optional[float] = None
    cv_skill_breakdown: Optional[list] = None
    cv_evidence: Optional[list] = None
    cv_missing_skills: Optional[list] = None
    model_config = ConfigDict(from_attributes=True)


class CandidateEmailUpdate(BaseModel):
    email: str


class BulkInviteRequest(BaseModel):
    app_ids: List[int]
    custom_message: Optional[str] = None


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class PaginatedCampaignCandidates(BaseModel):

    items: List[CampaignCandidate]
    total: int
    page: int
    page_size: int
    total_pages: int
    model_config = ConfigDict(from_attributes=True)


@router.get("/{batch_id}/candidates", response_model=PaginatedCampaignCandidates)
def get_campaign_candidates(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("cv_score"),
    sort_dir: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    _batch = get_batch_for_recruiter(batch_id, recruiter, db)

    company_id = getattr(recruiter, "_company_id", None)

    if page_size > 200:
        page_size = 200

    query = db.query(Application).filter(
        Application.batch_id == batch_id,
        Application.company_id == company_id,
        Application.deleted_at.is_(None),
    )

    if status and status.strip() and status.strip().lower() != "all":
        query = query.filter(Application.status == status.strip())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(Application.full_name.ilike(term), Application.email.ilike(term))
        )

    total = query.count()

    is_desc = (sort_dir or "desc").lower() == "desc"

    if sort_by == "cv_score":
        # Canonical CV score: EvaluationResult.cv_score.
        # Application.analysis_score is legacy and must not be used for sorting.
        latest_session_id = (
            db.query(func.max(EvaluationSession.id))
            .filter(EvaluationSession.application_id == Application.id)
            .correlate(Application)
            .scalar_subquery()
        )

        query = query.outerjoin(
            EvaluationResult,
            EvaluationResult.evaluation_session_id == latest_session_id,
        )

        score_col = func.coalesce(
            EvaluationResult.cv_score,
            -1.0 if is_desc else 9999.0,
        )
        order_clause = desc(score_col) if is_desc else asc(score_col)

        query = query.order_by(
            order_clause,
            desc(Application.id) if is_desc else asc(Application.id),
        )
    elif sort_by == "created_at":
        order_clause = (
            desc(Application.created_at) if is_desc else asc(Application.created_at)
        )
        query = query.order_by(
            order_clause, desc(Application.id) if is_desc else asc(Application.id)
        )
    elif sort_by == "status":
        order_clause = desc(Application.status) if is_desc else asc(Application.status)
        query = query.order_by(
            order_clause, desc(Application.id) if is_desc else asc(Application.id)
        )
    elif sort_by == "full_name":
        name_col = func.coalesce(Application.full_name, "")
        order_clause = desc(name_col) if is_desc else asc(name_col)
        query = query.order_by(
            order_clause, desc(Application.id) if is_desc else asc(Application.id)
        )
    elif sort_by == "email":
        order_clause = desc(Application.email) if is_desc else asc(Application.email)
        query = query.order_by(
            order_clause, desc(Application.id) if is_desc else asc(Application.id)
        )
    else:
        query = query.order_by(desc(Application.created_at), desc(Application.id))

    offset = (page - 1) * page_size
    apps = (
        query.options(
            undefer(Application.recruiter_notes),
            selectinload(Application.evaluation_sessions).selectinload(
                EvaluationSession.evaluation_result
            ),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    result = []
    for app in apps:
        user_name = app.full_name
        if not user_name:
            try:
                user_name = get_user_name(app.owner) if app.owner else "Unknown"
            except Exception as e:
                logger.error(f"Error fetching candidate name: {e}")
                user_name = "Unknown"

        score_entity = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        interview_entity = (
            app.evaluation_sessions[0] if app.evaluation_sessions else None
        )

        interview_state = (
            (interview_entity.interview_state or "not_started")
            if interview_entity
            else "not_started"
        )
        is_interview_done = interview_state in ["completed", "flagged"]
        interview_progress = (
            interview_entity.interview_progress if interview_entity else 0
        )
        cv_score = (
            score_entity.cv_score
            if (score_entity and score_entity.cv_score is not None)
            else app.analysis_score
        )
        interview_score_val = (
            score_entity.final_score
            if (
                score_entity
                and score_entity.final_score
                and score_entity.final_score > 0
                and is_interview_done
            )
            else 0
        )

        delta = 0
        if interview_score_val > 0 and cv_score:
            delta = interview_score_val - cv_score

        # Always initialize analysis so candidates without CV analysis
        # do not raise UnboundLocalError below.
        analysis = {}
        rubric_match = None
        _cv_doc = app.cv_document
        _analysis_raw = getattr(_cv_doc, "analysis_json", None) or getattr(
            app, "analysis_json", None
        )
        if _analysis_raw:
            try:
                analysis = (
                    _analysis_raw
                    if isinstance(_analysis_raw, dict)
                    else json.loads(_analysis_raw)
                )
                rubric_match = analysis.get("rubric_match")
            except Exception:
                analysis = {}
                rubric_match = None

        # CV rubric-weighted breakdown (P1). Mirrors the /scores endpoint —
        # read from the CV document's analysis_json (durable) so recruiters
        # see why the CV scored as it did.
        _cv_bd = analysis if isinstance(analysis, dict) else {}
        _cv_weighted_flag = _cv_bd.get("cv_rubric_weighted")
        cv_rubric_weighted = (
            bool(_cv_weighted_flag) if _cv_weighted_flag is not None else None
        )
        cv_skill_breakdown = [
            {
                "name": name,
                "score": round(float(details.get("score", 0) or 0), 1)
                if isinstance(details, dict)
                else 0,
                "weight": details.get("weight") if isinstance(details, dict) else None,
                "normalized_weight": (
                    details.get("normalized_weight")
                    if isinstance(details, dict)
                    else None
                ),
                "level": details.get("level") if isinstance(details, dict) else None,
                "feedback": (
                    details.get("feedback") if isinstance(details, dict) else None
                ),
                "category": (
                    details.get("category") if isinstance(details, dict) else None
                ),
            }
            for name, details in (_cv_bd.get("skill_scores") or {}).items()
        ]
        cv_missing_skills = _cv_bd.get("missing_skills") or []

        result.append(
            {
                "id": app.id,
                "full_name": user_name,
                "email": app.email,
                "status": app.status,
                "is_registered": bool(
                    app.owner
                    and app.owner.hashed_password
                    and not app.owner.temp_password
                ),
                "cv_score": cv_score,
                "interview_score": interview_score_val,
                "delta": delta,
                "opened_at": app.opened_at.isoformat() if app.opened_at else None,
                "clicked_at": app.clicked_at.isoformat() if app.clicked_at else None,
                "interview_state": interview_state,
                "interview_progress": interview_progress,
                "phone": app.phone,
                "rubric_match": rubric_match,
                "can_invite": bool(
                    app.email and not app.email.endswith("@import.local")
                ),
                "recommendation": (
                    score_entity.verdict if score_entity else None
                ),
                "cv_rubric_weighted": cv_rubric_weighted,
                "cv_scoring_method": _cv_bd.get("scoring_method"),
                "cv_coverage_pct": _cv_bd.get("coverage_pct"),
                "cv_skill_breakdown": cv_skill_breakdown,
                "cv_evidence": [
                    {
                        "skill_name": row.get("criterion_name"),
                        "score": row.get("score"),
                        "weight": row.get("weight"),
                        "feedback": row.get("feedback"),
                    }
                    for row in (_cv_bd.get("detail_rows") or [])
                ]
                or cv_skill_breakdown,
                "cv_missing_skills": cv_missing_skills,
            }
        )

    total_pages = ceil(total / page_size) if total > 0 else 1
    return {
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.patch("/{batch_id}/candidates/{app_id}/email")
def update_candidate_email(
    batch_id: int,
    app_id: int,
    data: CandidateEmailUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    _batch = get_batch_for_recruiter(batch_id, recruiter, db)

    app = get_application_for_recruiter(app_id, recruiter, db)
    if app.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="Candidate not found")

    new_email = (data.email or "").strip()
    if "@" not in new_email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    app.email = new_email
    db.commit()
    return {"success": True, "email": new_email}


@router.post("/{batch_id}/candidates/{app_id}/invite")
async def invite_candidate(
    batch_id: int,
    app_id: int,
    request: Request,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    commit: bool = True,
):
    from backend.config import get_settings
    from backend.dependencies import generate_interview_token
    from backend.email_service import email_service
    from backend.notifications import notify_user
    from backend.utils.account_service import ensure_candidate_account

    settings = get_settings()

    batch = get_batch_for_recruiter(batch_id, recruiter, db)

    app = get_application_for_recruiter(app_id, recruiter, db)
    if app.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if app.email and app.email.endswith("@import.local"):
        raise HTTPException(
            status_code=400,
            detail="Cannot invite candidate with placeholder email. Please update their email first.",
        )

    token_data = generate_interview_token(app_id)
    token = token_data["token"]
    access_url = f"{settings.frontend_url}/auth/interview-access?app_id={app_id}&token={token}"

    candidate_user, plain_password = ensure_candidate_account(
        db, app.email, app.full_name or "Candidate"
    )

    if not app.user_id and candidate_user:
        # Do not commit here.
        # The bulk invite flow has already reserved the interview quota
        # in this transaction. Commit everything only after the email
        # has been sent successfully below.
        app.user_id = candidate_user.id

    candidate_name = get_user_name(candidate_user)
    if candidate_name.startswith("Name: "):
        candidate_name = candidate_name[6:].strip()

    recruiter_name = get_user_name(recruiter) or "The Recruiting Team"
    # plain_password is None only when the candidate already had a real
    # account; otherwise ensure_candidate_account created/reclaimed one and
    # returned the generated temporary password.
    is_registered = plain_password is None
    password_block = ""
    if plain_password:
        password_block = f"""
            <div style="margin:0 0 24px;padding:16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">
                <p style="margin:0 0 8px;font-size:13px;color:#64748b;font-weight:600;">YOUR LOGIN DETAILS</p>
                <p style="margin:0 0 4px;font-size:14px;color:#1e293b;">Email: <strong>{html.escape(app.email)}</strong></p>
                <p style="margin:0;font-size:14px;color:#1e293b;">Temporary password: <strong>{html.escape(plain_password)}</strong></p>
                <p style="margin:8px 0 0;font-size:12px;color:#94a3b8;">Use these to sign in afterwards and view your interview results. You can change your password once signed in.</p>
            </div>
        """
    subject = f"🚀 Invitation to AI Interview: {batch.title}"

    if plain_password:
        account_text = (
            "Click the button below to start your interview. Your login details are shown below, "
            "so you can sign in afterwards and view your interview results."
        )
    else:
        account_text = (
            "Click the button below to start your interview. An account already exists for this email — "
            "sign in with your existing password afterwards to view your interview results."
        )

    email_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
        <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:36px 32px;text-align:center">
            <h1 style="color:#fff;margin:0;font-size:26px;font-weight:800;letter-spacing:-0.5px">AI Interview Invitation</h1>
            <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:15px">Powered by Candway Intelligence</p>
        </div>
        <div style="padding:36px 32px">
            <p style="font-size:16px;color:#1e293b;margin:0 0 12px">Dear <strong>{candidate_name}</strong>,</p>
            <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px">
                We have reviewed your profile and are pleased to invite you to an AI-powered interview for the
                <strong>{batch.target_role or batch.title}</strong> position.
            </p>

            <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px">
                {account_text}
            </p>

            {password_block}

            <div style="text-align:center;margin:32px 0">
                <a href="{access_url}"
                   style="background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;padding:16px 40px;
                          text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;
                          display:inline-block;box-shadow:0 8px 24px rgba(79,70,229,0.35)">
                    Start Your AI Interview →
                </a>
            </div>
            <hr style="border:0;border-top:1px solid #f1f5f9;margin:32px 0">
            <p style="font-size:13px;color:#94a3b8;margin:0">
                Best regards,<br><strong style="color:#475569">{recruiter_name}</strong> via Candway Platform
            </p>
        </div>
    </div>
    """

    try:
        from backend.database import EvaluationSession

        existing_session = (
            db.query(EvaluationSession)
            .filter(EvaluationSession.application_id == app.id)
            .first()
        )
        if not existing_session:
            session = EvaluationSession(
                application_id=app.id,
                company_id=app.company_id,
                rubric_id=app.rubric_id or batch.rubric_id,
                status="pending",
                interview_state="not_started",
            )
            db.add(session)

        email_service.send_email(app.email, subject, email_body)
        app.status = "invited"
        app.invited_at = _utcnow()
        if commit:
            db.commit()

        try:
            await notify_user(
                str(recruiter.id),
                f"Invitation sent to {candidate_name}",
                title="Invite Sent",
                level="info",
                body=f"Subject: {subject}\n\nCandidate: {candidate_name} ({app.email})\nCampaign: {batch.title}",
            )
        except Exception as ne:
            logger.error(f"Failed to notify recruiter: {ne}")

        logger.info(f"Invite sent to {app.email} for app {app_id}")
        return {
            "success": True,
            "message": f"Invitation sent to {app.email}",
            "candidate_registered": is_registered,
        }
    except Exception as e:
        logger.error(f"Failed to send invite email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


@router.post("/{batch_id}/invite-all")
async def invite_all_candidates(
    batch_id: int,
    req: BulkInviteRequest,
    request: Request,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Bulk candidate invitation.

    Important:
    - Email delivery is an external side effect and cannot be rolled back.
    - Therefore each candidate is processed independently.
    - Quota is consumed only after a successful invitation.
    - A failed invitation does not abort successful invitations.
    """
    from backend.subscription_service import SubscriptionService

    batch = get_batch_for_recruiter(batch_id, recruiter, db)

    # De-duplicate while preserving the frontend's order.
    app_ids = list(dict.fromkeys(req.app_ids))

    if not app_ids:
        return {
            "success": True,
            "sent": 0,
            "failed": [],
            "total_attempted": 0,
            "success_rate": "100.0%",
            "remaining_quota": None,
            "message": "No candidates selected.",
        }

    plan = SubscriptionService.get_user_plan(recruiter, db)
    if not plan:
        raise HTTPException(
            status_code=403,
            detail="No active subscription plan.",
        )

    recruiter_usage = (
        getattr(
            getattr(recruiter, "recruiter_profile", None),
            "usage_ai_interviews",
            0,
        )
        or 0
    )

    plan_limit = plan.ai_interview_limit or 0

    if plan_limit == -1:
        available_quota = len(app_ids)
    else:
        available_quota = max(0, plan_limit - recruiter_usage)

    if available_quota <= 0:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Interview quota exhausted. Your plan allows "
                f"{plan_limit} invites. Current usage: {recruiter_usage}"
            ),
        )

    # Never attempt more candidates than the available quota.
    candidates_to_process = app_ids[:available_quota]

    sent = 0
    failed = []

    for idx, app_id in enumerate(candidates_to_process):
        if idx > 0:
            await asyncio.sleep(0.5)

        try:
            app = get_application_for_recruiter(app_id, recruiter, db)

            if app.batch_id != batch_id:
                failed.append({
                    "app_id": app_id,
                    "error": "Candidate not found in this campaign",
                })
                continue

            if app.email and app.email.endswith("@import.local"):
                failed.append({
                    "app_id": app_id,
                    "error": "Candidate has a placeholder email",
                })
                continue

            # Consume quota BEFORE sending the email.
            #
            # If the email fails, we immediately compensate the quota.
            if not SubscriptionService.record_usage(
                recruiter,
                "conduct_interview",
                db,
                commit=False,
            ):
                failed.append({
                    "app_id": app_id,
                    "error": "Interview quota reached",
                })
                continue

            try:
                await invite_candidate(
                    batch_id,
                    app_id,
                    request,
                    recruiter,
                    db,
                    commit=True,
                )
            except Exception as email_error:
                # The invitation did not complete successfully.
                # Compensate the quota consumed above.
                try:
                    SubscriptionService.decrement_usage(
                        recruiter,
                        "conduct_interview",
                        db,
                    )
                except Exception as compensation_error:
                    logger.error(
                        "Failed to compensate interview quota for app %s: %s",
                        app_id,
                        compensation_error,
                    )

                failed.append({
                    "app_id": app_id,
                    "error": str(email_error),
                })
                continue

            sent += 1

        except HTTPException as exc:
            failed.append({
                "app_id": app_id,
                "error": exc.detail,
            })
            db.rollback()
            continue

        except Exception as exc:
            db.rollback()
            logger.error(
                "Bulk invite failed for app %s: %s",
                app_id,
                exc,
                exc_info=True,
            )
            failed.append({
                "app_id": app_id,
                "error": "Unexpected error while inviting candidate",
            })
            continue

    # Calculate remaining quota from the database rather than from the
    # initial snapshot. This keeps the response accurate.
    try:
        db.refresh(recruiter)
    except Exception:
        pass

    current_usage = (
        getattr(
            getattr(recruiter, "recruiter_profile", None),
            "usage_ai_interviews",
            0,
        )
        or 0
    )

    if plan_limit == -1:
        remaining_quota = -1
    else:
        remaining_quota = max(0, plan_limit - current_usage)

    total_attempted = len(candidates_to_process)
    success_rate = (
        f"{(sent / total_attempted * 100):.1f}%"
        if total_attempted
        else "100.0%"
    )

    if len(app_ids) > len(candidates_to_process):
        failed.extend(
            {
                "app_id": app_id,
                "error": "Skipped because interview quota was exhausted",
            }
            for app_id in app_ids[len(candidates_to_process):]
        )

    return {
        "success": sent > 0 or not failed,
        "sent": sent,
        "failed": failed,
        "total_attempted": len(app_ids),
        "processed": total_attempted,
        "success_rate": success_rate,
        "remaining_quota": remaining_quota,
        "message": (
            f"Successfully invited {sent} candidate(s)."
            if not failed
            else (
                f"Successfully invited {sent} of {len(app_ids)} "
                "candidate(s)."
            )
        ),
    }
