"""Organization portal — member management.

All endpoints are tenant-scoped to the org admin's company and gated by
`require_org_admin` (active CompanyMember role owner/admin AND User role
'company'). Cross-company access returns 404 to prevent resource
enumeration. Every mutation is AuditLog'd with the acting org admin.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import AuditLog, CompanyMember, EmailVerification, User
from backend.dependencies import (
    create_access_token,
    get_db,
    pwd_context,
    require_org_admin,
)
from backend.logger import logger
from backend.password_validator import validate_email
from backend.profile_helpers import get_user_email, get_user_name
from backend.simple_rate_limiter import interview_rate_limiter
from backend.utils.account_service import generate_random_password

router = APIRouter(prefix="/org", tags=["org"])

ALLOWED_MEMBER_ROLES = {"recruiter", "member"}
OWNER_ROLES = ("owner", "admin")


def _get_member(db: Session, company_id: int, user_id: int) -> CompanyMember:
    """Tenant-safe membership lookup — 404 on cross-company or missing."""
    membership = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    return membership


def _assert_seat_available(db: Session, company_id: int) -> None:
    """Enforce the company's recruiter seat limit (bought via org billing).

    Only ``recruiter`` members count against the seat pool; owner/admin and
    deactivated members do not. Returns a clear 400 when seats are exhausted.
    """
    from backend.database import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    limit = company.max_users or 0
    used = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.role == "recruiter",
            CompanyMember.is_active == True,  # noqa: E712
        )
        .count()
    )
    if used >= limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Recruiter seat limit reached ({used}/{limit}). "
                "Upgrade the company plan in Billing to add more seats."
            ),
        )


def _member_payload(membership: CompanyMember, db: Optional[Session] = None) -> dict:
    user = membership.user
    rp = getattr(user, "recruiter_profile", None)
    credit_balance = 0.0
    if db is not None:
        from backend.credit_service import get_user_credit_balance

        credit_balance = get_user_credit_balance(db, user)
    return {
        "user_id": membership.user_id,
        "name": get_user_name(user),
        "email": get_user_email(user),
        "role": membership.role,
        "is_active": bool(membership.is_active),
        "joined_at": membership.joined_at.strftime("%Y-%m-%d")
        if membership.joined_at
        else None,
        "credit_balance": credit_balance,
        "usage": {
            "jobs": (rp.usage_jobs or 0) if rp else 0,
            "cvs": (rp.usage_cvs or 0) if rp else 0,
            "ai_interviews": (rp.usage_ai_interviews or 0) if rp else 0,
        },
    }


def _send_member_credentials(
    email: str, name: str, password: str, company_name: str
) -> None:
    """Email a freshly-created recruiter their sign-in credentials."""
    settings = get_settings()
    body = (
        f"Hello {name},\n\n"
        f"You have been added to {company_name} on Candway as a recruiter.\n"
        f"Sign in at {settings.frontend_url}/auth/login with:\n"
        f"Email: {email}\nPassword: {password}\n\n"
        "Please change your password after your first sign-in. You will also "
        "receive a separate email to verify your email address."
    )
    try:
        from backend.email_utils import send_email

        send_email(email, f"Welcome to {company_name} on Candway", body)
    except Exception as e:
        logger.error(f"org member credentials email failed for {email}: {e}")


def _send_verification_email(email: str, token: str) -> None:
    """Send the email-verification link to a new recruiter member."""
    try:
        from backend.email_service import email_service

        email_service.send_verification_email(email, token)
    except Exception as e:
        logger.error(f"org member verification email failed for {email}: {e}")


class OrgMemberCreate(BaseModel):
    name: str
    email: str
    password: Optional[str] = None
    role: str = "recruiter"


class OrgMemberInvite(BaseModel):
    name: str
    email: str


class OrgMemberUpdate(BaseModel):
    role: Optional[str] = None


@router.get("/members")
def list_members(
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """List all members of the org admin's company."""
    company_id = current_user._company_id
    memberships = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == company_id)
        .order_by(CompanyMember.id)
        .all()
    )
    return {
        "company_id": company_id,
        "members": [_member_payload(m, db) for m in memberships],
    }


@router.post("/members")
def create_member(
    data: OrgMemberCreate,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Directly create a recruiter member account for the company."""
    company_id = current_user._company_id
    email = data.email.lower().strip()
    name = (data.name or "").strip()
    if not email or not name:
        raise HTTPException(status_code=400, detail="Name and email are required")
    validate_email(email)
    if data.role not in ALLOWED_MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid member role")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if data.role == "recruiter":
        _assert_seat_available(db, company_id)

    password = data.password or generate_random_password()
    user = User(
        email=email,
        name=name,
        role="recruiter",
        hashed_password=pwd_context.hash(password),
        temp_password=password if not data.password else None,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    from backend.models.evaluation.profile import RecruiterProfile

    db.add(
        RecruiterProfile(
            user_id=user.id,
            name=name,
            email=email,
            company_name=current_user.recruiter_profile.company_name
            if current_user.recruiter_profile
            else None,
            company_id=company_id,
            email_settings="{}",
            tier="free",
            subscription_status="active",
        )
    )
    membership = CompanyMember(
        company_id=company_id,
        user_id=user.id,
        role=data.role,
        is_active=True,
        joined_at=datetime.now(UTC),
    )
    db.add(membership)
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_create_member",
            target_id=str(user.id),
            details=f"Org admin {get_user_email(current_user)} created recruiter {email} ({data.role})",
            ip_address=request.client.host,
        )
    )

    verification_token = secrets.token_urlsafe(32)
    db.add(
        EmailVerification(
            user_id=user.id,
            token=verification_token,
            code=None,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

    db.commit()
    db.refresh(membership)

    company_name = (
        current_user.recruiter_profile.company_name
        if current_user.recruiter_profile
        else "Candway"
    )
    _send_member_credentials(email, name, password, company_name)
    _send_verification_email(email, verification_token)

    return {
        "message": "Member created",
        "password": password,
        **_member_payload(membership),
    }


@router.post("/members/{user_id}/impersonate")
def impersonate_member(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Company 'enter as' — switch into one of the company's own accounts.

    Issues a short-lived token acting as the target recruiter/member, so the
    company admin can verify the workspace from the inside. The target must be
    an active member of the SAME company (404 otherwise) and not the owner.
    """
    company_id = current_user._company_id
    membership = _get_member(db, company_id, user_id)
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot impersonate the owner")
    if membership.role not in ALLOWED_MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid target role")

    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        f"org_impersonate_{current_user.id}", max_requests=10, window_seconds=3600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many impersonation attempts. Wait {retry_after}s",
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")

    access_token = create_access_token(
        data={
            "sub": target_user.email,
            "role": target_user.role,
            "id": target_user.id,
            "impersonated_by": current_user.id,
        },
        expires_delta=timedelta(minutes=60),
    )

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_impersonate_member",
            target_id=str(user_id),
            details=(
                f"Org admin {get_user_email(current_user)} entered the account "
                f"of {get_user_email(target_user)} (impersonation, 60 min token)"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": target_user.role,
        "user_email": target_user.email,
    }


@router.post("/members/invite")
def invite_member(
    data: OrgMemberInvite,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Create a shadow recruiter account and email the credentials."""
    company_id = current_user._company_id
    email = data.email.lower().strip()
    name = (data.name or "").strip()
    if not email or not name:
        raise HTTPException(status_code=400, detail="Name and email are required")
    validate_email(email)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    _assert_seat_available(db, company_id)

    password = generate_random_password()
    user = User(
        email=email,
        name=name,
        role="recruiter",
        hashed_password=pwd_context.hash(password),
        temp_password=password,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    from backend.models.evaluation.profile import RecruiterProfile

    db.add(
        RecruiterProfile(
            user_id=user.id,
            name=name,
            email=email,
            company_id=company_id,
            email_settings="{}",
            tier="free",
            subscription_status="active",
        )
    )
    db.add(
        CompanyMember(
            company_id=company_id,
            user_id=user.id,
            role="recruiter",
            is_active=True,
            invited_at=datetime.now(UTC),
            joined_at=datetime.now(UTC),
        )
    )
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_invite_member",
            target_id=str(user.id),
            details=f"Org admin {get_user_email(current_user)} invited recruiter {email}",
            ip_address=request.client.host,
        )
    )
    db.commit()

    company_name = (
        current_user.recruiter_profile.company_name
        if current_user.recruiter_profile
        else "Candway"
    )
    body = (
        f"Hello {name},\n\n"
        f"You have been added to {company_name} on Candway as a recruiter.\n"
        f"Sign in with:\nEmail: {email}\nPassword: {password}\n\n"
        "Please change your password after your first sign-in."
    )
    try:
        from backend.email_utils import send_email

        send_email(email, f"Welcome to {company_name} on Candway", body)
    except Exception as e:
        logger.error(f"org invite email failed for {email}: {e}")

    return {"message": "Invitation sent", "email": email}


@router.patch("/members/{user_id}")
def update_member(
    user_id: int,
    data: OrgMemberUpdate,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Update a member's role (owner/admin management only)."""
    company_id = current_user._company_id
    membership = _get_member(db, company_id, user_id)
    if data.role is not None:
        if data.role not in ALLOWED_MEMBER_ROLES and data.role not in OWNER_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if membership.role == "owner":
            raise HTTPException(
                status_code=400, detail="Cannot change the owner's role"
            )
        old_role = membership.role
        membership.role = data.role
        db.add(
            AuditLog(
                user_id=current_user.id,
                company_id=company_id,
                action="org_update_member_role",
                target_id=str(user_id),
                details=f"Org admin {get_user_email(current_user)} changed member {user_id} role {old_role} -> {data.role}",
                ip_address=request.client.host,
            )
        )
    db.commit()
    db.refresh(membership)
    return {"message": "Member updated", **_member_payload(membership)}


@router.post("/members/{user_id}/deactivate")
def deactivate_member(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a member's company membership."""
    company_id = current_user._company_id
    membership = _get_member(db, company_id, user_id)
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot deactivate the owner")
    membership.is_active = False
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_deactivate_member",
            target_id=str(user_id),
            details=f"Org admin {get_user_email(current_user)} deactivated member {user_id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Member deactivated"}


@router.post("/members/{user_id}/activate")
def activate_member(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Reactivate a member's company membership."""
    company_id = current_user._company_id
    membership = _get_member(db, company_id, user_id)
    membership.is_active = True
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_activate_member",
            target_id=str(user_id),
            details=f"Org admin {get_user_email(current_user)} reactivated member {user_id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Member activated"}


@router.post("/members/{user_id}/reset-usage")
def reset_member_usage(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Reset a recruiter member's usage counters to zero."""
    company_id = current_user._company_id
    _membership = _get_member(db, company_id, user_id)
    from backend.models.evaluation.profile import RecruiterProfile

    rp = db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user_id).first()
    if rp:
        rp.usage_jobs = 0
        rp.usage_cvs = 0
        rp.usage_ai_interviews = 0
        rp.usage_reset_date = datetime.now(UTC)
    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_reset_member_usage",
            target_id=str(user_id),
            details=f"Org admin {get_user_email(current_user)} reset usage for member {user_id}",
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {"message": "Usage reset"}


class OrgGrantCreditsRequest(BaseModel):
    credits: int
    note: Optional[str] = None


@router.post("/members/{user_id}/grant-credits")
def grant_member_credits(
    user_id: int,
    req: OrgGrantCreditsRequest,
    request: Request,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Transfer credits from the company pool to a member's personal wallet.

    The company pool is the billing owner's wallet (see
    resolve_company_billing_user). Debits the pool, credits the target
    member, atomically and idempotently. 404 for cross-company members,
    400 for invalid amounts or insufficient company balance.
    """
    company_id = current_user._company_id
    _membership = _get_member(db, company_id, user_id)

    from backend.credit_service import transfer_company_credits

    try:
        result = transfer_company_credits(
            db,
            company_id,
            _membership.user,
            req.credits,
            note=req.note,
            admin_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.add(
        AuditLog(
            user_id=current_user.id,
            company_id=company_id,
            action="org_grant_credits",
            target_id=str(user_id),
            details=(
                f"Org admin {get_user_email(current_user)} granted {req.credits} credits "
                f"to member {user_id} from the company pool"
            ),
            ip_address=request.client.host,
        )
    )
    db.commit()
    return {
        "message": "Credits transferred",
        "user_id": user_id,
        "credits": req.credits,
        "member_balance": result["target_balance"],
        "company_balance": result["source_balance"],
        "duplicate": result["duplicate"],
    }
