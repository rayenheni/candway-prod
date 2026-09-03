"""
Feature Flags API
==================
Manages feature flags for gradual rollout of new features.
Supports global flags and per-user overrides.
"""

import hashlib
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import FeatureFlag, User
from backend.dependencies import get_current_user, get_db, require_admin
from backend.logger import logger
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])

DEFAULT_FLAGS = {
    "recruiter_enhancements": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "All recruiter v5.0 enhancements",
    },
    "recruiter_onboarding_tour": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Interactive onboarding tour for recruiters",
    },
    "recruiter_help_center": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Help center modal with FAQ and guides",
    },
    "recruiter_tooltips": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Contextual tooltips across recruiter UI",
    },
    "ai_debrief": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "AI-powered interview debrief summaries",
    },
    "automation_rules": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Pipeline automation rules engine",
    },
    "scorecards": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Interview scorecard system",
    },
    "webhook_integrations": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Webhook integrations for external systems",
    },
    # ── V1 monetization flag set (MONETIZATION_DESIGN.md §10.6) ──────
    "ai_interview": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "AI interview module",
    },
    "ghost_report": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Anonymized ghost candidate reports",
    },
    "talent_scout": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "AI talent sourcing agent",
    },
    "ai_copilot": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Recruiter AI copilot chat",
    },
    "ai_search_rerank": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "AI search re-ranking",
    },
    "career_roadmap": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Candidate career roadmap",
    },
    "cv_enriched_review": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Enriched CV review",
    },
    "recruiter_desktop": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Recruiter desktop workspace",
    },
    "translation": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "AI translation",
    },
    "bulk_import": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Bulk candidate import",
    },
    "maintenance_mode": {
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Global maintenance kill switch",
    },
    "payments_enabled": {
        "enabled": True,
        "rollout_percentage": 100,
        "description": "Manual bank transfer payments",
    },
}


class FlagResponse(BaseModel):
    key: str
    enabled: bool
    rollout_percentage: int
    description: Optional[str] = None
    visibility: str = "public"
    audiences: str = "all"
    maintenance_mode: bool = False
    kill_switch: bool = False
    depends_on: Optional[str] = None
    plan_restrictions: Optional[str] = None
    company_override_key: Optional[str] = None
    temp_unlock_user_id: Optional[int] = None
    temp_unlock_until: Optional[datetime] = None
    permanent_unlock_user_id: Optional[int] = None


class FlagUpdate(BaseModel):
    enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    audiences: Optional[str] = None
    maintenance_mode: Optional[bool] = None
    kill_switch: Optional[bool] = None
    depends_on: Optional[str] = None
    plan_restrictions: Optional[str] = None
    company_override_key: Optional[str] = None
    temp_unlock_user_id: Optional[int] = None
    temp_unlock_until: Optional[datetime] = None
    permanent_unlock_user_id: Optional[int] = None


class FlagCreate(BaseModel):
    key: str
    enabled: bool = False
    rollout_percentage: int = 0
    description: Optional[str] = None
    visibility: str = "public"
    audiences: str = "all"
    maintenance_mode: bool = False
    kill_switch: bool = False
    depends_on: Optional[str] = None
    plan_restrictions: Optional[str] = None
    company_override_key: Optional[str] = None
    temp_unlock_user_id: Optional[int] = None
    temp_unlock_until: Optional[datetime] = None
    permanent_unlock_user_id: Optional[int] = None


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _check_rollout(flag: FeatureFlag, user_id: int) -> bool:
    """Deterministic rollout check based on user ID"""
    if flag.rollout_percentage >= 100:
        return True
    if flag.rollout_percentage <= 0:
        return False
    hash_input = f"{flag.flag_key}:{user_id}"
    hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100
    return hash_val < flag.rollout_percentage


@router.get("/config")
def get_feature_flags(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all active feature flags for the current user"""
    global_flags = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.flag_key.in_(list(DEFAULT_FLAGS.keys())),
            FeatureFlag.user_id is None,
            FeatureFlag.enabled,
        )
        .all()
    )

    user_flags = (
        db.query(FeatureFlag).filter(FeatureFlag.user_id == current_user.id).all()
    )

    result = {}
    for flag in global_flags:
        if _check_rollout(flag, current_user.id):
            result[flag.flag_key] = True

    for flag in user_flags:
        result[flag.flag_key] = flag.enabled

    for key, default in DEFAULT_FLAGS.items():
        if key not in result and default["enabled"]:
            result[key] = True

    return result


@router.get("/config/{flag_key}")
def get_flag(
    flag_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if a specific flag is enabled for the current user"""
    user_flag = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.flag_key == flag_key, FeatureFlag.user_id == current_user.id
        )
        .first()
    )

    if user_flag:
        return {"key": flag_key, "enabled": user_flag.enabled}

    global_flag = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.flag_key == flag_key,
            FeatureFlag.user_id is None,
            FeatureFlag.enabled,
        )
        .first()
    )

    if global_flag:
        enabled = _check_rollout(global_flag, current_user.id)
        return {"key": flag_key, "enabled": enabled}

    default = DEFAULT_FLAGS.get(flag_key, {})
    return {"key": flag_key, "enabled": default.get("enabled", False)}


@router.get("/", response_model=List[dict])
def list_all_flags(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """List all feature flags for the admin's company (admin only)"""
    flags = (
        db.query(FeatureFlag)
        .filter(FeatureFlag.company_id == company_id)
        .order_by(FeatureFlag.flag_key)
        .all()
    )
    result = []
    for f in flags:
        result.append(
            {
                "id": f.id,
                "flag_key": f.flag_key,
                "user_id": f.user_id,
                "enabled": f.enabled,
                "rollout_percentage": f.rollout_percentage,
                "description": f.description,
                "visibility": f.visibility,
                "audiences": f.audiences,
                "maintenance_mode": f.maintenance_mode,
                "kill_switch": f.kill_switch,
                "depends_on": f.depends_on,
                "plan_restrictions": f.plan_restrictions,
                "company_override_key": f.company_override_key,
                "temp_unlock_user_id": f.temp_unlock_user_id,
                "temp_unlock_until": f.temp_unlock_until.isoformat()
                if f.temp_unlock_until
                else None,
                "permanent_unlock_user_id": f.permanent_unlock_user_id,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
        )
    return result


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_flag(
    data: FlagCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Create a new feature flag (admin only)"""
    existing = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.flag_key == data.key,
            FeatureFlag.user_id.is_(None),
            FeatureFlag.company_id == company_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Flag already exists")

    flag = FeatureFlag(
        flag_key=data.key,
        company_id=company_id,
        enabled=data.enabled,
        rollout_percentage=data.rollout_percentage,
        description=data.description,
        visibility=data.visibility or "public",
        audiences=data.audiences or "all",
        maintenance_mode=data.maintenance_mode,
        kill_switch=data.kill_switch,
        depends_on=data.depends_on,
        plan_restrictions=data.plan_restrictions,
        company_override_key=data.company_override_key,
        temp_unlock_user_id=data.temp_unlock_user_id,
        temp_unlock_until=data.temp_unlock_until,
        permanent_unlock_user_id=data.permanent_unlock_user_id,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)

    logger.info(f"Feature flag created: {flag.flag_key} by {admin.email}")
    return {"success": True, "flag_id": flag.id}


@router.patch("/{flag_id}")
def update_flag(
    flag_id: int,
    data: FlagUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Update a feature flag (admin only)"""
    flag = (
        db.query(FeatureFlag)
        .filter(FeatureFlag.id == flag_id, FeatureFlag.company_id == company_id)
        .first()
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    if data.enabled is not None:
        flag.enabled = data.enabled
    if data.rollout_percentage is not None:
        flag.rollout_percentage = max(0, min(100, data.rollout_percentage))
    if data.description is not None:
        flag.description = data.description
    if data.visibility is not None:
        flag.visibility = data.visibility
    if data.audiences is not None:
        flag.audiences = data.audiences
    if data.maintenance_mode is not None:
        flag.maintenance_mode = data.maintenance_mode
    if data.kill_switch is not None:
        flag.kill_switch = data.kill_switch
    if data.depends_on is not None:
        flag.depends_on = data.depends_on
    if data.plan_restrictions is not None:
        flag.plan_restrictions = data.plan_restrictions
    if data.company_override_key is not None:
        flag.company_override_key = data.company_override_key
    if data.temp_unlock_user_id is not None:
        flag.temp_unlock_user_id = data.temp_unlock_user_id
    if data.temp_unlock_until is not None:
        flag.temp_unlock_until = data.temp_unlock_until
    if data.permanent_unlock_user_id is not None:
        flag.permanent_unlock_user_id = data.permanent_unlock_user_id

    flag.updated_at = _utcnow()
    db.commit()

    logger.info(f"Feature flag updated: {flag.flag_key} by {admin.email}")
    return {"success": True}


@router.delete("/{flag_id}")
def delete_flag(
    flag_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Delete a feature flag (admin only)"""
    flag = (
        db.query(FeatureFlag)
        .filter(FeatureFlag.id == flag_id, FeatureFlag.company_id == company_id)
        .first()
    )
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    db.delete(flag)
    db.commit()
    return {"success": True}


@router.post("/seed")
def seed_default_flags(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
):
    """Seed default feature flags for the admin's company (admin only)"""
    created = 0
    for key, default in DEFAULT_FLAGS.items():
        existing = (
            db.query(FeatureFlag)
            .filter(
                FeatureFlag.flag_key == key,
                FeatureFlag.user_id.is_(None),
                FeatureFlag.company_id == company_id,
            )
            .first()
        )
        if not existing:
            flag = FeatureFlag(
                flag_key=key,
                company_id=company_id,
                enabled=default["enabled"],
                rollout_percentage=default["rollout_percentage"],
                description=default["description"],
                visibility=default.get("visibility", "public"),
                audiences=default.get("audiences", "all"),
                maintenance_mode=default.get("maintenance_mode", False),
                kill_switch=default.get("kill_switch", False),
            )
            db.add(flag)
            created += 1

    if created > 0:
        db.commit()
        logger.info(f"Seeded {created} default feature flags")

    return {"success": True, "created": created}
