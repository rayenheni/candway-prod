"""Organization portal — analytics endpoints.

Gated by `require_org_admin`. All queries tenant-scoped to the org
admin's company_id; cross-company access returns 404.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import CompanyMember, User
from backend.dependencies import get_db, require_org_admin
from backend.org_analytics_service import (
    get_company_overview,
    get_credit_economy,
    get_recruiter_detail,
)

router = APIRouter(prefix="/org/analytics", tags=["org"])


@router.get("/overview")
def overview(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company_id = current_user._company_id
    return get_company_overview(db, company_id)


@router.get("/recruiters/{user_id}")
def recruiter_analytics(
    user_id: int,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company_id = current_user._company_id
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    return get_recruiter_detail(db, company_id, user_id)


@router.get("/credits")
def credit_economy(
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    company_id = current_user._company_id
    economy = get_credit_economy(db, company_id)
    from backend.credit_service import get_all_credit_pricing

    economy["pricing"] = get_all_credit_pricing(db)
    return economy
