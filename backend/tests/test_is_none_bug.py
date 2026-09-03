"""
Regression test for the ``Column is None`` filter bug.

The admin users management page was returning 0 users even
though the DB had 41 active rows. Root cause: the route did

    query = db.query(User).filter(User.deleted_at is None)

which is a Python ``is`` comparison on the *Column descriptor*
itself. Since the descriptor is never ``None`` at the class
level, the expression evaluated to ``False`` and SQLAlchemy
emitted ``WHERE false``, returning zero rows.

The fix is to use ``== None`` (or ``.is_(None)``) which pushes
the comparison to SQL.

The same bug existed in the recruiter pipeline-stages router
(``backend/routers/recruiter_enhancements/stages.py``), which
this test covers too.
"""

import os

# Set env BEFORE importing backend modules.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import Base, PipelineStage, User  # noqa: E402


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


def _make_user(db, **kwargs):
    defaults = dict(
        email="u@example.com",
        name="User",
        phone="+15555550100",
        role="candidate",
        hashed_password="x",
        deleted_at=None,
    )
    defaults.update(kwargs)
    u = User(**defaults)
    db.add(u)
    db.flush()
    return u


def _make_stage(db, **kwargs):
    defaults = dict(
        recruiter_id=1,
        name="Applied",
        slug="applied",
        color="#000",
        icon="fa-circle",
        sort_order=1,
        is_active=True,
        batch_id=None,
    )
    defaults.update(kwargs)
    s = PipelineStage(**defaults)
    db.add(s)
    db.flush()
    return s


# ---------- pure-SQLAlchemy tests (always run) ----------


def test_old_is_none_form_compiles_to_where_false(db_session):
    """The buggy ``Column is None`` form really does emit WHERE false."""
    _make_user(db_session, id=1, email="a@example.com")
    db_session.commit()

    buggy = db_session.query(User).filter(User.deleted_at is None)
    sql = str(buggy.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "false" in sql.lower(), sql
    assert buggy.count() == 0


def test_fixed_eq_none_form_returns_active_users(db_session):
    """The fixed ``Column == None`` form returns non-deleted users."""
    _make_user(db_session, id=1, email="a@example.com", name="Alice")
    _make_user(db_session, id=2, email="b@example.com", name="Bob")
    _make_user(
        db_session,
        id=3,
        email="c@example.com",
        name="Carol",
        deleted_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    active = db_session.query(User).filter(User.deleted_at == None).all()  # noqa: E711
    assert len(active) == 2
    assert {u.email for u in active} == {"a@example.com", "b@example.com"}

    # Confirm the buggy form is still 0.
    buggy = db_session.query(User).filter(User.deleted_at is None).all()
    assert buggy == []


def test_recruiter_stages_fixed_form_returns_global_stage(db_session):
    """The same bug fix applies to the recruiter stages router."""
    _make_stage(db_session, id=1, name="Applied", slug="applied", sort_order=1)
    _make_stage(
        db_session,
        id=2,
        name="Phone Screen",
        slug="phone_screen",
        sort_order=2,
        batch_id=42,
    )
    db_session.commit()

    # The fixed form.
    global_only = (
        db_session.query(PipelineStage)
        .filter(PipelineStage.batch_id == None)  # noqa: E711
        .all()
    )
    assert len(global_only) == 1
    assert global_only[0].name == "Applied"

    # The buggy form.
    buggy = db_session.query(PipelineStage).filter(PipelineStage.batch_id is None).all()
    assert buggy == []


# ---------- HTTP-level tests (use the real router function) ----------


def test_admin_users_endpoint_returns_real_count(db_session, monkeypatch):
    """The admin /users endpoint must return real rows after the fix."""
    from backend.routers.admin import users as admin_users

    _make_user(db_session, id=1, email="a@example.com", name="Alice", role="candidate")
    _make_user(db_session, id=2, email="b@example.com", name="Bob", role="recruiter")
    _make_user(
        db_session,
        id=3,
        email="c@example.com",
        name="Carol",
        role="candidate",
        deleted_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    admin = User(
        id=99,
        email="admin@example.com",
        name="Root",
        role="admin",
        hashed_password="x",
        is_super_admin=True,
    )

    resp = admin_users.get_all_users(
        role=None,
        search=None,
        page=1,
        per_page=50,
        current_user=admin,
        db=db_session,
    )
    assert resp["total"] == 2
    assert len(resp["users"]) == 2
    assert {u["email"] for u in resp["users"]} == {"a@example.com", "b@example.com"}


def test_recruiter_stages_endpoint_returns_global_stage(db_session, monkeypatch):
    """The recruiter /stages endpoint must return global stages after the fix."""
    from backend.routers.recruiter_enhancements import stages as stages_mod

    _make_stage(db_session, id=1, name="Applied", slug="applied", sort_order=1)
    _make_stage(
        db_session,
        id=2,
        name="Phone Screen",
        slug="phone_screen",
        sort_order=2,
        batch_id=42,
    )
    db_session.commit()

    recruiter = User(
        id=1,
        email="rec@example.com",
        name="Rec",
        role="recruiter",
        hashed_password="x",
    )

    resp = stages_mod.get_pipeline_stages(
        batch_id=None,
        recruiter=recruiter,
        db=db_session,
    )
    # The endpoint returns a list of dicts, not a {stages: ...}
    # envelope.
    assert isinstance(resp, list), resp
    assert any(s.get("name") == "Applied" for s in resp), resp
