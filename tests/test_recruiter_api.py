"""Tests for recruiter API route access control."""
import pytest
from fastapi.testclient import TestClient

# Cache the original get_current_user at module level so dependency_overrides
# always uses the original function as key, even if a prior test monkeypatched it.
from backend.dependencies import get_current_user as _ORIG_GET_CURRENT_USER


class _RecruiterUser:
    def __init__(self, id=1, email="recruiter@masar.com", role="recruiter"):
        self.id = id
        self.email = email
        self.role = role
        self.tier = "pro"
        self.usage_jobs = 0
        self.usage_cvs = 0
        self.usage_ai_interviews = 0


class _NonRecruiterUser:
    def __init__(self, id=99, email="user@example.com", role="candidate"):
        self.id = id
        self.email = email
        self.role = role
        self.tier = "free"


def _client(recruiter=True, monkeypatch=None):
    from backend.app import create_app

    mock_user = _RecruiterUser() if recruiter else _NonRecruiterUser()

    async def _mock_current_user():
        return mock_user

    if monkeypatch is not None:
        monkeypatch.setattr("backend.dependencies.get_current_user", _mock_current_user)
    app = create_app()
    app.dependency_overrides[_ORIG_GET_CURRENT_USER] = _mock_current_user
    return TestClient(app)


class TestRecruiterDashboard:
    @pytest.fixture
    def recruiter_client(self, monkeypatch):
        return _client(recruiter=True, monkeypatch=monkeypatch)

    @pytest.fixture
    def non_recruiter_client(self, monkeypatch):
        return _client(recruiter=False, monkeypatch=monkeypatch)


class TestRecruiterSSR:
    @pytest.fixture
    def recruiter_client(self):
        return _client(recruiter=True)

    @pytest.fixture
    def non_recruiter_client(self):
        return _client(recruiter=False)

    def test_dashboard_stats_access(self, recruiter_client):
        resp = recruiter_client.get("/api/v1/recruiter/dashboard/stats")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_dashboard_stats_forbidden(self, non_recruiter_client):
        resp = non_recruiter_client.get("/api/v1/recruiter/dashboard/stats")
        assert resp.status_code == 403

    def test_jobs_list_access(self, recruiter_client):
        resp = recruiter_client.get("/api/v1/recruiter/jobs/my")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_jobs_list_forbidden(self, non_recruiter_client):
        resp = non_recruiter_client.get("/api/v1/recruiter/jobs/my")
        assert resp.status_code == 403

    def test_candidates_search_access(self, recruiter_client):
        resp = recruiter_client.get("/api/v1/recruiter/candidates/search")
        assert resp.status_code in (200, 404), f"Unexpected: {resp.status_code}"

    def test_candidates_search_forbidden(self, non_recruiter_client):
        resp = non_recruiter_client.get("/api/v1/recruiter/candidates/search")
        assert resp.status_code == 403


class TestRecruiterSSR:
    @pytest.fixture
    def recruiter_client(self):
        return _client(recruiter=True)

    @pytest.fixture
    def non_recruiter_client(self):
        return _client(recruiter=False)

    _RECRUITER_PAGES = [
        "/recruiter/dashboard",
        "/recruiter/jobs",
        "/recruiter/candidates",
        "/recruiter/campaigns",
        "/recruiter/analytics",
        "/recruiter/calendar",
        "/recruiter/pipeline",
        "/recruiter/team",
        "/recruiter/reports",
        "/recruiter/templates",
        "/recruiter/billing",
        "/recruiter/settings",
        "/recruiter/interviews",
        "/recruiter/offers",
        "/recruiter/sourcing",
    ]

    @pytest.mark.parametrize("page", _RECRUITER_PAGES)
    def test_recruiter_ssr_pages_require_auth(self, non_recruiter_client, page):
        resp = non_recruiter_client.get(page, follow_redirects=False)
        assert resp.status_code == 403, f"{page} returned {resp.status_code}"

    @pytest.mark.parametrize("page", _RECRUITER_PAGES)
    def test_recruiter_ssr_pages_accessible(self, recruiter_client, page):
        resp = recruiter_client.get(page, follow_redirects=False)
        assert resp.status_code in (200, 302), f"{page} returned {resp.status_code}"
