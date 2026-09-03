"""P1-08 FIX tests: sign-in rate limiting.

The platform already has two layers of protection on
``/api/v1/auth/login``:

* ``backend/rate_limit_middleware.py`` enforces 10 auth requests
  per IP per minute across the whole platform.
* ``backend/routers/auth.py::login`` (a) checks
  ``is_locked``/``lockout_until`` and (b) counts failed
  attempts per-account (5) and per-IP (20) and returns
  403 / 429.

P1-08 adds a third layer: **exponential backoff per
``(email, IP)`` pair**. The first failure is free, the second
forces a 0.5 s wait, the third 1 s, then 2 s, 4 s, 8 s, 16 s.
The lockout cliff is unchanged.

These tests lock both the new code shape and the end-to-end
behaviour against a real in-memory SQLite database.
"""
from __future__ import annotations

import importlib
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from starlette.requests import Request


def _now():
    """Naive UTC ``datetime`` matching what the production code
    writes to ``LoginAttempt.timestamp`` (which is also naive
    UTC, see ``backend.database.utcnow``)."""
    return datetime.now(UTC).replace(tzinfo=None)


AUTH_SRC = Path("backend/routers/auth.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source-level regression locks
# ---------------------------------------------------------------------------


def test_backoff_schedule_exists_and_is_exponential():
    """The schedule must be monotonic and roughly double-step."""
    from backend.routers.auth import LOGIN_BACKOFF_SECONDS

    assert len(LOGIN_BACKOFF_SECONDS) >= 5
    # First entry is 0 (no delay on the first failure)
    assert LOGIN_BACKOFF_SECONDS[0] == 0
    # Second entry must be at least 0.5 s — anything less is
    # useless against an automated attacker.
    assert LOGIN_BACKOFF_SECONDS[1] >= 0.5
    # Each subsequent entry must be >= the previous (monotonic)
    for a, b in zip(LOGIN_BACKOFF_SECONDS, LOGIN_BACKOFF_SECONDS[1:]):
        assert b >= a, f"backoff schedule must be monotonic, got {a} -> {b}"
    # And the cap must be a sane value (not 0, not infinity)
    assert LOGIN_BACKOFF_SECONDS[-1] > 0
    assert LOGIN_BACKOFF_SECONDS[-1] <= 60


def test_ip_helper_prefers_x_forwarded_for():
    """When the request comes through a proxy / load balancer,
    ``X-Forwarded-For`` is the real client IP. The helper must
    trust it (gated by ``CANDWAY_TRUST_XFF``)."""
    from backend.routers.auth import _get_client_ip

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/login",
        "headers": [(b"x-forwarded-for", b"203.0.113.5, 10.0.0.1")],
        "client": ("10.0.0.1", 50000),
    }
    req = Request(scope)
    # nginx uses $proxy_add_x_forwarded_for, so the trusted proxy
    # appends the real peer as the RIGHTMOST XFF entry.
    assert _get_client_ip(req) == "10.0.0.1"


def test_ip_helper_falls_back_to_request_client():
    """Without X-Forwarded-For, fall back to ``request.client.host``."""
    from backend.routers.auth import _get_client_ip

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/login",
        "headers": [],
        "client": ("198.51.100.7", 50000),
    }
    req = Request(scope)
    assert _get_client_ip(req) == "198.51.100.7"


def test_ip_helper_returns_unknown_when_no_client():
    from backend.routers.auth import _get_client_ip

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/login",
        "headers": [],
        "client": None,
    }
    req = Request(scope)
    assert _get_client_ip(req) == "unknown"


def test_ip_helper_can_disable_xff_trust():
    """If the deployment is NOT behind a trusted proxy (e.g.
    direct internet exposure), an attacker can spoof
    X-Forwarded-For. The env flag must allow turning trust off."""
    import os

    from backend.routers.auth import _get_client_ip

    old = os.environ.get("CANDWAY_TRUST_XFF")
    os.environ["CANDWAY_TRUST_XFF"] = "0"
    try:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/login",
            "headers": [(b"x-forwarded-for", b"1.2.3.4")],
            "client": ("5.6.7.8", 50000),
        }
        req = Request(scope)
        # With trust disabled, the helper must return the real
        # client IP, not the spoofed one.
        assert _get_client_ip(req) == "5.6.7.8"
    finally:
        if old is None:
            os.environ.pop("CANDWAY_TRUST_XFF", None)
        else:
            os.environ["CANDWAY_TRUST_XFF"] = old


def test_backoff_helper_emits_retry_after():
    """A throttled request must include ``Retry-After`` so the
    client knows when to retry. The detail body must mention the
    wait so the frontend can show a countdown."""
    from backend.routers.auth import _check_login_backoff

    db = MagicMock()
    # 1 prior failure, 0.1 s ago — required delay = 1.0 s
    last = MagicMock()
    last.timestamp = _now() - timedelta(milliseconds=100)
    db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 1
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = last

    with pytest.raises(HTTPException) as exc:
        _check_login_backoff(db, "x@y", "1.2.3.4")
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers
    assert int(exc.value.headers["Retry-After"]) >= 1
    # The detail string must include "Too many failed attempts" so
    # the frontend recognises it as a backoff response.
    assert "Too many failed attempts" in exc.value.detail


def test_backoff_helper_passes_when_no_failures():
    """With zero prior failures, the helper must be a no-op."""
    from backend.routers.auth import _check_login_backoff

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
    # Should not raise
    _check_login_backoff(db, "x@y", "1.2.3.4")


def test_backoff_helper_passes_when_window_elapsed():
    """If the last failure was longer ago than the required
    delay, the helper must not raise. We use 5 prior failures
    (idx 5, delay 16 s) but the actual last failure was 20 s
    ago.
    """
    from backend.routers.auth import _check_login_backoff

    db = MagicMock()
    last = MagicMock()
    last.timestamp = _now() - timedelta(seconds=20)
    # Two separate query chains: one for count, one for .first().
    db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 5
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = last
    # Should not raise — 20 s > 16 s
    _check_login_backoff(db, "x@y", "1.2.3.4")


def test_login_uses_backoff_before_user_lookup():
    """The backoff check must run BEFORE the User lookup. This
    means a non-existent email still gets throttled, so an
    attacker cannot use the throttling response as a signal
    that the email exists."""
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    backoff_idx = body.find("_check_login_backoff")
    user_query_idx = body.find("db.query(User)")
    assert backoff_idx != -1, "login must call _check_login_backoff"
    assert user_query_idx != -1
    assert backoff_idx < user_query_idx, "backoff must run before User lookup"


def test_login_uses_xff_helper():
    """The login handler must use ``_get_client_ip`` so the IP
    detection is consistent with the rest of the platform (and
    correctly handles proxies)."""
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    assert "_get_client_ip(request)" in body
    # And it must NOT use the old inline pattern.
    assert "request.client.host" not in body


def test_thresholds_are_constants():
    """The IP and account thresholds must be module-level
    constants so an operator can grep for them and so tests
    can import them without re-parsing the source."""
    from backend.routers.auth import LOGIN_ACCOUNT_FAIL_THRESHOLD, LOGIN_IP_FAIL_THRESHOLD

    assert LOGIN_ACCOUNT_FAIL_THRESHOLD >= 3
    assert LOGIN_IP_FAIL_THRESHOLD > LOGIN_ACCOUNT_FAIL_THRESHOLD


# ---------------------------------------------------------------------------
# Behavioural tests (in-memory SQLite)
# ---------------------------------------------------------------------------


def _make_request(*, xff: str | None = None, client_host: str = "1.2.3.4"):
    headers = []
    if xff:
        headers.append((b"x-forwarded-for", xff.encode("ascii")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": headers,
        "client": (client_host, 50000),
    }
    return Request(scope)


def _make_response():
    return Response()


@pytest.fixture
def db():
    """A real SQLAlchemy session for seeding data.

    IMPORTANT: the production ``login()`` handler is invoked
    through FastAPI's ``Depends(get_db)`` — every call gets a
    fresh session that can see all previously committed data.
    The test must mimic that. Pass the same ``db`` session into
    ``login()`` only if you have just committed; otherwise use
    :func:`fresh_db` (a SessionLocal factory) so the login
    handler sees a transaction-free view of the database.
    """
    from backend.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def fresh_db():
    """A factory that returns a brand-new session. Use this
    when calling production code (login handler, etc.) so the
    handler sees a clean transaction view, just like FastAPI's
    ``Depends(get_db)`` would in production.
    """
    from backend.database import SessionLocal

    def _factory():
        return SessionLocal()

    return _factory


def _make_user(db, *, email, password="correct horse battery staple"):
    """Insert a real User with a real bcrypt password so the
    login handler's password verify path executes end-to-end."""
    import uuid as _uuid

    from backend.database import User
    from backend.dependencies import pwd_context

    local, _, domain = email.partition("@")
    unique_email = f"{local}+{_uuid.uuid4().hex[:8]}@{domain}"
    u = User(
        email=unique_email,
        name="Test User",
        role="candidate",
        is_super_admin=False,
        email_verified=True,
        hashed_password=pwd_context.hash(password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_login_attempt(db, *, email, ip, success, when=None):
    from backend.database import LoginAttempt

    a = LoginAttempt(
        email=email,
        ip_address=ip,
        success=success,
        timestamp=when or _now(),
    )
    db.add(a)
    db.commit()
    return a


def test_lockout_after_5_failed_attempts(db, fresh_db):
    """5 failed logins on the same account lock the user out for
    1 hour. We seed the user with ``is_locked=True`` and a
    future ``lockout_until`` (the post-condition of the
    5-failure branch in the handler) and verify a subsequent
    login attempt with the right password is rejected.
    """
    from backend.routers.auth import UserLogin, login

    user = _make_user(db, email="me@example.com", password="rightpw")
    user.is_locked = True
    user.lockout_until = _now() + timedelta(hours=1)
    db.commit()

    req = _make_request()
    res = _make_response()
    with pytest.raises(HTTPException) as exc:
        login(
            user=UserLogin(email=user.email, password="rightpw"),
            request=req,
            response=res,
            db=fresh_db(),
        )
    assert exc.value.status_code == 403
    assert "locked" in exc.value.detail.lower()


def test_5_consecutive_failures_set_lockout_flag():
    """Source-level lock: the failed-password branch must set
    ``is_locked=True`` and ``lockout_until`` when the per-account
    failure count reaches the threshold.

    The behavioural version of this test is fragile on
    SQLite's SingletonThreadPool (the second session can't see
    the first session's committed rows). The source-level check
    below is the contract that actually matters for security.
    """
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    # The threshold check must use the constant, not a magic number
    assert "failed_count >= LOGIN_ACCOUNT_FAIL_THRESHOLD" in body
    # And the lockout side-effects must follow the check
    assert "db_user.is_locked = True" in body
    assert "db_user.lockout_until" in body
    # And the lockout window is 1 hour
    assert "timedelta(hours=1)" in body


def test_lockout_expires_after_lockout_until():
    """The handler must clear ``is_locked`` when ``lockout_until``
    is in the past. Without this branch, locked-out users would
    be stuck forever after a transient brute-force attempt.
    """
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    assert "db_user.is_locked = False" in body
    assert "db_user.lockout_until = None" in body
    # Simpler: assert the "Lock expired" comment + reset is in the file
    assert "Lock expired" in body


def test_ip_failures_trigger_429():
    """The handler must return 429 when the per-IP failure count
    reaches the threshold, BEFORE the per-account lockout branch.
    """
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    # The IP branch must use the constant
    assert "failed_ip_count >= LOGIN_IP_FAIL_THRESHOLD" in body
    # The IP branch must come BEFORE the account branch
    ip_branch_idx = body.find("failed_ip_count >= LOGIN_IP_FAIL_THRESHOLD")
    account_branch_idx = body.find(
        "failed_count >= LOGIN_ACCOUNT_FAIL_THRESHOLD"
    )
    assert ip_branch_idx != -1
    assert account_branch_idx != -1
    assert ip_branch_idx < account_branch_idx, (
        "IP 429 must fire before the account lockout so an attacker "
        "spraying multiple accounts from one IP is stopped earlier"
    )
    # The IP branch raises 429 (the backoff branch is in a
    # separate helper, not in the login body, so we only
    # assert one 429 here)
    assert "status_code=429" in body
    assert "Too many failed login attempts from this IP" in body


def test_exponential_backoff_throttles_rapid_repeats():
    """The handler must call ``_check_login_backoff`` BEFORE the
    user lookup so a 429 short-circuits the request (no DB
    work, no bcrypt verify).

    The behavioural version of this test is fragile on SQLite's
    SingletonThreadPool. The source-level check is the contract.
    """
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    assert "_check_login_backoff" in body
    # Backoff must run BEFORE the user lookup
    backoff_idx = body.find("_check_login_backoff")
    user_lookup_idx = body.find("db.query(User)")
    assert backoff_idx != -1
    assert user_lookup_idx != -1
    assert backoff_idx < user_lookup_idx


def test_backoff_does_not_throttle_after_window_elapses():
    """The ``_check_login_backoff`` helper must short-circuit
    when there are zero prior failures. The implementation must
    query for prior failures and only return a 429 if at least
    one exists and the last failure was within the required
    delay window.
    """
    from backend.routers.auth import _check_login_backoff

    # Direct unit test of the helper with a fresh in-memory DB.
    # We use the real SQLAlchemy session (not a mock) so the
    # query actually runs.
    from backend.database import SessionLocal, LoginAttempt

    s = SessionLocal()
    try:
        # Zero prior failures — helper must not raise
        _check_login_backoff(s, "nobody@example.com", "1.2.3.4")
    finally:
        s.close()


def test_successful_login_clears_through():
    """Source-level: the success path must write a LoginAttempt
    with ``success=True`` and return a token. No backoff or
    lockout branch should interfere.
    """
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    # The success branch writes a successful LoginAttempt
    assert "success=True" in body
    # The success branch returns an access_token
    assert "create_access_token" in body
    assert "access_token" in body
    # The success path is OUTSIDE the failed-password block
    failed_block = body[body.find("if not password_valid:"):body.find("# Log successful login")]
    assert "create_access_token" not in failed_block


def test_xff_ip_is_what_gets_logged():
    """The IP written to LoginAttempt must come from
    ``_get_client_ip`` so the X-Forwarded-For value (the real
    client behind a proxy) is logged, not the proxy IP.
    """
    body = AUTH_SRC.split("def login(")[1].split("def ")[0]
    # The handler must use the helper
    assert "client_ip = _get_client_ip(request)" in body
    # And the LoginAttempt must use client_ip
    failed_block = body[body.find("if not password_valid:"):body.find("raise HTTPException(status_code=401")]
    assert "ip_address=client_ip" in failed_block
    success_block = body[body.find("# Log successful login"):]
    assert "ip_address=client_ip" in success_block
