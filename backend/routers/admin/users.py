from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import AuditLog, Job, SubscriptionPlan, User
from backend.dependencies import (
    create_access_token,
    get_current_user,
    get_db,
)
from backend.logger import logger
from backend.profile_helpers import (
    get_user_email,
    get_user_is_super_admin,
    get_user_name,
    get_user_subscription_plan,
    get_user_tier,
)
from backend.routers.admin.common import check_permission, paginate
from backend.simple_rate_limiter import interview_rate_limiter

router = APIRouter(tags=["admin"])


@router.get("/users")
def get_all_users(
    role: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_users")

    if per_page > 100:
        per_page = 100
    if page < 1:
        page = 1

    # Bug fix: ``User.deleted_at is None`` is a Python ``is``
    # comparison on the column *descriptor*, which is always
    # False, so SQLAlchemy emitted ``WHERE false`` and the
    # listing returned 0 users. Use ``== None`` (or
    # ``.is_(None)``) so the comparison happens at the SQL
    # level: ``WHERE users.deleted_at IS NULL``.
    query = db.query(User).filter(User.deleted_at == None)  # noqa: E711

    if role and role != "all":
        query = query.filter(User.role == role)

    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )

    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "users": [
            {
                "id": u.id,
                "email": get_user_email(u),
                "role": u.role,
                "name": get_user_name(u),
                "tier": getattr(u, "tier", "free"),
                "current_plan_id": getattr(u, "current_plan_id", None),
                "is_active": u.deleted_at is None,
                "joined": u.created_at.strftime("%Y-%m-%d") if u.created_at else "N/A",
            }
            for u in users
        ],
    }


@router.post("/users/{user_id}/impersonate")
def impersonate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "edit_users")

    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        f"admin_impersonate_{current_user.id}", max_requests=5, window_seconds=3600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many impersonation attempts. Wait {retry_after}s",
        )

    target_user = (
        db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    )
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.role == "admin":
        raise HTTPException(status_code=403, detail="Cannot impersonate another admin")

    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={
            "sub": target_user.email,
            "role": target_user.role,
            "id": target_user.id,
            "impersonated_by": current_user.id,
        },
        expires_delta=access_token_expires,
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="impersonate",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} impersonated {target_user.email}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": target_user.role,
        "user_email": target_user.email,
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "delete_users")

    is_allowed, retry_after = interview_rate_limiter.is_allowed(
        f"admin_delete_{current_user.id}", max_requests=10, window_seconds=3600
    )
    if not is_allowed:
        raise HTTPException(
            status_code=429, detail=f"Too many deletion requests. Wait {retry_after}s"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    audit = AuditLog(
        user_id=current_user.id,
        action="delete_user",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} soft-deleted user {get_user_email(user)}",
        ip_address=request.client.host,
    )
    db.add(audit)

    user.deleted_at = datetime.now(UTC)
    user_email = get_user_email(user)
    if "@" in user_email:
        # Dual-write to profile
        profile = user.candidate_profile or user.recruiter_profile
        if profile:
            profile.email = f"deleted_{user.id}_{user_email}"
        user.email = f"deleted_{user.id}_{user_email}"

    db.commit()

    try:
        from backend.redis_cache import redis_cache

        redis_cache.delete("admin:dashboard_stats")
    except Exception as e:
        logger.error(f"Failed to clear Redis dashboard_stats cache: {e}")

    return {"message": "User soft-deleted"}


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    audit = AuditLog(
        user_id=current_user.id,
        action="suspend_user",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} suspended user {get_user_email(user)}",
        ip_address=request.client.host,
    )
    db.add(audit)

    user.deleted_at = datetime.now(UTC)
    db.commit()

    try:
        from backend.redis_cache import redis_cache

        redis_cache.delete("admin:dashboard_stats")
    except Exception as e:
        logger.error(f"Failed to clear Redis dashboard_stats cache: {e}")

    return {"message": "User suspended"}


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    audit = AuditLog(
        user_id=current_user.id,
        action="activate_user",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} activated user {get_user_email(user)}",
        ip_address=request.client.host,
    )
    db.add(audit)

    user.deleted_at = None
    db.commit()

    try:
        from backend.redis_cache import redis_cache

        redis_cache.delete("admin:dashboard_stats")
    except Exception as e:
        logger.error(f"Failed to clear Redis dashboard_stats cache: {e}")

    return {"message": "User activated"}


# --- RECRUITER USAGE ---
@router.get("/users/usage")
def get_recruiters_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 30,
):
    check_permission(current_user, "manage_finance")
    query = db.query(User).filter(User.role == "recruiter", User.deleted_at.is_(None))
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "users": [
            {
                "id": u.id,
                "name": get_user_name(u),
                "email": get_user_email(u),
                "tier": get_user_tier(u),
                "plan_name": get_user_subscription_plan(u)
                or (u.current_plan.name if u.current_plan else get_user_tier(u)),
                "cv_limit": getattr(u.current_plan, "cv_limit", 50)
                if u.current_plan
                else 50,
                "ai_interview_limit": getattr(u.current_plan, "ai_interview_limit", 10)
                if u.current_plan
                else 10,
                "active_jobs": db.query(Job)
                .filter(
                    Job.recruiter_id == u.id,
                    Job.is_active,
                    Job.deleted_at.is_(None),
                )
                .count(),
                "usage_jobs": getattr(
                    getattr(u, "recruiter_profile", None), "usage_jobs", 0
                )
                or 0,
                "usage_cvs": getattr(
                    getattr(u, "recruiter_profile", None), "usage_cvs", 0
                )
                or 0,
                "usage_ai_interviews": getattr(
                    getattr(u, "recruiter_profile", None), "usage_ai_interviews", 0
                )
                or 0,
            }
            for u in result["items"]
        ],
    }


@router.post("/users/{user_id}/usage")
def adjust_user_usage(
    user_id: int,
    request: Request,
    action: str = Body(...),
    amount: int = Body(0),
    field: str = Body("usage_cvs"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rp = getattr(user, "recruiter_profile", None)
    if not rp:
        raise HTTPException(status_code=404, detail="Recruiter profile not found")
    if action == "reset":
        if field in ["all", "usage_cvs"]:
            rp.usage_cvs = 0
        if field in ["all", "usage_interviews"]:
            rp.usage_ai_interviews = 0
        if field in ["all", "usage_jobs"]:
            rp.usage_jobs = 0
    elif action == "give_bonus":
        amount = max(0, amount)
        if field in ["all", "usage_cvs"]:
            rp.usage_cvs = max(0, (rp.usage_cvs or 0) - amount)
        if field in ["all", "usage_interviews"]:
            rp.usage_ai_interviews = max(0, (rp.usage_ai_interviews or 0) - amount)
        if field in ["all", "usage_jobs"]:
            rp.usage_jobs = max(0, (rp.usage_jobs or 0) - amount)

    audit = AuditLog(
        user_id=current_user.id,
        action="adjust_user_usage",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} adjusted usage for user #{user_id}: {action} {field} {amount}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": "Usage adjusted"}


@router.post("/users/{user_id}/assign-plan/{plan_id}")
def assign_plan_manually(
    user_id: int,
    plan_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.id == plan_id)
        .with_for_update()
        .first()
    )
    if not user or not plan:
        raise HTTPException(status_code=404, detail="Not found")
    from backend.models.evaluation.profile import RecruiterProfile

    rp = db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user.id).first()
    if rp:
        rp.current_plan_id = plan.id
        rp.tier = "pro" if plan.price_monthly > 0 else "free"

    audit = AuditLog(
        user_id=current_user.id,
        action="assign_plan",
        target_id=str(user_id),
        details=f"Admin {get_user_email(current_user)} assigned plan #{plan_id} ({plan.name}) to user #{user_id}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": "Plan assigned"}


# --- RBAC MANAGEMENT ---
class PermissionUpdate(BaseModel):
    permissions: str


ALLOWED_PERMISSIONS = {
    "view_users",
    "edit_users",
    "delete_users",
    "view_analytics",
    "manage_content",
    "manage_finance",
    "view_logs",
    "manage_admins",
    "manage_settings",
    "manage_marketing",
    "manage_ai",
}

SUPER_ADMIN_ONLY = {"manage_admins", "manage_settings", "manage_finance"}


@router.put("/users/{user_id}/permissions")
def update_admin_permissions(
    user_id: int,
    payload: PermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    if user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Cannot modify your own permissions"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    requested_perms = set(
        p.strip() for p in payload.permissions.split(",") if p.strip()
    )
    invalid_perms = requested_perms - ALLOWED_PERMISSIONS

    if invalid_perms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid permissions: {invalid_perms}. Allowed: {ALLOWED_PERMISSIONS}",
        )

    if requested_perms & SUPER_ADMIN_ONLY:
        if not get_user_is_super_admin(current_user):
            raise HTTPException(
                status_code=403, detail="Cannot assign super admin permissions"
            )

    admin_profile = getattr(user, "admin_profile", None)
    if not admin_profile:
        raise HTTPException(status_code=404, detail="Admin profile not found")

    old_perms = admin_profile.permissions
    admin_profile.permissions = payload.permissions

    # Audit log for permission change (A-P1-03)
    audit = AuditLog(
        user_id=current_user.id,
        action="update_permissions",
        target_id=str(user_id),
        details=f"Permissions changed: '{old_perms}' -> '{payload.permissions}'",
        ip_address=getattr(current_user, "last_ip", None),
    )
    db.add(audit)

    db.commit()

    return {"message": "Permissions updated", "permissions": admin_profile.permissions}
