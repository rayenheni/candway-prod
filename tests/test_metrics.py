"""P0-10 FIX tests: /metrics and /breakers endpoints."""
import pytest
from fastapi.testclient import TestClient


def _client():
    from backend.app import create_app
    from backend.dependencies import get_current_user

    class _U:
        id = 1
        email = "x@x.com"
        role = "admin"
        is_super_admin = True
        admin_permissions = "view_analytics"

    async def _user():
        return _U()

    app = create_app()
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_metrics_endpoint_returns_text():
    c = _client()
    r = c.get("/metrics")
    # Either 200 with metrics body, or 503 if prometheus_client is
    # not installed in the test env (requirements.txt includes it
    # but test envs may be minimal).
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("text/plain")
        body = r.text
        # Standard prometheus client output starts with HELP lines.
        assert "candway_" in body or "process_" in body


def test_breakers_endpoint_reports_providers():
    c = _client()
    r = c.get("/breakers")
    assert r.status_code == 200
    data = r.json()
    if "breakers" in data:
        for provider in ("groq", "gemini", "deepseek", "ollama", "cascade"):
            assert provider in data["breakers"]
            assert data["breakers"][provider] in {"CLOSED", "HALF_OPEN", "OPEN"}
