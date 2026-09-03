"""Subscription lifecycle service (Monetization S3).

Wraps the manual activation flow: admin approves a bank-transfer
Transaction → creates/updates the Subscription row (single source of
truth), writes an immutable SubscriptionHistory event, and grants the
plan's monthly credits. Profile tier/subscription_* columns remain cached
mirrors for read-compat.
"""

from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import (
    PlanVersion,
    Subscription,
    SubscriptionHistory,
    SubscriptionPlan,
    Transaction,
    User,
    CompanyMember
)
from backend.logger import logger

VALID_ACTIONS = {
    "created",
    "activated",
    "extended",
    "renewed",
    "upgraded",
    "downgraded",
    "canceled",
    "expired",
    "reinstate",
    "payment_received",
    "trial_started",
}


def log_subscription_history(
    db: Session,
    subscription: Subscription,
    action: str,
    amount_paid: Optional[float] = None,
    transaction: Optional[Transaction] = None,
    admin_user_id: Optional[int] = None,
    from_plan_id: Optional[int] = None,
    to_plan_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> SubscriptionHistory:
    """Append one immutable lifecycle event row."""
    if action not in VALID_ACTIONS:
        logger.warning(f"log_subscription_history: unknown action '{action}'")
    event = SubscriptionHistory(
        subscription_id=subscription.id,
        user_id=subscription.user_id,
        company_id=subscription.company_id,
        action=action,
        amount_paid=amount_paid,
        transaction_id=transaction.id if transaction else None,
        admin_user_id=admin_user_id,
        from_plan_id=from_plan_id,
        to_plan_id=to_plan_id,
        notes=notes,
    )
    db.add(event)
    return event


def _period_end(billing_cycle: str, start: datetime) -> datetime:
    days = 365 if billing_cycle == "yearly" else 30
    return start + timedelta(days=days)
def get_user_company_id(db: Session, user_id: int):
    return (
        db.query(CompanyMember.company_id)
        .filter(CompanyMember.user_id == user_id)
        .scalar()
    )

def get_or_create_subscription(db: Session, user: User) -> Subscription:
    """Return the user's active/pending subscription, creating one lazily."""
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.id.desc())
        .first()
    )
    if sub:
        return sub
    sub = Subscription(
        user_id=user.id,
        company_id=get_user_company_id(db, user.id), 
        plan_id=1,
        target_audience="recruiter" if user.role == "recruiter" else "candidate",
        status="pending",
        billing_cycle="monthly",
    )
    db.add(sub)
    db.flush()
    return sub


def activate_subscription(
    db: Session,
    user: User,
    plan: SubscriptionPlan,
    billing_cycle: str = "yearly",
    transaction: Optional[Transaction] = None,
    admin_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> Subscription:
    """Activate (create or renew) the user's Subscription row.

    Mirrors the existing approve flow semantics (existing code extends
    RecruiterProfile by 365 days); the Subscription row is the new source
    of truth. Returns the Subscription.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    plan_version_id = None
    try:
        pv = (
            db.query(PlanVersion)
            .filter(PlanVersion.plan_id == plan.id)
            .order_by(PlanVersion.version.desc())
            .first()
        )
        if pv:
            plan_version_id = pv.id
    except Exception as e:
        logger.warning(f"activate_subscription plan_version lookup failed: {e}")

    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "pending", "past_due", "trialing"]),
        )
        .order_by(Subscription.id.desc())
        .first()
    )
    if not sub:
        sub = Subscription(
            user_id=user.id,
            company_id=getattr(user, "_company_id", None) or 1,
            plan_id=plan.id,
            plan_version_id=plan_version_id,
            target_audience=plan.target_audience
            or ("recruiter" if user.role == "recruiter" else "candidate"),
        )
        db.add(sub)
        db.flush()

    from_plan_id = sub.plan_id
    sub.plan_id = plan.id
    sub.plan_version_id = plan_version_id
    sub.status = "active"
    sub.billing_cycle = billing_cycle
    sub.current_period_start = now
    sub.current_period_end = _period_end(billing_cycle, now)
    sub.grace_end = None
    sub.cancel_at_period_end = False
    sub.canceled_at = None
    sub.reason_canceled = None
    sub.renewal_reminder_sent = False
    if transaction:
        sub.last_payment_transaction_id = transaction.id
    if not sub.started_at:
        sub.started_at = now

    log_subscription_history(
        db,
        sub,
        action="activated",
        amount_paid=transaction.amount if transaction else None,
        transaction=transaction,
        admin_user_id=admin_user_id,
        from_plan_id=from_plan_id,
        to_plan_id=plan.id,
        notes=note or "Manual bank transfer approved by admin",
    )

    # Grant the plan's monthly credit allocation.
    if plan.credits_monthly:
        from backend.credit_service import grant_credits

        try:
            grant_credits(
                db,
                user,
                plan.credits_monthly,
                provider="admin",
                provider_ref=f"sub-activate-{sub.id}",
                note=f"Monthly credit allocation for {plan.slug}",
            )
        except Exception as e:
            logger.error(
                f"activate_subscription credit grant failed for user {user.id}: {e}"
            )

    db.flush()
    return sub


def cancel_subscription(
    db: Session,
    sub: Subscription,
    reason: str = "Canceled by admin",
    admin_user_id: Optional[int] = None,
    immediate: bool = False,
) -> Subscription:
    if immediate:
        sub.status = "canceled"
        sub.canceled_at = datetime.now(UTC).replace(tzinfo=None)
        sub.reason_canceled = reason
        log_subscription_history(
            db, sub, "canceled", admin_user_id=admin_user_id, notes=reason
        )
    else:
        sub.cancel_at_period_end = True
        log_subscription_history(
            db,
            sub,
            "canceled",
            admin_user_id=admin_user_id,
            notes=f"{reason} (effective at period end)",
        )
    return sub


def expire_subscription(
    db: Session,
    sub: Subscription,
    reason: str = "Subscription period ended",
    admin_user_id: Optional[int] = None,
) -> Subscription:
    sub.status = "expired"
    sub.reason_canceled = reason
    log_subscription_history(
        db, sub, "expired", admin_user_id=admin_user_id, notes=reason
    )
    return sub


def reinstate_subscription(
    db: Session,
    sub: Subscription,
    admin_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> Subscription:
    if sub.status in ("expired", "canceled"):
        raise ValueError(
            f"Cannot reinstate a {sub.status} subscription; activate a new one instead."
        )
    sub.status = "active"
    sub.cancel_at_period_end = False
    sub.grace_end = None
    log_subscription_history(
        db,
        sub,
        "reinstate",
        admin_user_id=admin_user_id,
        notes=note or "Reinstated by admin",
    )
    return sub
