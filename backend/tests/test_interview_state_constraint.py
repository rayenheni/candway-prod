"""Guard: the DB CHECK on evaluation_sessions.interview_state must accept
every state production code persists (alembic revision m80).

Regression: 'evaluating' (session.py, chat.py) and 'transcription_failed'
(media.py) are written to EvaluationSession.interview_state, and 'failed' /
'initializing' are engine state-machine targets, but the p1prod constraint
only allowed six states, so those writes raise IntegrityError on servers that
enforce CHECK constraints.
"""

import importlib.util
import pathlib
import re

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from backend.ai.state_machine import InterviewState, InterviewStateMachine
from backend.models.evaluation.evaluation import EvaluationSession

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Read-only legacy alias, normalised on read and never written.
_READ_ONLY_ALIASES = {InterviewState.IDLE}


def _load_m80():
    path = (
        REPO_ROOT / "alembic/versions/m80_widen_eval_session_interview_state_check.py"
    )
    spec = importlib.util.spec_from_file_location("m80", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m80 = _load_m80()


def _allowed_states() -> set[str]:
    (ck,) = [
        c
        for c in EvaluationSession.__table__.constraints
        if isinstance(c, CheckConstraint)
        and c.name == "ck_eval_session_interview_state"
    ]
    return set(re.findall(r"'([a-z_]+)'", str(ck.sqltext)))


@pytest.mark.parametrize(
    "state", [s for s in InterviewState if s not in _READ_ONLY_ALIASES]
)
def test_check_constraint_accepts_engine_state(state):
    assert state.value in _allowed_states()


def test_every_state_machine_target_is_allowed():
    targets = {t.value for ts in InterviewStateMachine.TRANSITIONS.values() for t in ts}
    assert targets <= _allowed_states()


def test_migration_m80_matches_model():
    assert set(m80.NEW_STATES) == _allowed_states()
    assert len(m80.NEW_STATES) == len(set(m80.NEW_STATES))


def test_transcription_failed_is_allowed():
    assert "transcription_failed" in _allowed_states()
    assert "transcription_failed" in m80.NEW_STATES
    assert "transcription_failed" not in m80.OLD_STATES


# (file, value) pairs matched by the scan below that are never persisted:
# display-only locals in the recruiter scoring view, and a column-name mapping
# in the phase3 backfill script.
_NOT_PERSISTED = {
    ("backend/routers/recruiter_candidates/scoring.py", "pending"),
    ("backend/routers/recruiter_candidates/scoring.py", "in-progress"),
    ("backend/migrations/phase3_backfill_app_to_eval_session.py", "interview_state"),
}
_WRITE_PATTERNS = (
    re.compile(r"\binterview_state\s*=\s*[\"']([A-Za-z_-]+)[\"']"),
    re.compile(r"[\"']interview_state[\"']\s*:\s*[\"']([A-Za-z_-]+)[\"']"),
)


def test_every_literal_interview_state_write_is_allowed():
    """Scan production code for literal interview_state writes (attribute
    assignment, keyword argument or dict update). Every value must be in the
    constraint, so a new state cannot ship without widening it (the
    media.py 'transcription_failed' bug)."""
    allowed = _allowed_states()
    seen: set[str] = set()
    offenders = []
    for path in sorted((REPO_ROOT / "backend").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("backend/tests/"):
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in _WRITE_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1)
                if (rel, value) in _NOT_PERSISTED:
                    continue
                seen.add(value)
                if value not in allowed:
                    line = text.count("\n", 0, match.start()) + 1
                    offenders.append(f"{rel}:{line} writes {value!r}")
    assert not offenders, "\n".join(offenders)
    # The scan must actually see the live writes it guards.
    assert {"evaluating", "transcription_failed", "expired"} <= seen


def _application(db_session, test_user, test_company):
    from backend.database import Application

    app = Application(
        user_id=test_user.id, company_id=test_company.id, status="interviewing"
    )
    db_session.add(app)
    db_session.flush()
    return app


@pytest.mark.parametrize("state", m80.NEW_STATES)
def test_db_accepts_every_allowed_state(db_session, test_user, test_company, state):
    app = _application(db_session, test_user, test_company)
    es = EvaluationSession(
        application_id=app.id, company_id=test_company.id, interview_state=state
    )
    db_session.add(es)
    db_session.commit()
    db_session.refresh(es)
    assert es.interview_state == state


@pytest.mark.parametrize("state", ["bogus", "idle", "in-progress", "pending"])
def test_db_rejects_unknown_state(db_session, test_user, test_company, state):
    app = _application(db_session, test_user, test_company)
    db_session.add(
        EvaluationSession(
            application_id=app.id, company_id=test_company.id, interview_state=state
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evaluating_transition_keeps_the_same_session(
    db_session, test_user, test_company
):
    """transition_to(EVALUATING) must update the live session, not spawn a
    blank one that becomes "latest" and orphans the transcript."""
    import asyncio

    from backend.ai.engine import InterviewEngine

    app = _application(db_session, test_user, test_company)
    live = EvaluationSession(
        application_id=app.id,
        company_id=test_company.id,
        status="in_progress",
        interview_state="in_progress",
        interview_log=[{"role": "user", "content": "final answer"}],
    )
    db_session.add(live)
    db_session.commit()

    asyncio.run(
        InterviewEngine(db_session).transition_to(
            app.id, InterviewState.EVALUATING, reason="Max questions reached"
        )
    )

    db_session.expire_all()
    sessions = (
        db_session.query(EvaluationSession).filter_by(application_id=app.id).all()
    )
    assert [s.id for s in sessions] == [live.id]
    assert sessions[0].interview_state == "evaluating"
    assert sessions[0].interview_last_saved is not None
