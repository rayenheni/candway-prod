import csv
import io
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_db, require_recruiter
from backend.eeo_analytics_service import EEOAnalyticsService
from backend.logger import logger
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter/eeo", tags=["Recruiter EEO"])


def _parse_filters(
    job_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    filters = {}
    if job_id:
        filters["job_id"] = job_id
    if date_from:
        try:
            filters["date_from"] = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date_from format (use YYYY-MM-DD)"
            )
    if date_to:
        try:
            filters["date_to"] = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date_to format (use YYYY-MM-DD)"
            )
    return filters


@router.get("/dashboard")
async def get_eeo_dashboard(
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        stats = EEOAnalyticsService.get_aggregate_stats(company_id=company_id, db=db)
        compliance = EEOAnalyticsService.get_compliance_summary(
            company_id=company_id, db=db
        )
        trends = EEOAnalyticsService.get_diversity_trends(
            company_id=company_id, months=12, db=db
        )
        return {
            "success": True,
            "stats": stats,
            "compliance": compliance,
            "trends": trends,
        }
    except Exception as e:
        logger.error(f"Failed to get EEO dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to load EEO dashboard")


@router.get("/pipeline-diversity")
async def get_pipeline_diversity(
    group_by: str = Query("gender", pattern="^(gender|race|veteran|disability)$"),
    job_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        filters = _parse_filters(job_id, date_from, date_to)
        data = EEOAnalyticsService.get_pipeline_diversity(
            company_id=company_id, filters=filters, group_by=group_by, db=db
        )
        return {"success": True, "diversity": data}
    except Exception as e:
        logger.error(f"Failed to get pipeline diversity: {e}")
        raise HTTPException(status_code=500, detail="Failed to load pipeline diversity")


@router.get("/selection-rates")
async def get_selection_rates(
    group_by: str = Query("gender", pattern="^(gender|race|veteran|disability)$"),
    job_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        filters = _parse_filters(job_id, date_from, date_to)
        data = EEOAnalyticsService.get_selection_rates(
            company_id=company_id, filters=filters, group_by=group_by, db=db
        )
        return {"success": True, "selection_rates": data}
    except Exception as e:
        logger.error(f"Failed to get selection rates: {e}")
        raise HTTPException(status_code=500, detail="Failed to load selection rates")


@router.get("/trends")
async def get_diversity_trends(
    group_by: str = Query("gender", pattern="^(gender|race|veteran|disability)$"),
    months: int = Query(12, ge=1, le=60),
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        data = EEOAnalyticsService.get_diversity_trends(
            company_id=company_id, months=months, db=db
        )
        return {"success": True, "trends": data}
    except Exception as e:
        logger.error(f"Failed to get diversity trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to load diversity trends")


@router.get("/eeo1-report")
async def get_eeo1_report(
    year: int = Query(default=datetime.now(UTC).year, ge=2020, le=2100),
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        data = EEOAnalyticsService.get_eeo1_report(
            company_id=company_id, year=year, db=db
        )
        return {"success": True, "eeo1": data}
    except Exception as e:
        logger.error(f"Failed to get EEO-1 report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate EEO-1 report")


@router.get("/compliance-summary")
async def get_compliance_summary(
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        data = EEOAnalyticsService.get_compliance_summary(company_id=company_id, db=db)
        return {"success": True, "compliance": data}
    except Exception as e:
        logger.error(f"Failed to get compliance summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to load compliance summary")


@router.get("/coverage-rate")
async def get_coverage_rate(
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        data = EEOAnalyticsService.get_coverage_rate(company_id=company_id, db=db)
        return {"success": True, "coverage": data}
    except Exception as e:
        logger.error(f"Failed to get coverage rate: {e}")
        raise HTTPException(status_code=500, detail="Failed to load coverage rate")


@router.get("/coverage-detail")
async def get_coverage_detail(
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        data = EEOAnalyticsService.get_coverage_detail(company_id=company_id, db=db)
        return {"success": True, "coverage": data}
    except Exception as e:
        logger.error(f"Failed to get coverage detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to load coverage detail")


@router.post("/export/{export_format}")
async def export_eeo_report(
    export_format: str,
    group_by: str = Query("gender", pattern="^(gender|race|veteran|disability)$"),
    year: int = Query(default=datetime.now(UTC).year),
    user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    try:
        if export_format == "csv":
            diversity = EEOAnalyticsService.get_pipeline_diversity(
                company_id=company_id, filters={}, group_by=group_by, db=db
            )
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(["Pipeline Stage"] + diversity["groups"])
            for stage in diversity["stages"]:
                row = [stage] + [
                    diversity["data"].get(stage, [0])[i]
                    if i < len(diversity["data"].get(stage, []))
                    else 0
                    for i in range(len(diversity["groups"]))
                ]
                writer.writerow(row)

            writer.writerow([])
            writer.writerow(["EEO-1 Report", str(year)])
            eeo1 = EEOAnalyticsService.get_eeo1_report(
                company_id=company_id, year=year, db=db
            )
            writer.writerow(["Job Category", "Total"])
            for cat in eeo1.get("job_categories", []):
                writer.writerow([cat, eeo1["matrix"].get(cat, {}).get("total", 0)])

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=eeo_report_{year}.csv"
                },
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export EEO report: {e}")
        raise HTTPException(status_code=500, detail="Failed to export EEO report")
