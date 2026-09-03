import pytest
from fastapi import status

from backend.database import Application
from backend.dependencies import generate_interview_token


@pytest.fixture
def guest_application(db_session, test_company):
    """Create a guest application (no user_id)"""
    app = Application(
        company_id=test_company.id,
        email="guest@example.com",
        full_name="Guest Candidate",
        status="invited",
        declared_role="Python Developer",
        interview_state="in_progress",
        interview_progress=0,
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app


def test_guest_auth_flow(client, guest_application):
    """
    Test the full guest authentication flow:
    1. HMAC token verification via /auth/guest-login provides a JWT
    2. Guest JWT provides access to interview endpoints
    3. Guest JWT provides access to candidate portal endpoints
    """
    app_id = guest_application.id
    token_dict = generate_interview_token(app_id)
    token = token_dict["token"]

    # 1. Guest Login (HMAC -> JWT)
    response = client.post(
        "/api/v1/auth/guest-login",
        json={"app_id": guest_application.id, "token": token},
    )

    print(f"DEBUG: Guest Login Response: {response.status_code}")
    print(f"DEBUG: Response data: {response.json()}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    jwt_token = data["access_token"]
    print(f"DEBUG: Captured jwt_token (truncated): {jwt_token[:10]}...")
    headers = {"Authorization": f"Bearer {jwt_token}"}

    # 2. Access /ai/interview/chat with Guest JWT
    response = client.post(
        "/api/v1/ai/interview/chat",
        headers=headers,
        json={"candidate_id": app_id, "message": "ready", "language": "English"},
    )
    # Note: Even if AI generation fails specifically in test env, it should not be 401
    assert response.status_code != status.HTTP_401_UNAUTHORIZED

    # 3. Access /ai/interview/evaluate-final with Guest JWT
    response = client.post(
        "/api/v1/ai/interview/evaluate-final",
        headers=headers,
        json={"application_id": app_id},
    )
    assert response.status_code != status.HTTP_401_UNAUTHORIZED

    # 4. Access /candidate/current-application with Guest JWT
    response = client.get("/api/v1/candidate/current-application", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == app_id
    assert data["status"] == guest_application.status


def test_guest_direct_hmac_access(client, guest_application):
    """
    Test that endpoints accepting get_interview_access can also be accessed via HMAC directly
    (for initial loads before JWT is obtained)
    """
    app_id = guest_application.id
    token_dict = generate_interview_token(app_id)
    token = token_dict["token"]

    # Access /api/v1/candidate/applications/{app_id}?token={token}
    response = client.get(f"/api/v1/candidate/applications/{app_id}?token={token}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == app_id
