"""
Privilege escalation security tests for critical fixes (P1.1 - P1.6).
"""

import pytest
from fastapi import HTTPException

from backend.authz import (
    get_application_for_candidate,
    get_application_for_recruiter,
    get_job_for_recruiter,
)
from backend.credit_service import grant_credits
from backend.database import (
    Application,
    Company,
    Job,
    User,
)
from backend.models.evaluation.profile import AdminProfile

# ── Helpers ──────────────────────────────────────────────────────


def _make_job(db_session, recruiter_id: int, company_id: int = 1, **kw) -> Job:
    if "company" in kw:
        kw.pop("company")
    j = Job(recruiter_id=recruiter_id, title="Engineer", company_id=company_id, **kw)
    db_session.add(j)
    db_session.flush()
    return j


def _make_app(
    db_session, user_id: int, job_id: int = None, company_id: int = 1, **kw
) -> Application:
    a = Application(
        user_id=user_id,
        job_id=job_id,
        declared_role="Engineer",
        company_id=company_id,
        **kw,
    )
    db_session.add(a)
    db_session.flush()
    return a


# ── authz.py unit tests ──────────────────────────────────────────


class TestGetApplicationForCandidate:
    def test_owner_can_access(self, db_session, test_user):
        app = _make_app(db_session, test_user.id)
        db_session.commit()
        result = get_application_for_candidate(app.id, test_user, db_session)
        assert result.id == app.id

    def test_non_owner_gets_404(self, db_session, test_user):
        other = User(
            email="other@test.com",
            name="Other",
            hashed_password="x",
            role="candidate",
            email_verified=True,
        )
        db_session.add(other)
        db_session.flush()
        app = _make_app(db_session, test_user.id)
        db_session.commit()
        with pytest.raises(HTTPException) as exc:
            get_application_for_candidate(app.id, other, db_session)
        assert exc.value.status_code == 404

    def test_nonexistent_app_404(self, db_session, test_user):
        with pytest.raises(HTTPException) as exc:
            get_application_for_candidate(99999, test_user, db_session)
        assert exc.value.status_code == 404


class TestGetApplicationForRecruiter:
    def test_job_owner_can_access(self, db_session, test_recruiter):
        job = _make_job(db_session, test_recruiter.id)
        app = _make_app(db_session, test_recruiter.id, job.id)
        db_session.commit()
        result = get_application_for_recruiter(app.id, test_recruiter, db_session)
        assert result.id == app.id

    def test_assigned_recruiter_can_access(self, db_session, test_recruiter):
        app = _make_app(db_session, test_recruiter.id, assigned_to=test_recruiter.id)
        db_session.commit()
        result = get_application_for_recruiter(app.id, test_recruiter, db_session)
        assert result.id == app.id

    def test_admin_can_access_any(self, db_session, test_recruiter):
        admin = User(
            email="admin@test.com",
            name="Admin",
            hashed_password="x",
            role="admin",
            email_verified=True,
            is_super_admin=True,
            admin_permissions="all",
        )
        db_session.add(admin)
        db_session.flush()
        admin_profile = AdminProfile(
            user_id=admin.id,
            company_id=1,
            is_super_admin=True,
            permissions="all",
        )
        db_session.add(admin_profile)
        db_session.flush()
        job = _make_job(db_session, test_recruiter.id)
        app = _make_app(db_session, test_recruiter.id, job.id)
        db_session.commit()
        result = get_application_for_recruiter(app.id, admin, db_session)
        assert result.id == app.id

    def test_other_recruiter_gets_404(self, db_session, test_recruiter):
        r2 = User(
            email="recruiter2@test.com",
            name="Recruiter Two",
            hashed_password="x",
            role="recruiter",
            email_verified=True,
        )
        db_session.add(r2)
        db_session.flush()
        job = _make_job(db_session, test_recruiter.id)
        app = _make_app(db_session, test_recruiter.id, job.id)
        db_session.commit()
        with pytest.raises(HTTPException) as exc:
            get_application_for_recruiter(app.id, r2, db_session)
        assert exc.value.status_code == 404


class TestGetJobForRecruiter:
    def test_owner_can_access(self, db_session, test_recruiter):
        job = _make_job(db_session, test_recruiter.id)
        db_session.commit()
        result = get_job_for_recruiter(job.id, test_recruiter, db_session)
        assert result.id == job.id

    def test_other_recruiter_gets_404(self, db_session, test_recruiter):
        r2 = User(
            email="recruiter3@test.com",
            name="Recruiter Three",
            hashed_password="x",
            role="recruiter",
            email_verified=True,
        )
        db_session.add(r2)
        db_session.flush()
        job = _make_job(db_session, test_recruiter.id)
        db_session.commit()
        with pytest.raises(HTTPException) as exc:
            get_job_for_recruiter(job.id, r2, db_session)
        assert exc.value.status_code == 404


# ── EEO endpoint integration tests (P1.1 + P1.2) ────────────────


class TestEEOEndpointsAuth:
    """Verify EEO endpoints enforce authentication."""

    def test_submit_requires_auth(self, client, db_session):
        """Unauthenticated POST /eeo/submit returns 401/403."""
        resp = client.post(
            "/api/v1/candidate/eeo/submit",
            json={"application_id": 1},
        )
        assert resp.status_code in (401, 403)

    def test_status_requires_auth(self, client, db_session):
        """Unauthenticated GET /eeo/status/1 returns 401."""
        resp = client.get("/api/v1/candidate/eeo/status/1")
        assert resp.status_code in (401, 403)

    def test_owner_can_submit(self, client, db_session, auth_headers):
        """Authenticated candidate can submit EEO for own application."""
        user = db_session.query(User).filter_by(email="test@example.com").first()
        app = _make_app(db_session, user.id)
        db_session.commit()
        resp = client.post(
            "/api/v1/candidate/eeo/submit",
            json={
                "application_id": app.id,
                "consent_given": True,
                "gender": "male",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

    def test_non_owner_gets_404_on_submit(self, client, db_session, auth_headers):
        """Candidate cannot submit EEO for another candidate's application."""
        other = User(
            email="other2@test.com",
            name="Other Two",
            hashed_password="x",
            role="candidate",
            email_verified=True,
        )
        db_session.add(other)
        db_session.flush()
        app = _make_app(db_session, other.id)
        db_session.commit()
        resp = client.post(
            "/api/v1/candidate/eeo/submit",
            json={"application_id": app.id, "consent_given": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404, resp.text

    def test_non_owner_gets_404_on_status(self, client, db_session, auth_headers):
        """Candidate cannot check EEO status for another candidate."""
        other = User(
            email="other3@test.com",
            name="Other Three",
            hashed_password="x",
            role="candidate",
            email_verified=True,
        )
        db_session.add(other)
        db_session.flush()
        app = _make_app(db_session, other.id)
        db_session.commit()
        resp = client.get(
            f"/api/v1/candidate/eeo/status/{app.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404, resp.text

    def test_nonexistent_app_404(self, client, db_session, auth_headers):
        """EEO endpoint returns 404 for non-existent application."""
        resp = client.get("/api/v1/candidate/eeo/status/99999", headers=auth_headers)
        assert resp.status_code == 404, resp.text


# ── Recruiter search isolation test (P1.4) ───────────────────────


class TestRecruiterSearchIsolation:
    def test_search_returns_200_for_owned_candidates(
        self, client, db_session, recruiter_headers
    ):
        """Recruiter search returns 200 with company-isolated results."""
        r1 = db_session.query(User).filter_by(email="recruiter@example.com").first()
        grant_credits(db_session, r1, 100, provider="system", note="test credits")
        job = _make_job(db_session, r1.id, company_id=1)
        _app = _make_app(db_session, r1.id, job.id, full_name="Alice", company_id=1)
        db_session.commit()
        resp = client.post(
            "/api/v1/recruiter/search",
            json={"query": "Engineering"},
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text

    def test_search_excludes_other_company(self, client, db_session, recruiter_headers):
        """Recruiter search does not return other company candidates."""
        r1 = db_session.query(User).filter_by(email="recruiter@example.com").first()
        r2 = User(
            email="recruiter_excluded@test.com",
            name="Other Recruiter",
            hashed_password="x",
            role="recruiter",
            email_verified=True,
        )
        db_session.add(r2)
        db_session.flush()
        company_b = Company(name="Company B", slug="company-b-test")
        db_session.add(company_b)
        db_session.commit()
        grant_credits(db_session, r1, 100, provider="system", note="test credits")
        _job1 = _make_job(db_session, r1.id, company_id=1)
        job2 = _make_job(db_session, r2.id, company_id=company_b.id)
        app2 = _make_app(
            db_session, r2.id, job2.id, full_name="Bob", company_id=company_b.id
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/recruiter/search",
            json={"query": "Engineering"},
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        ids = [c["id"] for c in data]
        assert app2.id not in ids


# ── authz.py import & smoke test ────────────────────────────────


class TestAuthzModule:
    def test_module_imports_cleanly(self):
        from backend import authz

        assert authz.__name__ == "backend.authz"

    def test_get_application_for_candidate_404_on_missing(self, db_session, test_user):
        with pytest.raises(HTTPException) as exc:
            get_application_for_candidate(99999, test_user, db_session)
        assert exc.value.status_code == 404

    def test_get_application_for_recruiter_404_on_missing(
        self, db_session, test_recruiter
    ):
        with pytest.raises(HTTPException) as exc:
            get_application_for_recruiter(99999, test_recruiter, db_session)
        assert exc.value.status_code == 404
