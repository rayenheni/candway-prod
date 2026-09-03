from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import CampaignCost, User
from backend.dependencies import get_db, require_recruiter
from backend.repository.metrics_repository import MetricsRepository
from backend.security import sanitize_content
from backend.tenant import get_current_company_id

router = APIRouter(tags=["Recruiter Enhancements - Analytics"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class CampaignCostCreate(BaseModel):
    batch_id: int
    cost_type: str
    amount: float
    currency: str = "TND"
    description: Optional[str] = None


@router.get("/analytics/jd-bias")
def get_jd_bias_analytics(
    days: int = 30,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    return repo.get_jd_bias_analytics(company_id, days=days)


@router.get("/analytics/time-in-stage")
def get_time_in_stage_analytics(
    days: int = 30,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    return repo.get_time_in_stage_analytics(
        company_id, recruiter_id=recruiter.id, days=days
    )


@router.get("/analytics/source-attribution")
def get_source_attribution(
    days: int = 90,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    return repo.get_source_attribution(company_id, recruiter_id=recruiter.id, days=days)


@router.get("/analytics/cost-per-hire")
def get_cost_per_hire(
    days: int = 90,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    return repo.get_cost_per_hire(company_id, recruiter_id=recruiter.id, days=days)


@router.get("/analytics/rubric-deep")
def get_rubric_deep_analytics(
    days: int = 90,
    min_occurrences: int = 3,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    repo = MetricsRepository(db)
    return repo.get_rubric_deep_analytics(
        company_id,
        recruiter_id=recruiter.id,
        days=days,
        min_occurrences=min_occurrences,
    )


@router.post("/analytics/costs", status_code=status.HTTP_201_CREATED)
def add_campaign_cost(
    data: CampaignCostCreate,
    recruiter: User = Depends(require_recruiter),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    from backend.authz import get_batch_for_recruiter

    batch = get_batch_for_recruiter(data.batch_id, recruiter, db)
    if not batch:
        raise HTTPException(status_code=404, detail="Campaign not found")

    cost = CampaignCost(
        batch_id=data.batch_id,
        company_id=company_id,
        recruiter_id=recruiter.id,
        cost_type=data.cost_type,
        amount=data.amount,
        currency=data.currency,
        description=sanitize_content(data.description) if data.description else None,
    )
    db.add(cost)
    db.commit()

    return {"success": True, "cost_id": cost.id}
