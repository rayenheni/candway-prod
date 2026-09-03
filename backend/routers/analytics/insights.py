"""Analytics API Endpoints — thin wrappers over MetricsRepository.

No metric computation in this file.
"""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.repository._schemas import (
    DashboardMetrics,
    FunnelMetrics,
    InterviewMetrics,
)
from backend.repository.metrics_repository import MetricsRepository
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_analytics(
    days: Optional[int] = 30,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    try:
        repo = MetricsRepository(db)
        metrics = repo.get_dashboard_metrics(company_id, user.id)
        return {
            "success": True,
            "metrics": {
                "total_applications": metrics.total_applications,
                "total_candidates": metrics.total_candidates,
                "status_counts": metrics.status_counts,
                "hired": metrics.hired,
                "avg_score": metrics.avg_score,
                "ai_matches": metrics.ai_matches,
                "flagged": metrics.flagged,
                "avg_time_to_hire": metrics.avg_time_to_hire,
                "sources": metrics.sources,
                "active_jobs": metrics.active_jobs,
                "weekly_trend": repo.get_weekly_trend(
                    company_id, max(1, days // 7), user.id
                ),
                "daily_trend": repo.get_daily_trend(company_id, min(days, 7), user.id),
                "conversion_rates": repo.get_conversion_rates(company_id, user.id),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load analytics")


@router.get("/pipeline")
async def get_pipeline_analytics(
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Non-cumulative funnel — single canonical source."""
    try:
        repo = MetricsRepository(db)
        funnel = repo.get_funnel(company_id, user.id)
        return {
            "success": True,
            "pipeline": {
                "stages": [
                    {"name": "Applied", "count": funnel.applied},
                    {"name": "Screening", "count": funnel.screening},
                    {"name": "Interview", "count": funnel.interview},
                    {"name": "Offer", "count": funnel.offer},
                    {"name": "Hired", "count": funnel.hired},
                    {"name": "Rejected", "count": funnel.rejected},
                ],
                "total": sum(
                    [
                        funnel.applied,
                        funnel.screening,
                        funnel.interview,
                        funnel.offer,
                        funnel.hired,
                        funnel.rejected,
                    ]
                ),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get pipeline analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load pipeline analytics")


@router.get("/interviews")
async def get_interview_analytics(
    days: Optional[int] = 90,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    try:
        repo = MetricsRepository(db)
        metrics = repo.get_interview_metrics(company_id, user.id)
        weekly_trend = repo.get_interview_weekly_trend(company_id, 4, user.id)
        return {
            "success": True,
            "analytics": {
                "total": metrics.total,
                "scheduled": metrics.scheduled,
                "completed": metrics.completed,
                "cancelled": metrics.cancelled,
                "today": metrics.today,
                "no_show": metrics.no_show,
                "weekly_trend": weekly_trend,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get interview analytics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to load interview analytics"
        )


@router.get("/offers")
async def get_offer_analytics(
    days: Optional[int] = 90,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    try:
        repo = MetricsRepository(db)
        status_counts = repo.get_status_counts(company_id, user.id)
        hired = status_counts.get("hired", 0)
        offer = status_counts.get("offer", 0) + status_counts.get("offered", 0)
        return {
            "success": True,
            "analytics": {
                "total_offers": offer,
                "accepted": hired,
                "pending": offer - hired,
                "conversion_rate": round(hired / offer * 100, 1) if offer else 0,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get offer analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load offer analytics")


@router.get("/team")
async def get_team_performance(
    days: Optional[int] = 30,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Team performance — lightweight metric for now."""
    try:
        repo = MetricsRepository(db)
        status_counts = repo.get_status_counts(company_id, user.id)
        return {
            "success": True,
            "performance": {
                "total_applications": repo.get_total_applications(company_id, user.id),
                "total_candidates": repo.get_total_candidates(company_id, user.id),
                "hired": status_counts.get("hired", 0),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get team performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to load team performance")


@router.get("/export")
async def export_analytics(
    format: str = "json",
    days: Optional[int] = 30,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Export analytics — all metrics in one payload."""
    from backend.tenant import _resolve_company_id

    company_id = _resolve_company_id(user, db)
    try:
        repo = MetricsRepository(db)
        if company_id is None:
            dashboard = DashboardMetrics()
            funnel = FunnelMetrics()
            interview = InterviewMetrics()
        else:
            dashboard = repo.get_dashboard_metrics(company_id, user.id)
            funnel = repo.get_funnel(company_id, user.id)
            interview = repo.get_interview_metrics(company_id, user.id)

        export_data = {
            "generated_at": datetime.now(UTC).isoformat(),
            "period_days": days,
            "metrics": {
                "total_applications": dashboard.total_applications,
                "total_candidates": dashboard.total_candidates,
                "hired": dashboard.hired,
                "avg_score": dashboard.avg_score,
                "avg_time_to_hire": dashboard.avg_time_to_hire,
                "ai_matches": dashboard.ai_matches,
                "active_jobs": dashboard.active_jobs,
            },
            "funnel": {
                "applied": funnel.applied,
                "screening": funnel.screening,
                "interview": funnel.interview,
                "offer": funnel.offer,
                "hired": funnel.hired,
                "rejected": funnel.rejected,
            },
            "interviews": {
                "total": interview.total,
                "completed": interview.completed,
            },
        }

        if format == "json":
            return export_data
        elif format == "csv":
            import csv
            import io

            from fastapi.responses import StreamingResponse

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Metric", "Value", "Period (days)", "Generated At"])

            def _write(prefix, d):
                for k, v in d.items():
                    writer.writerow(
                        [f"{prefix} - {k}", v, days, export_data["generated_at"]]
                    )

            _write("Metrics", export_data["metrics"])
            _write("Funnel", export_data["funnel"])
            _write("Interviews", export_data["interviews"])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=analytics_export_"
                        f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
                    )
                },
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid export format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export analytics")
