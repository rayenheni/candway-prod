"""Tests for the credit wallet / ledger service (Monetization S2).

Covers: wallet auto-creation, atomic consume, idempotency (no double-charge
on retry), insufficient-funds rejection, compensating rollback, usage-event
metering, and ledger/balance integrity.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from backend import credit_service
from backend.database import CreditTransaction


@pytest.fixture
def credit_user(db_session, test_company):
    from backend.database import User

    user = User(
        email="credits@example.com",
        name="Credit User",
        role="candidate",
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    user._company_id = test_company.id
    return user


def _balance(db, user):
    return float(credit_service.get_or_create_wallet(db, user).balance)


def test_wallet_auto_created_and_insufficient_rejected(db_session, credit_user):
    with pytest.raises(ValueError):
        credit_service.consume_credits(db_session, credit_user, 10, "cv_analysis")
    wallet = credit_service.get_or_create_wallet(db_session, credit_user)
    assert wallet is not None
    assert float(wallet.balance) == 0


def test_grant_consume_and_balance(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 30)
    assert _balance(db_session, credit_user) == 30
    credit_service.consume_credits(
        db_session, credit_user, 5, "cv_analysis", reference_type="app", reference_id=42
    )
    assert _balance(db_session, credit_user) == 25


def test_consume_is_idempotent_on_retry(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 30)
    first = credit_service.consume_credits(
        db_session, credit_user, 5, "cv_analysis", reference_type="app", reference_id=42
    )
    second = credit_service.consume_credits(
        db_session, credit_user, 5, "cv_analysis", reference_type="app", reference_id=42
    )
    assert second.id == first.id  # same ledger row, no double-debit
    assert _balance(db_session, credit_user) == 25


def test_drained_wallet_rejects(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 5)
    credit_service.consume_credits(
        db_session, credit_user, 5, "ai_search", reference_id=7
    )
    with pytest.raises(ValueError):
        credit_service.consume_credits(
            db_session, credit_user, 5, "ai_search", reference_id=8
        )


def test_rollback_restores_balance(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 10)
    tx = credit_service.consume_credits(
        db_session, credit_user, 3, "copilot_turn", reference_id=9
    )
    before = _balance(db_session, credit_user)
    credit_service.rollback_credits(db_session, tx)
    assert _balance(db_session, credit_user) == before + 3
    # rollback is itself a ledger row (reversal audit trail)
    rollbacks = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.type == "rollback")
        .count()
    )
    assert rollbacks == 1


def test_usage_event_recorded(db_session, credit_user, test_company):
    ev = credit_service.record_usage_event(
        db_session,
        credit_user.id,
        test_company.id,
        "cv_analysis",
        credits=5,
        cost_usd=0.002,
    )
    assert ev.id is not None
    assert ev.resource == "cv_analysis"
    assert ev.credits == 5


def test_ledger_balance_integrity(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 30)
    credit_service.consume_credits(
        db_session, credit_user, 5, "cv_analysis", reference_id=1
    )
    credit_service.consume_credits(
        db_session, credit_user, 20, "ai_search", reference_id=2
    )
    tx = credit_service.consume_credits(
        db_session, credit_user, 2, "copilot_turn", reference_id=3
    )
    credit_service.rollback_credits(db_session, tx)

    wallet = credit_service.get_or_create_wallet(db_session, credit_user)
    rows = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id)
        .all()
    )
    signed_sum = sum(float(r.amount) for r in rows)
    assert abs(signed_sum - float(wallet.balance)) < 0.001
    assert len(rows) == 5  # grant + 3 consumes (one consumed 20) + rollback


def test_idempotency_key_unique_constraint(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 10)
    credit_service.consume_credits(
        db_session, credit_user, 2, "ai_search", reference_type="app", reference_id=5
    )
    # Direct duplicate insert must violate the unique constraint
    wallet = credit_service.get_or_create_wallet(db_session, credit_user)
    dup = CreditTransaction(
        wallet_id=wallet.id,
        user_id=credit_user.id,
        company_id=wallet.company_id,
        amount=-2,
        type="consume",
        resource="ai_search",
        idempotency_key="consume:ai_search:5",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_multiple_wallets_are_per_user(db_session, credit_user, test_company_b):
    from backend.database import User

    other = User(
        email="other@example.com",
        name="Other",
        role="candidate",
        email_verified=True,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    credit_service.grant_credits(db_session, credit_user, 10)
    credit_service.grant_credits(db_session, other, 99)
    assert _balance(db_session, credit_user) == 10
    assert _balance(db_session, other) == 99


def test_adjust_credits_positive_and_negative(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 30)
    credit_service.adjust_credits(db_session, credit_user, 10, note="admin bonus")
    assert _balance(db_session, credit_user) == 40
    credit_service.adjust_credits(db_session, credit_user, -25, note="admin clawback")
    assert _balance(db_session, credit_user) == 15
    wallet = credit_service.get_or_create_wallet(db_session, credit_user)
    rows = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.wallet_id == wallet.id)
        .all()
    )
    adjustments = [r for r in rows if r.type == "adjustment"]
    assert len(adjustments) == 2
    assert all(r.actor_type == "admin" for r in adjustments)


def test_adjust_credits_rejects_overdraw(db_session, credit_user):
    credit_service.grant_credits(db_session, credit_user, 5)
    with pytest.raises(ValueError):
        credit_service.adjust_credits(db_session, credit_user, -10, note="overdraw")
    assert _balance(db_session, credit_user) == 5


def test_grant_credits_custom_type_and_actor(db_session, credit_user):
    tx = credit_service.grant_credits(
        db_session,
        credit_user,
        100,
        provider="manual",
        provider_ref="tx-999",
        note="credit pack purchase",
        tx_type="topup",
        actor_type="admin",
        actor_id=1,
    )
    assert tx.type == "topup"
    assert tx.provider == "manual"
    assert tx.provider_ref == "tx-999"
    assert tx.actor_type == "admin"
    assert _balance(db_session, credit_user) == 100
    # Idempotent: same key returns the same ledger row.
    again = credit_service.grant_credits(
        db_session,
        credit_user,
        100,
        provider="manual",
        provider_ref="tx-999",
        note="credit pack purchase",
        tx_type="topup",
        actor_type="admin",
        actor_id=1,
    )
    assert again.id == tx.id
    assert _balance(db_session, credit_user) == 100


def test_parse_credit_topup_detects_pack(db_session, credit_user, test_company):
    from backend.database import Transaction
    from backend.routers.admin.subscriptions import _parse_credit_topup

    tx = Transaction(
        user_id=credit_user.id,
        company_id=test_company.id,
        amount=50.0,
        currency="TND",
        status="pending",
        description="Credit top-up: 500 credits",
    )
    db_session.add(tx)
    db_session.commit()
    assert _parse_credit_topup(tx) == 500

    tx2 = Transaction(
        user_id=credit_user.id,
        company_id=test_company.id,
        amount=29.0,
        currency="TND",
        status="pending",
        description="Manual Upgrade to Pro",
    )
    db_session.add(tx2)
    db_session.commit()
    assert _parse_credit_topup(tx2) is None

    tx3 = Transaction(
        user_id=credit_user.id,
        company_id=test_company.id,
        amount=0.0,
        currency="TND",
        status="pending",
        description="Credit top-up: 0 credits",
    )
    db_session.add(tx3)
    db_session.commit()
    assert _parse_credit_topup(tx3) is None


def _make_owner(db, company, email="owner@example.com"):
    from backend.database import CompanyMember, User

    user = User(
        email=email,
        name="Company Owner",
        role="recruiter",
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    member = CompanyMember(
        company_id=company.id,
        user_id=user.id,
        role="owner",
        is_active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(user)
    return user


def test_resolve_company_billing_user_prefers_owner(
    db_session, test_company, test_user
):
    from backend.database import CompanyMember

    owner = _make_owner(db_session, test_company, "owner-a@example.com")
    # test_user is a 'member'; owner must win regardless of insertion order
    resolved = credit_service.resolve_company_billing_user(db_session, test_company.id)
    assert resolved is not None
    assert resolved.id == owner.id


def test_resolve_company_billing_user_falls_back_to_member(
    db_session, test_company, test_user
):
    # test_user is the only active member (role='member')
    resolved = credit_service.resolve_company_billing_user(db_session, test_company.id)
    assert resolved is not None
    assert resolved.id == test_user.id


def test_consume_company_credits_charges_owner_wallet(db_session, test_company):
    owner = _make_owner(db_session, test_company)
    credit_service.grant_credits(db_session, owner, 30)
    tx = credit_service.consume_company_credits(
        db_session,
        test_company.id,
        5,
        "ai_interview_evaluation",
        reference_type="application",
        reference_id=123,
    )
    assert tx is not None
    assert _balance(db_session, owner) == 25
    # idempotent per reference — same row, no double-debit
    tx2 = credit_service.consume_company_credits(
        db_session,
        test_company.id,
        5,
        "ai_interview_evaluation",
        reference_type="application",
        reference_id=123,
    )
    assert tx2.id == tx.id
    assert _balance(db_session, owner) == 25


def test_consume_company_credits_insufficient_returns_none(db_session, test_company):
    owner = _make_owner(db_session, test_company)
    # no credits granted — consume_company_credits swallows ValueError
    tx = credit_service.consume_company_credits(
        db_session, test_company.id, 5, "cv_analysis", reference_id=1
    )
    assert tx is None
    assert _balance(db_session, owner) == 0


def test_consume_company_credits_no_company_uses_fallback_user(
    db_session, test_company, credit_user
):
    # company_id=None (standalone) → fallback_user wallet is charged
    credit_service.grant_credits(db_session, credit_user, 10)
    tx = credit_service.consume_company_credits(
        db_session,
        None,
        3,
        "cv_analysis",
        reference_id=99,
        fallback_user=credit_user,
    )
    assert tx is not None
    assert _balance(db_session, credit_user) == 7


def test_consume_company_credits_no_resolvable_user_returns_none(
    db_session, test_company_b
):
    # company_b has no members → no charge, no crash
    tx = credit_service.consume_company_credits(
        db_session, test_company_b.id, 3, "cv_analysis", reference_id=1
    )
    assert tx is None


def _set_system_config(db, key, value):
    from backend.models import SystemConfig

    cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not cfg:
        cfg = SystemConfig(key=key)
        db.add(cfg)
    cfg.value = value
    db.commit()


def test_admin_cost_override_honored(db_session, credit_user):
    # Admin configures cv_analysis to cost 7 instead of the default 3
    _set_system_config(db_session, "ai_credit_cost_cv_analysis", "7")
    credit_service.grant_credits(db_session, credit_user, 30)
    credit_service.consume_credits(
        db_session, credit_user, 3, "cv_analysis", reference_type="app", reference_id=1
    )
    assert _balance(db_session, credit_user) == 23


def test_gating_disabled_makes_features_free(db_session, credit_user):
    # Gating off → consume is a no-op, no wallet debit, no ValueError
    _set_system_config(db_session, "ai_credit_gating_enabled", "false")
    tx = credit_service.consume_credits(
        db_session, credit_user, 3, "cv_analysis", reference_type="app", reference_id=1
    )
    assert tx is not None
    assert tx.id == 0  # synthetic free no-op
    assert _balance(db_session, credit_user) == 0
    # No ValueError even with zero balance


def test_zero_cost_makes_feature_free(db_session, credit_user):
    # Admin sets cv_analysis to 0 → free, regardless of wallet balance
    _set_system_config(db_session, "ai_credit_cost_cv_analysis", "0")
    tx = credit_service.consume_credits(
        db_session, credit_user, 3, "cv_analysis", reference_type="app", reference_id=1
    )
    assert tx.id == 0
    assert _balance(db_session, credit_user) == 0


def test_get_all_credit_pricing_returns_defaults(db_session):
    pricing = credit_service.get_all_credit_pricing(db_session)
    assert pricing["cv_analysis"] == 3
    assert pricing["ai_interview_evaluation"] == 5
    assert pricing["interview_question_gen"] == 5
    assert pricing["career_roadmap"] == 4
    assert pricing["jd_writer"] == 2
    assert "ai_search" in pricing
    assert "wizard_suggest" in pricing


def test_consume_company_credits_records_usage_event(db_session, test_company):
    from backend.database import UsageEvent

    owner = _make_owner(db_session, test_company)
    credit_service.grant_credits(db_session, owner, 30)
    credit_service.consume_company_credits(
        db_session,
        test_company.id,
        5,
        "ai_interview_evaluation",
        reference_type="application",
        reference_id=123,
    )
    events = (
        db_session.query(UsageEvent)
        .filter(UsageEvent.resource == "ai_interview_evaluation")
        .all()
    )
    assert len(events) == 1
    assert events[0].company_id == test_company.id
    assert events[0].user_id == owner.id
    assert events[0].credits == 5
    assert events[0].reference_id == 123
