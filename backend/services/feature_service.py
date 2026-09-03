"""Feature evaluation service (Monetization S7).

Single choke point for resolving whether a feature is enabled for a given
user+company. It is deliberately DB-backed so admins can toggle anything in
the Admin Panel with zero code deploys (see MONETIZATION_DESIGN.md Part 3).

This module must NOT import backend.subscription_service (circular guard):
the legacy plan permissions_json matrix is read directly here.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from backend.database import FeatureFlag, User
from backend.database import SubscriptionPlan as SubscriptionPlanModel
from backend.logger import logger


def get_feature_flag(
    db: Session, feature_key: str, company_id: Optional[int] = None
) -> Optional[FeatureFlag]:
    """Global (non-user-scoped) definition row for a feature key.

    Scoped to a company when company_id is provided; otherwise falls back to
    a non-scoped lookup (single-company deployments).
    """
    q = db.query(FeatureFlag).filter(
        FeatureFlag.flag_key == feature_key, FeatureFlag.user_id.is_(None)
    )
    if company_id is not None:
        q = q.filter(FeatureFlag.company_id == company_id)
    return q.first()


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check_rollout(flag: FeatureFlag, user_id: int) -> bool:
    """Deterministic rollout check based on user ID."""
    if flag.rollout_percentage is None or flag.rollout_percentage >= 100:
        return True
    if flag.rollout_percentage <= 0:
        return False
    hash_input = f"{flag.flag_key}:{user_id}"
    hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100
    return hash_val < flag.rollout_percentage


def _legacy_plan_matrix(user: User, db: Session, feature_key: str) -> Optional[bool]:
    """Read the legacy permissions_json plan matrix directly.

    Returns None when no plan exists or the key is absent, so callers can
    fall through to the flag row / default.
    """
    try:
        if user.current_plan_id:
            plan = (
                db.query(SubscriptionPlanModel)
                .filter(SubscriptionPlanModel.id == user.current_plan_id)
                .first()
            )
        else:
            plan = (
                db.query(SubscriptionPlanModel)
                .filter(SubscriptionPlanModel.slug == "free_recruiter")
                .first()
            )
        if not plan:
            return None
        permissions = json.loads(plan.permissions_json or "{}")
        return permissions.get(feature_key)
    except Exception as e:  # noqa: BLE001
        logger.error(f"feature_service plan-matrix error for user {user.id}: {e}")
        return None


def _plan_slug_allowed(flag: FeatureFlag, user: User, db: Session) -> bool:
    """plan_restrictions is a CSV of allowed plan slugs; empty/None = unrestricted."""
    restrictions = (flag.plan_restrictions or "").strip()
    if not restrictions:
        return True
    allowed = {s.strip() for s in restrictions.split(",") if s.strip()}
    if not allowed:
        return True
    slug = ""
    try:
        if user.current_plan_id:
            plan = (
                db.query(SubscriptionPlanModel)
                .filter(SubscriptionPlanModel.id == user.current_plan_id)
                .first()
            )
        else:
            plan = (
                db.query(SubscriptionPlanModel)
                .filter(SubscriptionPlanModel.slug == "free_recruiter")
                .first()
            )
        slug = plan.slug if plan else ""
    except Exception as e:  # noqa: BLE001
        logger.error(f"feature_service plan-slug error for user {user.id}: {e}")
    return slug in allowed


def _is_per_user_unlocked(flag: FeatureFlag, user: User) -> bool:
    if flag.permanent_unlock_user_id is not None:
        if flag.permanent_unlock_user_id == user.id:
            return True
    if flag.temp_unlock_user_id is not None:
        if flag.temp_unlock_user_id == user.id:
            if flag.temp_unlock_until is None:
                return True
            if _utcnow() <= flag.temp_unlock_until.replace(tzinfo=None):
                return True
    return False


def _resolve_company_override(
    flag: FeatureFlag, user: User, db: Session, company_id: Optional[int] = None
) -> Optional[bool]:
    """Resolve per-company override using the flag's company_override_key."""
    override_key = flag.company_override_key
    if not override_key:
        return None
    if company_id is None:
        company_id = getattr(user, "company_id", None)
        if company_id is None:
            company = getattr(user, "company", None)
            if company is not None:
                company_id = getattr(company, "id", None)
    if company_id is None:
        return None
    row = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.flag_key == override_key,
            FeatureFlag.user_id.is_(None),
            FeatureFlag.company_id == company_id,
        )
        .first()
    )
    if row is not None:
        return bool(row.enabled)
    return None


def feature_enabled(
    db: Session, feature_key: str, user: User, company_id: Optional[int] = None
) -> Tuple[bool, str]:
    """Evaluate a feature for a user+company. Returns (enabled, reason).

    Reasons: 'maintenance', 'admin_only', 'audience', 'plan', 'rollout',
    'override', 'company_override', 'flag', 'plan_matrix', 'missing'.
    """
    if user.role == "admin":
        return True, "admin"

    if company_id is None:
        company_id = getattr(user, "company_id", None)
        if company_id is None:
            company = getattr(user, "company", None)
            if company is not None:
                company_id = getattr(company, "id", None)

    flag = get_feature_flag(db, feature_key, company_id)

    if flag is not None:
        if flag.kill_switch or flag.maintenance_mode:
            return False, "maintenance"
        if flag.visibility == "internal" and user.role != "admin":
            return False, "admin_only"
        if flag.audiences not in ("all", user.role):
            return False, "audience"
        if not _plan_slug_allowed(flag, user, db):
            return False, "plan"
        if _is_per_user_unlocked(flag, user):
            return True, "override"
        company_override = _resolve_company_override(flag, user, db, company_id)
        if company_override is not None:
            return company_override, "company_override"
        if not _check_rollout(flag, user.id):
            return False, "rollout"
        return bool(flag.enabled), "flag"

    # No flag row → legacy plan permissions_json matrix.
    matrix = _legacy_plan_matrix(user, db, feature_key)
    if matrix is not None:
        return matrix, "plan_matrix"
    return False, "missing"


def has_feature(
    db: Session, feature_key: str, user: User, company_id: Optional[int] = None
) -> bool:
    """Convenience boolean wrapper over feature_enabled()."""
    enabled, _reason = feature_enabled(db, feature_key, user, company_id)
    return enabled
