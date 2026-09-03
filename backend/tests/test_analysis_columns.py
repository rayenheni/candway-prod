"""
Tests for the analysis-column lift (Bug B-31).

The audit's analysis_json column on ``Application`` was a
20-purpose bag. We lifted the four most-read keys
(strengths, weaknesses, final_score_breakdown, score) to
dedicated columns.

The bag continues to exist (we don't drop it) for the
remaining 14 keys. The helper mirrors writes to both, and
readers fall back to the bag if the column is NULL.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")

import json  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import Application, Base, Company, User  # noqa: E402


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


def _make_company(db):
    c = Company(name="Test Co", slug="test-co")
    db.add(c)
    db.flush()
    return c


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


def _make_app(db, user_id):
    company = _make_company(db)
    a = Application(
        user_id=user_id,
        company_id=company.id,
        status="pending",
        full_name="Cand",
        email="c@example.com",
    )
    db.add(a)
    db.flush()
    return a


def test_columns_exist():
    cols = {c.name for c in Application.__table__.columns}
    for required in {
        "analysis_strengths",
        "analysis_weaknesses",
        "analysis_score_breakdown",
        "analysis_score",
    }:
        assert required in cols, f"Missing column {required}"


def test_write_analysis_columns(db_session):
    from backend.analysis_columns import write_analysis_columns

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)

    write_analysis_columns(
        db_session,
        app,
        strengths=["Strong communicator", "Good problem solver"],
        weaknesses=["Limited TypeScript experience"],
        score_breakdown={"cv": 80, "interview": 70, "per_turn": 75},
        score=76.0,
        also_write_bag=False,
    )
    db_session.commit()

    fetched = db_session.query(Application).filter(Application.id == app.id).first()
    assert fetched.analysis_strengths == ["Strong communicator", "Good problem solver"]
    assert fetched.analysis_weaknesses == ["Limited TypeScript experience"]
    assert fetched.analysis_score_breakdown == {
        "cv": 80,
        "interview": 70,
        "per_turn": 75,
    }
    assert fetched.analysis_score == 76.0


def test_read_analysis_prefers_columns_over_bag(db_session):
    from backend.analysis_columns import read_analysis, write_analysis_columns

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)

    # Bag has different values from the columns.
    app.analysis_json = json.dumps(
        {
            "strengths": ["Bag strength"],
            "weaknesses": ["Bag weakness"],
            "final_score_breakdown": {"cv": 50},
            "score": 50.0,
        }
    )
    write_analysis_columns(
        db_session,
        app,
        strengths=["Column strength"],
        weaknesses=["Column weakness"],
        score_breakdown={"cv": 90, "interview": 80},
        score=85.0,
        also_write_bag=False,
    )
    db_session.commit()

    out = read_analysis(app)
    assert out["strengths"] == ["Column strength"]
    assert out["weaknesses"] == ["Column weakness"]
    assert out["score_breakdown"] == {"cv": 90, "interview": 80}
    assert out["analysis_score"] == 85.0


def test_read_analysis_falls_back_to_bag(db_session):
    from backend.analysis_columns import read_analysis

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    app.analysis_json = json.dumps(
        {
            "strengths": ["Bag strength"],
            "weaknesses": ["Bag weakness"],
            "missing_skills": ["Bag missing"],
            "final_score_breakdown": {"cv": 70},
            "match_score": 73.0,
        }
    )
    db_session.commit()

    out = read_analysis(app, include_bag_fallback=True)
    assert out["strengths"] == ["Bag strength"]
    assert out["weaknesses"] == [
        "Bag weakness"
    ]  # bag "weaknesses" wins over "missing_skills"
    assert out["score_breakdown"] == {"cv": 70}
    assert out["analysis_score"] == 73.0  # bag match_score fallback


def test_mirror_to_bag_keeps_legacy_readers_happy(db_session):
    from backend.analysis_columns import write_analysis_columns

    user = _make_user(db_session)
    app = _make_app(db_session, user.id)

    write_analysis_columns(
        db_session,
        app,
        strengths=["Mirrored"],
        weaknesses=[],
        score_breakdown={"cv": 60},
        score=60.0,
        also_write_bag=True,
    )
    db_session.commit()

    bag = json.loads(app.cv_document.analysis_json)
    assert bag["strengths"] == ["Mirrored"]
    assert bag["final_score_breakdown"] == {"cv": 60}
    assert bag["score"] == 60.0


def test_score_column_indexed_for_queries():
    """Verify the model declares the index inline so a future
    ``WHERE analysis_score > 80`` doesn't table-scan.

    (The index was added via the Alembic migration
    ``a5b6c7d8e9f0_lift_analysis_keys.py``; this test asserts
    the model carries the matching index for in-memory test
    schemas.)
    """
    from backend.database import Application

    table = Application.__table__
    indexes = {i.name for i in table.indexes}
    # Inline index is added below; if the assertion fails the
    # model and the migration are out of sync.
    assert "ix_applications_analysis_score" in indexes or any(
        "analysis_score" in (i.name or "") for i in table.indexes
    )
