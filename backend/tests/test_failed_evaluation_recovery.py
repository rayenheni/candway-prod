"""P0-5 regression: failed final evaluations are retried, safely and bounded.

Before the fix a final evaluation that failed (provider error, timeout,
invalid AI output, rubric aggregation error) left the session
``status="failed"`` while the interview stayed ``interview_state=
"evaluating"``; recover_stale_evaluations() only looked at pending/running,
so the candidate was stuck forever with no result.

Guarantees tested here:
  - a failed evaluation of a finished interview is retried after a backoff
    and completes with exactly one final result;
  - fresh failures (inside the backoff), failures outside the retry window,
    sessions whose interview is no longer "evaluating" and superseded
    (older) sessions are NOT retried;
  - repeated / concurrent recovery evaluates once;
  - a retry that fails again stays "failed" and is backed off again;
  - no double company credit charge.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.database import (
    Application,
    CreditTransaction,
    EvaluationResult,
    EvaluationSession,
)
from backend.routers.ai_interview.evaluation import (
    FAILED_RETRY_BACKOFF_SECONDS,
    FAILED_RETRY_MAX_AGE_SECONDS,
    recover_stale_evaluations,
)

FAKE_RESULT = {
    "final_score": 82.0,
    "skill_metrics": {"Technical": 82.0},
    "strengths": [],
    "weaknesses": [],
}


@pytest.fixture
def failed_eval(db_session, test_company, company_billing_owner):
    app = Application(
        company_id=test_company.id,
        full_name="Stuck Candidate",
        email="stuck@example.com",
        status="interviewing",
        language="English",
    )
    db_session.add(app)
    db_session.commit()
    es = EvaluationSession(
        application_id=app.id,
        company_id=test_company.id,
        status="failed",
        interview_state="evaluating",
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(es)
    db_session.commit()
    _age(db_session, es, FAILED_RETRY_BACKOFF_SECONDS + 60)
    return app, es


def _age(db, es, seconds):
    """Pretend the last attempt happened ``seconds`` ago."""
    db.query(EvaluationSession).filter(EvaluationSession.id == es.id).update(
        {"updated_at": datetime.now(UTC) - timedelta(seconds=seconds)},
        synchronize_session=False,
    )
    db.commit()


async def _recover(db, llm):
    with (
        patch(
            "backend.routers.ai_interview.evaluation.evaluate_complete_interview", llm
        ),
        patch("backend.email_service.email_service.send_interview_complete_email"),
        patch("backend.email_service.email_service.send_candidate_completion_email"),
    ):
        result = await recover_stale_evaluations(db)
    db.expire_all()
    return result


def _results(db, es):
    return (
        db.query(EvaluationResult)
        .filter(EvaluationResult.evaluation_session_id == es.id)
        .all()
    )


def _eval_charges(db, app):
    return (
        db.query(CreditTransaction)
        .filter(
            CreditTransaction.type == "consume",
            CreditTransaction.resource == "ai_interview_evaluation",
            CreditTransaction.reference_id == app.id,
        )
        .all()
    )


# ── Retry works ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_failed_evaluation_is_retried_and_completes(db_session, failed_eval):
    app, es = failed_eval
    llm = AsyncMock(return_value=FAKE_RESULT)

    assert await _recover(db_session, llm) >= 1

    llm.assert_awaited_once()
    db_session.refresh(es)
    assert es.status == "completed"
    assert es.interview_state == "completed"
    results = _results(db_session, es)
    assert len(results) == 1
    assert results[0].final_score is not None and results[0].final_score > 0
    assert len(_eval_charges(db_session, app)) == 1


# ── Not retried ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_fresh_failure_waits_for_backoff(db_session, failed_eval):
    _app, es = failed_eval
    _age(db_session, es, 30)  # failed 30s ago
    llm = AsyncMock(return_value=FAKE_RESULT)

    await _recover(db_session, llm)

    llm.assert_not_awaited()
    db_session.refresh(es)
    assert es.status == "failed"


@pytest.mark.asyncio
async def test_failure_outside_retry_window_is_not_retried(db_session, failed_eval):
    _app, es = failed_eval
    db_session.query(EvaluationSession).filter(EvaluationSession.id == es.id).update(
        {
            "created_at": datetime.now(UTC)
            - timedelta(seconds=FAILED_RETRY_MAX_AGE_SECONDS + 60)
        },
        synchronize_session=False,
    )
    db_session.commit()
    _age(db_session, es, FAILED_RETRY_BACKOFF_SECONDS + 60)
    llm = AsyncMock(return_value=FAKE_RESULT)

    await _recover(db_session, llm)

    llm.assert_not_awaited()
    db_session.refresh(es)
    assert es.status == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("interview_state", ["completed", "expired", "in_progress"])
async def test_failed_session_not_in_evaluating_is_not_retried(
    db_session, failed_eval, interview_state
):
    _app, es = failed_eval
    db_session.query(EvaluationSession).filter(EvaluationSession.id == es.id).update(
        {"interview_state": interview_state}, synchronize_session=False
    )
    db_session.commit()
    _age(db_session, es, FAILED_RETRY_BACKOFF_SECONDS + 60)
    llm = AsyncMock(return_value=FAKE_RESULT)

    await _recover(db_session, llm)

    llm.assert_not_awaited()
    db_session.refresh(es)
    assert es.status == "failed"


@pytest.mark.asyncio
async def test_superseded_failed_session_does_not_trigger_evaluation(
    db_session, failed_eval, test_company
):
    """An old failed attempt must not evaluate the candidate's NEW interview."""
    app, es = failed_eval
    newer = EvaluationSession(
        application_id=app.id,
        company_id=test_company.id,
        status="in_progress",
        interview_state="in_progress",
    )
    db_session.add(newer)
    db_session.commit()
    _age(db_session, es, FAILED_RETRY_BACKOFF_SECONDS + 60)
    llm = AsyncMock(return_value=FAKE_RESULT)

    await _recover(db_session, llm)

    llm.assert_not_awaited()
    db_session.refresh(es)
    db_session.refresh(newer)
    assert es.status == "failed"
    assert newer.status == "in_progress"


# ── Idempotent / single-flight ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_repeated_recovery_evaluates_once(db_session, failed_eval):
    app, es = failed_eval
    llm = AsyncMock(return_value=FAKE_RESULT)

    await _recover(db_session, llm)
    await _recover(db_session, llm)
    _age(db_session, es, FAILED_RETRY_BACKOFF_SECONDS + 60)  # even when "old"
    await _recover(db_session, llm)

    assert llm.await_count == 1
    assert len(_results(db_session, es)) == 1
    assert len(_eval_charges(db_session, app)) == 1


@pytest.mark.asyncio
async def test_concurrent_recovery_evaluates_once(db_session, failed_eval):
    app, es = failed_eval
    calls = 0

    async def slow_eval(*args, **kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return FAKE_RESULT

    with (
        patch(
            "backend.routers.ai_interview.evaluation.evaluate_complete_interview",
            side_effect=slow_eval,
        ),
        patch("backend.email_service.email_service.send_interview_complete_email"),
        patch("backend.email_service.email_service.send_candidate_completion_email"),
    ):
        await asyncio.gather(
            recover_stale_evaluations(db_session),
            recover_stale_evaluations(db_session),
        )

    db_session.expire_all()
    assert calls == 1
    assert len(_results(db_session, es)) == 1
    assert len(_eval_charges(db_session, app)) == 1


@pytest.mark.asyncio
async def test_retry_that_fails_again_stays_failed_and_backs_off(
    db_session, failed_eval
):
    _app, es = failed_eval
    failing = AsyncMock(side_effect=RuntimeError("provider still down"))

    await _recover(db_session, failing)

    failing.assert_awaited_once()
    db_session.refresh(es)
    assert es.status == "failed"
    assert es.interview_state == "evaluating"  # still retryable later
    assert _results(db_session, es) == [] or all(
        r.final_score is None for r in _results(db_session, es)
    )

    # Immediately afterwards: inside the backoff -> not retried again.
    await _recover(db_session, failing)
    failing.assert_awaited_once()

    # After the backoff: retried and completes.
    _age(db_session, es, FAILED_RETRY_BACKOFF_SECONDS + 60)
    ok = AsyncMock(return_value=FAKE_RESULT)
    await _recover(db_session, ok)
    ok.assert_awaited_once()
    db_session.refresh(es)
    assert es.status == "completed"


# ── No double credit charge ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_after_post_charge_failure_does_not_charge_twice(
    db_session, failed_eval, company_billing_owner
):
    """A previous attempt already charged the company (then failed later in
    the pipeline). The successful retry must not charge again."""
    from backend.credit_service import consume_company_credits, get_user_credit_balance

    app, es = failed_eval
    consume_company_credits(
        db_session,
        app.company_id,
        5,
        "ai_interview_evaluation",
        reference_type="application",
        reference_id=app.id,
    )
    db_session.commit()
    balance_before = get_user_credit_balance(db_session, company_billing_owner)

    await _recover(db_session, AsyncMock(return_value=FAKE_RESULT))

    db_session.refresh(es)
    assert es.status == "completed"
    assert len(_eval_charges(db_session, app)) == 1
    assert get_user_credit_balance(db_session, company_billing_owner) == balance_before
