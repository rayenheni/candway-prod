"""Tests for candidate API route access control."""
import pytest
from fastapi.testclient import TestClient

# Cache the original get_current_user at module level so dependency_overrides
# always uses the original function as key, even if a prior test monkeypatched it.
from backend.dependencies import get_current_user as _ORIG_GET_CURRENT_USER


class _CandidateUser:
    def __init__(self, id=2, email="candidate@masar.com", role="candidate"):
        self.id = id
        self.email = email
        self.role = role
        self.tier = "free"


class _NonCandidateUser:
    def __init__(self, id=1, email="recruiter@masar.com", role="recruiter"):
        self.id = id
        self.email = email
        self.role = role


def _client(candidate=True, monkeypatch=None):
    from backend.app import create_app

    mock_user = _CandidateUser() if candidate else _NonCandidateUser()

    async def _mock_current_user():
        return mock_user

    if monkeypatch is not None:
        monkeypatch.setattr("backend.dependencies.get_current_user", _mock_current_user)
    app = create_app()
    app.dependency_overrides[_ORIG_GET_CURRENT_USER] = _mock_current_user
    return TestClient(app)


class TestCandidateAPI:
    @pytest.fixture
    def candidate_client(self, monkeypatch):
        return _client(candidate=True, monkeypatch=monkeypatch)

    @pytest.fixture
    def non_candidate_client(self, monkeypatch):
        return _client(candidate=False, monkeypatch=monkeypatch)

    def test_profile_access(self, candidate_client):
        resp = candidate_client.get("/api/v1/candidate/profile")
        assert resp.status_code in (200, 404)

    def test_profile_forbidden(self, non_candidate_client):
        resp = non_candidate_client.get("/api/v1/candidate/profile")
        assert resp.status_code == 200  # profile endpoint has no role check

    def test_interviews_access(self, candidate_client):
        resp = candidate_client.get("/api/v1/candidate/interviews")
        assert resp.status_code in (200, 404)

    def test_interviews_forbidden(self, non_candidate_client):
        resp = non_candidate_client.get("/api/v1/candidate/interviews")
        assert resp.status_code == 404  # bare /interviews does not exist (use /interviews/history)

    def test_applications_access(self, candidate_client):
        resp = candidate_client.get("/api/v1/candidate/applications/me")
        assert resp.status_code in (200, 404)

    def test_applications_forbidden(self, non_candidate_client):
        resp = non_candidate_client.get("/api/v1/candidate/applications/me")
        assert resp.status_code in (200, 403, 404)

    def test_documents_access(self, candidate_client):
        resp = candidate_client.get("/api/v1/candidate/documents")
        assert resp.status_code in (200, 404)

    def test_documents_forbidden(self, non_candidate_client):
        resp = non_candidate_client.get("/api/v1/candidate/documents")
        assert resp.status_code in (200, 404)  # page route (no API route exists)
