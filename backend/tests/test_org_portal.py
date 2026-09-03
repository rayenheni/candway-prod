"""Tests for the organization portal (org admin self-service).

Covers:
- POST /auth/signup/org (company + org admin + owner membership + profile)
- require_org_admin / require_company_admin role gates
- Member management (list / create / invite / role / deactivate / activate / reset-usage)
- Cross-company 404 isolation
- Org analytics endpoints

Follows the module-scoped TestClient pattern from test_user_facing_features.py
to avoid the alembic auto-upgrade startup interfering with per-test sessions.
"""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_encoding_12345"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

import backend.database  # noqa: E402
import backend.dependencies  # noqa: E402
from backend.database import (  # noqa: E402
    AuditLog,
    Base,
    Company,
    CompanyMember,
    User,
)
from backend.dependencies import pwd_context  # noqa: E402
from backend.main import app  # noqa: E402

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
    if resp.status_code != 200:
        raise AssertionError(
            f"Login failed for {email}: {resp.status_code} {resp.text}"
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
    company = Company(
        name="Org Test Co",
        slug="org-test-co",
        tier="free",
        subscription_status="active",
        max_users=10,
        max_jobs=50,
        max_ai_interviews=500,
        is_active=True,
    )
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
def org_admin(client, test_company):
    from datetime import UTC, datetime

    from backend.models.evaluation.profile import RecruiterProfile

    db = backend.database.SessionLocal()
    user = User(
        email="orgadmin@test.tn",
        name="Org Admin",
        hashed_password=pwd_context.hash("orgpass123"),
        role="company",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(
        RecruiterProfile(
            user_id=user.id,
            name="Org Admin",
            email="orgadmin@test.tn",
            company_name="Org Test Co",
            company_id=test_company.id,
            email_settings="{}",
            tier="free",
            subscription_status="active",
        )
    )
    db.add(
        CompanyMember(
            company_id=test_company.id,
            user_id=user.id,
            role="owner",
            is_active=True,
            joined_at=datetime.now(UTC),
        )
    )
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def org_member(client, org_admin, test_company):
    from datetime import UTC, datetime

    from backend.models.evaluation.profile import RecruiterProfile

    db = backend.database.SessionLocal()
    user = User(
        email="recruiter@acme.tn",
        name="Recruiter",
        hashed_password=pwd_context.hash("recruitpass123"),
        role="recruiter",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(
        RecruiterProfile(
            user_id=user.id,
            name="Recruiter",
            email="recruiter@acme.tn",
            company_id=test_company.id,
            email_settings="{}",
            tier="free",
            subscription_status="active",
            usage_jobs=7,
            usage_cvs=3,
            usage_ai_interviews=1,
        )
    )
    db.add(
        CompanyMember(
            company_id=test_company.id,
            user_id=user.id,
            role="recruiter",
            is_active=True,
            joined_at=datetime.now(UTC),
        )
    )
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()
    db2 = backend.database.SessionLocal()
    fresh = db2.query(User).filter(User.id == uid).first()
    yield fresh
    db2.close()


@pytest.fixture(scope="module")
def org_admin_headers(client, org_admin):
    return _login(client, "orgadmin@test.tn", "orgpass123")


@pytest.fixture(scope="module")
def org_member_headers(client, org_member):
    return _login(client, "recruiter@acme.tn", "recruitpass123")


# ── A. Signup ──────────────────────────────────────────────────────


def test_signup_org_creates_company_owner_profile(client):
    resp = client.post(
        "/api/v1/auth/signup/org",
        json={
            "company_name": "Signup Corp",
            "admin_name": "Signup Admin",
            "admin_email": "signup@corp.tn",
            "admin_password": "SecurePass123!",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "company"
    assert data["access_token"]

    db = backend.database.SessionLocal()
    user = db.query(User).filter(User.email == "signup@corp.tn").first()
    assert user is not None
    assert user.role == "company"
    membership = (
        db.query(CompanyMember).filter(CompanyMember.user_id == user.id).first()
    )
    assert membership is not None
    assert membership.role == "owner"
    assert membership.is_active is True
    company = db.query(Company).filter(Company.id == membership.company_id).first()
    assert company is not None
    assert company.tier == "free"

    from backend.models.evaluation.profile import RecruiterProfile

    profile = (
        db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user.id).first()
    )
    assert profile is not None
    assert profile.company_id == company.id
    assert profile.name == "Signup Admin"
    db.close()


def test_signup_org_duplicate_email_rejected(client):
    resp = client.post(
        "/api/v1/auth/signup/org",
        json={
            "company_name": "Dup Corp 2",
            "admin_name": "Dup Admin 2",
            "admin_email": "signup@corp.tn",
            "admin_password": "SecurePass123!",
        },
    )
    assert resp.status_code == 400


def test_signup_org_invalid_password(client):
    resp = client.post(
        "/api/v1/auth/signup/org",
        json={
            "company_name": "Weak Corp",
            "admin_name": "Weak Admin",
            "admin_email": "weak@corp.tn",
            "admin_password": "123",
        },
    )
    assert resp.status_code == 400


# ── B. Role gates ──────────────────────────────────────────────────


def test_org_admin_can_list_members(client, org_admin_headers, org_member):
    resp = client.get("/api/v1/org/members", headers=org_admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["company_id"] is not None
    emails = [m["email"] for m in data["members"]]
    assert "orgadmin@test.tn" in emails
    assert "recruiter@acme.tn" in emails


def test_org_admin_cannot_access_platform_admin(client, org_admin_headers):
    resp = client.get("/api/v1/admin/stats", headers=org_admin_headers)
    assert resp.status_code == 403


def test_plain_recruiter_cannot_access_org_portal(client, org_member_headers):
    resp = client.get("/api/v1/org/members", headers=org_member_headers)
    assert resp.status_code == 403
    assert "Organization portal" in resp.json()["detail"]


def test_company_admin_role_not_organization_denied(client, test_company):
    """CompanyMember admin but User.role != organization → 403."""
    from datetime import UTC, datetime

    from backend.models.evaluation.profile import RecruiterProfile

    db = backend.database.SessionLocal()
    user = User(
        email="companyadmin@test.tn",
        name="Company Admin",
        hashed_password=pwd_context.hash("cmpadmin123"),
        role="recruiter",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(
        RecruiterProfile(
            user_id=user.id,
            name="Company Admin",
            email="companyadmin@test.tn",
            company_id=test_company.id,
            email_settings="{}",
            tier="free",
            subscription_status="active",
        )
    )
    db.add(
        CompanyMember(
            company_id=test_company.id,
            user_id=user.id,
            role="admin",
            is_active=True,
            joined_at=datetime.now(UTC),
        )
    )
    db.commit()
    db.close()
    headers = _login(client, "companyadmin@test.tn", "cmpadmin123")
    resp = client.get("/api/v1/org/members", headers=headers)
    assert resp.status_code == 403
    assert "Organization portal" in resp.json()["detail"]


# ── C. Member management ───────────────────────────────────────────


def test_create_member(client, org_admin_headers, test_company):
    resp = client.post(
        "/api/v1/org/members",
        json={"name": "New Recruiter", "email": "new@acme.tn", "role": "recruiter"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "new@acme.tn"
    assert data["role"] == "recruiter"
    assert data["password"]

    db = backend.database.SessionLocal()
    user = db.query(User).filter(User.email == "new@acme.tn").first()
    assert user is not None
    assert user.role == "recruiter"
    membership = (
        db.query(CompanyMember).filter(CompanyMember.user_id == user.id).first()
    )
    assert membership is not None
    assert membership.company_id == test_company.id
    assert membership.role == "recruiter"
    audit = db.query(AuditLog).filter(AuditLog.action == "org_create_member").first()
    assert audit is not None
    assert audit.company_id == test_company.id
    db.close()


def test_create_member_duplicate_email_rejected(client, org_admin_headers, org_member):
    resp = client.post(
        "/api/v1/org/members",
        json={"name": "Dup", "email": "recruiter@acme.tn", "role": "recruiter"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 400


def test_create_member_invalid_role_rejected(client, org_admin_headers):
    resp = client.post(
        "/api/v1/org/members",
        json={"name": "Bad", "email": "bad@acme.tn", "role": "owner"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 400


def test_update_member_role(client, org_admin_headers, org_member):
    resp = client.patch(
        f"/api/v1/org/members/{org_member.id}",
        json={"role": "admin"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"


def test_cannot_change_owner_role(client, org_admin_headers, org_admin):
    resp = client.patch(
        f"/api/v1/org/members/{org_admin.id}",
        json={"role": "recruiter"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 400


def test_deactivate_and_reactivate_member(client, org_admin_headers, org_member):
    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/deactivate",
        headers=org_admin_headers,
    )
    assert resp.status_code == 200
    db = backend.database.SessionLocal()
    membership = (
        db.query(CompanyMember).filter(CompanyMember.user_id == org_member.id).first()
    )
    assert membership.is_active is False
    db.close()

    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/activate",
        headers=org_admin_headers,
    )
    assert resp.status_code == 200
    db = backend.database.SessionLocal()
    membership = (
        db.query(CompanyMember).filter(CompanyMember.user_id == org_member.id).first()
    )
    assert membership.is_active is True
    db.close()


def test_cannot_deactivate_owner(client, org_admin_headers, org_admin):
    resp = client.post(
        f"/api/v1/org/members/{org_admin.id}/deactivate",
        headers=org_admin_headers,
    )
    assert resp.status_code == 400


def test_reset_member_usage(client, org_admin_headers, org_member):
    from backend.models.evaluation.profile import RecruiterProfile

    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/reset-usage",
        headers=org_admin_headers,
    )
    assert resp.status_code == 200
    db = backend.database.SessionLocal()
    rp = (
        db.query(RecruiterProfile)
        .filter(RecruiterProfile.user_id == org_member.id)
        .first()
    )
    assert rp.usage_jobs == 0
    assert rp.usage_cvs == 0
    assert rp.usage_ai_interviews == 0
    db.close()


def test_invite_member(client, org_admin_headers, test_company, monkeypatch):
    def fake_send_email(to, subject, body):
        assert "invited@acme.tn" in to
        return True

    monkeypatch.setattr("backend.email_utils.send_email", fake_send_email)
    resp = client.post(
        "/api/v1/org/members/invite",
        json={"name": "Invited", "email": "invited@acme.tn"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    db = backend.database.SessionLocal()
    user = db.query(User).filter(User.email == "invited@acme.tn").first()
    assert user is not None
    assert user.role == "recruiter"
    assert user.temp_password is not None
    db.close()


def test_cross_company_member_404(client, org_admin_headers, test_company):
    """Org admin from Company A cannot touch another company's member → 404."""
    from datetime import UTC, datetime

    db = backend.database.SessionLocal()
    other_co = Company(
        name="Evil Corp",
        slug="evil-corp",
        tier="free",
        subscription_status="active",
        max_users=10,
        max_jobs=50,
        max_ai_interviews=500,
        is_active=True,
    )
    db.add(other_co)
    db.flush()
    attacker = User(
        email="attacker@evilcorp.com",
        name="Evil Recruiter",
        hashed_password=pwd_context.hash("attackerpass123"),
        role="recruiter",
        email_verified=True,
    )
    db.add(attacker)
    db.flush()
    db.add(
        CompanyMember(
            company_id=other_co.id,
            user_id=attacker.id,
            role="recruiter",
            is_active=True,
            joined_at=datetime.now(UTC),
        )
    )
    db.commit()
    other_id = attacker.id
    db.close()

    resp = client.patch(
        f"/api/v1/org/members/{other_id}",
        json={"role": "admin"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 404


# ── D. Analytics ───────────────────────────────────────────────────


def test_org_overview(client, org_admin_headers):
    resp = client.get("/api/v1/org/analytics/overview", headers=org_admin_headers)
    assert resp.status_code == 200
    assert resp.json() is not None


def test_org_credits_economy(client, org_admin_headers):
    resp = client.get("/api/v1/org/analytics/credits", headers=org_admin_headers)
    assert resp.status_code == 200


def test_org_recruiter_detail(client, org_admin_headers, org_member):
    resp = client.get(
        f"/api/v1/org/analytics/recruiters/{org_member.id}",
        headers=org_admin_headers,
    )
    assert resp.status_code == 200


def test_org_recruiter_detail_missing_404(client, org_admin_headers):
    resp = client.get(
        "/api/v1/org/analytics/recruiters/999999",
        headers=org_admin_headers,
    )
    assert resp.status_code == 404


# ── E. Org credit transfer ─────────────────────────────────────────


def _seed_pool(db, user, credits):
    from backend.credit_service import grant_credits

    grant_credits(
        db,
        user,
        credits,
        provider="system",
        note="test pool seed",
    )


def test_grant_member_credits_transfers_from_pool(
    client, org_admin_headers, org_admin, org_member
):
    """Org admin transfers credits: pool (owner wallet) debited, member credited."""
    from backend.credit_service import get_user_credit_balance

    db = backend.database.SessionLocal()
    member_before = get_user_credit_balance(db, org_member)
    pool_before = get_user_credit_balance(db, org_admin)
    _seed_pool(db, org_admin, 500)
    db.close()

    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/grant-credits",
        json={"credits": 120, "note": "Monthly bonus"},
        headers=org_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["credits"] == 120
    assert data["duplicate"] is False

    db = backend.database.SessionLocal()
    assert get_user_credit_balance(db, org_member) == member_before + 120
    assert get_user_credit_balance(db, org_admin) == pool_before + 500 - 120
    db.close()


def test_grant_member_credits_idempotent(client, org_admin_headers, org_admin, org_member):
    """Retrying the same grant (same amount + note) never double-moves."""
    from backend.credit_service import get_user_credit_balance

    db = backend.database.SessionLocal()
    member_before = get_user_credit_balance(db, org_member)
    _seed_pool(db, org_admin, 300)
    db.close()

    payload = {"credits": 50, "note": "Bonus"}
    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/grant-credits",
        json=payload,
        headers=org_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    resp2 = client.post(
        f"/api/v1/org/members/{org_member.id}/grant-credits",
        json=payload,
        headers=org_admin_headers,
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["duplicate"] is True

    db = backend.database.SessionLocal()
    assert get_user_credit_balance(db, org_member) == member_before + 50
    db.close()


def test_grant_member_credits_insufficient_pool_400(
    client, org_admin_headers, org_admin, org_member
):
    db = backend.database.SessionLocal()
    _seed_pool(db, org_admin, 10)
    db.close()

    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/grant-credits",
        json={"credits": 100000},
        headers=org_admin_headers,
    )
    assert resp.status_code == 400


def test_grant_member_credits_invalid_amount_400(
    client, org_admin_headers, org_admin, org_member
):
    db = backend.database.SessionLocal()
    _seed_pool(db, org_admin, 200)
    db.close()

    resp = client.post(
        f"/api/v1/org/members/{org_member.id}/grant-credits",
        json={"credits": 0},
        headers=org_admin_headers,
    )
    assert resp.status_code == 400


def test_grant_member_credits_cross_company_404(
    client, org_admin_headers, test_company
):
    """Org admin cannot grant credits to a member of another company → 404."""
    from datetime import UTC, datetime

    db = backend.database.SessionLocal()
    other_co = Company(
        name="Rival Corp",
        slug="rival-corp",
        tier="free",
        subscription_status="active",
        max_users=10,
        max_jobs=50,
        max_ai_interviews=500,
        is_active=True,
    )
    db.add(other_co)
    db.flush()
    outsider = User(
        email="outsider@rivalcorp.com",
        name="Outsider",
        hashed_password=pwd_context.hash("outsiderpass123"),
        role="recruiter",
        email_verified=True,
    )
    db.add(outsider)
    db.flush()
    db.add(
        CompanyMember(
            company_id=other_co.id,
            user_id=outsider.id,
            role="recruiter",
            is_active=True,
            joined_at=datetime.now(UTC),
        )
    )
    db.commit()
    outsider_id = outsider.id
    db.close()

    resp = client.post(
        f"/api/v1/org/members/{outsider_id}/grant-credits",
        json={"credits": 50},
        headers=org_admin_headers,
    )
    assert resp.status_code == 404


def test_member_list_includes_credit_balance(client, org_admin_headers, org_member):
    resp = client.get("/api/v1/org/members", headers=org_admin_headers)
    assert resp.status_code == 200, resp.text
    member = next(m for m in resp.json()["members"] if m["user_id"] == org_member.id)
    assert "credit_balance" in member
    assert member["credit_balance"] >= 0


def test_billing_summary_includes_company_credit_balance(
    client, org_admin_headers, org_admin
):
    resp = client.get("/api/v1/org/billing/summary", headers=org_admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "company_credit_balance" in data
    assert data["company_credit_balance"] >= 0


# ── F. Company-managed recruiter plan surfacing ────────────────────


def test_company_managed_recruiter_sees_company_plan(
    client, org_member_headers, test_company, org_admin
):
    """A recruiter member sees the company's plan (tier/name/limits), not
    their own free profile, when their subscription is company-managed."""
    from backend.database import SubscriptionPlan

    db = backend.database.SessionLocal()
    plan = SubscriptionPlan(
        name="Recruiter Enterprise",
        slug="recruiter-enterprise",
        price_monthly=499.0,
        price_yearly=4990.0,
        currency="TND",
        job_limit=200,
        cv_limit=500,
        ai_interview_limit=500,
        team_seat_limit=50,
        credits_monthly=1000,
        plan_group="paid",
    )
    db.add(plan)
    db.flush()
    co = db.query(Company).filter(Company.id == test_company.id).first()
    co.plan_id = plan.id
    co.tier = plan.slug
    co.subscription_status = "active"
    db.commit()
    db.close()

    resp = client.get(
        "/api/v1/recruiter/subscription/status",
        headers=org_member_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["managed_by_company"] is True
    assert data["tier"] == "recruiter-enterprise"
    assert data["plan_name"] == "Recruiter Enterprise"
    assert data["plan_slug"] == "recruiter-enterprise"
    assert data["status"] == "active"
    assert data["limits"]["job_limit"] == 200
    assert data["limits"]["team_seat_limit"] == 50
