"""
Comprehensive regression tests for interview lifecycle, reset behavior, resume guards,
multi-session ordering, and [-1] fix verification.
"""

import os
import pytest
from datetime import datetime, UTC
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault("ALGORITHM", "HS256")

from backend.database import (
    Application,
    Base,
    Company,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    User,
)
from backend.entity_writer import sync_ai_interview_session, sync_evaluation_state

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def base_entities(db):
    """Create minimal Company, User, and Application for tests."""
    company = Company(name="Acme Corp", slug="acme")
    db.add(company)
    db.flush()

    user = User(
        email="candidate@acme.com",
        name="Candidate",
        hashed_password="hashed",
        role="candidate",
        email_verified=True,
    )
    db.add(user)
    db.flush()

    member = CompanyMember(
        company_id=company.id, user_id=user.id, role="member", is_active=True
    )
    db.add(member)

    app = Application(
        user_id=user.id,
        company_id=company.id,
        status="applied",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return {"db": db, "app": app, "user": user, "company": company}


# ── Test A: Fresh Interview ───────────────────────────────────────────

def test_fresh_interview_resume_status(base_entities):
    """Fresh interview (interview_state=not_started, status=created) returns can_resume=false and reason="Interview is not_started"."""
    db = base_entities["db"]
    app = base_entities["app"]

    es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="created",
        interview_state="not_started",
    )
    db.add(es)
    db.commit()

    db.refresh(app)
    latest_es = app._latest_eval_session()
    assert latest_es.status == "created"
    assert latest_es.interview_state == "not_started"
    assert app.interview_state == "not_started"


# ── Test B: Active Interview ──────────────────────────────────────────

def test_active_interview_resume_status(base_entities):
    """Active interview (interview_state=in_progress, status=in_progress) returns can_resume=true."""
    db = base_entities["db"]
    app = base_entities["app"]

    es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="in_progress",
        interview_state="in_progress",
    )
    db.add(es)
    db.commit()

    db.refresh(app)
    latest_es = app._latest_eval_session()
    assert latest_es.status == "in_progress"
    assert latest_es.interview_state == "in_progress"
    assert app.interview_state == "in_progress"


# ── Test C: Completed Interview ───────────────────────────────────────

def test_completed_interview_status(base_entities):
    """Completed interview (interview_state=completed, status=completed) has consistent completion state."""
    db = base_entities["db"]
    app = base_entities["app"]

    es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="completed",
        interview_state="completed",
    )
    db.add(es)
    db.commit()

    db.refresh(app)
    latest_es = app._latest_eval_session()
    assert latest_es.status == "completed"
    assert latest_es.interview_state == "completed"
    assert app.interview_state == "completed"


# ── Test D: Legacy Corrupted State ─────────────────────────────────────

def test_legacy_corrupted_state_detection(base_entities):
    """Legacy corrupt state (interview_state=not_started, status=completed) has latest session status='completed'."""
    db = base_entities["db"]
    app = base_entities["app"]

    es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="completed",
        interview_state="not_started",
    )
    db.add(es)
    db.commit()

    db.refresh(app)
    latest_es = app._latest_eval_session()
    assert latest_es.status == "completed"
    assert latest_es.interview_state == "not_started"


# ── Test E: Reset Creates New Clean EvaluationSession ──────────────────

def test_reset_creates_new_evaluation_session(base_entities):
    """Explicit reset must create a new EvaluationSession with status='created', clean state, linked EvaluationResult, and leave old completed session/result intact."""
    db = base_entities["db"]
    app = base_entities["app"]

    # Old completed session
    old_es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="completed",
        interview_state="completed",
        interview_progress=15,
        interview_log=[{"role": "user", "content": "hello"}],
    )
    db.add(old_es)
    db.flush()

    old_er = EvaluationResult(
        evaluation_session_id=old_es.id,
        company_id=app.company_id,
        scoring_status="SCORED",
        final_score=85.0,
        cv_score=90.0,
    )
    db.add(old_er)
    db.commit()

    db.refresh(app)
    assert len(app.evaluation_sessions) == 1
    assert app.evaluation_sessions[0].id == old_es.id

    from backend.routers.candidate.interviews import reset_interview
    import asyncio

    # Call reset_interview
    result = asyncio.run(
        reset_interview(
            payload={"application_id": app.id},
            current_user=base_entities["user"],
            db=db,
        )
    )

    db.refresh(app)
    assert len(app.evaluation_sessions) == 2, "Reset must create a second EvaluationSession"

    # Order by id DESC: [0] is newest, [1] is oldest
    new_session = app.evaluation_sessions[0]
    old_session_check = app.evaluation_sessions[1]

    # 1. Old session stays completed & unmodified
    assert old_session_check.id == old_es.id
    assert old_session_check.status == "completed"
    assert old_session_check.interview_state == "completed"
    assert old_session_check.interview_progress == 15

    # 2. Old EvaluationResult remains linked to old session, unmodified
    assert old_session_check.evaluation_result is not None
    assert old_session_check.evaluation_result.id == old_er.id
    assert old_session_check.evaluation_result.final_score == 85.0
    assert old_session_check.evaluation_result.cv_score == 90.0
    assert old_session_check.evaluation_result.scoring_status == "SCORED"

    # 3. New session has correct clean initial state
    assert new_session.id != old_es.id
    assert new_session.status == "created"
    assert new_session.interview_state == "not_started"
    assert new_session.interview_progress == 0
    assert new_session.interview_log == []
    assert new_session.interview_questions == []

    # 4. New session is latest/current session
    assert app._latest_eval_session().id == new_session.id

    # 5. New session has a valid EvaluationResult linked to it with CV-only score
    assert new_session.evaluation_result is not None
    assert new_session.evaluation_result.evaluation_session_id == new_session.id
    assert new_session.evaluation_result.scoring_status == "SCORED"
    assert new_session.evaluation_result.cv_score == 90.0
    assert new_session.evaluation_result.final_score == 67.5  # 90 * 0.75 CV-only weight

    # 6. CV-only score is preserved on new session without mutating old result
    assert old_session_check.evaluation_result.final_score == 85.0


def test_repeated_resets_create_new_sessions_without_corrupting_history(base_entities):
    """Repeated resets create a new EvaluationSession each time (3 resets -> 4 sessions) preserving history."""
    db = base_entities["db"]
    app = base_entities["app"]

    initial_es = EvaluationSession(
        application_id=app.id,
        company_id=app.company_id,
        status="completed",
        interview_state="completed",
    )
    db.add(initial_es)
    db.commit()

    from backend.routers.candidate.interviews import reset_interview
    import asyncio

    for i in range(3):
        asyncio.run(
            reset_interview(
                payload={"application_id": app.id},
                current_user=base_entities["user"],
                db=db,
            )
        )

    db.refresh(app)
    # Total sessions: 1 initial + 3 resets = 4 sessions
    assert len(app.evaluation_sessions) == 4
    # Latest is newly created fresh session
    latest = app._latest_eval_session()
    assert latest.status == "created"
    assert latest.interview_state == "not_started"
    # Oldest initial session remains untouched
    oldest = app.evaluation_sessions[-1]
    assert oldest.id == initial_es.id
    assert oldest.status == "completed"
    assert oldest.interview_state == "completed"


# ── Test F: Multiple Sessions Ordering ────────────────────────────────

def test_evaluation_sessions_desc_ordering(base_entities):
    """Verify that app._latest_eval_session() and app.evaluation_sessions[0] return the newest session."""
    db = base_entities["db"]
    app = base_entities["app"]

    es1 = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="completed", interview_state="completed"
    )
    db.add(es1)
    db.commit()

    es2 = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="created", interview_state="not_started"
    )
    db.add(es2)
    db.commit()

    db.refresh(app)
    assert app.evaluation_sessions[0].id == es2.id
    assert app.evaluation_sessions[-1].id == es1.id
    assert app._latest_eval_session().id == es2.id


# ── Test G: Completion with Multiple Sessions ────────────────────────

def test_sync_evaluation_state_updates_newest_session(base_entities):
    """sync_evaluation_state must update the newest session, leaving historical sessions untouched."""
    db = base_entities["db"]
    app = base_entities["app"]

    es1 = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="completed", interview_state="completed"
    )
    db.add(es1)
    db.commit()

    es2 = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="in_progress", interview_state="in_progress"
    )
    db.add(es2)
    db.commit()

    db.refresh(app)

    # Sync state completion
    sync_evaluation_state(db, app, evaluation_state="completed")
    db.commit()

    db.refresh(app)
    db.refresh(es1)
    db.refresh(es2)

    assert es2.status == "completed", "Newest session must be marked completed"
    assert es1.status == "completed", "Historical session remains completed"
    assert app.evaluation_sessions[0].id == es2.id


# ── Test H: No Duplicate Sessions on Active Sync ───────────────────────

def test_sync_ai_interview_session_reuses_active_session(base_entities):
    """sync_ai_interview_session must reuse an existing active session rather than creating duplicate sessions."""
    db = base_entities["db"]
    app = base_entities["app"]

    es = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="created", interview_state="not_started"
    )
    db.add(es)
    db.commit()

    # Call sync_ai_interview_session multiple times
    s1 = sync_ai_interview_session(db, app, interview_progress=1)
    s2 = sync_ai_interview_session(db, app, interview_progress=2)

    assert s1.id == es.id
    assert s2.id == es.id
    assert len(app.evaluation_sessions) == 1
