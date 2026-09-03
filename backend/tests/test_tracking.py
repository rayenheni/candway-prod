import pytest
from fastapi.testclient import TestClient

from backend.database import Application, Base, Company, SessionLocal, engine
from backend.main import app
from backend.routers.tracking import make_tracking_token

client = TestClient(app)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_track_click_redirection_and_logic(db_session):
    # 1. Create a dummy application
    company = Company(name="Tracking Test Co", slug="tracking-test-co")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    test_app = Application(
        user_id=1,
        email="tracking_test@example.com",
        declared_role="Software Engineer",
        interview_state="not_started",
        company_id=company.id,
    )
    db_session.add(test_app)
    db_session.commit()
    db_session.refresh(test_app)

    try:
        # 2. Call track_click endpoint (prevent auto-redirect follow)
        response = client.get(
            f"/api/v1/track/click/{make_tracking_token(test_app.id)}",
            follow_redirects=False,
        )

        # 3. Verify redirection (it redirects to /auth/interview-access?app_id=...)
        assert response.status_code == 307
        assert "/auth/interview-access" in response.headers["location"]
        assert f"app_id={test_app.id}" in response.headers["location"]

        # 4. Verify DB update
        db_session.refresh(test_app)
        assert test_app.clicked_at is not None

    finally:
        # Cleanup
        db_session.delete(test_app)
        db_session.commit()


def test_track_click_invalid_app(db_session):
    # Use an ID that doesn't exist
    response = client.get(
        f"/api/v1/track/click/{make_tracking_token(99999)}",
        follow_redirects=False,
    )
    # Should still redirect to /auth/interview-access?app_id=99999
    assert response.status_code == 307
    assert "/auth/interview-access" in response.headers["location"]
    assert "app_id=99999" in response.headers["location"]
