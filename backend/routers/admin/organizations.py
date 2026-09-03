"""
Admin Organizations Management — full CRUD for companies/tenants.

Provides list (search + filter + paginate), detail, create, edit,
soft-delete, activate/deactivate, and audit-log endpoints for Company
rows. Platform admins (super admin) manage ALL organizations; non-super
admin users are tenant-scoped via ``get_admin_company_id``.
"""

import math
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.database import (
    Application,
    AuditLog,
    Company,
    CompanyMember,
    CvDocument,
    Job,
    Qualification,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.routers.admin.common import check_permission
from backend.tenant import get_admin_company_id

router = APIRouter(tags=["admin"])


def _company_storage(db: Session, company_id: int) -> dict:
    """Storage usage for a company (bytes + document counts)."""
    member_user_ids = [
        r[0]
        for r in db.query(CompanyMember.user_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .all()
    ]
    qualifications_bytes = 0
    if member_user_ids:
        qualifications_bytes = (
            db.query(func.coalesce(func.sum(Qualification.file_size), 0))
            .filter(
                Qualification.user_id.in_(member_user_ids),
                Qualification.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )
    cv_count = (
        db.query(func.count(CvDocument.id))
        .join(Application, Application.id == CvDocument.application_id)
        .filter(Application.company_id == company_id)
        .scalar()
        or 0
    )
    return {
        "bytes": int(qualifications_bytes),
        "documents": int(cv_count),
        "formatted": _format_bytes(int(qualifications_bytes)),
    }


def _format_bytes(n: int) -> str:
    if n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024


def _company_row(db: Session, c: Company) -> dict:
    recruiter_count = (
        db.query(func.count(CompanyMember.id))
        .filter(CompanyMember.company_id == c.id, CompanyMember.is_active)
        .scalar()
        or 0
    )
    jobs_count = (
        db.query(func.count(Job.id))
        .filter(Job.company_id == c.id, Job.deleted_at.is_(None))
        .scalar()
        or 0
    )
    applications_count = (
        db.query(func.count(Application.id))
        .filter(Application.company_id == c.id)
        .scalar()
        or 0
    )
    storage = _company_storage(db, c.id)
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "domain": c.domain,
        "tier": c.tier,
        "subscription_status": c.subscription_status,
        "max_users": c.max_users,
        "max_jobs": c.max_jobs,
        "max_ai_interviews": c.max_ai_interviews,
        "logo_url": c.logo_url,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "recruiter_count": int(recruiter_count),
        "jobs_count": int(jobs_count),
        "applications_count": int(applications_count),
        "storage": storage,
    }


@router.get("/organizations")
def list_organizations(
    search: Optional[str] = None,
    status: Optional[str] = "all",
    tier: Optional[str] = None,
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Company).filter(Company.deleted_at.is_(None))
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    if search:
        q = f"%{search}%"
        query = query.filter(
            or_(
                Company.name.ilike(q),
                Company.slug.ilike(q),
                Company.domain.ilike(q),
            )
        )
    if status == "active":
        query = query.filter(Company.is_active)
    elif status == "inactive":
        query = query.filter(not Company.is_active)
    if tier:
        query = query.filter(Company.tier == tier)

    total = query.count()
    if page < 1:
        page = 1
    per_page = min(per_page, 100)
    items = (
        query.order_by(Company.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, math.ceil(total / per_page)),
        "organizations": [_company_row(db, c) for c in items],
    }


@router.get("/organizations/{org_id}")
def get_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Company).filter(Company.id == org_id, Company.deleted_at.is_(None))
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    company = query.first()
    if not company:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _company_row(db, company)


@router.post("/organizations")
async def create_organization(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    slug = (data.get("slug") or name.lower().replace(" ", "-")).strip()
    existing = db.query(Company).filter(Company.slug == slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already exists")

    company = Company(
        name=name,
        slug=slug,
        domain=data.get("domain"),
        tier=data.get("tier") or "free",
        subscription_status=data.get("subscription_status") or "active",
        max_users=int(data.get("max_users") or 10),
        max_jobs=int(data.get("max_jobs") or 50),
        max_ai_interviews=int(data.get("max_ai_interviews") or 500),
        logo_url=data.get("logo_url"),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="create_organization",
            target_id=str(company.id),
            details=f"Admin created organization: {company.name} ({company.slug})",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "Organization created",
        "id": company.id,
        **_company_row(db, company),
    }


@router.put("/organizations/{org_id}")
async def update_organization(
    org_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Company).filter(Company.id == org_id, Company.deleted_at.is_(None))
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    company = query.first()
    if not company:
        raise HTTPException(status_code=404, detail="Organization not found")

    data = await request.json()
    if data.get("name"):
        company.name = data["name"].strip()
    if data.get("slug"):
        company.slug = data["slug"].strip()
    if "domain" in data:
        company.domain = data.get("domain")
    if data.get("tier"):
        company.tier = data["tier"]
    if "subscription_status" in data:
        company.subscription_status = data.get("subscription_status")
    if "max_users" in data:
        company.max_users = int(data["max_users"])
    if "max_jobs" in data:
        company.max_jobs = int(data["max_jobs"])
    if "max_ai_interviews" in data:
        company.max_ai_interviews = int(data["max_ai_interviews"])
    if "logo_url" in data:
        company.logo_url = data.get("logo_url")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="update_organization",
            target_id=str(company.id),
            details=f"Admin updated organization: {company.name}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    db.refresh(company)
    return {"message": "Organization updated", **_company_row(db, company)}


@router.delete("/organizations/{org_id}")
def delete_organization(
    org_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Company).filter(Company.id == org_id, Company.deleted_at.is_(None))
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    company = query.first()
    if not company:
        raise HTTPException(status_code=404, detail="Organization not found")

    company.deleted_at = datetime.now(UTC)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="delete_organization",
            target_id=str(company.id),
            details=f"Admin soft-deleted organization: {company.name}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Organization deleted"}


@router.post("/organizations/{org_id}/toggle")
def toggle_organization(
    org_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Company).filter(Company.id == org_id, Company.deleted_at.is_(None))
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    company = query.first()
    if not company:
        raise HTTPException(status_code=404, detail="Organization not found")

    company.is_active = not company.is_active
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="toggle_organization",
            target_id=str(company.id),
            details=(
                f"Admin {'deactivated' if not company.is_active else 'activated'} "
                f"organization: {company.name}"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()
    db.refresh(company)
    return {"message": "Organization updated", "is_active": company.is_active}


@router.get("/organizations/{org_id}/audit")
def organization_audit(
    org_id: int,
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_analytics")
    query = db.query(Company).filter(Company.id == org_id, Company.deleted_at.is_(None))
    if company_id is not None:
        query = query.filter(Company.id == company_id)
    company = query.first()
    if not company:
        raise HTTPException(status_code=404, detail="Organization not found")

    logs_q = (
        db.query(AuditLog)
        .filter(
            or_(
                AuditLog.target_id == str(org_id),
                AuditLog.details.ilike(f"%{company.name}%"),
            )
        )
        .order_by(AuditLog.timestamp.desc())
    )
    total = logs_q.count()
    per_page = min(per_page, 100)
    logs = logs_q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, math.ceil(total / per_page)),
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "user_id": log.user_id,
                "ip_address": log.ip_address,
                "created_at": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if log.timestamp
                else None,
            }
            for log in logs
        ],
    }
