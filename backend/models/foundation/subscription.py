"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, utcnow


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        Index("idx_subscription_plans_audience", "target_audience"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))  # e.g. "Pro Candidate", "Enterprise Recruiter"
    slug = Column(String(255), unique=True, index=True)  # e.g. "pro-candidate"

    target_audience = Column(String(50))  # 'candidate' or 'recruiter'

    price_monthly = Column(Float, default=0.0)
    price_yearly = Column(Float, default=0.0)
    currency = Column(String(10), default="TND")

    features = deferred(
        Column(Text)
    )  # JSON list of strings e.g. ["Verified Badge", "Priority Support"]
    permissions_json = deferred(
        Column(Text, default="{}")
    )  # Feature matrix: {"ghost_formatter": true, "talent_scout": false}

    # Limits (Recruiter-focused)
    job_limit = Column(Integer, default=5)
    cv_limit = Column(Integer, default=50)
    ai_interview_limit = Column(Integer, default=10)
    team_seat_limit = Column(Integer, default=1)

    # CANDIDATE SUBSCRIPTION ENHANCEMENT: Candidate-specific limits
    candidate_cv_uploads_limit = Column(Integer, default=2)  # CV uploads per month
    candidate_ai_analyses_limit = Column(Integer, default=1)  # AI analyses per month
    candidate_pdf_downloads_limit = Column(
        Integer, default=0
    )  # PDF downloads per month
    candidate_job_matches_limit = Column(Integer, default=5)  # Job matches shown

    # Billing / credit engine (S1 redesign)
    credits_monthly = Column(Integer, default=0)  # AI credits granted per cycle
    plan_group = Column(String(20), default="standard")  # free|standard|enterprise

    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    versions = relationship("PlanVersion", back_populates="plan")


class PlanVersion(Base):
    """Price/limit snapshot for grandfathering (S1 redesign).

    Every plan price/limit edit creates a new immutable version row; active
    subscriptions keep their version_id so price changes never hit them.
    """

    __tablename__ = "plan_versions"
    __table_args__ = (
        Index("idx_plan_versions_plan", "plan_id"),
        Index("idx_plan_versions_valid", "plan_id", "valid_from"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("subscription_plans.id"), nullable=False, index=True
    )

    version = Column(Integer, nullable=False, default=1)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)

    price_monthly = Column(Float, default=0.0)
    price_yearly = Column(Float, default=0.0)
    currency = Column(String(10), default="TND")

    job_limit = Column(Integer, default=5)
    cv_limit = Column(Integer, default=50)
    ai_interview_limit = Column(Integer, default=10)
    team_seat_limit = Column(Integer, default=1)
    credits_monthly = Column(Integer, default=0)

    candidate_cv_uploads_limit = Column(Integer, default=2)
    candidate_ai_analyses_limit = Column(Integer, default=1)
    candidate_pdf_downloads_limit = Column(Integer, default=0)
    candidate_job_matches_limit = Column(Integer, default=5)

    features = deferred(Column(Text))
    permissions_json = deferred(Column(Text, default="{}"))

    valid_from = Column(DateTime, default=utcnow)
    valid_to = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    plan = relationship("SubscriptionPlan", back_populates="versions")
