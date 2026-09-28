"""P0-1 regression: interview chat must not trust a client-supplied session_id.

Before the fix, a logged-in user who was not the owner of an application
could POST /ai/interview/chat with {candidate_id: <victim app>, session_id:
<victim session>} and the chat core resolved the victim's application from
the (sequential) session id without any ownership check, writing a turn into
the victim's interview.
"""

import pytest

from backend.database import Application, EvaluationSession, User
from backend.dependencies import generate_interview_token
from backend.routers.ai_interview.chat import _caller_may_access_application
from backend.tests.conftest import _fetch_csrf_token, pwd_context
from backend.tests.test_recruiter_interview_invite import (  # noqa: F401
    _apply,
    candidate_profile,
    job,
    prior_analyzed_app,
)

CHAT_URL = "/api/v1/ai/interview/chat"


def _login(client, email, password):
    csrf = _fetch_csrf_token(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    return {
        "Authorization": f"Bearer {resp.json()['access_token']}",
        "X-CSRF-Token": csrf,
    }


def _latest_session(db_session, app_id):
    db_session.expire_all()
    return (
        db_session.query(EvaluationSession)
        .filter(EvaluationSession.application_id == app_id)
        .order_by(EvaluationSession.id.desc())
        .first()
    )


@pytest.fixture
def invited_app(
    client,
    auth_headers,
    recruiter_headers,
    job,  # noqa: F811
    candidate_profile,  # noqa: F811
    prior_analyzed_app,  # noqa: F811
    db_session,
    monkeypatch,
):
    """Candidate A (test_user) applies and is invited by the recruiter."""
    resp = _apply(client, auth_headers, job.id, monkeypatch)
    assert resp.status_code == 200, resp.text
    app_id = resp.json()["application_id"]
    inv = client.post(
        f"/api/v1/recruiter/applications/{app_id}/invite-interview",
        headers=recruiter_headers,
    )
    assert inv.status_code == 200, inv.text
    es = _latest_session(db_session, app_id)
    assert es is not None
    return app_id, es.id


@pytest.fixture
def attacker_headers(client, db_session):
    """Candidate B: an unrelated, verified candidate account."""
    attacker = User(
        email="attacker@example.com",
        name="Attacker",
        hashed_password=pwd_context.hash("attackerpass123"),
        role="candidate",
        email_verified=True,
    )
    db_session.add(attacker)
    db_session.commit()
    return _login(client, "attacker@example.com", "attackerpass123")


def test_other_candidate_cannot_chat_with_victim_session_id(
    client, invited_app, attacker_headers, db_session
):
    app_id, session_id = invited_app
    before = _latest_session(db_session, app_id)
    log_before = len(before.interview_log or [])
    seq_before = before.interview_turn_seq

    resp = client.post(
        CHAT_URL,
        headers=attacker_headers,
        json={
            "candidate_id": app_id,
            "session_id": session_id,
            "message": "I am ready, start the interview",
        },
    )

    assert resp.status_code == 404
    after = _latest_session(db_session, app_id)
    assert after.id == session_id
    assert len(after.interview_log or []) == log_before
    assert after.interview_turn_seq == seq_before


def test_other_candidate_cannot_chat_with_own_candidate_id_and_victim_session(
    client, invited_app, attacker_headers, db_session
):
    """A bogus candidate_id plus the victim's session id is rejected too."""
    app_id, session_id = invited_app
    before = _latest_session(db_session, app_id)
    log_before = len(before.interview_log or [])

    resp = client.post(
        CHAT_URL,
        headers=attacker_headers,
        json={"candidate_id": 999999, "session_id": session_id, "message": "hi"},
    )

    assert resp.status_code == 404
    assert len(_latest_session(db_session, app_id).interview_log or []) == log_before


def test_owner_can_chat_with_own_session_id(
    client, invited_app, auth_headers, db_session
):
    app_id, session_id = invited_app

    resp = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={
            "candidate_id": app_id,
            "session_id": session_id,
            "message": "I am ready, start the interview",
        },
    )

    # Question generation has no provider in tests and returns a structured
    # retry state; the point is that the owner is authorised and the turn
    # is processed against their own session.
    assert resp.status_code == 200, resp.text
    after = _latest_session(db_session, app_id)
    assert after.id == session_id
    assert len(after.interview_log or []) >= 1


def test_guest_signed_token_access_still_works_and_ignores_foreign_session(
    client, invited_app, db_session, test_company
):
    """Guest HMAC access is token-bound; a foreign session_id cannot redirect it."""
    victim_app_id, victim_session_id = invited_app
    victim_log_before = len(
        _latest_session(db_session, victim_app_id).interview_log or []
    )

    guest_app = Application(
        company_id=test_company.id,
        email="guest@example.com",
        full_name="Guest Candidate",
        status="invited",
        declared_role="Python Developer",
    )
    db_session.add(guest_app)
    db_session.commit()
    token = generate_interview_token(guest_app.id)["token"]

    resp = client.post(
        CHAT_URL,
        headers={"X-CSRF-Token": _fetch_csrf_token(client)},
        json={
            "candidate_id": guest_app.id,
            "token": token,
            "session_id": victim_session_id,
            "message": "ready",
        },
    )

    assert resp.status_code not in (401, 403, 404), resp.text
    # The guest request was served against the guest's own application.
    assert (
        len(_latest_session(db_session, victim_app_id).interview_log or [])
        == victim_log_before
    )


def test_caller_may_access_application_rules(
    db_session, test_user, test_company, test_recruiter
):
    owned = Application(
        user_id=test_user.id, company_id=test_company.id, status="invited"
    )
    guest = Application(user_id=None, company_id=test_company.id, status="invited")
    db_session.add_all([owned, guest])
    db_session.commit()

    assert _caller_may_access_application(test_user, owned, db_session) is True
    assert _caller_may_access_application(None, owned, db_session) is False
    # A logged-in candidate never gains access to an unowned (guest) app.
    assert _caller_may_access_application(test_user, guest, db_session) is False
    # Same-company recruiter keeps legitimate access.
    assert _caller_may_access_application(test_recruiter, owned, db_session) is True
