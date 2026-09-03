"""Organization portal analytics — company-wide view over all recruiters.

Reuses `MetricsRepository` (which already accepts `recruiter_id` for
tenant-scoped per-recruiter KPIs) and adds AI usage/cost aggregation from
the `usage_events` metering stream. Every query is filtered by
`company_id` — tenant isolation is mandatory.
"""

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    CompanyMember,
    CreditTransaction,
    Job,
    UsageEvent,
)
from backend.profile_helpers import get_user_email, get_user_name
from backend.repository.metrics_repository import MetricsRepository


def _company_members(db: Session, company_id: int) -> list[CompanyMember]:
    return (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .order_by(CompanyMember.id)
        .all()
    )


def _ai_usage(db: Session, company_id: int, user_ids: list[int]) -> dict:
    """Aggregate usage_events → {user_id: {calls, cost_usd, credits}}."""
    if not user_ids:
        return {}
    rows = (
        db.query(
            UsageEvent.user_id,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.cost_usd), 0),
            func.coalesce(func.sum(UsageEvent.credits), 0),
        )
        .filter(UsageEvent.company_id == company_id, UsageEvent.user_id.in_(user_ids))
        .group_by(UsageEvent.user_id)
        .all()
    )
    return {
        r[0]: {"calls": int(r[1]), "cost_usd": float(r[2]), "credits": int(r[3])}
        for r in rows
    }


def get_recruiter_kpis(db: Session, company_id: int, recruiter_id: int) -> dict:
    """Per-recruiter KPIs for one active member."""
    repo = MetricsRepository(db)
    metrics = repo.get_dashboard_metrics(company_id, recruiter_id)
    funnel = repo.get_funnel(company_id, recruiter_id)
    interviews = repo.get_interview_metrics(company_id, recruiter_id)
    ai = _ai_usage(db, company_id, [recruiter_id]).get(recruiter_id, {})
    active_jobs = (
        db.query(func.count(Job.id))
        .filter(
            Job.company_id == company_id,
            Job.recruiter_id == recruiter_id,
            Job.is_active,
            Job.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    return {
        "active_jobs": active_jobs,
        "total_applications": metrics.total_applications,
        "total_candidates": metrics.total_candidates,
        "hired": metrics.hired,
        "avg_score": metrics.avg_score or 0,
        "funnel": {
            "applied": funnel.applied,
            "screening": funnel.screening,
            "interview": funnel.interview,
            "offer": funnel.offer,
            "hired": funnel.hired,
        },
        "interviews": {
            "total": interviews.total,
            "scheduled": interviews.scheduled,
            "completed": interviews.completed,
        },
        "ai": {
            "calls": ai.get("calls", 0),
            "cost_usd": round(ai.get("cost_usd", 0), 4),
            "credits": ai.get("credits", 0),
        },
    }


def get_company_overview(db: Session, company_id: int) -> dict:
    """Company-level aggregates across all active members."""
    members = _company_members(db, company_id)
    recruiter_ids = [m.user_id for m in members]
    repo = MetricsRepository(db)

    total_jobs = (
        db.query(func.count(Job.id))
        .filter(Job.company_id == company_id, Job.is_active)
        .scalar()
        or 0
    )
    total_apps = repo.get_total_applications(company_id)
    funnel = repo.get_funnel(company_id)
    interviews = repo.get_interview_metrics(company_id)
    avg_score = repo.get_avg_score(company_id) or 0
    ai = _ai_usage(db, company_id, recruiter_ids)

    per_recruiter = []
    for m in members:
        user = m.user
        k = get_recruiter_kpis(db, company_id, m.user_id)
        per_recruiter.append(
            {
                "user_id": m.user_id,
                "name": get_user_name(user),
                "email": get_user_email(user),
                "role": m.role,
                **k,
            }
        )
    per_recruiter.sort(key=lambda r: -r["total_applications"])

    return {
        "company_id": company_id,
        "recruiters": len(recruiter_ids),
        "total_jobs": total_jobs,
        "total_applications": total_apps,
        "total_candidates": repo.get_total_candidates(company_id),
        "hired": funnel.hired,
        "avg_score": round(avg_score, 1) if avg_score else 0,
        "funnel": {
            "applied": funnel.applied,
            "screening": funnel.screening,
            "interview": funnel.interview,
            "offer": funnel.offer,
            "hired": funnel.hired,
        },
        "interviews": {
            "total": interviews.total,
            "scheduled": interviews.scheduled,
            "completed": interviews.completed,
        },
        "ai": {
            "calls": sum(a.get("calls", 0) for a in ai.values()),
            "cost_usd": round(sum(a.get("cost_usd", 0) for a in ai.values()), 4),
            "credits": sum(a.get("credits", 0) for a in ai.values()),
        },
        "recruiter_kpis": per_recruiter,
    }


def get_recruiter_detail(db: Session, company_id: int, recruiter_id: int) -> dict:
    """Deep analytics for a single recruiter."""
    repo = MetricsRepository(db)
    kpis = get_recruiter_kpis(db, company_id, recruiter_id)
    daily_trend = repo.get_daily_trend(company_id, days=7, recruiter_id=recruiter_id)
    score_dist = repo.get_score_distribution(company_id, recruiter_id)

    job_rows = (
        db.query(
            Job.id,
            Job.title,
            Job.is_active,
            func.count(Application.id).label("applicant_count"),
            func.coalesce(
                func.sum(case((Application.status == "hired", 1), else_=0)), 0
            ).label("hired_count"),
        )
        .outerjoin(Application, Application.job_id == Job.id)
        .filter(
            Job.company_id == company_id,
            Job.recruiter_id == recruiter_id,
            Job.deleted_at.is_(None),
        )
        .group_by(Job.id)
        .all()
    )
    jobs = [
        {
            "id": r.id,
            "title": r.title,
            "is_active": bool(r.is_active),
            "applicant_count": int(r.applicant_count),
            "hired_count": int(r.hired_count),
        }
        for r in job_rows
    ]

    recent = repo.get_recent_applications(
        company_id, recruiter_id=recruiter_id, limit=10
    )
    return {
        "user_id": recruiter_id,
        "kpis": kpis,
        "trends": [{"date": p["date"], "count": p["count"]} for p in daily_trend],
        "score_distribution": score_dist,
        "jobs": jobs,
        "recent_applications": recent,
    }


def get_credit_economy(db: Session, company_id: int) -> dict:
    """Credit grants vs consumption across the company's recruiters."""
    members = _company_members(db, company_id)
    user_ids = [m.user_id for m in members]
    rows = (
        db.query(
            CreditTransaction.type,
            func.coalesce(func.sum(CreditTransaction.amount), 0),
        )
        .filter(CreditTransaction.user_id.in_(user_ids))
        .group_by(CreditTransaction.type)
        .all()
    )
    by_type = {r[0]: int(r[1]) for r in rows}
    return {
        "granted": by_type.get("grant", 0) + by_type.get("promo", 0),
        "purchased": by_type.get("purchase", 0) + by_type.get("topup", 0),
        "consumed": by_type.get("consume", 0),
        "refunded": by_type.get("refund", 0) + by_type.get("rollback", 0),
    }
