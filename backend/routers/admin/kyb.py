"""Admin KYB (Know Your Business) review.

Lists companies that submitted KYB details + documents and lets an admin
approve or reject them. Mutations are AuditLog'd with the company_id and
the org owner is notified by email.
"""

import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import AuditLog, Company, CompanyMember, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name
from backend.routers.admin.common import check_permission, paginate

router = APIRouter(tags=["admin"])


class KybRejectBody(BaseModel):
    reason: str


def _kyb_documents(company: Company) -> list:
    if not company.kyb_documents:
        return []
    try:
        docs = json.loads(company.kyb_documents)
        return docs if isinstance(docs, list) else []
    except (ValueError, TypeError):
        return []


def _company_owner(db: Session, company_id: int) -> Optional[User]:
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.role == "owner",
        )
        .first()
    )
    if not membership:
        return None
    return db.query(User).filter(User.id == membership.user_id).first()


def _kyb_payload(db: Session, company: Company) -> dict:
    owner = _company_owner(db, company.id)
    return {
        "company_id": company.id,
        "company_name": company.name,
        "slug": company.slug,
        "billing_email": company.billing_email,
        "billing_address": company.billing_address,
        "tax_id": company.tax_id,
        "kyb_status": company.kyb_status,
        "kyb_documents": _kyb_documents(company),
        "owner_email": get_user_email(owner) if owner else None,
        "owner_name": get_user_name(owner) if owner else None,
        "created_at": company.created_at.strftime("%Y-%m-%d")
        if company.created_at
        else None,
    }


@router.get("/kyb")
def list_kyb(
    status: str = "pending",
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List company KYB submissions filtered by status (default pending)."""
    check_permission(current_user, "manage_finance")
    valid = {"pending", "approved", "rejected"}
    if status not in valid:
        raise HTTPException(
            status_code=400, detail="status must be one of pending/approved/rejected"
        )

    query = (
        db.query(Company)
        .filter(Company.kyb_status == status)
        .order_by(Company.created_at.desc())
    )
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "companies": [_kyb_payload(db, c) for c in result["items"]],
    }


@router.post("/kyb/{company_id}/approve")
def approve_kyb(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a company's KYB verification."""
    check_permission(current_user, "manage_finance")
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.kyb_status = "approved"
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company.id,
            action="kyb_approve",
            target_id=str(company.id),
            details=(
                f"Admin {get_user_email(current_user)} approved KYB for {company.name}"
            ),
        )
    )
    db.commit()

    owner = _company_owner(db, company.id)
    if owner:
        try:
            from backend.email_service import email_service

            body = (
                f"Dear {get_user_name(owner)},\n\n"
                f"Great news! Your company verification (KYB) has been approved "
                f"for {company.name}.\n\n"
                "You can now proceed with your company subscription in the "
                "Company workspace (Billing).\n\n"
                "Best regards,\nThe Candway Team"
            )
            email_service.send_email(
                get_user_email(owner), "Company Verification Approved - Candway", body
            )
        except Exception as e:
            logger.error(f"KYB approve email failed for company {company.id}: {e}")

    return {
        "message": "KYB approved",
        "company_id": company.id,
        "kyb_status": company.kyb_status,
    }


@router.post("/kyb/{company_id}/reject")
def reject_kyb(
    company_id: int,
    body: KybRejectBody = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a company's KYB verification with a reason."""
    check_permission(current_user, "manage_finance")
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A rejection reason is required")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.kyb_status = "rejected"
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company.id,
            action="kyb_reject",
            target_id=str(company.id),
            details=(
                f"Admin {get_user_email(current_user)} rejected KYB for "
                f"{company.name}: {reason}"
            ),
        )
    )
    db.commit()

    owner = _company_owner(db, company.id)
    if owner:
        try:
            from backend.email_service import email_service

            body = (
                f"Dear {get_user_name(owner)},\n\n"
                f"Your company verification (KYB) for {company.name} was rejected.\n\n"
                f"Reason: {reason}\n\n"
                "Please correct the details and re-submit in the Company workspace.\n\n"
                "Best regards,\nThe Candway Team"
            )
            email_service.send_email(
                get_user_email(owner), "Company Verification Update - Candway", body
            )
        except Exception as e:
            logger.error(f"KYB reject email failed for company {company.id}: {e}")

    return {
        "message": "KYB rejected",
        "company_id": company.id,
        "kyb_status": company.kyb_status,
    }
