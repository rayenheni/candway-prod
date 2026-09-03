"""Tests for the org portal company-level billing (S9).

Covers:
- GET /org/billing/plans (recruiter team plans)
- POST /org/billing/subscribe (company-scoped pending Transaction + Subscription)
- POST /org/billing/receipt/{tx} (proof upload)
- GET /org/billing/summary + /transactions + /invoices
- GET/POST /org/billing/kyb
- Company-aware admin approval (admin/subscriptions.py) → seats raised + invoice
- Seat enforcement in /org/members create/invite
"""

import io
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
    Base,
    Company,
    CompanyMember,
    Invoice,
    Subscription,
    SubscriptionPlan,
    Transaction,
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
    assert resp.status_code == 200, resp.text
    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}


def _create_plan(db, slug, name, audience, price, seats):
    plan = SubscriptionPlan(
        name=name,
        slug=slug,
        target_audience=audience,
        price_monthly=price,
        price_yearly=price * 12,
        currency="TND",
        team_seat_limit=seats,
        job_limit=5,
        cv_limit=50,
        ai_interview_limit=10,
        credits_monthly=0,
        is_active=True,
    )
    db.add(plan)
    db.flush()
    return plan


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def seeded(client):
    """Company (limited seats), org admin, recruiter member, recruiter plan."""
    from datetime import UTC, datetime

    db = backend.database.SessionLocal()

    plan = _create_plan(db, "recruiter-pro", "Recruiter Pro", "recruiter", 149.0, 5)
    _create_plan(db, "recruiter-free", "Free Recruiter", "recruiter", 0.0, 1)
    _create_plan(db, "candidate-pro", "Candidate Pro", "candidate", 29.0, 1)

    company = Company(
        name="Billing Co",
        slug="billing-co",
        tier="free",
        subscription_status="active",
        max_users=1,
        max_jobs=50,
        max_ai_interviews=500,
        is_active=True,
    )
    db.add(company)
    db.flush()
    cid = company.id

    admin = User(
        email="billingadmin@test.tn",
        name="Billing Admin",
        hashed_password=pwd_context.hash("billingpass123"),
        role="company",
        email_verified=True,
    )
    db.add(admin)
    db.flush()
    from backend.models.evaluation.profile import RecruiterProfile

    db.add(
        RecruiterProfile(
            user_id=admin.id,
            name="Billing Admin",
            email="billingadmin@test.tn",
            company_name="Billing Co",
            company_id=cid,
            email_settings="{}",
            tier="free",
            subscription_status="active",
        )
    )
    db.add(
        CompanyMember(
            company_id=cid,
            user_id=admin.id,
            role="owner",
            is_active=True,
            joined_at=datetime.now(UTC),
        )
    )
    db.commit()
    result = {
        "company_id": cid,
        "admin_id": admin.id,
        "plan_id": plan.id,
        "plan": plan,
    }
    db.close()
    return result


@pytest.fixture(scope="module")
def billing_admin_headers(client, seeded):
    return _login(client, "billingadmin@test.tn", "billingpass123")


# ── Plans ────────────────────────────────────────────────────────────


def test_list_company_plans(client, billing_admin_headers, seeded):
    resp = client.get("/api/v1/org/billing/plans", headers=billing_admin_headers)
    assert resp.status_code == 200, resp.text
    plans = resp.json()
    slugs = {p["slug"] for p in plans}
    assert "recruiter-pro" in slugs
    assert "candidate-pro" not in slugs
    pro = next(p for p in plans if p["slug"] == "recruiter-pro")
    assert pro["team_seat_limit"] == 5
    assert pro["price_monthly"] == 149.0


def test_plans_require_org_admin(client, seeded):
    # clear session cookies so the shared TestClient is unauthenticated again
    client.cookies.clear()
    resp = client.get("/api/v1/org/billing/plans")
    assert resp.status_code in (401, 403)


# ── KYB ──────────────────────────────────────────────────────────────


def test_kyb_submit_and_read(client, billing_admin_headers, seeded):
    resp = client.post(
        "/api/v1/org/billing/kyb",
        json={
            "billing_email": "finance@billingco.tn",
            "billing_address": "Avenue Habib Bourguiba, Tunis",
            "tax_id": "1234567/A/M/000",
        },
        headers=billing_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["kyb_status"] == "pending"

    resp = client.get("/api/v1/org/billing/kyb", headers=billing_admin_headers)
    assert resp.status_code == 200
    k = resp.json()
    assert k["billing_email"] == "finance@billingco.tn"
    assert k["tax_id"] == "1234567/A/M/000"
    assert k["kyb_status"] == "pending"


def test_kyb_requires_email(client, billing_admin_headers):
    resp = client.post(
        "/api/v1/org/billing/kyb",
        json={"billing_email": "  "},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 400


# ── Subscription purchase ────────────────────────────────────────────


def test_subscribe_creates_pending_tx_and_sub(client, billing_admin_headers, seeded):
    resp = client.post(
        "/api/v1/org/billing/subscribe",
        json={"plan_id": seeded["plan_id"], "billing_cycle": "yearly"},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["transaction_id"]

    db = backend.database.SessionLocal()
    tx = db.query(Transaction).filter(Transaction.id == data["transaction_id"]).first()
    assert tx is not None
    assert tx.company_id == seeded["company_id"]
    assert tx.status == "pending"
    assert tx.description.startswith("Company subscription")
    assert tx.amount_ttc == 149.0 * 12
    assert tx.amount_ht > 0

    sub = (
        db.query(Subscription)
        .filter(Subscription.company_id == seeded["company_id"])
        .order_by(Subscription.id.desc())
        .first()
    )
    assert sub is not None
    assert sub.status == "pending"
    assert sub.plan_id == seeded["plan_id"]
    assert sub.billing_cycle == "yearly"
    db.close()

    # duplicate pending → 400
    resp2 = client.post(
        "/api/v1/org/billing/subscribe",
        json={"plan_id": seeded["plan_id"], "billing_cycle": "monthly"},
        headers=billing_admin_headers,
    )
    assert resp2.status_code == 400


def test_subscribe_invalid_plan(client, billing_admin_headers):
    resp = client.post(
        "/api/v1/org/billing/subscribe",
        json={"plan_id": 999999, "billing_cycle": "monthly"},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 404


def test_subscribe_candidate_plan_rejected(client, billing_admin_headers, seeded):
    db = backend.database.SessionLocal()
    cand_plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.slug == "candidate-pro")
        .first()
    )
    db.close()
    resp = client.post(
        "/api/v1/org/billing/subscribe",
        json={"plan_id": cand_plan.id, "billing_cycle": "monthly"},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 400


_PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f"
    "15c4890000000d4944415478da63fccfc0500f000485018084a98c21000000"
    "0049454e44ae426082"
)


def _png_file(name="proof.png"):
    return (name, io.BytesIO(_PNG_1PX), "image/png")


def test_receipt_upload(client, billing_admin_headers, seeded, monkeypatch):
    # python-magic not installed in CI → skip content MIME validation
    monkeypatch.setattr(
        "backend.file_security.validate_file_content",
        lambda content, ext, max_size: (True, ""),
    )
    db = backend.database.SessionLocal()
    tx = (
        db.query(Transaction)
        .filter(
            Transaction.company_id == seeded["company_id"],
            Transaction.status == "pending",
        )
        .first()
    )
    db.close()
    assert tx is not None

    resp = client.post(
        f"/api/v1/org/billing/receipt/{tx.id}",
        files={"file": _png_file()},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    db = backend.database.SessionLocal()
    fresh = db.query(Transaction).filter(Transaction.id == tx.id).first()
    assert fresh.proof_url is not None
    db.close()


def test_receipt_foreign_tx_404(client, billing_admin_headers):
    resp = client.post(
        "/api/v1/org/billing/receipt/999999",
        files={"file": _png_file("p.png")},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 404


def test_summary_shows_pending(client, billing_admin_headers, seeded):
    resp = client.get("/api/v1/org/billing/summary", headers=billing_admin_headers)
    assert resp.status_code == 200, resp.text
    s = resp.json()
    assert s["company_id"] == seeded["company_id"]
    assert s["pending_transaction"] is not None
    assert s["kyb_status"] == "pending"
    assert s["seats"]["available"] >= 0


# ── Admin approval (company-aware) ───────────────────────────────────


def test_admin_approve_company_subscription(client, billing_admin_headers, seeded):

    # platform admin
    db = backend.database.SessionLocal()
    tx = (
        db.query(Transaction)
        .filter(
            Transaction.company_id == seeded["company_id"],
            Transaction.status == "pending",
        )
        .first()
    )
    db.close()

    # create a finance-capable admin
    admin = User(
        email="platformadmin@test.tn",
        name="Platform Admin",
        hashed_password=pwd_context.hash("platformpass123"),
        role="admin",
        email_verified=True,
    )
    db = backend.database.SessionLocal()
    db.add(admin)
    db.flush()
    from backend.models.evaluation.profile import AdminProfile

    db.add(
        AdminProfile(
            user_id=admin.id,
            is_super_admin=True,
            permissions="manage_finance,manage_users",
            company_id=seeded["company_id"],
        )
    )
    db.commit()
    db.close()
    admin_headers = _login(client, "platformadmin@test.tn", "platformpass123")

    resp = client.post(
        f"/api/v1/admin/subscriptions/{tx.id}/approve",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["seats"] == 5

    db = backend.database.SessionLocal()
    company = db.query(Company).filter(Company.id == seeded["company_id"]).first()
    assert company.plan_id == seeded["plan_id"]
    assert company.max_users == 5
    assert company.subscription_status == "active"

    sub = (
        db.query(Subscription)
        .filter(Subscription.company_id == seeded["company_id"])
        .order_by(Subscription.id.desc())
        .first()
    )
    assert sub.status == "active"
    assert sub.current_period_end is not None

    invoice = db.query(Invoice).filter(Invoice.transaction_id == tx.id).first()
    assert invoice is not None
    assert invoice.company_id == seeded["company_id"]
    assert invoice.client_name == "Billing Co"
    assert invoice.client_mf == "1234567/A/M/000"
    db.close()


def test_subscribe_blocked_when_active_sub_exists(
    client, billing_admin_headers, seeded
):
    # If an earlier test already approved a subscription for this module-scoped
    # company, the first subscribe is already rejected. Otherwise purchase and
    # approve one first, then verify a second purchase is rejected (409) instead
    # of stacking another active subscription.
    resp = client.post(
        "/api/v1/org/billing/subscribe",
        json={"plan_id": seeded["plan_id"], "billing_cycle": "yearly"},
        headers=billing_admin_headers,
    )
    if resp.status_code == 200:
        tx_id = resp.json()["transaction_id"]
        admin = User(
            email="platformadmin2@test.tn",
            name="Platform Admin 2",
            hashed_password=pwd_context.hash("platformpass123"),
            role="admin",
            email_verified=True,
        )
        db = backend.database.SessionLocal()
        db.add(admin)
        db.flush()
        from backend.models.evaluation.profile import AdminProfile

        db.add(
            AdminProfile(
                user_id=admin.id,
                is_super_admin=True,
                permissions="manage_finance,manage_users",
                company_id=seeded["company_id"],
            )
        )
        db.commit()
        db.close()
        admin_headers = _login(client, "platformadmin2@test.tn", "platformpass123")

        resp = client.post(
            f"/api/v1/admin/subscriptions/{tx_id}/approve",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text

    # An active subscription exists → buying again must be refused.
    resp2 = client.post(
        "/api/v1/org/billing/subscribe",
        json={"plan_id": seeded["plan_id"], "billing_cycle": "yearly"},
        headers=billing_admin_headers,
    )
    assert resp2.status_code == 409

    # The company must hold exactly one active sub (approval deactivates any
    # previously active ones).
    db = backend.database.SessionLocal()
    active_subs = (
        db.query(Subscription)
        .filter(
            Subscription.company_id == seeded["company_id"],
            Subscription.status.in_(("active", "trialing", "past_due")),
        )
        .all()
    )
    db.close()
    assert len(active_subs) == 1


# ── Seat enforcement ─────────────────────────────────────────────────


def test_seat_limit_enforced_on_create(client, billing_admin_headers, seeded):
    # company.max_users == 5 after approval; org admin + 0 recruiters →
    # creating a 6th recruiter is rejected. Test with role=recruiter repeatedly.
    for i in range(5):
        resp = client.post(
            "/api/v1/org/members",
            json={
                "name": f"Seat {i}",
                "email": f"seat{i}@billingco.tn",
                "role": "recruiter",
            },
            headers=billing_admin_headers,
        )
        assert resp.status_code == 200, f"seat {i} create failed: {resp.text}"

    # 6th recruiter → 400 seat limit
    resp = client.post(
        "/api/v1/org/members",
        json={"name": "Too Many", "email": "toomany@billingco.tn", "role": "recruiter"},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 400
    assert "seat limit" in resp.json()["detail"].lower()


def test_seat_limit_enforced_on_invite(client, billing_admin_headers, seeded):
    resp = client.post(
        "/api/v1/org/members/invite",
        json={"name": "Invite Overflow", "email": "invoverflow@billingco.tn"},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 400
    assert "seat limit" in resp.json()["detail"].lower()


def test_member_role_not_seat_counted(client, billing_admin_headers, seeded):
    # 'member' role does not consume recruiter seats
    resp = client.post(
        "/api/v1/org/members",
        json={"name": "Ops", "email": "ops@billingco.tn", "role": "member"},
        headers=billing_admin_headers,
    )
    assert resp.status_code == 200, resp.text


def test_transactions_and_invoices_endpoints(client, billing_admin_headers, seeded):
    resp = client.get("/api/v1/org/billing/transactions", headers=billing_admin_headers)
    assert resp.status_code == 200
    assert resp.json()["transactions"]

    resp = client.get("/api/v1/org/billing/invoices", headers=billing_admin_headers)
    assert resp.status_code == 200
    invoices = resp.json()["invoices"]
    assert invoices, "expected at least one company invoice"

    inv = invoices[0]
    resp = client.get(
        f"/api/v1/org/billing/invoices/{inv['id']}/download",
        headers=billing_admin_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
