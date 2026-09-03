"""
Security Tests — Chatbot API Authorization

Validates:
  - Unauthenticated access blocked (401)
  - Non-recruiter blocked from recruiter endpoints (403)
  - Cross-company access returns 404 (tenant mismatch, not 403) — IDOR / enumeration prevention
  - Legitimate intra-company access allowed (200)
  - Audit logging on lead access
"""

from datetime import UTC, datetime

from fastapi import status

from backend.database import AuditLog, ChatbotLead
from backend.tests.conftest import _fetch_csrf_token


def _make_lead(db_session, company_id=None, **kwargs):
    """Create a test ChatbotLead row."""
    defaults = dict(
        conversation_id=f"conv-{kwargs.get('name', 'test')}-{datetime.now(UTC).timestamp()}",
        name="Test Lead",
        email="lead@test.com",
        phone="+21650000000",
        role_interest="Engineer",
        experience_level="mid",
        skills="Python, JS",
        message_history="[]",
        stage="capturing",
        company_id=company_id,
    )
    defaults.update(kwargs)
    lead = ChatbotLead(**defaults)
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


def _anon_csrf_headers(client):
    """Return headers with a CSRF token but no auth (for unauthenticated POST tests)."""
    token = _fetch_csrf_token(client)
    return {"X-CSRF-Token": token}


# ── Unauthenticated Access ───────────────────────────────────────────


class TestUnauthenticated:
    """All protected chatbot endpoints must reject unauthenticated requests."""

    def test_get_leads_requires_auth(self, client):
        resp = client.get("/api/v1/chatbot/leads")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_transfer_requires_auth(self, client):
        headers = _anon_csrf_headers(client)
        resp = client.post("/api/v1/chatbot/transfer/test-conv", headers=headers)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_assign_lead_requires_auth(self, client):
        headers = _anon_csrf_headers(client)
        resp = client.post(
            "/api/v1/chatbot/leads/1/assign?recruiter_id=1", headers=headers
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_contacted_lead_requires_auth(self, client):
        headers = _anon_csrf_headers(client)
        resp = client.post("/api/v1/chatbot/leads/1/contacted", headers=headers)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ── Role Enforcement ─────────────────────────────────────────────────


class TestRoleEnforcement:
    """Non-recruiter users must be blocked from recruiter endpoints with 403."""

    def test_candidate_cannot_list_leads(self, client, auth_headers):
        resp = client.get("/api/v1/chatbot/leads", headers=auth_headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_candidate_cannot_assign_lead(
        self, client, auth_headers, db_session, test_company
    ):
        lead = _make_lead(db_session, company_id=test_company.id)
        resp = client.post(
            f"/api/v1/chatbot/leads/{lead.id}/assign?recruiter_id=1",
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_candidate_cannot_mark_contacted(
        self, client, auth_headers, db_session, test_company
    ):
        lead = _make_lead(db_session, company_id=test_company.id)
        resp = client.post(
            f"/api/v1/chatbot/leads/{lead.id}/contacted",
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── Cross-Company Access (IDOR Prevention) ───────────────────────────


class TestCrossCompanyAccess:
    """Company A recruiter → Company B's leads → 404 Not Found (tenant mismatch)."""

    def test_cross_company_list_leads(
        self, client, recruiter_headers, db_session, test_company_b
    ):
        _make_lead(db_session, company_id=test_company_b.id, name="Evil Lead")
        resp = client.get("/api/v1/chatbot/leads", headers=recruiter_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["total"] == 0, "Company A must not see Company B leads"

    def test_cross_company_assign_lead(
        self, client, recruiter_headers, db_session, test_company_b
    ):
        lead = _make_lead(db_session, company_id=test_company_b.id)
        resp = client.post(
            f"/api/v1/chatbot/leads/{lead.id}/assign?recruiter_id=1",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_company_mark_contacted(
        self, client, recruiter_headers, db_session, test_company_b
    ):
        lead = _make_lead(db_session, company_id=test_company_b.id)
        resp = client.post(
            f"/api/v1/chatbot/leads/{lead.id}/contacted",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_company_transfer_lead(
        self, client, recruiter_headers, db_session, test_company_b
    ):
        lead = _make_lead(db_session, company_id=test_company_b.id)
        resp = client.post(
            f"/api/v1/chatbot/transfer/{lead.conversation_id}",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ── Legitimate Intra-Company Access ──────────────────────────────────


class TestIntraCompanyAccess:
    """Recruiter can access leads within their own company."""

    def test_recruiter_lists_own_leads(
        self, client, recruiter_headers, db_session, test_company
    ):
        _make_lead(db_session, company_id=test_company.id, name="Alice")
        _make_lead(db_session, company_id=test_company.id, name="Bob")
        resp = client.get("/api/v1/chatbot/leads", headers=recruiter_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["total"] == 2
        names = {lead["name"] for lead in data["leads"]}
        assert "Alice" in names
        assert "Bob" in names

    def test_recruiter_assigns_own_lead(
        self, client, recruiter_headers, db_session, test_company
    ):
        lead = _make_lead(db_session, company_id=test_company.id)
        resp = client.post(
            f"/api/v1/chatbot/leads/{lead.id}/assign?recruiter_id=1",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        db_session.refresh(lead)
        assert lead.assigned_recruiter_id == 1

    def test_recruiter_contacts_own_lead(
        self, client, recruiter_headers, db_session, test_company
    ):
        lead = _make_lead(db_session, company_id=test_company.id)
        assert lead.contacted_at is None
        resp = client.post(
            f"/api/v1/chatbot/leads/{lead.id}/contacted",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        db_session.refresh(lead)
        assert lead.contacted_at is not None


# ── IDOR Prevention — Numeric ID Probing ────────────────────────────


class TestIDORPrevention:
    """Attacker probing numeric lead IDs must not leak cross-company data."""

    def test_idor_assign_lead_nonexistent(self, client, recruiter_headers):
        resp = client.post(
            "/api/v1/chatbot/leads/99999/assign?recruiter_id=1",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_contacted_nonexistent(self, client, recruiter_headers):
        resp = client.post(
            "/api/v1/chatbot/leads/99999/contacted",
            headers=recruiter_headers,
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ── Audit Logging ────────────────────────────────────────────────────


class TestAuditLogging:
    """AuditLog entries must be created for lead access operations."""

    def test_audit_log_on_list(
        self, client, recruiter_headers, db_session, test_company
    ):
        _make_lead(db_session, company_id=test_company.id)
        client.get("/api/v1/chatbot/leads", headers=recruiter_headers)

        log = (
            db_session.query(AuditLog).filter(AuditLog.action == "leads_listed").first()
        )
        assert log is not None
        assert log.user_id is not None
        assert log.company_id == test_company.id

    def test_audit_log_on_assign(
        self, client, recruiter_headers, db_session, test_company
    ):
        lead = _make_lead(db_session, company_id=test_company.id)
        client.post(
            f"/api/v1/chatbot/leads/{lead.id}/assign?recruiter_id=1",
            headers=recruiter_headers,
        )

        log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "lead_assigned")
            .first()
        )
        assert log is not None
        assert str(lead.id) in (log.target_id or "")

    def test_audit_log_on_contacted(
        self, client, recruiter_headers, db_session, test_company
    ):
        lead = _make_lead(db_session, company_id=test_company.id)
        client.post(
            f"/api/v1/chatbot/leads/{lead.id}/contacted",
            headers=recruiter_headers,
        )

        log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "lead_contacted")
            .first()
        )
        assert log is not None
        assert str(lead.id) in (log.target_id or "")
