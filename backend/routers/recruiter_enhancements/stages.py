import json
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.database import (
    ActivityLog,
    ApplicationStageHistory,
    PipelineStage,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.routers.recruiter_candidates.applications import (
    ALLOWED_APPLICATION_STATUSES,
)
from backend.security import sanitize_content
from backend.tenant import get_current_company_id

router = APIRouter(tags=["Recruiter Enhancements - Pipeline Stages"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class PipelineStageCreate(BaseModel):
    name: str
    slug: str
    color: str = "#6366f1"
    icon: str = "fa-circle"
    sort_order: int = 0
    batch_id: Optional[int] = None


class PipelineStageUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class StageTransitionRequest(BaseModel):
    app_id: int
    new_stage: str
    trigger_type: str = "manual"


@router.get("/stages")
def get_pipeline_stages(
    batch_id: Optional[int] = None,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Get custom pipeline stages (global + campaign-specific)"""
    query = db.query(PipelineStage).filter(
        PipelineStage.company_id == company_id, PipelineStage.is_active
    )

    if batch_id:
        # Bug fix: same as admin/users — ``Column is None``
        # compiles to ``WHERE false`` because the Python
        # descriptor is never None. Use ``== None`` so the
        # comparison is pushed to SQL.
        query = query.filter(
            or_(
                PipelineStage.batch_id == batch_id,
                PipelineStage.batch_id == None,  # noqa: E711
            )
        )
    else:
        query = query.filter(PipelineStage.batch_id == None)  # noqa: E711

    stages = query.order_by(PipelineStage.sort_order).all()

    # If no custom stages, return defaults
    if not stages:
        defaults = [
            {
                "name": "Applied",
                "slug": "applied",
                "color": "#64748b",
                "icon": "fa-inbox",
                "sort_order": 0,
                "is_default": True,
            },
            {
                "name": "Invited",
                "slug": "invited",
                "color": "#0ea5e9",
                "icon": "fa-envelope",
                "sort_order": 1,
                "is_default": True,
            },
            {
                "name": "Interviewing",
                "slug": "interviewing",
                "color": "#6366f1",
                "icon": "fa-video",
                "sort_order": 2,
                "is_default": True,
            },
            {
                "name": "Offer",
                "slug": "offer",
                "color": "#f59e0b",
                "icon": "fa-file-signature",
                "sort_order": 3,
                "is_default": True,
            },
            {
                "name": "Hired",
                "slug": "hired",
                "color": "#10b981",
                "icon": "fa-check-circle",
                "sort_order": 4,
                "is_default": True,
            },
            {
                "name": "Rejected",
                "slug": "rejected",
                "color": "#ef4444",
                "icon": "fa-times-circle",
                "sort_order": 5,
                "is_default": True,
            },
        ]
        return defaults

    return [
        {
            "id": s.id,
            "name": s.name,
            "slug": s.slug,
            "color": s.color,
            "icon": s.icon,
            "sort_order": s.sort_order,
            "is_default": s.is_default,
            "batch_id": s.batch_id,
        }
        for s in stages
    ]


@router.post("/stages", status_code=status.HTTP_201_CREATED)
def create_pipeline_stage(
    data: PipelineStageCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Create a custom pipeline stage"""
    # Check for duplicate slug
    existing = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.company_id == company_id,
            PipelineStage.slug == data.slug,
            PipelineStage.batch_id == data.batch_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Stage slug already exists")

    stage = PipelineStage(
        recruiter_id=recruiter.id,
        company_id=company_id,
        name=sanitize_content(data.name),
        slug=sanitize_content(data.slug),
        color=data.color,
        icon=data.icon,
        sort_order=data.sort_order,
        batch_id=data.batch_id,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)

    logger.info(f"Pipeline stage created: {stage.name} by {recruiter.email}")
    return {
        "success": True,
        "stage": {"id": stage.id, "name": stage.name, "slug": stage.slug},
    }


@router.patch("/stages/{stage_id}")
def update_pipeline_stage(
    stage_id: int,
    data: PipelineStageUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Update a custom pipeline stage"""
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.id == stage_id, PipelineStage.company_id == company_id)
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    if stage.is_default:
        raise HTTPException(status_code=400, detail="Cannot modify default stages")

    if data.name is not None:
        stage.name = sanitize_content(data.name)
    if data.color is not None:
        stage.color = data.color
    if data.icon is not None:
        stage.icon = data.icon
    if data.sort_order is not None:
        stage.sort_order = data.sort_order
    if data.is_active is not None:
        stage.is_active = data.is_active

    db.commit()
    return {"success": True}


@router.delete("/stages/{stage_id}")
def delete_pipeline_stage(
    stage_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Delete (deactivate) a custom pipeline stage"""
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.id == stage_id, PipelineStage.company_id == company_id)
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    if stage.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default stages")

    stage.is_active = False
    db.commit()
    return {"success": True}


@router.post("/stage-transition")
def record_stage_transition(
    data: StageTransitionRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Record a stage transition with history tracking"""
    app = get_application_for_recruiter(data.app_id, recruiter, db)

    if data.new_stage not in ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"'{data.new_stage}' is not a valid application status",
        )

    # Record exit from current stage
    if app.status:
        exit_history = ApplicationStageHistory(
            application_id=app.id,
            company_id=company_id,
            stage_slug=app.status,
            stage_name=app.status,
            exited_at=_utcnow(),
            triggered_by=recruiter.id,
            trigger_type=data.trigger_type,
        )
        db.add(exit_history)

        # Calculate duration for previous stage
        prev_entry = (
            db.query(ApplicationStageHistory)
            .filter(
                ApplicationStageHistory.application_id == app.id,
                ApplicationStageHistory.stage_slug == app.status,
                ApplicationStageHistory.exited_at is None,
            )
            .order_by(desc(ApplicationStageHistory.entered_at))
            .first()
        )

        if prev_entry:
            prev_entry.exited_at = _utcnow()
            duration = (prev_entry.exited_at - prev_entry.entered_at).total_seconds()
            prev_entry.duration_seconds = int(duration)

    # Update application status
    app.status = data.new_stage

    # Record entry to new stage
    entry_history = ApplicationStageHistory(
        application_id=app.id,
        company_id=company_id,
        stage_slug=data.new_stage,
        stage_name=data.new_stage,
        triggered_by=recruiter.id,
        trigger_type=data.trigger_type,
    )
    db.add(entry_history)

    # Log activity
    log = ActivityLog(
        user_id=recruiter.id,
        company_id=company_id,
        action="stage_transition",
        application_id=app.id,
        details=json.dumps(
            {"from": app.status, "to": data.new_stage, "trigger": data.trigger_type}
        ),
    )
    db.add(log)

    db.commit()

    return {"success": True, "new_status": data.new_stage}


@router.get("/stage-history/{app_id}")
def get_stage_history(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Get full stage history for an application"""
    get_application_for_recruiter(app_id, recruiter, db)
    history = (
        db.query(ApplicationStageHistory)
        .filter(ApplicationStageHistory.application_id == app_id)
        .order_by(ApplicationStageHistory.entered_at)
        .all()
    )

    return [
        {
            "id": h.id,
            "stage_slug": h.stage_slug,
            "stage_name": h.stage_name,
            "entered_at": h.entered_at.isoformat(),
            "exited_at": h.exited_at.isoformat() if h.exited_at else None,
            "duration_seconds": h.duration_seconds,
            "duration_hours": round(h.duration_seconds / 3600, 1)
            if h.duration_seconds
            else None,
            "trigger_type": h.trigger_type,
        }
        for h in history
    ]
