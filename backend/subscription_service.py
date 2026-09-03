import json

from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import SubscriptionPlan, User
from backend.models.foundation.company import CompanyMember
from backend.models.finance.subscription import Subscription
from backend.logger import logger
from backend.models.evaluation.profile import RecruiterProfile

settings = get_settings()

# Whitelist of allowed column names — single source of truth
# Any change here must be reviewed for security implications
_USAGE_FIELDS = {
    "create_job": "usage_jobs",
    "analyze_cv": "usage_cvs",
    "conduct_interview": "usage_ai_interviews",
}

_USAGE_LIMITS = {}


class SubscriptionService:
    @staticmethod
    def get_user_plan(user: User, db: Session) -> SubscriptionPlan:
        """
        Resolve the effective recruiter plan.

        Priority:
        1. Active company subscription for company-managed recruiters.
        2. Recruiter's own profile plan.
        3. User's own plan.
        4. Free recruiter fallback.

        Company subscription is authoritative for company-managed recruiters.
        """

        # ---------------------------------------------------------
        # 1. Company-managed recruiter
        # ---------------------------------------------------------
        membership = (
            db.query(CompanyMember)
            .filter(
                CompanyMember.user_id == user.id,
                CompanyMember.is_active == True,  # noqa: E712
            )
            .first()
        )

        if membership:
            company_subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == membership.company_id,
                    Subscription.status == "active",
                )
                .order_by(Subscription.id.desc())
                .first()
            )

            if company_subscription:
                company_plan = (
                    db.query(SubscriptionPlan)
                    .filter(
                        SubscriptionPlan.id == company_subscription.plan_id,
                        SubscriptionPlan.is_active == True,
                    )
                    .first()
                )

                if company_plan:
                    logger.info(
                        "Resolved company subscription for user %s: "
                        "company_id=%s subscription_id=%s plan=%s job_limit=%s",
                        user.id,
                        membership.company_id,
                        company_subscription.id,
                        company_plan.slug,
                        company_plan.job_limit,
                    )
                    return company_plan

        # ---------------------------------------------------------
        # 2. Individual recruiter profile plan
        # ---------------------------------------------------------
        profile_plan_id = getattr(
            getattr(user, "recruiter_profile", None),
            "current_plan_id",
            None,
        )

        plan_id = profile_plan_id or user.current_plan_id

        if plan_id:
            plan = (
                db.query(SubscriptionPlan)
                .filter(
                    SubscriptionPlan.id == plan_id,
                    SubscriptionPlan.is_active == True,
                )
                .first()
            )

            if plan:
                return plan

        # ---------------------------------------------------------
        # 3. Free recruiter fallback
        # ---------------------------------------------------------
        default_plan = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.slug == "free_recruiter",
                SubscriptionPlan.is_active == True,
            )
            .first()
        )

        if not default_plan:
            default_plan = SubscriptionPlan(
                name="Free Tier",
                slug="free_recruiter",
                target_audience="recruiter",
                price_monthly=0,
                currency="TND",
                job_limit=3,
                cv_limit=20,
                ai_interview_limit=5,
                credits_monthly=25,
                plan_group="free",
            )
            db.add(default_plan)
            db.commit()
            db.refresh(default_plan)

        return default_plan

    @staticmethod
    def _subscription_expired(user: User) -> bool:
        from datetime import UTC, datetime

        profile = getattr(user, "recruiter_profile", None)
        if not profile:
            return False
        end = getattr(profile, "subscription_end", None)
        if end is None:
            return False
        if end.tzinfo is not None:
            end = end.replace(tzinfo=None)
        return end < datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def has_feature(user: User, feature_key: str, db: Session) -> bool:
        if user.role == "admin":
            return True

        if SubscriptionService._subscription_expired(user):
            return False

        # S7: primary evaluation goes through the DB-backed feature_service,
        # which consults FeatureFlag rows and falls back to the legacy
        # permissions_json plan matrix so both systems coexist during migration.
        try:
            from backend.services.feature_service import has_feature as _ff_has_feature

            return _ff_has_feature(db, feature_key, user)
        except Exception as e:
            logger.warning(f"FeatureFlag override check failed for {feature_key}: {e}")

        plan = SubscriptionService.get_user_plan(user, db)
        if not plan:
            return False

        try:
            permissions = json.loads(plan.permissions_json or "{}")
            return permissions.get(feature_key, False)
        except Exception as e:
            logger.error(f"Error parsing permissions for user {user.id}: {e}")
            return False

    @staticmethod
    def can_perform_action(user: User, action_type: str, db: Session) -> bool:
        """Check quota without consuming it."""
        if user.role == "admin":
            return True

        if SubscriptionService._subscription_expired(user):
            return False

        plan = SubscriptionService.get_user_plan(user, db)
        if not plan:
            return False

        action_map = {
            "create_job": ("usage_jobs", plan.job_limit),
            "analyze_cv": ("usage_cvs", plan.cv_limit),
            "conduct_interview": (
                "usage_ai_interviews",
                plan.ai_interview_limit,
            ),
        }

        if action_type not in action_map:
            return False

        field, limit = action_map[action_type]

        if limit == -1:
            return True

        profile = getattr(user, "recruiter_profile", None)
        if not profile:
            return False

        current_usage = getattr(profile, field, 0) or 0

        return current_usage < limit

    @staticmethod
    def record_usage(
        user: User,
        action_type: str,
        db: Session,
        commit: bool = True,
    ) -> bool:
        """
        Consume exactly one quota unit.

        Returns:
            True  -> quota consumed
            False -> quota unavailable / invalid action
        """
        if user.role == "admin":
            return True

        field = _USAGE_FIELDS.get(action_type)
        if field is None:
            return False

        plan = SubscriptionService.get_user_plan(user, db)
        if not plan:
            return False

        limits = {
            "create_job": plan.job_limit,
            "analyze_cv": plan.cv_limit,
            "conduct_interview": plan.ai_interview_limit,
        }

        limit = limits.get(action_type)
        if limit is None:
            return False

        # Unlimited
        if limit == -1:
            stmt = (
                update(RecruiterProfile)
                .where(RecruiterProfile.user_id == user.id)
                .values(**{
                    field: getattr(RecruiterProfile, field) + 1
                })
            )
        else:
            # Atomic quota consumption.
            stmt = (
                update(RecruiterProfile)
                .where(RecruiterProfile.user_id == user.id)
                .where(getattr(RecruiterProfile, field) < limit)
                .values(**{
                    field: getattr(RecruiterProfile, field) + 1
                })
            )

        try:
            result = db.execute(stmt)

            if result.rowcount != 1:
                db.rollback()
                return False

            if commit:
                db.commit()

            return True

        except Exception as e:
            logger.error(
                "record_usage failed for user %s action=%s: %s",
                user.id,
                action_type,
                e,
            )
            db.rollback()
            return False

    @staticmethod
    def decrement_usage(user: User, action_type: str, db: Session):
        if user.role == "admin":
            return

        field = _USAGE_FIELDS.get(action_type)
        if field is None:
            return

        try:
            stmt = (
                update(RecruiterProfile)
                .where(RecruiterProfile.user_id == user.id)
                .where(getattr(RecruiterProfile, field) > 0)
                .values(**{field: getattr(RecruiterProfile, field) - 1})
            )
            db.execute(stmt)
            db.commit()
        except Exception as e:
            logger.error(f"decrement_usage failed for user {user.id}: {e}")
            db.rollback()
