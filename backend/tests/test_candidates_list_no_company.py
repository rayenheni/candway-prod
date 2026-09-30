"""A recruiter-role user without a company gets an empty candidate list and
never a query scoped on ``company_id IS NULL``."""

from unittest.mock import patch

from backend.database import User
from backend.dependencies import pwd_context


def _login(client, email, password):
    resp = client.get("/login")
    csrf = resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token") or ""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    return {
        "Authorization": f"Bearer {resp.json()['access_token']}",
        "X-CSRF-Token": csrf,
    }


def test_candidates_list_without_company_is_empty(client, db_session):
    db_session.add(
        User(
            email="lonely-recruiter@example.com",
            name="Lonely Recruiter",
            hashed_password=pwd_context.hash("lonelypass123"),
            role="recruiter",
            email_verified=True,
        )
    )
    db_session.commit()
    headers = _login(client, "lonely-recruiter@example.com", "lonelypass123")

    with patch("backend.routers.recruiter_candidates.search.MetricsRepository") as repo:
        resp = client.get("/api/v1/recruiter/candidates/list", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["pagination"]["total_applications"] == 0
    repo.assert_not_called()


def test_candidates_list_with_company_still_queries(client, recruiter_headers):
    resp = client.get("/api/v1/recruiter/candidates/list", headers=recruiter_headers)
    assert resp.status_code == 200, resp.text
    assert "items" in resp.json() and "pagination" in resp.json()
