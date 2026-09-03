from datetime import UTC, datetime
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.authz import get_batch_for_recruiter, get_job_for_recruiter
from backend.database import Application, BatchJob, CompanyMember, Job, Rubric, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.models.core.batch_job import batch_counters
from backend.repository.metrics_repository import MetricsRepository
from backend.security import sanitize_content
from backend.tenant import get_current_company_id

from . import router


class BatchJobCreate(BaseModel):
    title: str
    job_id: int


class BatchJobResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
    candidate_count: int
    worker_status: Optional[str] = "completed"
    total_files: Optional[int] = 0
    processed_files: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)


class CampaignUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class FullCampaignCreate(BaseModel):
    title: str
    job_id: Optional[int] = None
    target_role: Optional[str] = None
    description: Optional[str] = None
    rubric_id: Optional[int] = None
    skill_tree_id: Optional[int] = None
    skill_option: Optional[str] = "existing"
    language: Optional[str] = "English"
    duration_minutes: Optional[int] = 45
    difficulty: Optional[str] = "medium"
    interview_instructions: Optional[str] = None
    template_id: Optional[int] = None
    candidate_source: Optional[str] = "upload"
    location: Optional[str] = None


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


@router.get("", response_model=List[BatchJobResponse])
def get_campaigns(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    batches = (
        db.query(BatchJob)
        .join(CompanyMember, CompanyMember.user_id == BatchJob.recruiter_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
            BatchJob.deleted_at.is_(None),
        )
        .order_by(BatchJob.created_at.desc(), BatchJob.id.desc())
        .all()
    )
    if not batches:
        return []
    repo = MetricsRepository(db)
    metrics = repo.get_campaign_list_metrics(company_id)
    result = []
    for b in batches:
        m = metrics.get(b.id, {})
        counters = batch_counters(db, b.id)
        result.append(
            {
                "id": b.id,
                "title": b.title,
                "status": b.status,
                "created_at": b.created_at,
                "candidate_count": m.get("candidate_count", 0),
                "worker_status": b.worker_status or "completed",
                "total_files": counters["total_files"],
                "processed_files": counters["processed_files"],
            }
        )
    return result


@router.post("/", response_model=BatchJobResponse)
async def create_campaign(
    campaign: BatchJobCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    from backend.redis_rate_limiter import check_rate_limit

    is_allowed, metadata = await check_rate_limit(
        f"create_campaign_{recruiter.id}", max_requests=10, window_seconds=3600
    )
    retry_after = metadata.get("retry_after", 0) if isinstance(metadata, dict) else 0
    if not is_allowed:
        raise HTTPException(
            status_code=429, detail=f"Rate limit exceeded. Try in {retry_after}s"
        )

    _job = get_job_for_recruiter(campaign.job_id, recruiter, db)

    new_batch = BatchJob(
        recruiter_id=recruiter.id,
        company_id=company_id,
        title=campaign.title,
        status="active",
        job_id=campaign.job_id,
    )
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    return {
        "id": new_batch.id,
        "title": new_batch.title,
        "status": new_batch.status,
        "created_at": new_batch.created_at,
        "candidate_count": 0,
    }


@router.patch("/{batch_id}")
def update_campaign(
    batch_id: int,
    request: CampaignUpdateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    batch = get_batch_for_recruiter(batch_id, recruiter, db)

    if request.title is not None:
        batch.title = sanitize_content(request.title.strip())

    if request.status is not None:
        if request.status not in ["active", "archived"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        batch.status = request.status
        if request.status == "archived":
            batch.deleted_at = _utcnow()
        else:
            batch.deleted_at = None

    db.commit()
    logger.info(f"Updated campaign {batch_id}")
    return {"success": True, "title": batch.title, "status": batch.status}


@router.delete("/{batch_id}")
def delete_campaign(
    batch_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    batch = get_batch_for_recruiter(batch_id, recruiter, db)

    now = datetime.now(UTC)
    db.query(Application).filter(Application.batch_id == batch_id).update(
        {"deleted_at": now}, synchronize_session=False
    )
    batch.deleted_at = now
    db.commit()
    logger.info(f"Soft-deleted campaign {batch_id}")
    return {"success": True}


@router.post("/full")
async def create_full_campaign(
    campaign: FullCampaignCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """
    Create a campaign with full configuration: skill tree selection,
    interview settings, candidate source, etc.
    """
    from backend.redis_rate_limiter import check_rate_limit

    is_allowed, metadata = await check_rate_limit(
        f"create_campaign_{recruiter.id}", max_requests=10, window_seconds=3600
    )
    retry_after = metadata.get("retry_after", 0) if isinstance(metadata, dict) else 0
    if not is_allowed:
        raise HTTPException(
            status_code=429, detail=f"Rate limit exceeded. Try in {retry_after}s"
        )

    _job = None
    if campaign.job_id:
        _job = get_job_for_recruiter(campaign.job_id, recruiter, db)

    rubric_id = campaign.rubric_id or campaign.skill_tree_id
    if rubric_id:
        rubric = (
            db.query(Rubric)
            .filter(
                Rubric.id == rubric_id,
                Rubric.company_id == company_id,
                Rubric.is_active == 1,
            )
            .first()
        )
        if not rubric:
            raise HTTPException(status_code=404, detail="Rubric not found")

    new_batch = BatchJob(
        recruiter_id=recruiter.id,
        company_id=company_id,
        title=sanitize_content(campaign.title),
        status="active",
        job_id=campaign.job_id,
        target_role=sanitize_content(campaign.target_role)
        if campaign.target_role
        else None,
        description=sanitize_content(campaign.description)
        if campaign.description
        else None,
        language=campaign.language or "English",
        duration_minutes=campaign.duration_minutes,
        difficulty=campaign.difficulty,
        candidate_source=campaign.candidate_source,
        location=sanitize_content(campaign.location)
        if campaign.location
        else None,
        interview_instructions=sanitize_content(campaign.interview_instructions)
        if campaign.interview_instructions
        else None,
        template_id=campaign.template_id,
        worker_status="pending",
        rubric_id=rubric.id if rubric_id else None,
    )

    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)

    logger.info(
        f"Full campaign created: id={new_batch.id} title={campaign.title} "
        f"by recruiter={recruiter.id}"
    )

    return {
        "success": True,
        "id": new_batch.id,
        "title": new_batch.title,
        "status": new_batch.status,
        "job_id": new_batch.job_id,
        "created_at": new_batch.created_at.isoformat()
        if new_batch.created_at
        else None,
    }


def _parse_rubric_categories(rubric) -> list:
    """Parse rubric.criteria_json into a list of category dicts."""
    import json as _json

    raw = rubric.criteria_json
    if not raw:
        return []
    if isinstance(raw, (dict, list)):
        data = raw
    else:
        try:
            data = _json.loads(raw)
        except (ValueError, TypeError):
            return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("criteria", "skills", "categories", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _format_evaluation_rubric(rubric, job=None) -> dict:
    """Serialise a Rubric row as a real evaluation rubric for campaign creation."""
    cats = _parse_rubric_categories(rubric)
    skill_count = sum(
        len(sub.get("skills", []))
        for cat in cats
        for sub in cat.get("subcategories", [])
    )
    category_names = [c.get("name") for c in cats if c.get("name")]
    return {
        "id": rubric.id,
        "job_id": rubric.job_id,
        "title": rubric.title,
        "job_name": rubric.title
        or (job.title if job else f"Rubric #{rubric.id}"),
        "category_name": category_names[0] if category_names else None,
        "categories": category_names,
        "version": rubric.version,
        "seniority": rubric.complexity or "mid",
        "skill_count": skill_count,
        "category_count": len(cats),
        "published": bool(rubric.is_active),
        "created_at": rubric.created_at.isoformat() if rubric.created_at else None,
    }


@router.get("/rubrics")
def list_campaign_rubrics(
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """List real evaluation rubrics for the recruiter's company.

    Includes admin-created global templates (company_id IS NULL) plus
    rubrics generated by this company (skill trees / rubric generation).
    """
    rubrics = (
        db.query(Rubric)
        .filter(Rubric.is_active == 1)
        .order_by(Rubric.created_at.desc())
        .all()
    )

    def _visible(r):
        return r.company_id == company_id or r.company_id is None

    visible = [r for r in rubrics if _visible(r)]

    job_ids = list({r.job_id for r in visible if r.job_id})
    job_map = {}
    if job_ids:
        for j in db.query(Job).filter(Job.id.in_(job_ids)).all():
            job_map[j.id] = j

    return {
        "rubrics": [_format_evaluation_rubric(r, job_map.get(r.job_id)) for r in visible]
    }


@router.get("/{batch_id}/stats")
def get_campaign_stats_endpoint(
    batch_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    from backend.authz import get_batch_for_recruiter

    _batch = get_batch_for_recruiter(batch_id, recruiter, db)
    repo = MetricsRepository(db)
    stats = repo.get_campaign_stats(batch_id, company_id)
    return {
        "success": True,
        "stats": {
            "total_candidates": stats.total_candidates,
            "avg_cv_score": stats.avg_cv_score,
            "interviewed": stats.interviewed,
            "invited": stats.invited,
            "opened": stats.opened,
        },
    }
