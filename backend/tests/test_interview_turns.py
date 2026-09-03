"""
Tests for the ``interview_turns`` table.

The legacy ``Application.interview_qa_structured`` JSON bag was
removed in Phase 3B (June 2026). All turn data lives in the
dedicated ``InterviewTurn`` table.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import (  # noqa: E402
    Application,
    Base,
    Company,
    CompanyMember,
    EvaluationSession,
    InterviewTurn,
    User,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_user(db, id=1, email="c@example.com", name="Cand"):
    u = User(
        id=id,
        email=email,
        name=name,
        phone="+15555550100",
        role="candidate",
        hashed_password="x",
    )
    db.add(u)
    db.flush()
    return u


def _make_company(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.flush()
    return c


def _make_app(db, user_id):
    company = _make_company(db)
    db.add(
        CompanyMember(
            company_id=company.id,
            user_id=user_id,
            role="recruiter" if user_id == 1 else "member",
        )
    )
    a = Application(
        user_id=user_id,
        company_id=company.id,
        status="pending",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
    )
    db.add(a)
    db.flush()
    return a


def test_model_has_expected_columns():
    cols = {c.name for c in InterviewTurn.__table__.columns}
    for required in {
        "id",
        "application_id",
        "user_id",
        "turn_number",
        "question",
        "answer",
        "score",
        "feedback",
        "reasoning",
        "quality",
        "type",
        "difficulty",
        "response_time_seconds",
        "status",
        "question_timestamp",
        "answer_timestamp",
        "created_at",
    }:
        assert required in cols, f"Missing column {required}"


def test_write_turn_inserts_and_overwrites(db_session):
    from backend.interview_turns import write_turn

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)

    # First write: insert.
    write_turn(
        db_session,
        app,
        turn_number=1,
        question="What is OOP?",
        answer="Object-oriented programming",
        score=85.0,
        feedback="Good",
    )
    db_session.commit()
    row = (
        db_session.query(InterviewTurn)
        .filter(InterviewTurn.evaluation_session_id.isnot(None))
        .first()
    )
    assert row is not None
    assert row.turn_number == 1
    assert row.score == 85.0

    # Second write for the same turn: overwrite.
    write_turn(
        db_session,
        app,
        turn_number=1,
        question="What is OOP?",
        answer="Object-oriented programming",
        score=92.0,
        feedback="Better after a second pass",
    )
    db_session.commit()
    rows = (
        db_session.query(InterviewTurn)
        .filter(InterviewTurn.evaluation_session_id.isnot(None))
        .all()
    )
    assert len(rows) == 1
    assert rows[0].score == 92.0
    assert rows[0].feedback == "Better after a second pass"


def test_unique_turn_number_per_application(db_session):
    from sqlalchemy.exc import IntegrityError

    from backend.interview_turns import write_turn

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    write_turn(db_session, app, 1, question="q1", answer="a1")
    db_session.commit()
    # Direct insert at the ORM level bypassing the helper
    # should violate the unique constraint.
    # Need an EvaluationSession for the FK constraint.
    es = EvaluationSession(
        application_id=app.id, company_id=app.company_id, status="created"
    )
    db_session.add(es)
    db_session.flush()
    dup = InterviewTurn(
        application_id=app.id,
        user_id=user.id,
        turn_number=1,
        company_id=app.company_id,
        evaluation_session_id=es.id,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_load_turns_from_new_table(db_session):
    from backend.interview_turns import load_turns, write_turn

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    write_turn(db_session, app, 1, question="Q1", answer="A1", score=80.0)
    write_turn(db_session, app, 2, question="Q2", answer="A2", score=90.0)
    write_turn(db_session, app, 3, question="Q3", answer="A3", score=70.0)
    db_session.commit()

    turns = load_turns(db_session, app)
    assert len(turns) == 3
    assert [t["number"] for t in turns] == [1, 2, 3]
    assert turns[1]["score"] == 90.0


def test_load_turns_returns_empty_when_no_turns(db_session):
    from backend.interview_turns import load_turns

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    db_session.commit()
    turns = load_turns(db_session, app)
    assert turns == []
