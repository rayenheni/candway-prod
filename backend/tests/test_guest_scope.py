"""
H-2 regression tests: guest / interview-scoped JWTs must NOT be able to
reach normal user endpoints (dashboard, profile, etc.). They may only be
used on interview-scoped endpoints via get_current_interview_user.

Security model enforced here:
  * guest-login now issues tokens with ``scope: "interview"``
  * get_current_user rejects guest-scoped tokens -> 401
  * get_current_interview_user (get_interview_access) still accepts them,
    bound to the application the interview link was minted for
"""

import hashlib
import hmac
import secrets
import time

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from jose import jwt

import backend.database
import backend.dependencies
from backend.database import Application, Base, Company, User
from backend.dependencies import (
    ALGORITHM,
    JWT_SECRET_KEY,
    generate_interview_token,
    pwd_context,
)
from backend.main import app

# Reuse the in-memory test engine wired up by conftest (StaticPool single
# shared connection). This module defines its own module-scoped client so we
# avoid conftest's per-test db_session teardown that closes the connection
# before drop_all (the pre-existing "closed database" error).
test_engine = backend.database.engine


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)


def _db():
    return backend.database.SessionLocal()


def _make_user(db, email, password="testpassword123", role="candidate"):
    user = User(
        email=email,
        name=email.split("@")[0],
        hashed_password=pwd_context.hash(password),
        role=role,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_app(db, company_id, email, user_id=None, status="invited"):
    app = Application(
        company_id=company_id,
        email=email,
        full_name=email.split("@")[0],
        status=status,
        user_id=user_id,
        declared_role="Python Developer",
        interview_state="not_started",
        interview_progress=0,
    )
    db.add(app)
    db.flush()
    return app


def _seed_company_user(db, email):
    slug = f"h2-{hashlib.md5(email.encode()).hexdigest()[:10]}"
    company = db.query(Company).filter(Company.slug == slug).first()
    if not company:
        company = Company(name=email.split("@")[0], slug=slug)
        db.add(company)
        db.flush()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = _make_user(db, email)
    db.commit()
    return company.id, user


def _guest_login(client, app_id):
    token_dict = generate_interview_token(app_id)
    response = client.post(
        "/api/v1/auth/guest-login",
        json={"app_id": app_id, "token": token_dict["token"]},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


def _decode_token(token):
    return jwt.decode(
        token, JWT_SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False}
    )


def _expired_guest_token(app_id):
    now = int(time.time())
    payload = {
        "sub": f"guest_{app_id}",
        "role": "candidate",
        "id": None,
        "guest": True,
        "scope": "interview",
        "app_id": app_id,
        "iat": now - 7200,
        "exp": now - 3600,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def _csrf_token(client):
    """Fresh CSRF token (mirrors conftest bootstrap)."""
    resp = client.get("/login")
    token = resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token")
    if token:
        return token
    session_id = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + 86400
    message = f"{session_id}:{expires_at}"
    token_hash = hmac.new(
        JWT_SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{session_id}.{expires_at}.{token_hash}"


def _normal_login(client, email, password):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": _csrf_token(client)},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Guest tokens carry the interview scope
# ---------------------------------------------------------------------------


def test_guest_token_carries_interview_scope(client):
    db = _db()
    company_id, user = _seed_company_user(db, "scope-owner@example.com")
    app_row = _make_app(db, company_id, user.email, user_id=user.id)
    db.commit()
    app_id = app_row.id

    token = _guest_login(client, app_id)
    payload = _decode_token(token)
    assert payload.get("scope") == "interview"
    assert payload.get("app_id") == app_id
    assert payload.get("guest") is True


# ---------------------------------------------------------------------------
# 2. Guest tokens are REJECTED on normal user endpoints (no escalation)
# ---------------------------------------------------------------------------

NORMAL_ENDPOINTS = ["/api/v1/candidate/profile-data", "/api/v1/candidate/dashboard"]


@pytest.mark.parametrize("endpoint", NORMAL_ENDPOINTS)
def test_existing_user_guest_token_rejected_on_normal_endpoints(client, endpoint):
    client.cookies.clear()
    db = _db()
    company_id, user = _seed_company_user(db, "existing-guest@example.com")
    app_row = _make_app(db, company_id, user.email, user_id=user.id)
    db.commit()
    token = _guest_login(client, app_row.id)

    response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("endpoint", NORMAL_ENDPOINTS)
def test_true_guest_token_rejected_on_normal_endpoints(client, endpoint):
    client.cookies.clear()
    db = _db()
    company_id, _ = _seed_company_user(db, "true-guest@example.com")
    app_row = _make_app(db, company_id, "true-guest@example.com")
    db.commit()
    token = _guest_login(client, app_row.id)

    response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 3. Guest tokens are ACCEPTED on interview-scoped endpoints
# ---------------------------------------------------------------------------


def test_existing_user_guest_token_allowed_on_interview_endpoint(client):
    db = _db()
    company_id, user = _seed_company_user(db, "interview-guest@example.com")
    app_row = _make_app(db, company_id, user.email, user_id=user.id)
    db.commit()
    token = _guest_login(client, app_row.id)

    response = client.post(
        "/api/v1/ai/interview/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "candidate_id": app_row.id,
            "message": "ready",
            "language": "English",
        },
    )
    assert response.status_code != status.HTTP_401_UNAUTHORIZED


def test_existing_user_guest_token_can_view_own_application(client):
    db = _db()
    company_id, user = _seed_company_user(db, "view-own@example.com")
    app_row = _make_app(db, company_id, user.email, user_id=user.id)
    db.commit()
    token = _guest_login(client, app_row.id)

    response = client.get(
        "/api/v1/candidate/current-application",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == app_row.id


def test_true_guest_token_allowed_on_interview_endpoint(client):
    db = _db()
    company_id, _ = _seed_company_user(db, "true-interview@example.com")
    app_row = _make_app(db, company_id, "true-interview@example.com")
    db.commit()
    token = _guest_login(client, app_row.id)

    response = client.post(
        "/api/v1/ai/interview/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "candidate_id": app_row.id,
            "message": "ready",
            "language": "English",
        },
    )
    assert response.status_code != status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 4. Normal login tokens still work on normal endpoints
# ---------------------------------------------------------------------------


def test_normal_token_still_works_on_normal_endpoints(client):
    db = _db()
    _seed_company_user(db, "normal@example.com")
    db.commit()
    token = _normal_login(client, "normal@example.com", "testpassword123")

    response = client.get(
        "/api/v1/candidate/profile-data", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# 5. Expired guest tokens are rejected everywhere
# ---------------------------------------------------------------------------


def test_expired_guest_token_rejected_on_interview_endpoint(client):
    client.cookies.clear()
    db = _db()
    company_id, _ = _seed_company_user(db, "expired@example.com")
    app_row = _make_app(db, company_id, "expired@example.com")
    db.commit()
    token = _expired_guest_token(app_row.id)

    response = client.post(
        "/api/v1/ai/interview/chat",
        headers={
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": _csrf_token(client),
        },
        json={
            "candidate_id": app_row.id,
            "message": "ready",
            "language": "English",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_expired_guest_token_rejected_on_normal_endpoint(client):
    client.cookies.clear()
    db = _db()
    company_id, _ = _seed_company_user(db, "expired2@example.com")
    app_row = _make_app(db, company_id, "expired2@example.com")
    db.commit()
    token = _expired_guest_token(app_row.id)

    response = client.get(
        "/api/v1/candidate/profile-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 6. Guest tokens are bound to the exact application they were minted for
# ---------------------------------------------------------------------------


def test_existing_user_guest_token_cannot_access_other_application(client):
    client.cookies.clear()
    db = _db()
    company_id, user = _seed_company_user(db, "forger@example.com")
    _own_app = _make_app(db, company_id, user.email, user_id=user.id)
    other_user_app = _make_app(db, company_id, "other@example.com")
    db.commit()

    # Forge a guest token pointing at the OTHER application while carrying
    # test_user's identity. Ownership mismatch must be rejected.
    now = int(time.time())
    forged = jwt.encode(
        {
            "sub": user.email,
            "role": "candidate",
            "id": user.id,
            "guest": True,
            "scope": "interview",
            "app_id": other_user_app.id,
            "iat": now,
            "exp": now + 900,
        },
        JWT_SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.post(
        "/api/v1/ai/interview/chat",
        headers={
            "Authorization": f"Bearer {forged}",
            "X-CSRF-Token": _csrf_token(client),
        },
        json={
            "candidate_id": other_user_app.id,
            "message": "ready",
            "language": "English",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
