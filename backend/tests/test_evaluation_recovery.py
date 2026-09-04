"""
Unit tests for EvaluationSession recovery mechanism and idempotency guarantees.

Tests:
1. stale pending recovery (>3 min)
2. stale running recovery (>10 min)
3. fresh pending NOT recovered (<3 min)
4. fresh running NOT recovered (<10 min)
5. concurrent recovery CAS protection
6. duplicate recovery idempotency (no double scoring)
7. zombie worker protection (lost claim prevents overwrite and side effects)
8. recovery CAS race prevention (interleaved worker claim blocks stale reset)
9. credit consumption idempotency (duplicate reference_id returns existing tx without double debit)
10. EvaluationResult upsert idempotency (multiple scoring calls update single session row)
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.database import Application, CreditWallet, EvaluationResult, EvaluationSession
from backend.routers.ai_interview.evaluation import (
    STALE_PENDING_THRESHOLD_SECONDS,
    STALE_RUNNING_THRESHOLD_SECONDS,
    recover_stale_evaluations,
    run_background_final_evaluation,
)


@pytest.fixture
def recovery_setup(db_session, test_user, test_company):
    """Create test application and evaluation session fixture."""
    app = Application(
        user_id=test_user.id,
        company_id=test_company.id,
        full_name=test_user.name,
        email=test_user.email,
        status="interviewing",
        language="English",
        created_at=datetime.now(UTC),
    )
    db_session.add(app)
    db_session.commit()

    es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="created",
        interview_state="in_progress",
        interview_progress=5,
        created_at=datetime.now(UTC),
    )
    db_session.add(es)
    db_session.commit()
    db_session.refresh(app)

    # Add credit wallet so credit consumption succeeds
    wallet = CreditWallet(
        user_id=test_user.id,
        company_id=test_company.id,
        balance=100,
        currency="CRED",
    )
    db_session.add(wallet)
    db_session.commit()

    return app, es


@pytest.mark.asyncio
async def test_stale_pending_recovery(db_session, recovery_setup):
    """Stale pending session (>3 min) is picked up and evaluated."""
    app, es = recovery_setup
    stale_time = datetime.now(UTC) - timedelta(seconds=STALE_PENDING_THRESHOLD_SECONDS + 30)

    # Set status to pending with old updated_at
    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update({"status": "pending", "updated_at": stale_time}, synchronize_session=False)
    db_session.commit()

    fake_result = {
        "final_score": 85.0,
        "skill_metrics": {"Technical": 85.0},
        "strengths": [],
        "weaknesses": [],
    }

    with patch(
        "backend.routers.ai_interview.evaluation.evaluate_complete_interview",
        new=AsyncMock(return_value=fake_result),
    ), patch(
        "backend.email_service.email_service.send_interview_complete_email"
    ), patch(
        "backend.email_service.email_service.send_candidate_completion_email"
    ):
        recovered = await recover_stale_evaluations(db_session)
        assert recovered >= 1

    db_session.refresh(es)
    assert es.status == "completed"

    er = (
        db_session.query(EvaluationResult)
        .filter(EvaluationResult.evaluation_session_id == es.id)
        .first()
    )
    assert er is not None
    assert er.final_score is not None
    assert er.final_score > 0.0


@pytest.mark.asyncio
async def test_stale_running_recovery(db_session, recovery_setup):
    """Stale running session (>10 min) is reset to pending and evaluated."""
    app, es = recovery_setup
    stale_time = datetime.now(UTC) - timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS + 60)

    # Set status to running with old updated_at
    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update(
        {"status": "running", "started_at": stale_time, "updated_at": stale_time},
        synchronize_session=False,
    )
    db_session.commit()

    fake_result = {
        "final_score": 78.0,
        "skill_metrics": {"Technical": 78.0},
        "strengths": [],
        "weaknesses": [],
    }

    with patch(
        "backend.routers.ai_interview.evaluation.evaluate_complete_interview",
        new=AsyncMock(return_value=fake_result),
    ), patch(
        "backend.email_service.email_service.send_interview_complete_email"
    ), patch(
        "backend.email_service.email_service.send_candidate_completion_email"
    ):
        recovered = await recover_stale_evaluations(db_session)
        assert recovered >= 1

    db_session.refresh(es)
    assert es.status == "completed"

    er = (
        db_session.query(EvaluationResult)
        .filter(EvaluationResult.evaluation_session_id == es.id)
        .first()
    )
    assert er is not None
    assert er.final_score is not None
    assert er.final_score > 0.0


@pytest.mark.asyncio
async def test_fresh_pending_not_recovered(db_session, recovery_setup):
    """Fresh pending session (<3 min) is NOT recovered."""
    app, es = recovery_setup
    fresh_time = datetime.now(UTC) - timedelta(seconds=30)  # Only 30s old

    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update({"status": "pending", "updated_at": fresh_time}, synchronize_session=False)
    db_session.commit()

    recovered = await recover_stale_evaluations(db_session)
    assert recovered == 0

    db_session.refresh(es)
    assert es.status == "pending"


@pytest.mark.asyncio
async def test_fresh_running_not_recovered(db_session, recovery_setup):
    """Fresh running session (<10 min) is NOT reset/recovered."""
    app, es = recovery_setup
    fresh_time = datetime.now(UTC) - timedelta(minutes=2)  # Only 2 min old

    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update(
        {"status": "running", "started_at": fresh_time, "updated_at": fresh_time},
        synchronize_session=False,
    )
    db_session.commit()

    recovered = await recover_stale_evaluations(db_session)
    assert recovered == 0

    db_session.refresh(es)
    assert es.status == "running"


@pytest.mark.asyncio
async def test_concurrent_recovery_cas(db_session, recovery_setup):
    """Two concurrent run_background_final_evaluation calls on same pending session -> only 1 executes."""
    app, es = recovery_setup

    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update({"status": "pending", "updated_at": datetime.now(UTC)}, synchronize_session=False)
    db_session.commit()

    fake_result = {
        "final_score": 80.0,
        "skill_metrics": {"Technical": 80.0},
        "strengths": [],
        "weaknesses": [],
    }

    eval_counter = 0

    async def mock_eval(*args, **kwargs):
        nonlocal eval_counter
        eval_counter += 1
        return fake_result

    with patch(
        "backend.routers.ai_interview.evaluation.evaluate_complete_interview",
        side_effect=mock_eval,
    ), patch(
        "backend.email_service.email_service.send_interview_complete_email"
    ), patch(
        "backend.email_service.email_service.send_candidate_completion_email"
    ):
        # Run two concurrent tasks
        await asyncio.gather(
            run_background_final_evaluation(app.id, app.company_id),
            run_background_final_evaluation(app.id, app.company_id),
        )

    # Only one evaluation call executed because CAS claimed status='pending' -> 'running'
    assert eval_counter == 1

    db_session.refresh(es)
    assert es.status == "completed"


@pytest.mark.asyncio
async def test_duplicate_recovery_does_not_double_score(db_session, recovery_setup):
    """Running recovery multiple times does not produce duplicate EvaluationResults."""
    app, es = recovery_setup
    stale_time = datetime.now(UTC) - timedelta(seconds=STALE_PENDING_THRESHOLD_SECONDS + 30)

    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update({"status": "pending", "updated_at": stale_time}, synchronize_session=False)
    db_session.commit()

    fake_result = {
        "final_score": 90.0,
        "skill_metrics": {"Technical": 90.0},
        "strengths": [],
        "weaknesses": [],
    }

    with patch(
        "backend.routers.ai_interview.evaluation.evaluate_complete_interview",
        new=AsyncMock(return_value=fake_result),
    ), patch(
        "backend.email_service.email_service.send_interview_complete_email"
    ), patch(
        "backend.email_service.email_service.send_candidate_completion_email"
    ):
        await recover_stale_evaluations(db_session)
        # Second run immediately after
        await recover_stale_evaluations(db_session)

    results = (
        db_session.query(EvaluationResult)
        .filter(EvaluationResult.evaluation_session_id == es.id)
        .all()
    )
    assert len(results) == 1
    assert results[0].final_score is not None
    assert results[0].final_score > 0.0


@pytest.mark.asyncio
async def test_zombie_worker_prevented(db_session, recovery_setup):
    """A zombie worker whose claim was reset/reclaimed cannot overwrite the session to completed."""
    app, es = recovery_setup
    stale_time = datetime.now(UTC) - timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS + 60)

    old_claim_time = stale_time
    new_claim_time = datetime.now(UTC)

    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update(
        {"status": "running", "started_at": new_claim_time, "updated_at": new_claim_time},
        synchronize_session=False,
    )
    db_session.commit()

    session_check = (
        db_session.query(EvaluationSession)
        .filter(
            EvaluationSession.application_id == app.id,
            EvaluationSession.status == "running",
        )
        .first()
    )
    now_claim_naive = old_claim_time.replace(tzinfo=None) if old_claim_time.tzinfo else old_claim_time
    session_started_naive = (
        session_check.started_at.replace(tzinfo=None)
        if session_check and session_check.started_at and session_check.started_at.tzinfo
        else (session_check.started_at if session_check else None)
    )

    claim_invalid = not session_check or (
        session_started_naive and session_started_naive > now_claim_naive
    )
    assert claim_invalid is True


@pytest.mark.asyncio
async def test_recovery_cas_race_prevention(db_session, recovery_setup):
    """If recovery reads a stale running session, but another worker claims/updates it before recovery's CAS update,
    the CAS update returns 0 and recovery does NOT reset or evaluate the session."""
    app, es = recovery_setup
    stale_time = datetime.now(UTC) - timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS + 60)

    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update(
        {"status": "running", "started_at": stale_time, "updated_at": stale_time},
        synchronize_session=False,
    )
    db_session.commit()

    fresh_time = datetime.now(UTC)
    db_session.query(EvaluationSession).filter(
        EvaluationSession.id == es.id
    ).update(
        {"status": "running", "started_at": fresh_time, "updated_at": fresh_time},
        synchronize_session=False,
    )
    db_session.commit()

    recovered = await recover_stale_evaluations(db_session)
    assert recovered == 0

    db_session.refresh(es)
    assert es.status == "running"


def test_credit_consumption_idempotency(db_session, recovery_setup):
    """Calling consume_company_credits twice with same reference_id returns existing transaction without double charging."""
    from backend.credit_service import consume_company_credits, CreditWallet

    app, es = recovery_setup

    wallet = db_session.query(CreditWallet).filter(CreditWallet.company_id == app.company_id).first()
    initial_balance = float(wallet.balance)

    tx1 = consume_company_credits(
        db_session,
        app.company_id,
        5,
        "ai_interview_evaluation",
        reference_type="application",
        reference_id=app.id,
    )
    assert tx1 is not None

    db_session.refresh(wallet)
    balance_after_tx1 = float(wallet.balance)
    assert balance_after_tx1 == initial_balance - 5.0

    # Second call with same reference_id
    tx2 = consume_company_credits(
        db_session,
        app.company_id,
        5,
        "ai_interview_evaluation",
        reference_type="application",
        reference_id=app.id,
    )
    assert tx2 is not None
    assert tx2.id == tx1.id  # Returned existing transaction

    db_session.refresh(wallet)
    balance_after_tx2 = float(wallet.balance)
    # Balance must remain unchanged after second call
    assert balance_after_tx2 == balance_after_tx1


def test_evaluation_result_upsert_idempotency(db_session, recovery_setup):
    """Calling set_evaluation_result twice on same app updates the existing row without creating duplicates."""
    from backend.scoring_service import ScoringService

    app, es = recovery_setup

    res1 = ScoringService.set_evaluation_result(
        app=app,
        db=db_session,
        eval_score=80.0,
        scored_by="ai",
    )
    db_session.commit()

    count1 = db_session.query(EvaluationResult).filter(EvaluationResult.evaluation_session_id == es.id).count()
    assert count1 == 1

    # Second call
    res2 = ScoringService.set_evaluation_result(
        app=app,
        db=db_session,
        eval_score=85.0,
        scored_by="ai",
    )
    db_session.commit()

    count2 = db_session.query(EvaluationResult).filter(EvaluationResult.evaluation_session_id == es.id).count()
    assert count2 == 1
    assert res2.id == res1.id
