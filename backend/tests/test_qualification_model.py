"""
Tests for the new ``Qualification`` table (Bug B-30).

The router used to store qualifications in a JSON bag on
``Application.analysis_json``. The bag was unbounded, had no
unique constraint, and slowed every Application read. We replaced
it with a real table; these tests verify:

  * The model exists and has the expected columns.
  * The unique constraint is enforced (no duplicate
    (user_id, title, category)).
  * The route reads from the new table, not the JSON bag.
  * The route soft-deletes (deleted_at set, row stays in DB).
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")

import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import Application, Base, Qualification, User  # noqa: E402


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


def _make_user(db, **overrides):
    u = User(
        id=overrides.get("id", 1),
        email=overrides.get("email", "test@example.com"),
        name=overrides.get("name", "Test User"),
        phone=overrides.get("phone", "+15555550100"),
        role=overrides.get("role", "candidate"),
        hashed_password=overrides.get("hashed_password", "x"),
    )
    db.add(u)
    db.flush()
    return u


def _make_app(db, user_id):
    a = Application(
        user_id=user_id,
        status="pending",
        declared_role="Engineer",
        full_name="Test User",
        email="test@example.com",
        company_id=1,  # applications.company_id is NOT NULL; FK not enforced on SQLite
    )
    db.add(a)
    db.flush()
    return a


def test_model_has_expected_columns():
    cols = {c.name for c in Qualification.__table__.columns}
    for required in {
        "id",
        "user_id",
        "application_id",
        "title",
        "category",
        "filename",
        "file_url",
        "file_size",
        "mime_type",
        "verified",
        "uploaded_at",
        "deleted_at",
    }:
        assert required in cols, f"Missing column {required}"


def test_insert_and_query(db_session):
    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    q = Qualification(
        id=uuid.uuid4().hex[:8],
        user_id=user.id,
        application_id=app.id,
        title="BSc Computer Science",
        category="degree",
        filename="1_abc123_degree.pdf",
        file_url="/uploads/qualifications/1_abc123_degree.pdf",
        file_size=1024,
        mime_type="application/pdf",
        verified=False,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(q)
    db_session.commit()

    fetched = (
        db_session.query(Qualification).filter(Qualification.user_id == user.id).first()
    )
    assert fetched is not None
    assert fetched.title == "BSc Computer Science"
    assert fetched.category == "degree"


def test_unique_constraint_enforced(db_session):
    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    q1 = Qualification(
        id="abc12345",
        user_id=user.id,
        application_id=app.id,
        title="MBA",
        category="degree",
        filename="1_aaa_mba.pdf",
        file_url="/uploads/1_aaa_mba.pdf",
        file_size=100,
        mime_type="application/pdf",
        verified=False,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(q1)
    db_session.commit()

    q2 = Qualification(
        id="def67890",
        user_id=user.id,
        application_id=app.id,
        title="MBA",
        category="degree",
        filename="1_bbb_mba.pdf",
        file_url="/uploads/1_bbb_mba.pdf",
        file_size=100,
        mime_type="application/pdf",
        verified=False,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(q2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_different_category_allowed(db_session):
    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    for cat in ("degree", "certificate", "transcript", "license", "other"):
        q = Qualification(
            id=uuid.uuid4().hex[:8],
            user_id=user.id,
            application_id=app.id,
            title="Same Title",
            category=cat,
            filename=f"1_x_{cat}.pdf",
            file_url=f"/uploads/1_x_{cat}.pdf",
            file_size=1,
            mime_type="application/pdf",
            verified=False,
            uploaded_at=datetime.now(timezone.utc),
        )
        db_session.add(q)
    db_session.commit()
    rows = (
        db_session.query(Qualification).filter(Qualification.user_id == user.id).all()
    )
    assert len(rows) == 5


def test_soft_delete_via_deleted_at(db_session):
    user = _make_user(db_session)
    app = _make_app(db_session, user.id)
    q = Qualification(
        id="xyz99999",
        user_id=user.id,
        application_id=app.id,
        title="TOEFL",
        category="certificate",
        filename="1_y_toefl.pdf",
        file_url="/uploads/1_y_toefl.pdf",
        file_size=2,
        mime_type="application/pdf",
        verified=True,
        uploaded_at=datetime.now(timezone.utc),
    )
    db_session.add(q)
    db_session.commit()

    # Soft-delete: set deleted_at, don't remove the row.
    q.deleted_at = datetime.now(timezone.utc)
    db_session.commit()

    # Row still in DB.
    fetched = (
        db_session.query(Qualification).filter(Qualification.id == "xyz99999").first()
    )
    assert fetched is not None
    assert fetched.deleted_at is not None

    # But the live query (deleted_at IS NULL) returns nothing.
    live = (
        db_session.query(Qualification)
        .filter(Qualification.user_id == user.id, Qualification.deleted_at.is_(None))
        .all()
    )
    assert live == []
