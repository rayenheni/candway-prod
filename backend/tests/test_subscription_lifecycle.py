"""Tests for the subscription lifecycle service (Monetization S3).

Covers: activation creates the Subscription row + history + credit grant,
cancel/expire/reinstate transitions, and plan-change history.
"""

from datetime import UTC, datetime

import pytest

from backend import subscription_lifecycle_service as svc
from backend.database import CreditTransaction, Subscription, SubscriptionHistory
from backend.models.foundation.subscription import PlanVersion, SubscriptionPlan


@pytest.fixture
def test_plan(db_session):
    plan = SubscriptionPlan(
        name="Pro Test",
        slug="pro-test",
        target_audience="recruiter",
        price_monthly=149.0,
        currency="TND",
        credits_monthly=250,
        plan_group="standard",
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        PlanVersion(
            plan_id=plan.id,
            version=1,
            name=plan.name,
            slug=plan.slug,
            price_monthly=plan.price_monthly,
            credits_monthly=plan.credits_monthly,
        )
    )
    db_session.commit()
    db_session.refresh(plan)
    return plan


def test_activation_creates_subscription_and_history_and_credits(
    db_session, test_recruiter, test_plan, test_company
):
    test_recruiter._company_id = test_company.id
    sub = svc.activate_subscription(
        db_session, test_recruiter, test_plan, billing_cycle="yearly", admin_user_id=1
    )
    db_session.commit()

    assert sub.id is not None
    assert sub.status == "active"
    assert sub.plan_id == test_plan.id
    assert sub.target_audience == "recruiter"
    assert sub.current_period_end > datetime.now(UTC).replace(tzinfo=None)

    hist = (
        db_session.query(SubscriptionHistory)
        .filter(SubscriptionHistory.subscription_id == sub.id)
        .all()
    )
    assert len(hist) == 1
    assert hist[0].action == "activated"

    # Credit grant wired to activation
    credits = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.user_id == test_recruiter.id)
        .all()
    )
    assert len(credits) == 1
    assert credits[0].amount == 250


def test_cancel_immediate(db_session, test_recruiter, test_plan):
    sub = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()
    svc.cancel_subscription(db_session, sub, immediate=True)
    db_session.commit()

    assert sub.status == "canceled"
    assert sub.canceled_at is not None


def test_cancel_at_period_end(db_session, test_recruiter, test_plan):
    sub = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()
    svc.cancel_subscription(db_session, sub, immediate=False)
    db_session.commit()

    assert sub.status == "active"
    assert sub.cancel_at_period_end is True


def test_expire(db_session, test_recruiter, test_plan):
    sub = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()
    svc.expire_subscription(db_session, sub)
    db_session.commit()

    assert sub.status == "expired"


def test_reinstate_past_due(db_session, test_recruiter, test_plan):
    sub = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()
    sub.status = "past_due"
    db_session.commit()

    svc.reinstate_subscription(db_session, sub)
    db_session.commit()
    assert sub.status == "active"
    assert sub.grace_end is None


def test_reinstate_expired_raises(db_session, test_recruiter, test_plan):
    sub = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()
    sub.status = "expired"
    db_session.commit()
    with pytest.raises(ValueError):
        svc.reinstate_subscription(db_session, sub)


def test_reactivation_renews_instead_of_duplicate(
    db_session, test_recruiter, test_plan
):
    first = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()
    second = svc.activate_subscription(db_session, test_recruiter, test_plan)
    db_session.commit()

    assert first.id == second.id  # reused, not duplicated
    count = (
        db_session.query(Subscription)
        .filter(Subscription.user_id == test_recruiter.id)
        .count()
    )
    assert count == 1
