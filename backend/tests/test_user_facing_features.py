"""
Smoke Tests: User-Facing Features
====================================
Tests: Feature flags, tooltips, onboarding tour, help center
"""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_encoding_12345"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient

import backend.database
import backend.dependencies
from backend.database import Base, Company, CompanyMember, User
from backend.dependencies import pwd_context
from backend.main import app

test_engine = backend.database.engine
if test_engine.url.database != ":memory:":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    backend.database.engine = test_engine
    backend.database.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    backend.dependencies.SessionLocal = backend.database.SessionLocal


def _get_csrf_token(client):
    resp = client.get("/login")
    return resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token") or ""


def _login(client, email, password):
    csrf = _get_csrf_token(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def test_company(client):
    db = backend.database.SessionLocal()
    company = Company(name="User Face Co", slug="user-face-co")
    db.add(company)
    db.commit()
    db.refresh(company)
    cid = company.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(Company).filter(Company.id == cid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def recruiter(client, test_company):
    db = backend.database.SessionLocal()
    user = User(
        email="userface_recruiter@test.com",
        name="User Face Recruiter",
        hashed_password=pwd_context.hash("recruiter123"),
        role="recruiter",
        email_verified=True,
        company_name="User Face Co",
        tier="pro",
    )
    db.add(user)
    db.flush()
    membership = CompanyMember(
        company_id=test_company.id,
        user_id=user.id,
        role="admin",
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def admin(client, test_company):
    db = backend.database.SessionLocal()
    user = User(
        email="userface_admin@test.com",
        name="User Face Admin",
        hashed_password=pwd_context.hash("admin123"),
        role="admin",
        email_verified=True,
        is_super_admin=True,
    )
    db.add(user)
    db.flush()
    membership = CompanyMember(
        company_id=test_company.id,
        user_id=user.id,
        role="admin",
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def auth(client, recruiter):
    return _login(client, "userface_recruiter@test.com", "recruiter123")


@pytest.fixture(scope="module")
def admin_auth(client, admin):
    return _login(client, "userface_admin@test.com", "admin123")


class TestFeatureFlags:
    def test_seed_flags(self, client, admin_auth):
        resp = client.post("/api/v1/feature-flags/seed", headers=admin_auth)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["created"] >= 0

    def test_get_config(self, client, auth):
        resp = client.get("/api/v1/feature-flags/config", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "recruiter_enhancements" in data

    def test_get_specific_flag(self, client, auth):
        resp = client.get(
            "/api/v1/feature-flags/config/recruiter_enhancements", headers=auth
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "recruiter_enhancements"
        assert "enabled" in data

    def test_list_flags_admin(self, client, admin_auth):
        resp = client.get("/api/v1/feature-flags/", headers=admin_auth)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_flags_non_admin(self, client, auth):
        resp = client.get("/api/v1/feature-flags/", headers=auth)
        assert resp.status_code == 403

    def test_create_flag_admin(self, client, admin_auth):
        resp = client.post(
            "/api/v1/feature-flags/",
            json={
                "key": "test_flag",
                "enabled": True,
                "rollout_percentage": 50,
                "description": "Test flag",
            },
            headers=admin_auth,
        )
        assert resp.status_code == 201
        assert resp.json()["success"] is True

    def test_create_flag_duplicate(self, client, admin_auth):
        resp = client.post(
            "/api/v1/feature-flags/",
            json={"key": "test_flag", "enabled": False},
            headers=admin_auth,
        )
        assert resp.status_code == 400

    def test_update_flag(self, client, admin_auth):
        resp = client.get("/api/v1/feature-flags/", headers=admin_auth)
        flags = resp.json()
        test_flag = next((f for f in flags if f["flag_key"] == "test_flag"), None)
        assert test_flag is not None
        resp = client.patch(
            f"/api/v1/feature-flags/{test_flag['id']}",
            json={"enabled": False, "rollout_percentage": 25},
            headers=admin_auth,
        )
        assert resp.status_code == 200

    def test_delete_flag(self, client, admin_auth):
        resp = client.get("/api/v1/feature-flags/", headers=admin_auth)
        flags = resp.json()
        test_flag = next((f for f in flags if f["flag_key"] == "test_flag"), None)
        assert test_flag is not None
        resp = client.delete(
            f"/api/v1/feature-flags/{test_flag['id']}", headers=admin_auth
        )
        assert resp.status_code == 200

    def test_flag_not_found(self, client, admin_auth):
        resp = client.patch(
            "/api/v1/feature-flags/999999", json={"enabled": True}, headers=admin_auth
        )
        assert resp.status_code == 404


class TestCSSAndJSFiles:
    def test_tooltips_css_exists(self, client):
        resp = client.get("/css/tooltips.css")
        assert resp.status_code == 200
        assert "tooltip" in resp.text.lower()

    def test_feature_flags_js_exists(self, client):
        resp = client.get("/js/feature-flags.js")
        assert resp.status_code == 200
        assert "FeatureFlags" in resp.text

    def test_recruiter_onboarding_js_exists(self, client):
        resp = client.get("/js/recruiter-onboarding.js")
        assert resp.status_code == 200
        assert "RecruiterTour" in resp.text

    def test_help_center_js_exists(self, client):
        resp = client.get("/js/help-center.js")
        assert resp.status_code == 200
        assert "HelpCenter" in resp.text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
