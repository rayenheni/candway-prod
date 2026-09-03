"""S10 — Payment proof review workflow (admin view/verify/reject)."""

import io
import os

import pytest
from fastapi.testclient import TestClient

from backend.database import (
    AdminProfile,
    Company,
    CompanyMember,
    SubscriptionPlan,
    Transaction,
    User,
)
from backend.dependencies import pwd_context

# Ensure all models are registered with Base.metadata before db_session creates tables
from backend.models.foundation.system import SystemConfig  # noqa: F401


def _login(client: TestClient, email: str, password: str):
    csrf = client.get("/login").headers.get("X-CSRF-Token") or client.get("/login").cookies.get("csrf_token")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    return resp.json()["access_token"], csrf


def _admin_headers(client: TestClient, db_session, company):
    email = "admin@test.com"
    password = "adminpass123"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name="Admin User",
            hashed_password=pwd_context.hash(password),
            role="admin",
            email_verified=True,
        )
        db_session.add(user)
        db_session.flush()
        profile = AdminProfile(user_id=user.id, company_id=company.id, permissions="manage_finance")
        db_session.add(profile)
        db_session.commit()
    token, csrf = _login(client, email, password)
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}, user


def _company_user(client: TestClient, db_session, company, role="recruiter"):
    email = f"user_{role}@test.com"
    password = "userpass123"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name=f"Test {role}",
            hashed_password=pwd_context.hash(password),
            role=role,
            email_verified=True,
        )
        db_session.add(user)
        db_session.flush()
        membership = CompanyMember(
            company_id=company.id, user_id=user.id, role="admin", is_active=True
        )
        db_session.add(membership)
        db_session.commit()
    token, csrf = _login(client, email, password)
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}, user


def _create_pending_tx(db_session, user, company, with_proof=True):
    plan = db_session.query(SubscriptionPlan).filter_by(slug="recruiter-pro").first()
    if not plan:
        plan = SubscriptionPlan(
            name="Pro Plan",
            slug="recruiter-pro",
            price_monthly=149.0,
            target_audience="recruiter",
            is_active=True,
        )
        db_session.add(plan)
        db_session.flush()

    rp = getattr(user, "recruiter_profile", None)
    if rp:
        rp.subscription_plan = plan.slug

    tx = Transaction(
        user_id=user.id,
        company_id=company.id if company else None,
        amount=149.0,
        currency="TND",
        status="pending",
        description="Manual Upgrade to Pro",
        proof_url="uploads/company_receipts/test_receipt.png" if with_proof else None,
        proof_status="uploaded" if with_proof else None,
        proof_file_size=1234 if with_proof else None,
        proof_file_type="image/png" if with_proof else None,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)
    return tx


class TestPaymentProofWorkflow:
    def test_list_payment_proofs_empty(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        resp = client.get("/api/v1/admin/payment-proofs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["proofs"] == []

    def test_list_payment_proofs_with_proofs(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.get("/api/v1/admin/payment-proofs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["proofs"][0]["id"] == tx.id
        assert data["proofs"][0]["proof_status"] == "uploaded"
        assert data["proofs"][0]["proof_url"] == tx.proof_url

    def test_list_payment_proofs_filter_by_status(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx1 = _create_pending_tx(db_session, user, test_company)
        tx2 = _create_pending_tx(db_session, user, test_company)
        tx2.proof_status = "verified"
        db_session.commit()

        resp = client.get(
            "/api/v1/admin/payment-proofs?proof_status=uploaded", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["proofs"][0]["id"] == tx1.id

        resp = client.get(
            "/api/v1/admin/payment-proofs?proof_status=verified", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["proofs"][0]["id"] == tx2.id

    def test_get_payment_proof_detail(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.get(f"/api/v1/admin/payment-proofs/{tx.id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tx.id
        assert data["proof_status"] == "uploaded"
        assert data["proof_file_size"] == 1234
        assert data["proof_file_type"] == "image/png"

    def test_get_payment_proof_not_found(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        resp = client.get("/api/v1/admin/payment-proofs/99999", headers=admin_headers)
        assert resp.status_code == 404

    def test_verify_payment_proof(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.post(
            f"/api/v1/admin/payment-proofs/{tx.id}/verify",
            json={"notes": "Looks good"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Payment proof verified"

        db_session.refresh(tx)
        assert tx.proof_status == "verified"
        assert tx.proof_verified_by == admin_user.id
        assert tx.proof_verified_at is not None
        assert tx.proof_review_notes == "Looks good"

    def test_reject_payment_proof(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.post(
            f"/api/v1/admin/payment-proofs/{tx.id}/reject",
            json={"notes": "Amount does not match"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Payment proof rejected. The company may re-upload."

        db_session.refresh(tx)
        assert tx.proof_status == "rejected"
        assert tx.proof_review_notes == "Amount does not match"
        assert tx.proof_verified_at is None

    def test_reject_payment_proof_requires_reason(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.post(
            f"/api/v1/admin/payment-proofs/{tx.id}/reject",
            json={"notes": "   "},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_approve_subscription_sets_proof_verified(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        from backend.models.evaluation.profile import RecruiterProfile
        rp = db_session.query(RecruiterProfile).filter(RecruiterProfile.user_id == user.id).first()
        if not rp:
            rp = RecruiterProfile(user_id=user.id, subscription_plan="recruiter-pro")
            db_session.add(rp)
            db_session.commit()
        else:
            rp.subscription_plan = "recruiter-pro"
            db_session.commit()

        resp = client.post(
            f"/api/v1/admin/subscriptions/{tx.id}/approve",
            headers=admin_headers,
        )
        assert resp.status_code == 200

        db_session.refresh(tx)
        assert tx.status == "succeeded"
        assert tx.proof_status == "verified"
        assert tx.proof_verified_by == admin_user.id
        assert tx.proof_verified_at is not None

    def test_reject_subscription_sets_proof_rejected(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.post(
            f"/api/v1/admin/payment-proofs/{tx.id}/reject",
            json={"notes": "Fraudulent proof"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Payment proof rejected. The company may re-upload."

        db_session.refresh(tx)
        assert tx.proof_status == "rejected"
        assert tx.proof_review_notes == "Fraudulent proof"

    def test_proof_endpoints_require_admin(self, client, db_session, test_company):
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company)

        resp = client.get("/api/v1/admin/payment-proofs", headers=user_headers)
        assert resp.status_code == 403

        resp = client.get(f"/api/v1/admin/payment-proofs/{tx.id}", headers=user_headers)
        assert resp.status_code == 403

        resp = client.post(
            f"/api/v1/admin/payment-proofs/{tx.id}/verify", headers=user_headers
        )
        assert resp.status_code == 403

    def test_verify_without_proof_returns_400(self, client, db_session, test_company):
        admin_headers, admin_user = _admin_headers(client, db_session, test_company)
        user_headers, user = _company_user(client, db_session, test_company)
        tx = _create_pending_tx(db_session, user, test_company, with_proof=False)

        resp = client.post(
            f"/api/v1/admin/payment-proofs/{tx.id}/verify",
            headers=admin_headers,
        )
        assert resp.status_code == 400
