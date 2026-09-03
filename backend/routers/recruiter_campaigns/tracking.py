import json
from datetime import datetime
from typing import List

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.authz import get_batch_for_recruiter
from backend.database import Application, BatchJob, CompanyMember, Job, Rubric, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.models.core.batch_job import batch_counters
from backend.repository.metrics_repository import MetricsRepository
from backend.tenant import get_current_company_id

from . import router


class EmailSequenceUpdate(BaseModel):
    enabled: bool
    days: List[int]


# Simple in-memory rate limiter for tracking endpoints
_tracking_limits: dict = {}


def _check_tracking_rate(ip: str, campaign_id: int, max_per_minute: int = 30) -> bool:
    import time

    now = time.time()
    key = f"{ip}:{campaign_id}"
    if len(_tracking_limits) > 10000:
        cutoff = now - 120
        stale = [k for k, v in _tracking_limits.items() if v and v[-1] < cutoff]
        for k in stale:
            del _tracking_limits[k]
    window = _tracking_limits.get(key, [])
    window = [t for t in window if t > now - 60]
    if len(window) >= max_per_minute:
        return False
    window.append(now)
    _tracking_limits[key] = window
    return True


@router.get("/{campaign_id}/analytics")
def get_campaign_analytics(
    campaign_id: int,
    threshold: float = Query(70.0, ge=0.0, le=100.0),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    campaign = get_batch_for_recruiter(campaign_id, recruiter, db)
    company_id = getattr(recruiter, "_company_id", None)
    apps = (
        db.query(Application)
        .filter(
            Application.batch_id == campaign_id, Application.company_id == company_id
        )
        .all()
    )

    total = len(apps)
    pending = sum(1 for a in apps if a.status == "pending")
    applied = sum(1 for a in apps if a.status == "applied")
    invited = sum(1 for a in apps if a.status == "invited")
    shortlisted = sum(1 for a in apps if a.status == "shortlisted")
    screening = sum(1 for a in apps if a.status == "screening")
    interviewing = sum(1 for a in apps if a.status == "interviewing")
    offer = sum(1 for a in apps if a.status == "offer")
    hired = sum(1 for a in apps if a.status == "hired")
    rejected = sum(1 for a in apps if a.status == "rejected")
    archived = sum(1 for a in apps if a.status == "archived")

    counters = batch_counters(db, campaign_id, qualified_threshold=threshold)
    emails_sent = counters["emails_sent"]
    emails_opened = counters["emails_opened"]
    emails_clicked = counters["emails_clicked"]
    qualified_count = counters["qualified_count"]
    avg_cv_score = counters["avg_cv_score"]

    open_rate = round((emails_opened / emails_sent * 100), 1) if emails_sent > 0 else 0
    click_rate = (
        round((emails_clicked / emails_sent * 100), 1) if emails_sent > 0 else 0
    )

    # Real response rate tracking based on invited candidates who entered interview stage or clicked link
    invited_total = invited + interviewing + offer + hired
    interviewed_total = sum(
        1 for a in apps if a.interview_log or a.status in ("interviewing", "reviewed", "offer", "hired")
    )
    if invited_total > 0:
        response_rate = round((interviewed_total / invited_total * 100), 1)
    else:
        response_rate = None

    in_pipeline = screening + interviewing + offer + hired
    screen_cumulative = in_pipeline
    interview_cumulative = interviewing + offer + hired
    offer_cumulative = offer + hired

    applied_to_screening = (
        round((screen_cumulative / total * 100), 1) if total > 0 else 0
    )
    screening_to_interview = (
        round((interview_cumulative / screen_cumulative * 100), 1)
        if screen_cumulative > 0
        else 0
    )
    interview_to_offer = (
        round((offer_cumulative / interview_cumulative * 100), 1)
        if interview_cumulative > 0
        else 0
    )
    offer_to_hired = (
        round((hired / offer_cumulative * 100), 1) if offer_cumulative > 0 else 0
    )

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.title,
        "total_candidates": total,
        "emails_sent": emails_sent,
        "emails_opened": emails_opened,
        "emails_clicked": emails_clicked,
        "responses_received": interviewed_total,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "response_rate": response_rate,
        "avg_cv_score": avg_cv_score,
        "qualified_count": qualified_count,
        "qualified_threshold": threshold,
        "pipeline": {
            "pending": pending,
            "applied": applied,
            "invited": invited,
            "shortlisted": shortlisted,
            "screening": screening,
            "interviewing": interviewing,
            "offer": offer,
            "hired": hired,
            "rejected": rejected,
            "archived": archived,
        },
        "conversion": {
            "applied_to_screening": applied_to_screening,
            "screening_to_interview": screening_to_interview,
            "interview_to_offer": interview_to_offer,
            "offer_to_hired": offer_to_hired,
        },
    }


@router.post("/{campaign_id}/track-open")
def track_email_open(
    campaign_id: int, app_id: int, request: Request, db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_tracking_rate(client_ip, campaign_id):
        logger.warning(
            f"Rate limit exceeded for track-open: {client_ip} / campaign {campaign_id}"
        )
        return {"detail": "Rate limited"}
    app = (
        db.query(Application)
        .filter(
            Application.id == app_id,
            Application.batch_id == campaign_id,
        )
        .first()
    )
    if app and not app.opened_at:
        app.opened_at = datetime.utcnow()
        db.commit()
    return {"success": True}


@router.post("/{campaign_id}/track-click")
def track_email_click(
    campaign_id: int,
    app_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_tracking_rate(client_ip, campaign_id):
        logger.warning(
            f"Rate limit exceeded for track-click: {client_ip} / campaign {campaign_id}"
        )
        return {"detail": "Rate limited"}
    app = (
        db.query(Application)
        .filter(
            Application.id == app_id,
            Application.batch_id == campaign_id,
        )
        .first()
    )
    if app and not app.clicked_at:
        app.clicked_at = datetime.utcnow()
        db.commit()
    return {"success": True}


@router.post("/{campaign_id}/email-sequence")
def update_email_sequence(
    campaign_id: int,
    data: EmailSequenceUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    campaign = get_batch_for_recruiter(campaign_id, recruiter, db)

    campaign.email_sequence_enabled = data.enabled
    campaign.email_sequence_days = json.dumps(data.days)
    db.commit()

    return {"success": True, "enabled": data.enabled, "days": data.days}


def _parse_rubric_categories(rubric) -> list:
    raw = rubric.criteria_json
    if not raw:
        return []
    if isinstance(raw, (dict, list)):
        data = raw
    else:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("criteria", "skills", "categories", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _format_rubric_summary(rubric) -> dict:
    cats = _parse_rubric_categories(rubric)
    skill_count = 0
    for cat in cats:
        skill_count += len(cat.get("skills", []) or [])
        for sub in cat.get("subcategories", []) or []:
            skill_count += len(sub.get("skills", []) or [])
    return {
        "id": rubric.id,
        "title": rubric.title,
        "category_count": len(cats),
        "skill_count": skill_count,
        "seniority": rubric.complexity or "mid",
    }


@router.get("/compare")
def compare_campaigns(
    ids: str = Query(..., description="Comma-separated campaign IDs, e.g. 1,2,3"),
    threshold: float = Query(70.0, ge=0.0, le=100.0),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Compare multiple campaigns side by side by returning analytics for each campaign ID."""
    try:
        campaign_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign IDs format. Must be comma-separated integers.")

    if not campaign_ids:
        return []

    res = []
    for cid in campaign_ids:
        try:
            analytics = get_campaign_analytics(cid, threshold=threshold, recruiter=recruiter, db=db)
            res.append(analytics)
        except Exception:
            continue

    return res


@router.get("/{batch_id}")
def get_campaign_detail(
    batch_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    campaign = get_batch_for_recruiter(batch_id, recruiter, db)
    repo = MetricsRepository(db)
    stats = repo.get_campaign_stats(batch_id, company_id)
    counters = batch_counters(db, batch_id)
    rubric = None
    if campaign.rubric_id:
        rubric = (
            db.query(Rubric)
            .filter(
                Rubric.id == campaign.rubric_id,
                (Rubric.company_id == company_id) | (Rubric.company_id.is_(None)),
            )
            .first()
        )
    return {
        "id": campaign.id,
        "title": campaign.title,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "worker_status": campaign.worker_status or "completed",
        "job_id": campaign.job_id,
        "target_role": campaign.target_role,
        "description": campaign.description,
        "language": campaign.language,
        "stats": {
            "total_candidates": stats.total_candidates,
            "avg_cv_score": stats.avg_cv_score,
            "interviewed": stats.interviewed,
            "invited": stats.invited,
            "opened": stats.opened,
        },
        "emails_sent": counters["emails_sent"],
        "emails_opened": counters["emails_opened"],
        "emails_clicked": counters["emails_clicked"],
        "total_files": counters["total_files"],
        "processed_files": counters["processed_files"],
        "failed_files": counters["failed_files"],
        "processing_status": counters["processing_status"],
        "rubric": _format_rubric_summary(rubric) if rubric else None,
    }
