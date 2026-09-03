import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import ReportSnapshot, SavedReport, User, get_db
from backend.dependencies import require_recruiter
from backend.logger import logger
from backend.report_builder import RECRUITER_METRICS, VISUALIZATION_TYPES, ReportBuilder
from backend.report_scheduler import ReportScheduler
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter/reports", tags=["Recruiter Reports"])


@router.post("/build")
async def build_report(
    config: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    try:
        result = ReportBuilder.build_report(config, current_user.id, db, company_id)
        return result
    except Exception as e:
        logger.error(f"Report build failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/save")
async def save_report(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = SavedReport(
        recruiter_id=current_user.id,
        company_id=company_id,
        name=data.get("name", "Untitled Report"),
        description=data.get("description"),
        config=json.dumps(data.get("config", {})),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "id": report.id,
        "name": report.name,
        "created_at": report.created_at.isoformat(),
    }


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    query = (
        db.query(SavedReport)
        .filter(SavedReport.company_id == company_id)
        .order_by(SavedReport.updated_at.desc())
    )
    total = query.count()
    reports = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "reports": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "config": json.loads(r.config) if isinstance(r.config, str) else r.config,
                "is_scheduled": r.is_scheduled,
                "schedule_frequency": r.schedule_frequency,
                "status": "ready" if r.last_generated_at else "draft",
                "last_generated_at": r.last_generated_at.isoformat()
                if r.last_generated_at
                else None,
                "next_scheduled_at": r.next_scheduled_at.isoformat()
                if r.next_scheduled_at
                else None,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in reports
        ],
    }


@router.get("/metrics")
async def list_metrics():
    return {
        "metrics": [
            {
                "key": k,
                "label": v,
                "type": "number"
                if k
                in (
                    "total_applications",
                    "applications_per_job",
                    "avg_time_to_hire",
                    "avg_time_to_interview",
                    "avg_cv_score",
                    "avg_interview_score",
                    "candidates_per_job",
                )
                else "rate"
                if k.endswith("_rate") or k == "offer_acceptance_rate"
                else "chart",
            }
            for k, v in RECRUITER_METRICS.items()
        ]
    }


@router.get("/visualizations")
async def list_visualizations():
    return {"visualizations": VISUALIZATION_TYPES}


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "name": report.name,
        "description": report.description,
        "config": json.loads(report.config)
        if isinstance(report.config, str)
        else report.config,
        "is_scheduled": report.is_scheduled,
        "schedule_frequency": report.schedule_frequency,
        "schedule_recipients": json.loads(report.schedule_recipients)
        if report.schedule_recipients
        else [],
        "last_generated_at": report.last_generated_at.isoformat()
        if report.last_generated_at
        else None,
        "next_scheduled_at": report.next_scheduled_at.isoformat()
        if report.next_scheduled_at
        else None,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


@router.put("/{report_id}")
async def update_report(
    report_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if "name" in data:
        report.name = data["name"]
    if "description" in data:
        report.description = data["description"]
    if "config" in data:
        report.config = json.dumps(data["config"])

    db.commit()
    db.refresh(report)
    return {"status": "ok", "id": report.id}


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(report)
    db.commit()
    return {"status": "deleted"}


@router.post("/{report_id}/generate")
async def generate_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    config = (
        json.loads(report.config) if isinstance(report.config, str) else report.config
    )
    result = ReportBuilder.build_report(config, current_user.id, db, company_id)

    snapshot = ReportSnapshot(
        report_id=report.id,
        company_id=company_id,
        report_data=json.dumps(result),
    )
    db.add(snapshot)
    report.last_generated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(snapshot)

    return {
        "snapshot_id": snapshot.id,
        "generated_at": snapshot.generated_at.isoformat(),
        "report_data": result,
    }


@router.post("/{report_id}/schedule")
async def schedule_report(
    report_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    frequency = data.get("frequency")
    if frequency not in ReportScheduler.FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency. Options: {list(ReportScheduler.FREQUENCIES.keys())}",
        )

    recipients = data.get("recipients", [])
    if not isinstance(recipients, list):
        raise HTTPException(
            status_code=400, detail="recipients must be a list of emails"
        )

    report.is_scheduled = True
    report.schedule_frequency = frequency
    report.schedule_recipients = json.dumps(recipients)
    report.next_scheduled_at = ReportScheduler.get_next_run(frequency)
    db.commit()
    db.refresh(report)

    return {
        "status": "scheduled",
        "frequency": frequency,
        "next_run": report.next_scheduled_at.isoformat()
        if report.next_scheduled_at
        else None,
    }


@router.delete("/{report_id}/schedule")
async def remove_schedule(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.is_scheduled = False
    report.schedule_frequency = None
    report.schedule_recipients = None
    report.next_scheduled_at = None
    db.commit()

    return {"status": "schedule_removed"}


@router.get("/{report_id}/snapshots")
async def list_snapshots(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    snapshots = (
        db.query(ReportSnapshot)
        .filter(ReportSnapshot.report_id == report_id)
        .order_by(ReportSnapshot.generated_at.desc())
        .limit(50)
        .all()
    )
    return {
        "snapshots": [
            {
                "id": s.id,
                "generated_at": s.generated_at.isoformat(),
                "file_path": s.file_path,
            }
            for s in snapshots
        ]
    }


@router.get("/{report_id}/snapshots/{snapshot_id}")
async def get_snapshot(
    report_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    snapshot = (
        db.query(ReportSnapshot)
        .filter(
            ReportSnapshot.id == snapshot_id,
            ReportSnapshot.report_id == report_id,
        )
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    report_data = json.loads(snapshot.report_data) if snapshot.report_data else {}
    return {
        "id": snapshot.id,
        "generated_at": snapshot.generated_at.isoformat(),
        "report_data": report_data,
    }


@router.post("/{report_id}/export/{format}")
async def export_report(
    report_id: int,
    format: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
):
    if format not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'pdf'")

    report = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.company_id == company_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    config = (
        json.loads(report.config) if isinstance(report.config, str) else report.config
    )
    result = ReportBuilder.build_report(config, current_user.id, db, company_id)

    if format == "csv":
        csv_content = ReportBuilder.export_csv(result)
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={report.name.replace(' ', '_')}.csv"
            },
        )
    else:
        pdf_bytes = ReportBuilder.export_pdf(result, report.name)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={report.name.replace(' ', '_')}.pdf"
            },
        )
