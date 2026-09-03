"""
Tests for the offer_declined application status (Bug: decline failed on
the applications.status CHECK constraint).

recruiter_offers.py:464 writes ``app.status = "offer_declined"`` when a
candidate declines an offer, but the ``ck_application_status`` CHECK
constraint never listed that value, so on enforcing databases the commit
raised a constraint violation and the decline failed.

Fix scope covered here:
  * The model CHECK constraint accepts ``offer_declined``.
  * A bogus status is still rejected (constraint stays enforced).
  * The full candidate decline flow persists offer.status="declined" and
    application.status="offer_declined".
  * The recruiter list endpoint surfaces is_declined=True for the new status.
"""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_encoding_12345")
os.environ.setdefault("TESTING", "true")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.database import (  # noqa: E402
    Application,
    Base,
    Company,
    CompanyMember,
    Job,
    Offer,
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


@pytest.fixture
def company(db_session):
    c = Company(name="Test Company", slug="test-company-offer")
    db_session.add(c)
    db_session.flush()
    return c


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


def _make_app(db, user, status="pending", job=None, company_id=None):
    app = Application(
        user_id=user.id,
        job_id=job.id if job else None,
        company_id=company_id,
        status=status,
        declared_role="Engineer",
        full_name=user.name,
        email=user.email,
    )
    db.add(app)
    db.flush()
    return app


def _make_offer(db, app, created_by, company_id=None):
    offer = Offer(
        application_id=app.id,
        created_by=created_by.id,
        company_id=company_id,
        position="Senior Engineer",
        salary="5000 TND",
        subject="Offer",
        body="<p>Welcome</p>",
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(offer)
    db.flush()
    return offer


def test_model_accepts_offer_declined(db_session, company):
    """Application.status='offer_declined' must commit without error."""
    candidate = _make_user(db_session, 2, "c@example.com", "Cand")
    app = Application(
        user_id=candidate.id,
        company_id=company.id,
        status="offer_declined",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
    )
    db_session.add(app)
    db_session.commit()

    fetched = db_session.query(Application).filter(Application.id == app.id).first()
    assert fetched.status == "offer_declined"


def test_model_still_rejects_bogus_status(db_session, company):
    """The CHECK constraint must remain enforced for unknown statuses."""
    candidate = _make_user(db_session, 2, "c@example.com", "Cand")
    app = Application(
        user_id=candidate.id,
        company_id=company.id,
        status="bogus_status",
        declared_role="Engineer",
        full_name="Cand",
        email="c@example.com",
    )
    db_session.add(app)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_offer_decline_flow_persists_status(db_session, company):
    """Full decline: offer.status='declined', app.status='offer_declined'."""
    from backend.routers.recruiter_offers import respond_to_offer

    candidate = _make_user(db_session, 2, "c@example.com", "Cand")
    recruiter = _make_user(db_session, 1, "r@example.com", "Recruiter", "recruiter")
    db_session.add(
        CompanyMember(
            company_id=company.id, user_id=recruiter.id, role="admin", is_active=True
        )
    )
    job = Job(
        id=1,
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Senior Engineer",
        company_name="Acme",
        type="full-time",
        location="Remote",
        is_active=True,
    )
    db_session.add(job)
    db_session.flush()
    app = _make_app(db_session, candidate, status="offer", job=job, company_id=company.id)
    offer = _make_offer(db_session, app, recruiter, company_id=company.id)

    result = respond_to_offer(
        offer_id=offer.id,
        accept=False,
        response_message="Accepted a competing offer",
        candidate=candidate,
        db=db_session,
    )
    assert result["success"] is True
    assert result["status"] == "declined"

    db_session.expire_all()
    app = db_session.query(Application).filter(Application.id == app.id).first()
    offer = db_session.query(Offer).filter(Offer.id == offer.id).first()
    assert app.status == "offer_declined"
    assert offer.status == "declined"
    assert offer.candidate_response == "Accepted a competing offer"


def test_recruiter_list_flags_offer_declined_as_declined(db_session, company):
    """Recruiter list must surface is_declined=True for offer_declined."""
    from backend.routers.recruiter_candidates.applications import (
        get_application_details,
    )

    candidate = _make_user(db_session, 2, "c@example.com", "Cand")
    recruiter = _make_user(db_session, 1, "r@example.com", "Recruiter", "recruiter")
    db_session.add(
        CompanyMember(
            company_id=company.id, user_id=recruiter.id, role="admin", is_active=True
        )
    )
    job = Job(
        id=1,
        recruiter_id=recruiter.id,
        company_id=company.id,
        title="Senior Engineer",
        company_name="Acme",
        type="full-time",
        location="Remote",
        is_active=True,
    )
    db_session.add(job)
    db_session.flush()
    app = _make_app(db_session, candidate, status="offer_declined", job=job, company_id=company.id)
    db_session.commit()

    detail = get_application_details(app_id=app.id, recruiter=recruiter, db=db_session)
    assert detail["status"] == "offer_declined"
    assert detail["is_declined"] is True


def test_recruiter_list_funnel_accepts_offer_declined():
    """_FUNNEL_OFFER already buckets offer_declined as an offer-stage entry."""
    from backend.routers.recruiter_jobs import _FUNNEL_OFFER

    assert "offer_declined" in _FUNNEL_OFFER


def test_display_status_passthrough_for_offer_declined():
    """_DISPLAY_STATUS_MAP must keep offer_declined visible, not remapped."""
    from backend.routers.recruiter_candidates.search import _DISPLAY_STATUS_MAP

    assert _DISPLAY_STATUS_MAP.get("offer_declined") == "offer_declined"
