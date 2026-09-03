"""Subscription lifecycle core + immutable history (Monetization S3).

The ``Subscription`` row is the single source of truth for billing state;
profile columns (tier/subscription_status/subscription_end) become cached
denormalized mirrors. Every lifecycle event writes one immutable history
row plus an AuditLog row (existing pattern).

Manual activation flow only — no Stripe/Konnect/webhooks: user uploads bank
proof → Transaction(pending) → admin approve → Invoice + Subscription(active)
+ credits grant.
"""

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
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Subscription(Base, TenantMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("idx_subscriptions_user", "user_id"),
        Index("idx_subscriptions_plan", "plan_id"),
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_period_end", "current_period_end"),
        Index("idx_subscriptions_user_status", "user_id", "status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    plan_version_id = Column(Integer, ForeignKey("plan_versions.id"), nullable=True)

    # candidate|recruiter — derived from plan
    target_audience = Column(String(20), nullable=False, default="recruiter")

    # trialing|active|pending|past_due|expired|canceled
    status = Column(String(20), nullable=False, default="pending", index=True)

    billing_cycle = Column(
        String(10), nullable=False, default="monthly"
    )  # monthly|yearly

    started_at = Column(DateTime, nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True, index=True)
    grace_end = Column(DateTime, nullable=True)

    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime, nullable=True)
    reason_canceled = Column(String(255), nullable=True)

    last_payment_transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=True
    )
    renewal_reminder_sent = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User")
    plan = relationship("SubscriptionPlan")
    plan_version = relationship("PlanVersion")
    history = relationship(
        "SubscriptionHistory",
        back_populates="subscription",
        order_by="SubscriptionHistory.id",
    )


class SubscriptionHistory(Base, TenantMixin):
    """Immutable audit of every lifecycle event (Part 1.4)."""

    __tablename__ = "subscription_history"
    __table_args__ = (
        Index("idx_sub_history_subscription", "subscription_id"),
        Index("idx_sub_history_user", "user_id"),
        Index("idx_sub_history_transaction", "transaction_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # created|activated|extended|renewed|upgraded|downgraded|canceled|expired|
    # reinstate|payment_received|trial_started
    action = Column(String(30), nullable=False)

    from_plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    to_plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)

    amount_paid = Column(Float, nullable=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    subscription = relationship("Subscription", back_populates="history")
