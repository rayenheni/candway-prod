"""Regression: the AI-interview evaluation charge can never undo the evaluation.

Bug (reproduced): the background final evaluation computed and flushed the
canonical score, then charged the company 5 credits with the committing
``consume_company_credits``. With an existing but underfunded billing wallet,
``consume_credits`` executed ``db.rollback()`` — discarding the uncommitted
score — and the evaluation was nevertheless marked ``completed``: the
candidate's final interview score silently disappeared (canonical score fell
back to the CV-only value) and nothing ever retried it.

Fixed contract (real pipeline; only the LLM skill extraction is mocked):
  * the charge is staged in a SAVEPOINT and committed together with the
    evaluation result (before notifications, as before);
  * a charge that cannot be made rolls back only its SAVEPOINT — the score is
    committed and the evaluation completes either way;
  * one charge per application/wallet, idempotent, never doubled;
  * a persistence failure never yields a completed evaluation or a score.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

import backend.routers.ai_interview.evaluation as evaluation_mod
from backend.credit_service import get_user_credit_balance
from backend.database import CreditTransaction, CreditWallet, EvaluationSession
from backend.scoring_service import ScoringService
from backend.tests import test_rubric_final_interview_scoring as rubric_t

# Real rubric interview: CV score 80 (session 1) + pinned-rubric interview
# session (session 2, rubric skills Python + SQL).
interview_app = rubric_t.interview_app

CV_SCORE = rubric_t.CV_SCORE
EXPECTED_FINAL = rubric_t._final(CV_SCORE, 90, 100)  # 90.0
CV_ONLY_SCORE = CV_SCORE * 0.75  # what the lost-score bug displayed (60.0)


async def _interview_and_evaluate(db_session, app):
    """Two strong answers (Python + SQL), then the real final evaluation."""
    await rubric_t._answer(
        app, rubric_t.PY_STRONG, "Python", [rubric_t._ev("Python", rubric_t.PY_STRONG)]
    )
    await rubric_t._answer(
        app, rubric_t.SQL_STRONG, "SQL", [rubric_t._ev("SQL", rubric_t.SQL_STRONG)]
    )
    with (
        patch("backend.email_service.email_service.send_interview_complete_email"),
        patch("backend.email_service.email_service.send_candidate_completion_email"),
    ):
        await rubric_t._finish(db_session, app)


def _charges(db, app, status=None):
    q = db.query(CreditTransaction).filter(
        CreditTransaction.type == "consume",
        CreditTransaction.resource == "ai_interview_evaluation",
        CreditTransaction.reference_id == app.id,
    )
    if status is not None:
        q = q.filter(CreditTransaction.status == status)
    return q.all()


def _set_balance(db, user, balance):
    wallet = db.query(CreditWallet).filter(CreditWallet.user_id == user.id).first()
    wallet.balance = balance
    db.commit()


def _assert_scored_and_completed(db_session, app):
    er = rubric_t._interview_result(db_session, app)
    es = rubric_t._interview_session(db_session, app)
    assert er is not None
    assert er.final_score == EXPECTED_FINAL
    assert er.rubric_score == 90.0
    assert er.rubric_coverage_pct == 100.0
    assert er.cv_score == CV_SCORE
    assert er.scoring_status != "PENDING"
    assert es.status == "completed"
    assert es.interview_state == "completed"
    canonical = ScoringService.get_canonical_score(app.id, db_session)
    assert canonical.id == er.id
    assert canonical.final_score == EXPECTED_FINAL


# ── 1. Company can pay ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_funded_company_score_persists_and_is_charged_once(
    db_session, interview_app, company_billing_owner
):
    balance_before = get_user_credit_balance(db_session, company_billing_owner)

    await _interview_and_evaluate(db_session, interview_app)

    _assert_scored_and_completed(db_session, interview_app)
    charges = _charges(db_session, interview_app)
    assert len(charges) == 1
    assert charges[0].status == "succeeded"
    assert float(charges[0].amount) == -5.0
    assert charges[0].user_id == company_billing_owner.id
    assert (
        get_user_credit_balance(db_session, company_billing_owner) == balance_before - 5
    )


# ── 2. Company cannot pay ─────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("balance", [0, 4])
async def test_underfunded_company_keeps_score_and_completes(
    db_session, interview_app, company_billing_owner, balance
):
    _set_balance(db_session, company_billing_owner, balance)

    await _interview_and_evaluate(db_session, interview_app)

    # The score is NOT rolled back (the bug showed the CV-only 60.0 here).
    _assert_scored_and_completed(db_session, interview_app)
    assert (
        ScoringService.get_canonical_score(interview_app.id, db_session).final_score
        != CV_ONLY_SCORE
    )
    # No successful evaluation charge, wallet untouched.
    assert _charges(db_session, interview_app, status="succeeded") == []
    assert get_user_credit_balance(db_session, company_billing_owner) == balance


@pytest.mark.asyncio
async def test_recovery_leaves_underfunded_completed_evaluation_alone(
    db_session, interview_app, company_billing_owner
):
    _set_balance(db_session, company_billing_owner, 0)
    await _interview_and_evaluate(db_session, interview_app)
    es = rubric_t._interview_session(db_session, interview_app)
    # Old enough for every recovery threshold (failed-retry backoff, stale
    # pending/running) — a completed evaluation must still not be touched.
    db_session.query(EvaluationSession).filter(EvaluationSession.id == es.id).update(
        {"updated_at": datetime.now(UTC) - timedelta(hours=2)},
        synchronize_session=False,
    )
    db_session.commit()

    llm = AsyncMock(return_value={"final_score": 99.0})
    with patch.object(evaluation_mod, "evaluate_complete_interview", llm):
        recovered = await evaluation_mod.recover_stale_evaluations(db_session)
    db_session.expire_all()

    assert recovered == 0
    llm.assert_not_called()
    _assert_scored_and_completed(db_session, interview_app)
    assert _charges(db_session, interview_app, status="succeeded") == []


# ── 3. Persistence failure is never a completed evaluation ────────────────
@pytest.mark.asyncio
async def test_score_persistence_failure_is_not_a_completed_evaluation(
    db_session, interview_app, company_billing_owner
):
    balance_before = get_user_credit_balance(db_session, company_billing_owner)
    with (
        patch.object(
            ScoringService,
            "set_evaluation_result",
            side_effect=RuntimeError("database unavailable"),
        ),
        pytest.raises(RuntimeError, match="database unavailable"),
    ):
        await _interview_and_evaluate(db_session, interview_app)

    es = rubric_t._interview_session(db_session, interview_app)
    er = rubric_t._interview_result(db_session, interview_app)
    assert es.status == "failed"
    assert es.interview_state == "evaluating"  # retryable (P0-5)
    assert er is None or er.final_score is None
    assert _charges(db_session, interview_app) == []
    assert get_user_credit_balance(db_session, company_billing_owner) == balance_before


@pytest.mark.asyncio
async def test_failure_after_scoring_does_not_persist_a_score_on_a_failed_evaluation(
    db_session, interview_app, company_billing_owner
):
    """An error after the score was computed (but before the final commit)
    fails the evaluation without leaving that uncommitted score visible."""
    balance_before = get_user_credit_balance(db_session, company_billing_owner)
    with (
        patch.object(
            evaluation_mod, "sync_cv_document", side_effect=RuntimeError("boom")
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await _interview_and_evaluate(db_session, interview_app)

    es = rubric_t._interview_session(db_session, interview_app)
    er = rubric_t._interview_result(db_session, interview_app)
    assert es.status == "failed"
    assert es.interview_state == "evaluating"
    assert er is None or er.final_score is None
    # The canonical score is still the prior (CV) result, not a half-written one.
    assert (
        ScoringService.get_canonical_score(interview_app.id, db_session).final_score
        == CV_ONLY_SCORE
    )
    assert _charges(db_session, interview_app) == []
    assert get_user_credit_balance(db_session, company_billing_owner) == balance_before


@pytest.mark.asyncio
async def test_completion_commit_failure_is_not_completed_and_retry_charges_once(
    db_session, interview_app, company_billing_owner
):
    """The database rejects the final completion write (after the score and
    the charge were committed). The evaluation must NOT be completed: it is
    marked failed (retryable), and the P0-5 retry completes it without
    charging the company a second time."""
    balance_before = get_user_credit_balance(db_session, company_billing_owner)
    real_sync = evaluation_mod.sync_evaluation_state

    def _sync_then_corrupt(db, app, **kwargs):
        real_sync(db, app, **kwargs)
        if kwargs.get("evaluation_state") == "completed":
            app.status = "not_a_valid_status"  # violates ck_application_status

    with (
        patch.object(evaluation_mod, "sync_evaluation_state", _sync_then_corrupt),
        pytest.raises(IntegrityError),
    ):
        await _interview_and_evaluate(db_session, interview_app)

    es = rubric_t._interview_session(db_session, interview_app)
    assert es.status == "failed"
    assert es.interview_state == "evaluating"
    assert len(_charges(db_session, interview_app, status="succeeded")) == 1

    # P0-5 recovery after the backoff: completes, still exactly one charge.
    db_session.query(EvaluationSession).filter(EvaluationSession.id == es.id).update(
        {
            "updated_at": datetime.now(UTC)
            - timedelta(seconds=evaluation_mod.FAILED_RETRY_BACKOFF_SECONDS + 60)
        },
        synchronize_session=False,
    )
    db_session.commit()
    llm = AsyncMock(return_value={"final_score": 99.0})
    with patch.object(evaluation_mod, "evaluate_complete_interview", llm):
        await evaluation_mod.recover_stale_evaluations(db_session)
    db_session.expire_all()

    _assert_scored_and_completed(db_session, interview_app)
    assert len(_charges(db_session, interview_app)) == 1
    assert (
        get_user_credit_balance(db_session, company_billing_owner) == balance_before - 5
    )


@pytest.mark.asyncio
async def test_charge_database_error_does_not_lose_the_score(
    db_session, interview_app, company_billing_owner
):
    """Any charge failure (not only insufficient credits) is confined to the
    charge SAVEPOINT."""
    balance_before = get_user_credit_balance(db_session, company_billing_owner)
    with patch(
        "backend.credit_service.consume_credits_in_transaction",
        side_effect=RuntimeError("wallet table locked"),
    ):
        await _interview_and_evaluate(db_session, interview_app)

    _assert_scored_and_completed(db_session, interview_app)
    assert _charges(db_session, interview_app) == []
    assert get_user_credit_balance(db_session, company_billing_owner) == balance_before


# ── 4. Retry / concurrency never double-charges ───────────────────────────
@pytest.mark.asyncio
async def test_rerun_and_concurrent_runs_never_double_charge(
    db_session, interview_app, company_billing_owner
):
    balance_before = get_user_credit_balance(db_session, company_billing_owner)
    await _interview_and_evaluate(db_session, interview_app)
    assert len(_charges(db_session, interview_app)) == 1

    # Re-run the already charged evaluation twice, concurrently.
    es = rubric_t._interview_session(db_session, interview_app)
    es.status = "pending"
    es.interview_state = "evaluating"
    db_session.commit()
    llm = AsyncMock(return_value={"final_score": 99.0})
    with (
        patch.object(evaluation_mod, "evaluate_complete_interview", llm),
        patch("backend.email_service.email_service.send_interview_complete_email"),
        patch("backend.email_service.email_service.send_candidate_completion_email"),
    ):
        await asyncio.gather(
            evaluation_mod.run_background_final_evaluation(
                interview_app.id, interview_app.company_id
            ),
            evaluation_mod.run_background_final_evaluation(
                interview_app.id, interview_app.company_id
            ),
        )
    db_session.expire_all()

    _assert_scored_and_completed(db_session, interview_app)
    charges = _charges(db_session, interview_app)
    assert len(charges) == 1
    assert charges[0].status == "succeeded"
    assert (
        get_user_credit_balance(db_session, company_billing_owner) == balance_before - 5
    )


@pytest.mark.asyncio
async def test_underfunded_then_funded_retry_charges_exactly_once(
    db_session, interview_app, company_billing_owner
):
    """An evaluation that could not be billed and is later re-run once the
    company has credits is charged exactly once (and never twice after)."""
    _set_balance(db_session, company_billing_owner, 0)
    await _interview_and_evaluate(db_session, interview_app)
    assert _charges(db_session, interview_app) == []

    _set_balance(db_session, company_billing_owner, 100)
    for _ in range(2):
        es = rubric_t._interview_session(db_session, interview_app)
        es.status = "pending"
        es.interview_state = "evaluating"
        db_session.commit()
        await rubric_t._finish(db_session, interview_app)

    _assert_scored_and_completed(db_session, interview_app)
    assert len(_charges(db_session, interview_app, status="succeeded")) == 1
    assert get_user_credit_balance(db_session, company_billing_owner) == 95
