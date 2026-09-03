"""
Phase 2 Validation — EvaluationSession as Source of Truth

Verifies that interview state is read from EvaluationSession (not deprecated
Application columns) and that the entity ownership contract is enforced.
"""

from datetime import datetime

import pytest
from sqlalchemy import func

from backend.database import Application, Company, EvaluationSession
from backend.entity_writer import sync_ai_interview_session

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def test_company(db_session):
    c = Company(name="Test Corp", slug="test-corp")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def test_app(db_session, test_user, test_company):
    app = Application(
        user_id=test_user.id,
        company_id=test_company.id,
        declared_role="Python Developer",
        full_name=test_user.name,
        email=test_user.email,
        status="analyzed",
        language="English",
        created_at=datetime.now(),
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app


# ── Tests ─────────────────────────────────────────────────────────────────


class TestEvaluationSessionOwnership:
    """EvaluationSession is the single source of truth for interview state."""

    def test_new_interview_creates_evaluation_session(self, db_session, test_app):
        """Creating an interview must create an EvaluationSession."""
        es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="not_started",
            interview_progress=0,
            interview_time_left=1800,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(es)
        db_session.commit()

        assert es.id is not None
        assert es.application_id == test_app.id
        assert es.interview_state == "not_started"

    def test_property_delegates_to_evaluation_session(self, db_session, test_app):
        """@property accessors MUST read from EvaluationSession."""
        # Set the correct value on EvaluationSession
        es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="in_progress",
            interview_progress=5,
            interview_time_left=1500,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(es)
        db_session.commit()
        db_session.refresh(test_app)

        # The @property MUST return EvaluationSession's value, not the deprecated column
        assert test_app.interview_state == "in_progress", (
            f"Expected 'in_progress' from EvaluationSession, got '{test_app.interview_state}'"
        )
        assert test_app.interview_progress == 5
        assert test_app.interview_time_left == 1500

    def test_latest_eval_session_returns_newest(self, db_session, test_app):
        """_latest_eval_session() must return the session with the highest id."""
        old_es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="completed",
            interview_progress=15,
            interview_time_left=0,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(old_es)
        db_session.flush()

        new_es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="not_started",
            interview_progress=0,
            interview_time_left=1800,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(new_es)
        db_session.commit()
        db_session.refresh(test_app)

        latest = test_app._latest_eval_session()
        assert latest is not None
        assert latest.id == new_es.id, (
            f"Expected latest session id={new_es.id}, got id={latest.id}"
        )
        assert latest.interview_state == "not_started"

    def test_latest_returns_none_when_no_sessions(self, db_session, test_app):
        """_latest_eval_session() must return None when no EvaluationSessions exist."""
        latest = test_app._latest_eval_session()
        assert latest is None

    def test_property_returns_none_when_no_session(self, db_session, test_app):
        """@property returns None when no EvaluationSession exists."""
        assert test_app.interview_state is None
        assert test_app.interview_progress is None

    def test_property_returns_none_when_no_session_and_no_fallback(
        self, db_session, test_app
    ):
        """@property returns None when no EvaluationSession exists (video_file_path not in ES)."""
        assert test_app.video_file_path is None

    def test_sync_ai_interview_session_writes_only_to_evaluation_session(
        self, db_session, test_app
    ):
        """sync_ai_interview_session() MUST write only to EvaluationSession, never to Application."""
        es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="in_progress",
            interview_progress=2,
            interview_time_left=1600,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(es)
        db_session.commit()
        # Expire the relationship so it's re-loaded from DB
        db_session.expire(test_app, attribute_names=["evaluation_sessions"])

        sync_ai_interview_session(
            db=db_session,
            app=test_app,
            interview_state="completed",
            interview_progress=15,
            interview_time_left=0,
        )

        db_session.flush()
        db_session.refresh(es)
        db_session.refresh(test_app)

        # EvaluationSession MUST have the new values
        assert es.interview_state == "completed", (
            f"Expected 'completed', got '{es.interview_state}'"
        )
        assert es.interview_progress == 15
        assert es.interview_time_left == 0

        # @property on Application must reflect the updated EvaluationSession value
        assert test_app.interview_state == "completed"

    def test_relationship_order_returns_newest_first(self, db_session, test_app):
        """evaluation_sessions relationship must return sessions in DESC order (newest first)."""
        ids = []
        for i in range(3):
            es = EvaluationSession(
                application_id=test_app.id,
                company_id=test_app.company_id,
                interview_state="not_started",
                interview_progress=0,
                interview_time_left=1800,
                interview_log=[],
                interview_questions=[],
            )
            db_session.add(es)
            db_session.flush()
            ids.append(es.id)
        db_session.commit()
        db_session.refresh(test_app)

        # Relationship must return newest first
        assert len(test_app.evaluation_sessions) == 3
        assert test_app.evaluation_sessions[0].id == ids[2], (
            f"Expected first element to be newest (id={ids[2]}), got id={test_app.evaluation_sessions[0].id}"
        )
        assert test_app.evaluation_sessions[2].id == ids[0], (
            f"Expected last element to be oldest (id={ids[0]}), got id={test_app.evaluation_sessions[2].id}"
        )

    def test_multiple_sessions_property_reads_newest(self, db_session, test_app):
        """With multiple EvaluationSessions, @property must read from the newest."""
        # Create old session (completed)
        old_es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="completed",
            interview_progress=15,
            interview_time_left=0,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(old_es)
        db_session.flush()

        # Create new session (reset — not_started)
        new_es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="not_started",
            interview_progress=0,
            interview_time_left=1800,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(new_es)
        db_session.commit()
        db_session.refresh(test_app)

        # @property must return NEWEST session's values
        assert test_app.interview_state == "not_started", (
            f"Expected 'not_started' from newest session, got '{test_app.interview_state}'"
        )
        assert test_app.interview_progress == 0
        assert test_app.interview_time_left == 1800

    def test_evaluation_session_query_filter(self, db_session, test_app):
        """Query filtering on interview_state must use EvaluationSession, not Application column."""
        # Create an EvaluationSession with interview_state="completed"
        es = EvaluationSession(
            application_id=test_app.id,
            company_id=test_app.company_id,
            interview_state="completed",
            interview_progress=15,
            interview_time_left=0,
            interview_log=[],
            interview_questions=[],
        )
        db_session.add(es)
        db_session.commit()

        # Query using the subquery pattern (latest session per application)
        latest_es = (
            db_session.query(
                EvaluationSession.application_id,
                func.max(EvaluationSession.id).label("max_id"),
            ).group_by(EvaluationSession.application_id)
        ).subquery("_latest_es")

        completed_apps = (
            db_session.query(Application)
            .join(latest_es, latest_es.c.application_id == Application.id)
            .join(EvaluationSession, EvaluationSession.id == latest_es.c.max_id)
            .filter(EvaluationSession.interview_state == "completed")
            .all()
        )

        assert len(completed_apps) == 1
        assert completed_apps[0].id == test_app.id

        # Filtering for "not_started" should return no results
        not_started_apps = (
            db_session.query(Application)
            .join(latest_es, latest_es.c.application_id == Application.id)
            .join(EvaluationSession, EvaluationSession.id == latest_es.c.max_id)
            .filter(EvaluationSession.interview_state == "not_started")
            .all()
        )
        assert len(not_started_apps) == 0

    def test_application_without_session_not_in_completed_query(
        self, db_session, test_app
    ):
        """Applications without any EvaluationSession must NOT appear in 'completed' queries."""
        # Note: test_app has no EvaluationSession at this point
        latest_es = (
            db_session.query(
                EvaluationSession.application_id,
                func.max(EvaluationSession.id).label("max_id"),
            ).group_by(EvaluationSession.application_id)
        ).subquery("_latest_es")

        # Inner join means apps without sessions are excluded
        completed_apps = (
            db_session.query(Application)
            .join(latest_es, latest_es.c.application_id == Application.id)
            .join(EvaluationSession, EvaluationSession.id == latest_es.c.max_id)
            .filter(EvaluationSession.interview_state == "completed")
            .all()
        )
        assert len(completed_apps) == 0
