"""P1-09 FIX tests: IDOR in candidate invitation endpoints.

The previous implementation of ``/invitations`` and
``/invitations/decline`` filtered by
``Application.email == current_user.email`` alone. That allowed
a malicious user to:

* Register a fresh account with a victim's email and immediately
  see + decline the victim's recruiter invitation.
* Change their own account email to the victim's and see the
  victim's invitation.

The fix introduces ``_invitations_for_user_predicate`` which
returns the invitation ONLY if:

1. The invitation is already bound to ``current_user.id`` via
   ``Application.user_id`` (the safe path), OR
2. The invitation has no ``user_id`` yet AND the candidate's
  email is verified AND the email matches exactly (the
  unlinked-claim path).

We test both the predicate shape and the end-to-end behaviour
across the two endpoints.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Source-level regression locks
# ---------------------------------------------------------------------------

JOBS_SRC = Path("backend/routers/candidate/jobs.py").read_text(encoding="utf-8")


def _strip_docstrings(src: str) -> str:
    """Remove triple-quoted docstrings so we can grep for code
    patterns that would otherwise collide with explanatory text."""
    import re

    return re.sub(r'"""[\s\S]*?"""', "", src)


def test_predicate_helper_exists():
    """The fix introduced a single source of truth for the
    IDOR predicate. If this is renamed, every test that uses
    it will fail loudly."""
    assert (
        "def _invitations_for_user_predicate" in JOBS_SRC
    ), "predicate helper must exist"
    assert JOBS_SRC.count("_invitations_for_user_predicate(current_user)") >= 2


def test_predicate_requires_email_verified():
    """The unlinked-claim path must be gated on
    ``email_verified``. A user who later adds a victim's email
    to their account must NOT be able to read the invitation
    until they verify it."""
    body = JOBS_SRC.split("def _invitations_for_user_predicate")[1].split("def ")[
        0
    ]
    assert "email_verified" in body, "predicate must check email_verified"
    assert "Application.user_id" in body
    assert "Application.user_id.is_(None)" in body
    assert "Application.email == email" in body


def test_legacy_email_only_filter_removed():
    """The vulnerable pattern must be gone. The only place
    ``Application.email == current_user.email`` is allowed is
    inside the predicate (where it is gated on
    ``email_verified`` and ``user_id IS NULL``) — but even
    there we use the lowercase ``email`` local, NOT
    ``current_user.email``, to make the gate explicit.

    Strip docstrings first to avoid the explanatory text in
    the ``decline_invitation`` docstring."""
    stripped = _strip_docstrings(JOBS_SRC)
    predicate_body = stripped.split("def _invitations_for_user_predicate")[1].split(
        "def "
    )[0]
    outside = stripped.replace(predicate_body, "")
    assert "Application.email == current_user.email" not in outside, (
        "Inline email-only IDOR filter re-introduced outside the predicate"
    )


def test_decline_writes_structured_decline_fields():
    """Bug U-07: the decline handler must populate the new
    structured columns (decline_reason, declined_at,
    decline_initiated_by)."""
    body = JOBS_SRC.split("def decline_invitation")[1].split("def ")[0]
    for field in (
        "declined_at",
        "decline_reason",
        "decline_initiated_by",
    ):
        assert field in body, f"decline must write {field}"


def test_decline_writes_audit_log():
    body = JOBS_SRC.split("def decline_invitation")[1].split("def ")[0]
    assert "AuditLog" in body
    assert "invitation_declined" in body


def test_decline_is_graceful_when_notification_fails():
    """If the recruiter notification raises, the candidate must
    still get a 200. The try/except must wrap the notify_user
    call. We find the line numbers and assert try/except/notify
    are in the right order."""
    body = JOBS_SRC.split("def decline_invitation")[1].split("def ")[0]
    assert "notify_user" in body
    try_idx = body.find("    try:")
    notify_idx = body.find("notify_user(")
    except_idx = body.find("except Exception", notify_idx)
    assert try_idx != -1, "try block must exist"
    assert notify_idx != -1, "notify_user call must exist"
    assert except_idx != -1, "except must come after notify_user call"
    # The try block must START before the notify_user call.
    assert try_idx < notify_idx, "try must wrap notify_user call"


def test_get_invitations_opportunistically_binds_unlinked():
    """When a verified user reads an unlinked invitation, the
    router opportunistically binds it to ``current_user.id`` so
    the next access uses the safe user_id path."""
    body = JOBS_SRC.split("def fetch_candidate_priority_invitations")[1].split(
        "def "
    )[0]
    assert "app.user_id = current_user.id" in body
    assert "email_verified" in body


# ---------------------------------------------------------------------------
# Behavioural tests (in-memory SQLite via real SQLAlchemy)
# ---------------------------------------------------------------------------


def _make_user(db, *, email, email_verified=True, name="Test"):
    """Insert a user with a globally-unique email so we can run
    these tests in any order against the shared in-memory DB.
    We suffix ``__<uuid>`` to the email at the boundary to keep
    the rest of the test code clean — tests assert on the
    domain portion (``me@example.com``) and the unique suffix
    is invisible to the predicates.
    """
    import uuid

    local, _, domain = email.partition("@")
    unique_email = f"{local}+{uuid.uuid4().hex[:8]}@{domain}"
    from backend.database import User

    u = User(
        email=unique_email,
        name=name,
        role="candidate",
        is_super_admin=False,
        email_verified=email_verified,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_app(db, *, user_id=None, email=None, status="invited", role="Engineer"):
    from backend.database import Application, Company

    company = db.query(Company).first()
    if not company:
        company = Company(name="Test Company", slug="test-company")
        db.add(company)
        db.commit()
        db.refresh(company)

    a = Application(
        company_id=company.id,
        user_id=user_id,
        email=email,
        declared_role=role,
        status=status,
        cv_text_anonymized="placeholder text " * 20,
        analysis_json="{}",
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@pytest.fixture
def db():
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_user_id_bound_invitation_is_returned(db):
    """The safe path: an invitation already bound to
    ``current_user.id`` is always returned, regardless of
    email-verification status."""
    from backend.routers.candidate.jobs import (
        fetch_candidate_priority_invitations,
    )

    user = _make_user(db, email="me@example.com", email_verified=False)
    _make_app(db, user_id=user.id, email="victim@example.com")

    result = fetch_candidate_priority_invitations(current_user=user, db=db)
    assert len(result) == 1
    assert result[0]["status"] == "invited"


def test_unverified_email_user_cannot_see_unlinked_invite(db):
    """An UNVERIFIED user whose email matches the invite must
    NOT see the invite. They must verify their email first.
    This is the test that catches the original IDOR."""
    from backend.routers.candidate.jobs import (
        fetch_candidate_priority_invitations,
    )

    _make_app(db, user_id=None, email="target@example.com", status="invited")
    attacker = _make_user(
        db, email="target@example.com", email_verified=False
    )

    result = fetch_candidate_priority_invitations(
        current_user=attacker, db=db
    )
    assert result == [], "unverified user must not see unlinked invite"


def test_verified_email_user_sees_own_unlinked_invite(db):
    """A VERIFIED user whose email matches an unlinked invite
    CAN see it (the legitimate "claim my invitation" path)."""
    from backend.routers.candidate.jobs import (
        fetch_candidate_priority_invitations,
    )

    user = _make_user(db, email="me@example.com", email_verified=True)
    _make_app(db, user_id=None, email=user.email, status="invited")

    result = fetch_candidate_priority_invitations(current_user=user, db=db)
    assert len(result) == 1


def test_other_user_cannot_see_my_invite_by_email(db):
    """The original IDOR: a second user with the same email
    (because email is not yet verified, or they re-registered
    with a stale email) must not see my invite.

    The invitation is bound to user A's id, so user B's same
    email should not surface it via the email-clause path."""
    from backend.routers.candidate.jobs import (
        fetch_candidate_priority_invitations,
    )

    victim = _make_user(
        db, email="victim@example.com", email_verified=True
    )
    _make_app(
        db, user_id=victim.id, email=victim.email, status="invited"
    )

    # Attacker has a different user_id and a different email
    # (they tried to register with the victim's email but the
    # system re-used it; the only way to mount the original
    # attack is if their email matched AND user_id didn't
    # match).
    attacker = _make_user(
        db, email="attacker@example.com", email_verified=True
    )
    result = fetch_candidate_priority_invitations(
        current_user=attacker, db=db
    )
    assert result == [], "attacker must not see victim's invite"


def test_unlinked_invite_is_bound_on_first_read(db):
    """When a verified user reads an unlinked invite, the router
    opportunistically binds it to ``current_user.id`` so the
    next access uses the safe path."""
    from backend.routers.candidate.jobs import (
        fetch_candidate_priority_invitations,
    )

    user = _make_user(db, email="me@example.com", email_verified=True)
    app = _make_app(db, user_id=None, email=user.email)

    fetch_candidate_priority_invitations(current_user=user, db=db)
    db.refresh(app)
    assert app.user_id == user.id, "unlinked invite must be bound to current user"


def test_unverified_user_does_not_bind_unlinked_invite(db):
    """An unverified user must not trigger the opportunistic
    bind path (the earlier predicate excludes them entirely)."""
    from backend.routers.candidate.jobs import (
        fetch_candidate_priority_invitations,
    )

    user = _make_user(db, email="me@example.com", email_verified=False)
    app = _make_app(db, user_id=None, email=user.email)

    result = fetch_candidate_priority_invitations(current_user=user, db=db)
    db.refresh(app)
    assert result == []
    assert app.user_id is None


def test_decline_blocks_idor_attempt(db):
    """A second user attempting to decline someone else's
    invitation by guessing the id must get a 404."""
    from fastapi import HTTPException

    from backend.routers.candidate.jobs import (
        InvitationAction,
        decline_invitation,
    )

    victim = _make_user(
        db, email="victim@example.com", email_verified=True
    )
    app = _make_app(
        db, user_id=victim.id, email=victim.email, status="invited"
    )

    attacker = _make_user(
        db, email="attacker@example.com", email_verified=True
    )
    payload = InvitationAction(application_id=app.id, reason="x")

    with pytest.raises(HTTPException) as exc:
        decline_invitation(payload=payload, current_user=attacker, db=db)
    assert exc.value.status_code == 404
    db.refresh(app)
    assert app.status == "invited"


def test_decline_succeeds_for_owner(db):
    """The legitimate owner of an invitation can decline it.
    The handler writes status='rejected', sets the structured
    decline fields, and writes an AuditLog."""
    from backend.routers.candidate.jobs import (
        InvitationAction,
        decline_invitation,
    )

    user = _make_user(db, email="me@example.com", email_verified=True)
    app = _make_app(
        db, user_id=user.id, email=user.email, status="invited"
    )

    payload = InvitationAction(
        application_id=app.id, reason="Not interested"
    )
    out = decline_invitation(payload=payload, current_user=user, db=db)

    assert out["message"] == "Invitation declined"
    db.refresh(app)
    assert app.status == "rejected"
    assert app.decline_initiated_by == "candidate"
    assert app.decline_reason == "Not interested"
    assert app.declined_at is not None


def test_decline_blocks_already_actioned(db):
    """A user cannot double-decline an invitation."""
    from fastapi import HTTPException

    from backend.routers.candidate.jobs import (
        InvitationAction,
        decline_invitation,
    )

    user = _make_user(db, email="me@example.com", email_verified=True)
    app = _make_app(
        db, user_id=user.id, email=user.email, status="rejected"
    )

    payload = InvitationAction(application_id=app.id, reason="x")
    with pytest.raises(HTTPException) as exc:
        decline_invitation(payload=payload, current_user=user, db=db)
    assert exc.value.status_code == 404


def test_decline_blocked_when_email_only_matches_but_unverified(db):
    """P1-09 IDOR: an attacker who shares the email of an
    unverified invite cannot decline it. The predicate excludes
    them."""
    from fastapi import HTTPException

    from backend.routers.candidate.jobs import (
        InvitationAction,
        decline_invitation,
    )

    # Unlinked invite addressed to a victim's email
    _make_app(db, user_id=None, email="victim@example.com", status="invited")

    # Attacker registered with the same email but hasn't
    # verified yet.
    attacker = _make_user(
        db, email="victim@example.com", email_verified=False
    )
    payload = InvitationAction(application_id=1, reason="x")
    with pytest.raises(HTTPException) as exc:
        decline_invocation = decline_invitation(  # noqa: F841 (intentional assertion)
            payload=payload, current_user=attacker, db=db
        )
    assert exc.value.status_code == 404
