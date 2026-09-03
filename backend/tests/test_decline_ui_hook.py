"""
Tests for recruiter-side declined-invitations UI hook (Bug U-07).

The candidate decline endpoint already existed; this fix adds:
  * Structured ``declined_at`` / ``decline_reason`` /
    ``decline_initiated_by`` columns on the Application model.
  * The candidate decline endpoint writes the new columns.
  * The recruiter list endpoint returns ``is_declined``,
    ``decline_reason``, ``declined_at`` so the UI can render a
    "Declined by candidate" badge.
  * The list endpoint accepts ``status=declined`` as an alias
    for ``status=rejected``.
"""

import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import Application, Base, User  # noqa: E402


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


def _make_user(db, id, email, name, role="candidate"):
    u = User(
        id=id,
        email=email,
        name=name,
        phone="+15555550100",
        role=role,
        hashed_password="x",
    )
    db.add(u)
    db.flush()
    return u


def test_decline_columns_exist_on_model():
    cols = {c.name for c in Application.__table__.columns}
    for required in {"declined_at", "decline_reason", "decline_initiated_by"}:
        assert required in cols, f"Missing column {required}"


def test_structured_decline_round_trip(db_session):
    candidate = _make_user(db_session, 2, "c@example.com", "Cand")
    app = Application(
        user_id=candidate.id,
        status="rejected",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
    )
    db_session.add(app)
    db_session.flush()

    # Simulate the candidate decline endpoint writing the
    # structured columns.
    app.declined_at = datetime.now(timezone.utc)
    app.decline_reason = "Accepted a competing offer."
    app.decline_initiated_by = "candidate"
    db_session.commit()

    fetched = db_session.query(Application).filter(Application.id == app.id).first()
    assert fetched.declined_at is not None
    assert fetched.decline_reason == "Accepted a competing offer."
    assert fetched.decline_initiated_by == "candidate"


def test_recruiter_list_exposes_decline_fields(db_session):
    from backend.routers.candidate_management import list_recruiter_candidates

    recruiter = _make_user(db_session, 1, "r@example.com", "Recruiter", "recruiter")
    candidate = _make_user(db_session, 2, "c@example.com", "Cand")

    # A Job owned by this recruiter (the list filters by
    # job ownership).
    from backend.database import Job

    job_a = Job(
        id=1,
        recruiter_id=recruiter.id,
        title="Senior Engineer A",
        company="Acme",
        type="full-time",
        location="Remote",
        is_active=True,
    )
    job_b = Job(
        id=2,
        recruiter_id=recruiter.id,
        title="Senior Engineer B",
        company="Acme",
        type="full-time",
        location="Remote",
        is_active=True,
    )
    db_session.add_all([job_a, job_b])
    db_session.flush()

    # Two applications: one declined, one active. They reference
    # different jobs to dodge the (user_id, job_id) unique
    # constraint.
    declined_app = Application(
        user_id=candidate.id,
        job_id=job_a.id,
        status="rejected",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
        declined_at=datetime.now(timezone.utc),
        decline_reason="Not interested in remote roles",
        decline_initiated_by="candidate",
    )
    active_app = Application(
        user_id=candidate.id,
        job_id=job_b.id,
        status="pending",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
    )
    db_session.add_all([declined_app, active_app])
    db_session.commit()

    # Hit the list endpoint with status=declined (alias for rejected).
    response = list_recruiter_candidates(
        status="declined",
        job_id=None,
        page=1,
        per_page=20,
        recruiter=recruiter,
        db=db_session,
    )
    # Only the declined one should be returned.
    assert len(response["candidates"]) == 1
    item = response["candidates"][0]
    assert item["is_declined"] is True
    assert item["decline_reason"] == "Not interested in remote roles"
    assert item["declined_at"] is not None


def test_recruiter_list_inactive_status_no_decline_metadata(db_session):
    from backend.routers.candidate_management import list_recruiter_candidates

    recruiter = _make_user(db_session, 1, "r@example.com", "Recruiter", "recruiter")
    candidate = _make_user(db_session, 2, "c@example.com", "Cand")
    from backend.database import Job

    job = Job(
        id=1,
        recruiter_id=recruiter.id,
        title="Senior Engineer",
        company="Acme",
        type="full-time",
        location="Remote",
        is_active=True,
    )
    db_session.add(job)
    db_session.flush()
    active_app = Application(
        user_id=candidate.id,
        job_id=job.id,
        status="pending",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
    )
    db_session.add(active_app)
    db_session.commit()

    response = list_recruiter_candidates(
        status=None,
        job_id=None,
        page=1,
        per_page=20,
        recruiter=recruiter,
        db=db_session,
    )
    assert len(response["candidates"]) == 1
    item = response["candidates"][0]
    assert item["is_declined"] is False
    assert item["decline_reason"] is None
    assert item["declined_at"] is None
