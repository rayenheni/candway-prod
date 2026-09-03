import html
import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.authz import get_application_for_recruiter, get_job_for_recruiter
from backend.config import get_settings
from backend.database import (
    Application,
    CompanyMember,
    Job,
    ReEngagementCampaign,
    ReEngagementCandidate,
    User,
)
from backend.dependencies import (
    get_db,
    get_pagination_meta,
    paginate,
    require_recruiter,
)
from backend.email_sequence_worker import _make_unsubscribe_token
from backend.email_service import email_service
from backend.logger import logger
from backend.notifications import notify_user
from backend.profile_helpers import get_user_company_name
from backend.reengagement_engine import ReEngagementEngine

router = APIRouter(prefix="/recruiter/reengagement", tags=["Recruiter Re-engagement"])

settings = get_settings()


class ReEngagementInviteRequest(BaseModel):
    candidate_ids: List[int]
    job_id: int
    message_template: Optional[str] = None
    preview: bool = False


class BulkInviteRequest(BaseModel):
    job_id: int


@router.post("/analyze/{job_id}")
async def analyze_job_reengagement(
    job_id: int,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)

    background_tasks.add_task(_run_analysis, job, recruiter.id)
    return {"message": "Re-engagement analysis started", "job_id": job_id}


async def _run_analysis(job: Job, recruiter_id: int):
    db_local = next(get_db())
    try:
        campaign = await ReEngagementEngine.create_campaign(job, recruiter_id, db_local)
        if campaign.matched_candidates > 0:
            try:
                await notify_user(
                    str(recruiter_id),
                    f"We found {campaign.matched_candidates} past candidates who match this job. Would you like to re-engage them?",
                    title="Re-engagement Opportunities Found",
                    level="info",
                    body=f"Job: {job.title}\nMatched Candidates: {campaign.matched_candidates}\nAverage Match Score: {campaign.avg_match_score:.1f}%",
                    notification_type="reengagement",
                    related_type="job",
                    related_id=job.id,
                    db_session=db_local,
                )
            except Exception as e:
                logger.error(f"Re-engagement notification failed: {e}")
    except Exception as e:
        logger.error(f"Analysis failed for job {job.id}: {e}")
    finally:
        db_local.close()


@router.get("/candidates/{job_id}")
def get_reengagement_candidates(
    job_id: int,
    min_score: float = Query(65.0),
    limit: int = Query(20),
    page: int = Query(1),
    sort_by: str = Query("match_score"),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    _job = get_job_for_recruiter(job_id, recruiter, db)
    company_id = getattr(recruiter, "_company_id", None)

    campaign = (
        db.query(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(
            ReEngagementCampaign.job_id == job_id,
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .order_by(ReEngagementCampaign.created_at.desc())
        .first()
    )
    if not campaign:
        return {
            "candidates": [],
            "campaign": None,
            "pagination": get_pagination_meta(0, page, limit),
        }

    query = db.query(ReEngagementCandidate).filter(
        ReEngagementCandidate.campaign_id == campaign.id,
        ReEngagementCandidate.match_score >= min_score,
    )

    if sort_by == "match_score":
        query = query.order_by(ReEngagementCandidate.match_score.desc())
    elif sort_by == "created_at":
        query = query.order_by(ReEngagementCandidate.created_at.desc())

    total = query.count()
    items = paginate(query, page, limit).all()

    candidates = []
    for rc in items:
        app = get_application_for_recruiter(rc.application_id, recruiter, db)
        reason_data = {}
        if rc.match_reason:
            try:
                reason_data = json.loads(rc.match_reason)
            except (json.JSONDecodeError, TypeError):
                reason_data = {"reason": rc.match_reason}
        candidates.append(
            {
                "id": rc.id,
                "application_id": rc.application_id,
                "candidate_name": app.full_name if app else "Unknown",
                "candidate_email": app.email if app else None,
                "declared_role": app.declared_role if app else None,
                "original_date": app.created_at if app else None,
                "match_score": rc.match_score,
                "match_reason": reason_data.get("reason", ""),
                "scoring_breakdown": reason_data.get("breakdown", {}),
                "invited_at": rc.invited_at,
                "responded_at": rc.responded_at,
                "response_status": rc.response_status,
            }
        )

    return {
        "candidates": candidates,
        "campaign": {
            "id": campaign.id,
            "status": campaign.status,
            "total_candidates": campaign.total_candidates,
            "matched_candidates": campaign.matched_candidates,
            "invited_count": campaign.invited_count,
            "response_count": campaign.response_count,
            "avg_match_score": campaign.avg_match_score,
        },
        "pagination": get_pagination_meta(total, page, limit),
    }


@router.post("/invite")
async def send_reengagement_invite(
    req: ReEngagementInviteRequest,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(req.job_id, recruiter, db)

    remaining = ReEngagementEngine.check_daily_sending_limit(recruiter.id, db)
    if len(req.candidate_ids) > remaining:
        raise HTTPException(
            status_code=429,
            detail=f"Daily sending limit reached. Only {remaining} invites remaining today.",
        )

    company_id = getattr(recruiter, "_company_id", None)
    campaign = (
        db.query(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(
            ReEngagementCampaign.job_id == req.job_id,
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .order_by(ReEngagementCampaign.created_at.desc())
        .first()
    )

    if req.preview:
        preview_candidates = []
        for cid in req.candidate_ids[:5]:
            rc = (
                db.query(ReEngagementCandidate)
                .join(ReEngagementCampaign)
                .join(
                    CompanyMember,
                    CompanyMember.user_id == ReEngagementCampaign.recruiter_id,
                )
                .filter(
                    ReEngagementCandidate.id == cid,
                    CompanyMember.company_id == company_id,
                    CompanyMember.is_active,
                )
                .first()
            )
            if not rc:
                continue
            app = get_application_for_recruiter(rc.application_id, recruiter, db)
            candidate_name = app.full_name if app else "Unknown"
            preview_candidates.append(
                {
                    "id": rc.id,
                    "candidate_name": candidate_name,
                    "match_score": rc.match_score,
                }
            )
        return {
            "preview": True,
            "candidates": preview_candidates,
            "job_title": job.title,
            "message_template": req.message_template or "",
        }

    sent = 0
    for cid in req.candidate_ids:
        rc = (
            db.query(ReEngagementCandidate)
            .join(ReEngagementCampaign)
            .join(
                CompanyMember,
                CompanyMember.user_id == ReEngagementCampaign.recruiter_id,
            )
            .filter(
                ReEngagementCandidate.id == cid,
                CompanyMember.company_id == company_id,
                CompanyMember.is_active,
            )
            .first()
        )
        if not rc or rc.invited_at:
            continue
        app = get_application_for_recruiter(rc.application_id, recruiter, db)
        if not app or not app.email:
            continue
        background_tasks.add_task(
            _send_invite, rc, app, job, recruiter, req.message_template or "", db
        )
        sent += 1

    if campaign:
        campaign.invited_count = (campaign.invited_count or 0) + sent
        campaign.status = "sending"
        db.commit()

    return {"message": f"Sent {sent} re-engagement invitations", "sent": sent}


@router.post("/bulk-invite/{job_id}")
async def bulk_invite(
    job_id: int,
    background_tasks: BackgroundTasks,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    job = get_job_for_recruiter(job_id, recruiter, db)
    company_id = getattr(recruiter, "_company_id", None)

    campaign = (
        db.query(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(
            ReEngagementCampaign.job_id == job_id,
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .order_by(ReEngagementCampaign.created_at.desc())
        .first()
    )
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail="No campaign found for this job. Run analysis first.",
        )

    remaining = ReEngagementEngine.check_daily_sending_limit(recruiter.id, db)
    candidates_to_invite = (
        db.query(ReEngagementCandidate)
        .filter(
            ReEngagementCandidate.campaign_id == campaign.id,
            ReEngagementCandidate.match_score >= 65,
            ReEngagementCandidate.invited_at.is_(None),
        )
        .limit(remaining)
        .all()
    )

    if not candidates_to_invite:
        raise HTTPException(status_code=400, detail="No candidates available to invite")

    sent = 0
    for rc in candidates_to_invite:
        app = get_application_for_recruiter(rc.application_id, recruiter, db)
        if not app or not app.email:
            continue
        background_tasks.add_task(_send_invite, rc, app, job, recruiter, "", db)
        sent += 1

    campaign.invited_count = (campaign.invited_count or 0) + sent
    if sent >= remaining:
        campaign.status = "completed"
        campaign.completed_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()

    return {
        "message": f"Sent {sent} re-engagement invitations",
        "sent": sent,
        "remaining": remaining - sent,
    }


async def _send_invite(
    rc: ReEngagementCandidate,
    app: Application,
    job: Job,
    recruiter: User,
    template: str,
    db: Session,
):
    try:
        candidate_name = app.full_name or "Candidate"
        subject = f"New Opportunity: {job.title} at {get_user_company_name(recruiter) or 'our company'}"

        if template:
            body = template.replace("{{name}}", html.escape(candidate_name)).replace(
                "{{job_title}}", html.escape(job.title)
            )
        else:
            body = await _generate_personalized_message(
                candidate_name,
                job.title,
                get_user_company_name(recruiter) or "our company",
                rc.match_score,
            )

        token = _make_unsubscribe_token(app.id)
        unsubscribe_url = f"{settings.frontend_url}/unsubscribe?token={token}"
        body_with_unsub = (
            body
            + f'<p style="font-size:12px;color:#94a3b8;"><a href="{html.escape(unsubscribe_url)}">Unsubscribe</a></p>'
        )

        email_service.send_email(app.email, subject, body_with_unsub)
        rc.invited_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        logger.info(f"Re-engagement invite sent to {app.email} for job {job.id}")
    except Exception as e:
        logger.error(f"Failed to send re-engagement invite to app {app.id}: {e}")


async def _generate_personalized_message(
    candidate_name: str, job_title: str, company: str, score: float
) -> str:
    try:
        data = await call_groq_cascade(
            [
                {
                    "role": "user",
                    "content": f"""Generate a short, professional re-engagement email body (HTML).
Candidate: {candidate_name}
Job: {job_title}
Company: {company}
Match Score: {score}/100

Return JSON with "body" containing HTML paragraph(s) explaining why we're reaching out again, expressing enthusiasm about the new role match, and inviting to apply.""",
                }
            ],
            temperature=0.3,
            max_tokens=600,
            json_mode=True,
        )
        if isinstance(data, dict) and "body" in data:
            return data["body"]
    except Exception:
        pass
    return f"""<p>Dear {html.escape(candidate_name)},</p>
<p>We have a new <strong>{html.escape(job_title)}</strong> opportunity at {html.escape(company)} that aligns well with your profile (Match Score: {score:.0f}%).</p>
<p>We would love to hear from you again. Please check out the details and apply if interested.</p>
<p>Best regards,<br>{html.escape(company)}</p>"""


@router.get("/stats")
def get_reengagement_stats(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    company_id = getattr(recruiter, "_company_id", None)
    campaigns = (
        db.query(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .all()
    )

    total_campaigns = len(campaigns)
    total_invited = sum(c.invited_count or 0 for c in campaigns)
    total_responses = sum(c.response_count or 0 for c in campaigns)

    total_candidates = (
        db.query(ReEngagementCandidate)
        .join(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .count()
    )

    avg_score = (
        db.query(func.avg(ReEngagementCandidate.match_score))
        .join(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .scalar()
    )

    recent_campaigns = (
        db.query(ReEngagementCampaign)
        .join(CompanyMember, CompanyMember.user_id == ReEngagementCampaign.recruiter_id)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active)
        .order_by(ReEngagementCampaign.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_campaigns": total_campaigns,
        "total_candidates_analyzed": total_candidates,
        "total_invited": total_invited,
        "total_responses": total_responses,
        "response_rate": round((total_responses / total_invited * 100), 1)
        if total_invited > 0
        else 0,
        "avg_match_score": round(avg_score, 1) if avg_score else 0,
        "recent_campaigns": [
            {
                "id": c.id,
                "job_id": c.job_id,
                "matched_candidates": c.matched_candidates,
                "invited_count": c.invited_count,
                "response_count": c.response_count,
                "avg_match_score": c.avg_match_score,
                "status": c.status,
                "created_at": c.created_at,
            }
            for c in recent_campaigns
        ],
    }
