"""
Candidate Subscription Service
Handles usage tracking and limit enforcement for candidate subscriptions
"""

from datetime import UTC, datetime, timedelta

import logging

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from backend.database import SubscriptionPlan, User
from backend.models.evaluation.profile import CandidateProfile


logger = logging.getLogger(__name__)


class CandidateSubscriptionService:
    """Service for managing candidate subscriptions and usage limits"""

    @staticmethod
    def get_candidate_plan(user: User, db: Session) -> SubscriptionPlan:
        """Get the subscription plan for a candidate"""
        if user.role != "candidate":
            raise ValueError("User is not a candidate")

        # Get plan from database
        if user.current_plan_id:
            plan = (
                db.query(SubscriptionPlan)
                .filter(
                    SubscriptionPlan.id == user.current_plan_id,
                    SubscriptionPlan.target_audience == "candidate",
                )
                .first()
            )
            if plan:
                return plan

        # Fallback to free plan
        free_plan = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.slug == "free-candidate",
                SubscriptionPlan.target_audience == "candidate",
            )
            .first()
        )

        if not free_plan:
            # Create default free plan if it doesn't exist
            free_plan = SubscriptionPlan(
                name="Free Starter",
                slug="free-candidate",
                target_audience="candidate",
                price_monthly=0,
                price_yearly=0,
                currency="TND",
                candidate_cv_uploads_limit=2,
                candidate_ai_analyses_limit=1,
                candidate_pdf_downloads_limit=0,
                candidate_job_matches_limit=5,
                features='["Basic profile", "Limited job matching"]',
                is_active=True,
                credits_monthly=20,
                plan_group="free",
            )
            db.add(free_plan)
            db.commit()
            db.refresh(free_plan)

        return free_plan

    @staticmethod
    def reset_usage_if_needed(user: User, db: Session):
        """Reset monthly usage counters if the reset date has passed"""
        now = datetime.now(UTC).replace(tzinfo=None)

        cp = getattr(user, "candidate_profile", None)
        if not cp:
            return

        # Initialize reset date if not set
        if not cp.candidate_usage_reset_date:
            cp.candidate_usage_reset_date = now + timedelta(days=30)
            cp.candidate_cv_uploads_this_month = 0
            cp.candidate_ai_analyses_this_month = 0
            cp.candidate_pdf_downloads_this_month = 0
            db.commit()
            return

        # Reset if past reset date
        reset_date = cp.candidate_usage_reset_date
        if reset_date and reset_date.tzinfo is not None:
            reset_date = reset_date.replace(tzinfo=None)

        if reset_date < now:
            cp.candidate_usage_reset_date = now + timedelta(days=30)
            cp.candidate_cv_uploads_this_month = 0
            cp.candidate_ai_analyses_this_month = 0
            cp.candidate_pdf_downloads_this_month = 0
            db.commit()

    @staticmethod
    def check_cv_upload_limit(user: User, db: Session):
        """Check if user can upload a CV and increment counter (atomic)"""
        CandidateSubscriptionService.reset_usage_if_needed(user, db)

        plan = CandidateSubscriptionService.get_candidate_plan(user, db)

        limit = plan.candidate_cv_uploads_limit
        if limit == -1:
            return

        stmt = (
            update(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .where(
                (CandidateProfile.candidate_cv_uploads_this_month < limit)
                | (CandidateProfile.candidate_cv_uploads_this_month.is_(None))
            )
            .values(
                candidate_cv_uploads_this_month=CandidateProfile.candidate_cv_uploads_this_month
                + 1
            )
        )
        result = db.execute(stmt)
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=403,
                detail=f"CV upload limit reached ({limit}/month). Upgrade your plan for more uploads.",
            )
        db.commit()

    @staticmethod
    def check_ai_analysis_limit(user: User, db: Session):
        """Reserve one AI analysis from the candidate monthly allowance."""
        CandidateSubscriptionService.reset_usage_if_needed(user, db)

        plan = CandidateSubscriptionService.get_candidate_plan(user, db)

        limit = plan.candidate_ai_analyses_limit
        if limit == -1:
            return

        stmt = (
            update(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .where(
                (CandidateProfile.candidate_ai_analyses_this_month < limit)
                | (CandidateProfile.candidate_ai_analyses_this_month.is_(None))
            )
            .values(
                candidate_ai_analyses_this_month=func.coalesce(
                    CandidateProfile.candidate_ai_analyses_this_month, 0
                ) + 1
            )
        )

        result = db.execute(stmt)

        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=403,
                detail=f"AI analysis limit reached ({limit}/month). Upgrade your plan for more analyses.",
            )

        db.commit()

    @staticmethod
    def rollback_ai_analysis_limit(user: User, db: Session):
        """Return one reserved AI analysis after a failed analysis."""
        stmt = (
            update(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .where(
                CandidateProfile.candidate_ai_analyses_this_month.isnot(None)
            )
            .where(
                CandidateProfile.candidate_ai_analyses_this_month > 0
            )
            .values(
                candidate_ai_analyses_this_month=(
                    CandidateProfile.candidate_ai_analyses_this_month - 1
                )
            )
        )

        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            logger.warning(
                "AI analysis quota rollback skipped for user %s: "
                "no positive reservation found",
                user.id,
            )

    @staticmethod
    def check_pdf_download_limit(user: User, db: Session):
        """Check if user can download PDF report and increment counter (atomic)"""
        CandidateSubscriptionService.reset_usage_if_needed(user, db)

        plan = CandidateSubscriptionService.get_candidate_plan(user, db)

        limit = plan.candidate_pdf_downloads_limit
        if limit == -1:
            return

        stmt = (
            update(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .where(
                (CandidateProfile.candidate_pdf_downloads_this_month < limit)
                | (CandidateProfile.candidate_pdf_downloads_this_month.is_(None))
            )
            .values(
                candidate_pdf_downloads_this_month=CandidateProfile.candidate_pdf_downloads_this_month
                + 1
            )
        )
        result = db.execute(stmt)
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=403,
                detail=f"PDF download limit reached ({limit}/month). Upgrade your plan for more downloads.",
            )
        db.commit()

    @staticmethod
    def get_usage_stats(user: User, db: Session) -> dict:
        """Get current usage statistics for a candidate"""
        CandidateSubscriptionService.reset_usage_if_needed(user, db)

        plan = CandidateSubscriptionService.get_candidate_plan(user, db)
        cp = getattr(user, "candidate_profile", None)

        return {
            "plan_name": plan.name,
            "plan_slug": plan.slug,
            "cv_uploads": {
                "used": cp.candidate_cv_uploads_this_month if cp else 0,
                "limit": plan.candidate_cv_uploads_limit,
                "unlimited": plan.candidate_cv_uploads_limit == -1,
            },
            "ai_analyses": {
                "used": cp.candidate_ai_analyses_this_month if cp else 0,
                "limit": plan.candidate_ai_analyses_limit,
                "unlimited": plan.candidate_ai_analyses_limit == -1,
            },
            "pdf_downloads": {
                "used": cp.candidate_pdf_downloads_this_month if cp else 0,
                "limit": plan.candidate_pdf_downloads_limit,
                "unlimited": plan.candidate_pdf_downloads_limit == -1,
            },
            "reset_date": cp.candidate_usage_reset_date.isoformat()
            if cp and cp.candidate_usage_reset_date
            else None,
        }
