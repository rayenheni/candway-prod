"""P0-3 regression: consume idempotency is scoped to the debited wallet.

Before the fix the idempotency key was global: ``consume:{resource}:{ref}``.
The candidate CV review (``cv_analysis``, reference = candidate's latest
application id) and the company apply-time CV analysis (``cv_analysis``,
reference = the JOB application id) could produce the SAME key, so:

  - whichever charge ran second silently returned the first wallet's ledger
    row (that wallet was never charged), and
  - a failure refund of one flow reversed the OTHER wallet's charge.

A refunded (reversed) charge also blocked every retry forever (free retries).

These tests drive the same credit calls the endpoints make:
  candidate review  -> consume_credits_or_402(..., reference_type="cv_review")
                       + rollback_credits on AI failure   (routers/candidate/cv.py)
  company apply     -> consume_credits_in_transaction(billing owner,
                       reference_type="application")      (routers/candidate/jobs.py)
                       + _refund_application_cv_analysis on analysis failure
                                                          (routers/candidate/applications.py)
"""

import pytest
from fastapi import HTTPException

from backend import credit_service
from backend.database import CreditTransaction, User
from backend.routers.candidate.applications import _refund_application_cv_analysis

APP_ID = 4242  # the same application id referenced by both flows
COST = 3  # default cv_analysis price; pricing is not changed by this fix


def _mk_user(db, email, role="candidate"):
    user = User(email=email, name=email, role=role, email_verified=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def wallets(db_session, test_company, company_billing_owner):
    candidate = _mk_user(db_session, "cand-p03@example.com")
    credit_service.grant_credits(db_session, candidate, 10)
    owner = credit_service.resolve_company_billing_user(db_session, test_company.id)
    assert owner is not None
    return candidate, owner


def _balance(db, user):
    db.expire_all()
    return float(credit_service.get_or_create_wallet(db, user).balance)


def _candidate_review_charge(db, candidate, ref=APP_ID):
    return credit_service.consume_credits_or_402(
        db, candidate, COST, "cv_analysis", reference_type="cv_review", reference_id=ref
    )


def _company_apply_charge(db, owner, ref=APP_ID):
    tx = credit_service.consume_credits_in_transaction(
        db, owner, COST, "cv_analysis", reference_type="application", reference_id=ref
    )
    db.commit()
    return tx


# ── 1. CV review failure refunds the candidate only ───────────────────────
def test_candidate_review_failure_refunds_candidate_only(db_session, wallets):
    candidate, owner = wallets
    owner_start = _balance(db_session, owner)

    company_tx = _company_apply_charge(db_session, owner)
    candidate_tx = _candidate_review_charge(db_session, candidate)

    assert candidate_tx.id != company_tx.id
    assert candidate_tx.wallet_id != company_tx.wallet_id
    assert _balance(db_session, candidate) == 10 - COST
    assert _balance(db_session, owner) == owner_start - COST

    # AI failure in the review endpoint -> rollback_credits(candidate charge)
    credit_service.rollback_credits(db_session, candidate_tx)

    assert _balance(db_session, candidate) == 10
    assert _balance(db_session, owner) == owner_start - COST
    db_session.refresh(company_tx)
    assert company_tx.status == "succeeded"


# ── 2. Company apply charge untouched / actually charged ──────────────────
def test_company_apply_charge_not_absorbed_by_prior_candidate_charge(
    db_session, wallets
):
    """Candidate review first, company apply second: the company MUST be
    charged (the old global key returned the candidate's row instead)."""
    candidate, owner = wallets
    owner_start = _balance(db_session, owner)

    candidate_tx = _candidate_review_charge(db_session, candidate)
    company_tx = _company_apply_charge(db_session, owner)

    assert company_tx.id != candidate_tx.id
    assert company_tx.user_id == owner.id
    assert _balance(db_session, owner) == owner_start - COST
    assert _balance(db_session, candidate) == 10 - COST


def test_application_analysis_refund_targets_company_charge_only(db_session, wallets):
    """_refund_application_cv_analysis must reverse the company apply charge,
    never the candidate's CV-review charge on the same application id —
    whichever was created last."""
    candidate, owner = wallets
    owner_start = _balance(db_session, owner)

    company_tx = _company_apply_charge(db_session, owner)
    candidate_tx = _candidate_review_charge(db_session, candidate)  # newer row

    assert _refund_application_cv_analysis(db_session, APP_ID) is True
    db_session.commit()

    db_session.refresh(company_tx)
    db_session.refresh(candidate_tx)
    assert company_tx.status == "reversed"
    assert candidate_tx.status == "succeeded"
    assert _balance(db_session, owner) == owner_start
    assert _balance(db_session, candidate) == 10 - COST

    # A second refund attempt never double-refunds.
    assert _refund_application_cv_analysis(db_session, APP_ID) is False
    db_session.commit()
    assert _balance(db_session, owner) == owner_start


def test_application_analysis_refund_is_noop_without_company_charge(
    db_session, wallets
):
    candidate, _owner = wallets
    candidate_tx = _candidate_review_charge(db_session, candidate)

    assert _refund_application_cv_analysis(db_session, APP_ID) is False
    db_session.commit()
    db_session.refresh(candidate_tx)
    assert candidate_tx.status == "succeeded"
    assert _balance(db_session, candidate) == 10 - COST


# ── 3. Same reference, different users: charged independently ─────────────
def test_same_reference_different_users_charged_independently(db_session, wallets):
    candidate, _owner = wallets
    other = _mk_user(db_session, "other-p03@example.com")
    credit_service.grant_credits(db_session, other, 10)

    tx_a = _candidate_review_charge(db_session, candidate)
    tx_b = _candidate_review_charge(db_session, other)

    assert tx_a.id != tx_b.id
    assert tx_a.idempotency_key != tx_b.idempotency_key
    assert _balance(db_session, candidate) == 10 - COST
    assert _balance(db_session, other) == 10 - COST


# ── 4. Same wallet + same operation stays idempotent ──────────────────────
def test_same_user_same_operation_is_idempotent(db_session, wallets):
    candidate, owner = wallets
    owner_start = _balance(db_session, owner)

    first = _candidate_review_charge(db_session, candidate)
    again = _candidate_review_charge(db_session, candidate)
    assert again.id == first.id
    assert _balance(db_session, candidate) == 10 - COST

    c1 = _company_apply_charge(db_session, owner)
    c2 = _company_apply_charge(db_session, owner)
    assert c1.id == c2.id
    assert _balance(db_session, owner) == owner_start - COST

    consumes = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.type == "consume")
        .count()
    )
    assert consumes == 2


# ── 5. Retry after refund is charged again ─────────────────────────────────
def test_retry_after_refund_is_charged(db_session, wallets):
    candidate, _owner = wallets

    first = _candidate_review_charge(db_session, candidate)
    credit_service.rollback_credits(db_session, first)
    assert _balance(db_session, candidate) == 10

    retry = _candidate_review_charge(db_session, candidate)
    assert retry.id != first.id
    assert retry.status == "succeeded"
    assert _balance(db_session, candidate) == 10 - COST

    # A duplicate of the retry is still idempotent.
    assert _candidate_review_charge(db_session, candidate).id == retry.id
    assert _balance(db_session, candidate) == 10 - COST

    # Refund of the retry works independently (distinct rollback row).
    credit_service.rollback_credits(db_session, retry)
    assert _balance(db_session, candidate) == 10
    rollbacks = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.type == "rollback")
        .all()
    )
    assert len(rollbacks) == 2
    assert len({r.idempotency_key for r in rollbacks}) == 2


def test_company_retry_after_refund_is_charged(db_session, wallets):
    _candidate, owner = wallets
    owner_start = _balance(db_session, owner)

    _company_apply_charge(db_session, owner)
    assert _refund_application_cv_analysis(db_session, APP_ID) is True
    db_session.commit()
    assert _balance(db_session, owner) == owner_start

    _company_apply_charge(db_session, owner)
    assert _balance(db_session, owner) == owner_start - COST


# ── 6. Insufficient credits keeps the existing error contract ─────────────
def test_insufficient_credits_contract_unchanged(db_session, wallets):
    _candidate, _owner = wallets
    broke = _mk_user(db_session, "broke-p03@example.com")
    credit_service.grant_credits(db_session, broke, 1)

    with pytest.raises(ValueError):
        credit_service.consume_credits(
            db_session, broke, COST, "cv_analysis", reference_id=APP_ID
        )
    with pytest.raises(HTTPException) as exc:
        _candidate_review_charge(db_session, broke)
    assert exc.value.status_code == 402
    assert exc.value.detail["error"] == "insufficient_credits"
    assert exc.value.detail["cost"] == COST
    with pytest.raises(ValueError):
        credit_service.consume_credits_in_transaction(
            db_session, broke, COST, "cv_analysis", reference_id=APP_ID
        )
    db_session.rollback()

    assert _balance(db_session, broke) == 1
    assert (
        db_session.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == broke.id,
            CreditTransaction.type == "consume",
        )
        .count()
        == 0
    )
