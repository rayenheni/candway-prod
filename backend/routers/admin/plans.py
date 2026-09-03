from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import AuditLog, PlanVersion, SubscriptionPlan, User
from backend.dependencies import get_current_user, get_db
from backend.routers.admin.common import check_permission, paginate
from backend.schemas import (
    SubscriptionPlan as SubscriptionPlanSchema,
)
from backend.schemas import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
)

router = APIRouter(tags=["admin"])


@router.get("/plans")
def get_subscription_plans(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    query = db.query(SubscriptionPlan)
    result = paginate(query, page, per_page)
    for p in result["items"]:
        if p.permissions_json is None:
            p.permissions_json = "{}"
        if p.job_limit is None:
            p.job_limit = 5
        if p.cv_limit is None:
            p.cv_limit = 50
        if p.ai_interview_limit is None:
            p.ai_interview_limit = 10
        if p.team_seat_limit is None:
            p.team_seat_limit = 1
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "plans": result["items"],
    }


@router.post("/plans", response_model=SubscriptionPlanSchema)
def create_subscription_plan(
    plan: SubscriptionPlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")

    existing = (
        db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == plan.slug).first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")

    new_plan = SubscriptionPlan(
        name=plan.name,
        slug=plan.slug,
        target_audience=plan.target_audience,
        price_monthly=plan.price_monthly,
        price_yearly=plan.price_yearly,
        currency=plan.currency,
        features=plan.features,
        permissions_json=plan.permissions_json,
        is_active=plan.is_active,
        is_featured=plan.is_featured,
        job_limit=plan.job_limit,
        cv_limit=plan.cv_limit,
        ai_interview_limit=plan.ai_interview_limit,
        team_seat_limit=plan.team_seat_limit,
        candidate_cv_uploads_limit=getattr(plan, "candidate_cv_uploads_limit", 2),
        candidate_ai_analyses_limit=getattr(plan, "candidate_ai_analyses_limit", 1),
        candidate_pdf_downloads_limit=getattr(plan, "candidate_pdf_downloads_limit", 0),
        candidate_job_matches_limit=getattr(plan, "candidate_job_matches_limit", 5),
        credits_monthly=getattr(plan, "credits_monthly", 0),
        plan_group=getattr(plan, "plan_group", "standard"),
    )

    db.add(new_plan)
    db.flush()
    db.add(
        PlanVersion(
            plan_id=new_plan.id,
            version=1,
            name=new_plan.name,
            slug=new_plan.slug,
            price_monthly=new_plan.price_monthly,
            price_yearly=new_plan.price_yearly,
            currency=new_plan.currency,
            job_limit=new_plan.job_limit,
            cv_limit=new_plan.cv_limit,
            ai_interview_limit=new_plan.ai_interview_limit,
            team_seat_limit=new_plan.team_seat_limit,
            credits_monthly=new_plan.credits_monthly,
            candidate_cv_uploads_limit=new_plan.candidate_cv_uploads_limit,
            candidate_ai_analyses_limit=new_plan.candidate_ai_analyses_limit,
            candidate_pdf_downloads_limit=new_plan.candidate_pdf_downloads_limit,
            candidate_job_matches_limit=new_plan.candidate_job_matches_limit,
            features=new_plan.features,
            permissions_json=new_plan.permissions_json,
        )
    )
    db.commit()
    db.refresh(new_plan)
    audit = AuditLog(
        user_id=current_user.id,
        action="create_plan",
        target_id=str(new_plan.id),
        details=f"Created subscription plan: {new_plan.name} ({new_plan.slug})",
    )
    db.add(audit)
    db.commit()
    return SubscriptionPlanSchema.model_validate(new_plan)


@router.get("/plans/{plan_id}")
def get_subscription_plan_detail(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return SubscriptionPlanSchema.model_validate(plan)


@router.get("/plans/{plan_id}/versions")
def get_subscription_plan_versions(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    versions = (
        db.query(PlanVersion)
        .filter(PlanVersion.plan_id == plan_id)
        .order_by(PlanVersion.version.desc(), PlanVersion.created_at.desc())
        .all()
    )
    return {
        "plan_id": plan_id,
        "plan_name": plan.name,
        "current_version": max((v.version for v in versions), default=1),
        "versions": [
            {
                "id": version.id,
                "plan_id": version.plan_id,
                "version": version.version,
                "name": version.name,
                "slug": version.slug,
                "price_monthly": version.price_monthly,
                "price_yearly": version.price_yearly,
                "currency": version.currency,
                "job_limit": version.job_limit,
                "cv_limit": version.cv_limit,
                "ai_interview_limit": version.ai_interview_limit,
                "team_seat_limit": version.team_seat_limit,
                "credits_monthly": version.credits_monthly,
                "candidate_cv_uploads_limit": version.candidate_cv_uploads_limit,
                "candidate_ai_analyses_limit": version.candidate_ai_analyses_limit,
                "candidate_pdf_downloads_limit": version.candidate_pdf_downloads_limit,
                "candidate_job_matches_limit": version.candidate_job_matches_limit,
                "features": version.features,
                "permissions_json": version.permissions_json,
                "valid_from": version.valid_from,
                "valid_to": version.valid_to,
                "created_at": version.created_at,
            }
            for version in versions
        ],
    }


@router.post("/plans/{plan_id}/activate")
def activate_subscription_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = True
    plan.updated_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return {"message": "Plan activated"}


@router.post("/plans/{plan_id}/archive")
def archive_subscription_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = False
    plan.updated_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return {"message": "Plan archived"}


@router.post("/plans/{plan_id}/duplicate")
def duplicate_subscription_plan(
    plan_id: int,
    payload: dict | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    source = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Plan not found")

    data = payload or {}
    slug = str(data.get("slug") or f"{source.slug}-copy-{uuid4().hex[:6]}")
    name = str(data.get("name") or f"{source.name} Copy")

    if db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == slug).first():
        raise HTTPException(status_code=400, detail="Duplicate slug already exists")

    duplicate = SubscriptionPlan(
        name=name,
        slug=slug,
        target_audience=source.target_audience,
        price_monthly=source.price_monthly,
        price_yearly=source.price_yearly,
        currency=source.currency,
        features=source.features,
        permissions_json=source.permissions_json,
        is_active=bool(data.get("is_active", source.is_active)),
        is_featured=bool(data.get("is_featured", source.is_featured)),
        job_limit=source.job_limit,
        cv_limit=source.cv_limit,
        ai_interview_limit=source.ai_interview_limit,
        team_seat_limit=source.team_seat_limit,
        candidate_cv_uploads_limit=source.candidate_cv_uploads_limit,
        candidate_ai_analyses_limit=source.candidate_ai_analyses_limit,
        candidate_pdf_downloads_limit=source.candidate_pdf_downloads_limit,
        candidate_job_matches_limit=source.candidate_job_matches_limit,
        credits_monthly=source.credits_monthly,
        plan_group=source.plan_group,
    )
    db.add(duplicate)
    db.flush()
    db.add(
        PlanVersion(
            plan_id=duplicate.id,
            version=1,
            name=duplicate.name,
            slug=duplicate.slug,
            price_monthly=duplicate.price_monthly,
            price_yearly=duplicate.price_yearly,
            currency=duplicate.currency,
            job_limit=duplicate.job_limit,
            cv_limit=duplicate.cv_limit,
            ai_interview_limit=duplicate.ai_interview_limit,
            team_seat_limit=duplicate.team_seat_limit,
            credits_monthly=duplicate.credits_monthly,
            candidate_cv_uploads_limit=duplicate.candidate_cv_uploads_limit,
            candidate_ai_analyses_limit=duplicate.candidate_ai_analyses_limit,
            candidate_pdf_downloads_limit=duplicate.candidate_pdf_downloads_limit,
            candidate_job_matches_limit=duplicate.candidate_job_matches_limit,
            features=duplicate.features,
            permissions_json=duplicate.permissions_json,
        )
    )
    db.commit()
    db.refresh(duplicate)
    return SubscriptionPlanSchema.model_validate(duplicate)


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanSchema)
def update_subscription_plan(
    plan_id: int,
    plan: SubscriptionPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    update_data = plan.model_dump(exclude_unset=True)
    if "slug" in update_data and update_data["slug"]:
        existing = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.slug == update_data["slug"])
            .first()
        )
        if existing and existing.id != plan_id:
            raise HTTPException(status_code=400, detail="Slug already exists")
    if "permissions_json" in update_data:
        update_data["permissions_json"] = update_data.get("permissions_json") or "{}"
    for key, value in update_data.items():
        setattr(db_plan, key, value)

    sensitive = {
        "price_monthly",
        "price_yearly",
        "currency",
        "job_limit",
        "cv_limit",
        "ai_interview_limit",
        "team_seat_limit",
        "credits_monthly",
        "candidate_cv_uploads_limit",
        "candidate_ai_analyses_limit",
        "candidate_pdf_downloads_limit",
        "candidate_job_matches_limit",
    }
    if sensitive.intersection(update_data.keys()):
        prev = (
            db.query(PlanVersion)
            .filter(PlanVersion.plan_id == plan_id)
            .order_by(PlanVersion.version.desc())
            .first()
        )
        db.add(
            PlanVersion(
                plan_id=db_plan.id,
                version=(prev.version + 1) if prev else 1,
                name=db_plan.name,
                slug=db_plan.slug,
                price_monthly=db_plan.price_monthly,
                price_yearly=db_plan.price_yearly,
                currency=db_plan.currency,
                job_limit=db_plan.job_limit,
                cv_limit=db_plan.cv_limit,
                ai_interview_limit=db_plan.ai_interview_limit,
                team_seat_limit=db_plan.team_seat_limit,
                credits_monthly=db_plan.credits_monthly,
                candidate_cv_uploads_limit=db_plan.candidate_cv_uploads_limit,
                candidate_ai_analyses_limit=db_plan.candidate_ai_analyses_limit,
                candidate_pdf_downloads_limit=db_plan.candidate_pdf_downloads_limit,
                candidate_job_matches_limit=db_plan.candidate_job_matches_limit,
                features=db_plan.features,
                permissions_json=db_plan.permissions_json,
            )
        )

    db.commit()
    db.refresh(db_plan)
    audit = AuditLog(
        user_id=current_user.id,
        action="update_plan",
        target_id=str(plan_id),
        details=f"Updated subscription plan: {db_plan.name}",
    )
    db.add(audit)
    db.commit()
    return SubscriptionPlanSchema.model_validate(db_plan)


@router.delete("/plans/{plan_id}")
def delete_subscription_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_name = db_plan.name
    db.delete(db_plan)
    db.commit()
    audit = AuditLog(
        user_id=current_user.id,
        action="delete_plan",
        target_id=str(plan_id),
        details=f"Deleted subscription plan: {plan_name}",
    )
    db.add(audit)
    db.commit()
    return {"message": "Plan deleted"}
