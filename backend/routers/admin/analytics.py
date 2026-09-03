import json
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.admin_analytics_service import AdminAnalyticsService
from backend.database import (
    AuditLog,
    Course,
    DailyPlatformReport,
    Enrollment,
    Rubric,
    Ticket,
    Transaction,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.routers.admin.common import check_permission

router = APIRouter(tags=["admin"])


@router.get("/stats")
def get_admin_stats(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")

    try:
        import redis as _redis

        from backend.config import get_settings

        _settings = get_settings()
        _r = _redis.Redis.from_url(_settings.redis_url)
        cached = _r.get("admin:dashboard_stats")
        if cached:
            return json.loads(cached)
    except Exception:
        logger.warning("Redis cache unavailable for reading admin:dashboard_stats")

    try:
        overview = AdminAnalyticsService.get_overview_stats(db)
        revenue = AdminAnalyticsService.get_revenue_analytics(db, months=1)

        def safe_count(q):
            try:
                return q.count()
            except Exception as e:
                logger.warning(f"Analytics count error: {e}")
                return 0

        action_items = {
            "pending_courses": safe_count(
                db.query(Course).filter(Course.status == "pending_review")
            ),
            "pending_payments": safe_count(
                db.query(Enrollment).filter(Enrollment.status == "pending_approval")
            ),
            "pending_subs": safe_count(
                db.query(Transaction.id).filter(Transaction.status == "pending")
            ),
            "open_tickets": safe_count(
                db.query(Ticket).filter(Ticket.status == "open")
            ),
        }

        ai_intel = AdminAnalyticsService.get_ai_performance(db)

        result = {
            "users": overview.get("users", {}),
            "activity": overview.get("activity", {}),
            "revenue": {
                "total": int(revenue.get("total_revenue", 0)),
                "monthly_trend": revenue.get("monthly_trend", []),
                "currency": "TND",
            },
            "action_queue": action_items,
            "ai_intelligence": ai_intel,
        }
    except Exception as e:
        logger.error(f"Dashboard stats fatal error: {e}", exc_info=True)
        result = {
            "users": {},
            "activity": {},
            "revenue": {"total": 0, "monthly_trend": [], "currency": "TND"},
            "action_queue": {
                "pending_courses": 0,
                "pending_payments": 0,
                "pending_subs": 0,
                "open_tickets": 0,
            },
            "ai_intelligence": {},
        }

    try:
        import redis as _redis

        from backend.config import get_settings

        _settings = get_settings()
        _r = _redis.Redis.from_url(_settings.redis_url)
        _r.setex("admin:dashboard_stats", 120, json.dumps(result))
    except Exception:
        logger.warning("Redis cache unavailable for writing admin:dashboard_stats")

    return result


@router.get("/activity")
def get_recent_activity(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(15).all()

    return [
        {
            "id": log.id,
            "action": log.action,
            "details": log.details,
            "user_id": log.user_id,
            "created_at": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for log in logs
    ]


@router.get("/analytics/overview")
def get_analytics_overview(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")
    return AdminAnalyticsService.get_overview_stats(db)


@router.get("/analytics/growth")
def get_analytics_growth(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_analytics")
    return AdminAnalyticsService.get_growth_data(db, days)


@router.get("/analytics/revenue")
def get_analytics_revenue(
    months: int = 6,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_analytics")
    return AdminAnalyticsService.get_revenue_analytics(db, months)


@router.get("/analytics/ai")
def get_analytics_ai(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")
    return AdminAnalyticsService.get_ai_performance(db)


@router.get("/analytics/efficiency")
def get_analytics_efficiency(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")
    return AdminAnalyticsService.get_platform_efficiency(db)


@router.get("/analytics/daily-report")
def get_daily_platform_report(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")
    today = datetime.now(UTC).date()
    report = (
        db.query(DailyPlatformReport).filter(DailyPlatformReport.date == today).first()
    )
    if not report:
        return {"message": "No report generated for today yet", "data": None}
    return json.loads(report.report_json)


@router.post("/analytics/daily-report/refresh")
async def refresh_daily_platform_report(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "view_analytics")
    report_data = await AdminAnalyticsService.generate_ai_daily_report(db)
    return report_data


@router.get("/rubrics")
def get_admin_rubrics(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    check_permission(current_user, "manage_content")
    from sqlalchemy import func

    rubrics = db.query(Rubric).order_by(Rubric.created_at.desc()).all()
    total = db.query(func.count(Rubric.id)).scalar()
    active = db.query(func.count(Rubric.id)).filter(Rubric.is_active).scalar()
    draft = db.query(func.count(Rubric.id)).filter(not Rubric.is_active).scalar()
    return {
        "rubrics": [
            {
                "id": r.id,
                "name": r.title or f"Rubric #{r.id}",
                "job_id": r.job_id,
                "version": getattr(r, "version", 1),
                "status": "active" if r.is_active else "draft",
                "skills_count": len(_rubric_criteria(r.criteria_json)),
                "applications": 0,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rubrics
        ],
        "stats": {"total": total or 0, "active": active or 0, "draft": draft or 0},
    }


def _rubric_criteria(criteria_json):
    import json as _json

    if not criteria_json:
        return []
    try:
        data = _json.loads(criteria_json)
    except (ValueError, TypeError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("criteria", "skills", "categories", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


@router.get("/rubrics/{rubric_id}")
def get_admin_rubric(
    rubric_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    r = db.query(Rubric).filter(Rubric.id == rubric_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return {
        "id": r.id,
        "name": r.title or f"Rubric #{r.id}",
        "title": r.title,
        "description": r.description,
        "job_id": r.job_id,
        "version": getattr(r, "version", 1),
        "status": "active" if r.is_active else "draft",
        "skills_count": len(_rubric_criteria(r.criteria_json)),
        "criteria_json": r.criteria_json,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class RubricCreate(BaseModel):
    title: str
    description: Optional[str] = None
    criteria_json: str
    is_active: bool = True


@router.post("/rubrics")
def create_rubric(
    rubric: RubricCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    import json as _json

    try:
        _json.loads(rubric.criteria_json)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="criteria_json must be valid JSON")

    new = Rubric(
        title=rubric.title,
        description=rubric.description,
        criteria_json=rubric.criteria_json,
        created_by=current_user.id,
        is_active=rubric.is_active,
        company_id=getattr(current_user, "company_id", None),
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return {"message": "Rubric created", "id": new.id}


@router.put("/rubrics/{rubric_id}")
def update_rubric(
    rubric_id: int,
    rubric: RubricCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    r = db.query(Rubric).filter(Rubric.id == rubric_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rubric not found")
    r.title = rubric.title
    r.description = rubric.description
    r.criteria_json = rubric.criteria_json
    r.is_active = rubric.is_active
    db.commit()
    return {"message": "Rubric updated", "id": r.id}


@router.delete("/rubrics/{rubric_id}")
def delete_rubric(
    rubric_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    r = db.query(Rubric).filter(Rubric.id == rubric_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rubric not found")
    db.delete(r)
    db.commit()
    return {"message": "Rubric deleted"}
