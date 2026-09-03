"""Recruiter Dashboard — thin wrappers over MetricsRepository.

No inline metric computation. No SQL aggregation in this file.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import Announcement, User
from backend.dependencies import get_current_user, get_db, require_recruiter
from backend.repository.metrics_repository import MetricsRepository
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter", tags=["Recruiter Dashboard"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


@router.get("/stats")
@router.get("/dashboard/stats")
def get_recruiter_stats(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    repo = MetricsRepository(db)
    metrics = repo.get_dashboard_metrics(company_id, recruiter.id)
    funnel = repo.get_funnel(company_id, recruiter.id)
    avg_tth = repo.get_avg_time_to_hire(company_id, recruiter.id)
    interview_metrics = repo.get_interview_metrics(company_id, recruiter.id)
    return {
        "active_jobs_count": metrics.active_jobs,
        "total_applications": metrics.total_applications,
        "applied": funnel.applied,
        "screening_count": funnel.screening,
        "interviewing": funnel.interview,
        "offer_count": funnel.offer,
        "hired": metrics.hired,
        "scheduled_interviews": interview_metrics.scheduled,
        "total_interviews": interview_metrics.total,
        "interviews_completed_count": interview_metrics.completed,
        "ai_matches": metrics.ai_matches,
        "interviews_conducted_count": interview_metrics.completed,
        "avg_time_to_hire": f"{int(avg_tth)} Days" if avg_tth else "N/A",
    }


@router.get("/dashboard/recent")
def get_recent_activity(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    repo = MetricsRepository(db)
    return repo.get_recent_applications(company_id, recruiter.id, limit=5)


@router.get("/dashboard/recommendations")
def get_ai_recommendations(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    repo = MetricsRepository(db)
    return repo.get_top_scored_applications(
        company_id, recruiter.id, limit=3, min_score=75
    )


@router.get("/analytics-dashboard")
def get_analytics_dashboard(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    # Platform admins may view this page but have no recruiter company
    # membership. Resolve company best-effort and return empty aggregates
    # instead of a 403 so the admin dashboard renders honestly.
    from backend.tenant import _resolve_company_id

    company_id = _resolve_company_id(recruiter, db)
    if company_id is None:
        return {
            "kpi": {"time_to_hire": 0, "avg_score": 0, "hired": 0},
            "total_applications": 0,
            "total_candidates": 0,
            "funnel": {
                "applied": 0,
                "unique_candidates": 0,
                "screened": 0,
                "interview": 0,
                "offer": 0,
                "hired": 0,
                "rejected": 0,
            },
            "sources": [],
            "trends": [],
        }

    repo = MetricsRepository(db)
    metrics = repo.get_dashboard_metrics(company_id, recruiter.id)
    funnel = repo.get_funnel(company_id, recruiter.id)
    daily_trend = repo.get_daily_trend(company_id, days=7, recruiter_id=recruiter.id)

    return {
        "kpi": {
            "time_to_hire": int(metrics.avg_time_to_hire)
            if metrics.avg_time_to_hire
            else 0,
            "avg_score": int(metrics.avg_score) if metrics.avg_score else 0,
            "hired": metrics.hired,
        },
        "total_applications": metrics.total_applications,
        "total_candidates": metrics.total_candidates,
        "funnel": {
            "applied": funnel.applied,
            "unique_candidates": metrics.total_candidates,
            "screened": funnel.screening,
            "interview": funnel.interview,
            "offer": funnel.offer,
            "hired": funnel.hired,
            "rejected": funnel.rejected,
        },
        "sources": metrics.sources,
        "trends": [p["count"] for p in daily_trend],
    }


@router.get("/announcements/active")
def get_active_announcements(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    now = datetime.now(UTC)
    return (
        db.query(Announcement)
        .filter(
            Announcement.is_active,
            ((Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)),
        )
        .order_by(Announcement.created_at.desc())
        .all()
    )
