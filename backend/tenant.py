"""
tenant.py — Scalable multi-tenant isolation for Candway.

Provides:
  - ``get_current_company_id()`` — FastAPI dependency resolving the
    current user's company from CompanyMember.
  - ``tenant_query()`` — Wraps any SQLAlchemy query with an automatic
    ``WHERE model.company_id == current_company_id`` filter.
  - ``assert_tenant_match()`` — Raises 404 if a resource does not
    belong to the given company.
  - ``get_tenant_application()``, ``get_tenant_job()`` etc. — helpers
    that validate both id and company_id without requiring a User
    object.  Designed for background workers and services.

Usage in routes::

    from backend.tenant import get_current_company_id, tenant_query

    @router.get("/items")
    def list_items(
        db: Session = Depends(get_db),
        company_id: int = Depends(get_current_company_id),
    ):
        query = tenant_query(db.query(Item), Item, company_id)
        return query.all()

Usage in background workers::

    from backend.tenant import get_tenant_application

    app = get_tenant_application(db, application_id, company_id)
    if not app:
        return  # or raise
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import inspect
from sqlalchemy.orm import Query, Session

from backend.database import (
    Application,
    BackgroundCheck,
    BatchJob,
    CompanyMember,
    Interview,
    InterviewScorecard,
    Job,
    Offer,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.logger import logger


def _resolve_company_id(user: User, db: Session) -> int | None:
    """Internal — resolve company_id from cache or CompanyMember table."""
    cached = getattr(user, "_company_id", None)
    if cached is not None:
        return cached
    membership = (
        db.query(CompanyMember.company_id)
        .filter(
            CompanyMember.user_id == user.id,
            CompanyMember.is_active,
        )
        .first()
    )
    if not membership:
        return None
    company_id = membership[0]
    user._company_id = company_id
    return company_id


def get_current_company_id(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int:
    """FastAPI dependency — return the current user's active company_id.

    Raises 403 if the user is not a member of any active company.
    """
    company_id = _resolve_company_id(current_user, db)
    if company_id is None:
        logger.warning(
            "User %s (%s) has no active company membership",
            current_user.email,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active company membership. Contact your admin.",
        )
    return company_id


def get_admin_company_id(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> int | None:
    """FastAPI dependency — company_id for admin management endpoints.

    Platform admins (super admin / role admin) manage resources across
    ALL organizations, so they must NOT be forced into a single company
    scope. Returns ``None`` for platform admins (no company filter) and
    the resolved company_id for non-admin members (tenant-scoped).

    ``None`` is only possible when the caller is a platform admin; callers
    without a membership that are NOT admins still get a 403.
    """
    from backend.dependencies import is_admin_user

    if is_admin_user(current_user):
        return None
    company_id = _resolve_company_id(current_user, db)
    if company_id is None:
        logger.warning(
            "User %s (%s) has no active company membership",
            current_user.email,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active company membership. Contact your admin.",
        )
    return company_id


def tenant_query(
    query: Query,
    model_class: type,
    company_id: int,
) -> Query:
    """Add a WHERE company_id = :company_id filter to any query.

    Args:
        query: SQLAlchemy Query object (e.g. ``db.query(Job)``).
        model_class: The ORM model class (must have ``company_id``).
        company_id: The company_id to filter by.

    Returns:
        The filtered Query object.
    """
    mapper = inspect(model_class)
    if "company_id" not in mapper.c:
        raise ValueError(
            f"{model_class.__name__} has no 'company_id' column and "
            f"cannot be tenant-filtered"
        )
    return query.filter(model_class.company_id == company_id)


def assert_tenant_match(
    resource,
    company_id: int,
    resource_name: str = "resource",
) -> None:
    """Assert that a resource belongs to the given company.

    Raises 404 (not 403) to prevent information leakage about
    resources that exist but belong to other tenants.
    """
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if getattr(resource, "company_id", None) != company_id:
        logger.warning(
            "Tenant violation: %s id=%d company=%d requested by company=%d",
            resource_name,
            getattr(resource, "id", None),
            getattr(resource, "company_id", None),
            company_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


# ── Tenant-safe query helpers (for background workers) ──────────────


def _tenant_get(
    db: Session,
    model_class: type,
    resource_id: int,
    company_id: int,
    resource_name: str = "resource",
):
    """Query *model_class* by PK + company_id, raise 404 on miss."""
    resource = (
        db.query(model_class)
        .filter(model_class.id == resource_id, model_class.company_id == company_id)
        .first()
    )
    assert_tenant_match(resource, company_id, resource_name)
    return resource


def get_tenant_application(
    db: Session, application_id: int, company_id: int
) -> "Application":
    from backend.database import Application

    return _tenant_get(db, Application, application_id, company_id, "Application")


def get_tenant_job(db: Session, job_id: int, company_id: int) -> "Job":
    from backend.database import Job

    return _tenant_get(db, Job, job_id, company_id, "Job")


def get_tenant_batch(db: Session, batch_id: int, company_id: int) -> "BatchJob":
    from backend.database import BatchJob

    return _tenant_get(db, BatchJob, batch_id, company_id, "BatchJob")


def get_tenant_interview(
    db: Session, interview_id: int, company_id: int
) -> "Interview":
    from backend.database import Interview

    return _tenant_get(db, Interview, interview_id, company_id, "Interview")


def get_tenant_background_check(
    db: Session, bg_check_id: int, company_id: int
) -> "BackgroundCheck":
    from backend.database import BackgroundCheck

    return _tenant_get(db, BackgroundCheck, bg_check_id, company_id, "BackgroundCheck")


def get_tenant_offer(db: Session, offer_id: int, company_id: int) -> "Offer":
    from backend.database import Offer

    return _tenant_get(db, Offer, offer_id, company_id, "Offer")


def get_tenant_interview_scorecard(
    db: Session, scorecard_id: int, company_id: int
) -> "InterviewScorecard":
    from backend.database import InterviewScorecard

    return _tenant_get(
        db, InterviewScorecard, scorecard_id, company_id, "InterviewScorecard"
    )


def tenant_validate_application(
    db: Session, application_id: int, company_id: int
) -> bool:
    """Return True if application exists and belongs to company_id.
    Logs and returns False on mismatch — does NOT raise.
    Safe for background workers that should skip silently.
    """
    from backend.database import Application

    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        return False
    if app.company_id != company_id:
        logger.warning(
            "Tenant mismatch: Application %d belongs to company %d, "
            "requested by company %d",
            application_id,
            app.company_id,
            company_id,
        )
        return False
    return True
