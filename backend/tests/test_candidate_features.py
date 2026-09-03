"""
Candidate feature coverage tests.
Focuses on stable candidate-facing API contracts that should work without external services.
"""

from datetime import datetime

import pytest
from fastapi import status

from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    SubscriptionPlan,
    SupportTicket,
    SystemConfig,
    User,
)
from backend.dependencies import pwd_context
from backend.entity_writer import sync_ai_interview_session
from backend.routers.tracking import make_tracking_token
from backend.tests.conftest import _fetch_csrf_token


@pytest.fixture
def seeded_application(db_session, test_user, test_company):
    from backend.entity_writer import sync_cv_document
    from backend.models.evaluation.profile import CandidateProfile

    profile = CandidateProfile(
        user_id=test_user.id,
        name=test_user.name,
        phone=test_user.phone,
        email=test_user.email,
    )
    db_session.add(profile)
    db_session.flush()

    app = Application(
        user_id=test_user.id,
        company_id=test_company.id,
        full_name=test_user.name,
        email=test_user.email,
        phone=test_user.phone,
        status="analyzed",
        created_at=datetime.now(),
        cv_text_anonymized=(
            "Experienced Python developer with FastAPI, SQLAlchemy, and testing background. "
            "Built APIs and production services for multiple teams."
        ),
    )
    db_session.add(app)
    db_session.flush()
    sync_cv_document(
        db_session,
        app,
        declared_role="Python Developer",
        cv_text_anonymized=(
            "Experienced Python developer with FastAPI, SQLAlchemy, and testing background. "
            "Built APIs and production services for multiple teams."
        ),
        analysis_json={
            "builder_data": {"summary": "Python backend profile"},
            "match_score": 82,
        },
    )
    _es = EvaluationSession(
        application_id=app.id, company_id=test_company.id, status="completed"
    )
    db_session.add(_es)
    db_session.flush()
    _sc = EvaluationResult(
        evaluation_session_id=_es.id,
        company_id=test_company.id,
        scoring_status="SCORED",
        final_score=78.0,
        cv_score=78.0,
    )
    db_session.add(_sc)
    db_session.commit()
    db_session.refresh(app)
    return app


@pytest.fixture
def active_job(db_session, test_recruiter, test_company):
    job = Job(
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        title="Senior Python Developer",
        company_name="Candway Tech",
        location="Tunis",
        salary_range="3500-5000 TND",
        type="Full-time",
        description="Backend API role",
        required_skills="Python,FastAPI,SQL",
        is_active=True,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def candidate_plan(db_session):
    plan = SubscriptionPlan(
        name="Candidate Pro",
        slug="candidate-pro",
        target_audience="candidate",
        price_monthly=49.0,
        price_yearly=490.0,
        currency="TND",
        features='["Priority matching","Advanced insights"]',
        is_active=True,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def payment_settings(db_session):
    configs = [
        SystemConfig(key="bank_name", value="Demo Bank"),
        SystemConfig(key="bank_account_name", value="Candway"),
        SystemConfig(key="bank_account_number", value="123456789"),
        SystemConfig(key="bank_iban", value="TN5900TESTIBAN"),
        SystemConfig(key="payment_instructions", value="Send proof after transfer."),
    ]
    db_session.add_all(configs)
    db_session.commit()
    return configs


def test_candidate_me_endpoint(client, auth_headers):
    response = client.get("/api/v1/candidate/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "candidate"


def test_candidate_profile_update_and_get(client, auth_headers):
    update_response = client.put(
        "/api/v1/candidate/profile",
        headers=auth_headers,
        json={
            "headline": "Senior Python Developer",
            "location": "Tunis",
            "bio": "Backend engineer",
        },
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["message"] == "Profile updated successfully"

    profile_response = client.get("/api/v1/candidate/profile", headers=auth_headers)
    assert profile_response.status_code == status.HTTP_200_OK
    profile = profile_response.json()
    assert profile["headline"] == "Senior Python Developer"
    assert profile["location"] == "Tunis"


def test_candidate_application_views(client, auth_headers, seeded_application):
    current = client.get("/api/v1/candidate/current-application", headers=auth_headers)
    assert current.status_code == status.HTTP_200_OK
    assert current.json()["id"] == seeded_application.id

    summary = client.get("/api/v1/candidate/applications/me", headers=auth_headers)
    assert summary.status_code == status.HTTP_200_OK
    assert summary.json()["id"] == seeded_application.id

    dashboard = client.get("/api/v1/candidate/dashboard", headers=auth_headers)
    assert dashboard.status_code == status.HTTP_200_OK
    assert dashboard.json()["id"] == seeded_application.id

    by_id = client.get(
        f"/api/v1/candidate/applications/{seeded_application.id}", headers=auth_headers
    )
    assert by_id.status_code == status.HTTP_200_OK
    assert by_id.json()["id"] == seeded_application.id


def test_dashboard_normalizes_legacy_qa_log(
    client, auth_headers, seeded_application, db_session
):
    sync_ai_interview_session(
        db_session,
        seeded_application,
        interview_log=[
            {"question": "Q1", "answer": "A1", "feedback": "Need more detail"}
        ],
    )

    dashboard = client.get("/api/v1/candidate/dashboard", headers=auth_headers)
    assert dashboard.status_code == status.HTTP_200_OK
    payload = dashboard.json()
    assert isinstance(payload.get("interview_log"), list)
    assert any(item.get("role") == "assistant" for item in payload["interview_log"])
    assert any(
        "Need more detail" in str(item.get("content", ""))
        for item in payload["interview_log"]
    )


def test_candidate_cv_data_graph_and_audit(client, auth_headers, seeded_application):
    cv_data = client.get("/api/v1/candidate/cv-data", headers=auth_headers)
    assert cv_data.status_code == status.HTTP_200_OK
    assert cv_data.json()["found"] is True

    graph = client.get("/api/v1/candidate/talent-graph", headers=auth_headers)
    assert graph.status_code == status.HTTP_200_OK
    graph_data = graph.json()
    assert "labels" in graph_data and "values" in graph_data
    assert len(graph_data["labels"]) == len(graph_data["values"])

    audit = client.get(
        f"/api/v1/candidate/applications/{seeded_application.id}/audit",
        headers=auth_headers,
    )
    assert audit.status_code == status.HTTP_200_OK
    assert "overall_score" in audit.json()


def test_candidate_subscription_usage_and_export(
    client, auth_headers, seeded_application
):
    usage = client.get("/api/v1/candidate/subscription/usage", headers=auth_headers)
    assert usage.status_code == status.HTTP_200_OK
    usage_data = usage.json()
    assert "plan_slug" in usage_data
    assert "cv_uploads" in usage_data

    export = client.get("/api/v1/candidate/export", headers=auth_headers)
    assert export.status_code == status.HTTP_200_OK
    export_data = export.json()
    assert export_data["user_info"]["email"] == "test@example.com"
    assert isinstance(export_data["applications"], list)


def test_candidate_jobs_match_and_apply_flow(
    client, auth_headers, seeded_application, active_job, monkeypatch
):
    import backend.ai as _backend_ai

    # The apply endpoint now runs a rubric-aware CV analysis in a background
    # task (safe_execute). Mock the AI so the test stays deterministic and
    # offline; the job has no rubric so the generic analyze_cv path is used.
    async def fake_analyze_cv(text, role):
        return {
            "score": 70,
            "detected_role": "Python Developer",
            "skills": ["python"],
            "verdict": "qualified",
            "summary": "Mock CV analysis",
        }

    monkeypatch.setattr(_backend_ai, "analyze_cv", fake_analyze_cv)

    matches = client.get("/api/v1/candidate/jobs/matches", headers=auth_headers)
    assert matches.status_code == status.HTTP_200_OK
    jobs = matches.json()
    assert any(j["id"] == active_job.id for j in jobs)

    first_apply = client.post(
        f"/api/v1/candidate/jobs/{active_job.id}/apply", headers=auth_headers
    )
    assert first_apply.status_code == status.HTTP_200_OK
    assert "application_id" in first_apply.json()

    second_apply = client.post(
        f"/api/v1/candidate/jobs/{active_job.id}/apply", headers=auth_headers
    )
    assert second_apply.status_code == status.HTTP_200_OK
    assert "Already applied" in second_apply.json()["message"]


def test_candidate_plans_payment_and_upgrade(
    client, auth_headers, db_session, candidate_plan, payment_settings
):
    plans = client.get("/api/v1/candidate/plans", headers=auth_headers)
    assert plans.status_code == status.HTTP_200_OK
    plans_data = plans.json()
    assert any(p["slug"] == candidate_plan.slug for p in plans_data)

    payment_config = client.get(
        "/api/v1/candidate/payment-config", headers=auth_headers
    )
    assert payment_config.status_code == status.HTTP_200_OK
    payment_data = payment_config.json()
    assert payment_data["bank_name"] == "Demo Bank"

    upgrade = client.post(
        "/api/v1/candidate/upgrade",
        headers=auth_headers,
        json={"plan_id": candidate_plan.id, "message": "Please upgrade my plan"},
    )
    assert upgrade.status_code == status.HTTP_200_OK
    assert upgrade.json()["status"] == "success"

    ticket = (
        db_session.query(SupportTicket)
        .filter(SupportTicket.category == "upgrade")
        .first()
    )
    assert ticket is not None

    duplicate_upgrade = client.post(
        "/api/v1/candidate/upgrade",
        headers=auth_headers,
        json={"plan_id": candidate_plan.id, "message": "retry"},
    )
    assert duplicate_upgrade.status_code == status.HTTP_200_OK
    assert duplicate_upgrade.json()["status"] == "pending"


def test_privacy_endpoints_removed(client, auth_headers, seeded_application):
    """Privacy router was intentionally removed (dead code, no frontend consumers)."""
    export = client.get("/api/v1/privacy/export-data", headers=auth_headers)
    assert export.status_code == status.HTTP_404_NOT_FOUND


def test_tracking_open_and_click_endpoints(client, db_session, seeded_application):
    tracking_token = make_tracking_token(seeded_application.id)
    open_resp = client.get(
        f"/api/v1/track/open/{tracking_token}"
    )
    assert open_resp.status_code == status.HTTP_200_OK
    assert open_resp.headers.get("content-type", "").startswith("image/png")

    db_session.refresh(seeded_application)
    assert seeded_application.opened_at is not None

    click_resp = client.get(
        f"/api/v1/track/click/{make_tracking_token(seeded_application.id)}?token=abc123",
        follow_redirects=False,
    )
    assert click_resp.status_code in (
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
    )
    assert (
        f"/auth/interview-access?app_id={seeded_application.id}&token=abc123"
        in click_resp.headers["location"]
    )

    db_session.refresh(seeded_application)
    assert seeded_application.clicked_at is not None


def test_candidate_profile_comprehensive_uses_profile_attributes(
    client, auth_headers, test_user, seeded_application, db_session
):
    from backend.models.evaluation.profile import CandidateProfile

    profile = (
        db_session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == test_user.id)
        .first()
    )
    assert profile is not None

    profile.availability = "Immediately"
    profile.work_preference = "Remote"
    profile.salary_expectation_min = 3000
    profile.salary_expectation_max = 5000
    db_session.commit()

    response = client.get(
        "/api/v1/candidate/profile/comprehensive", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["availability"] == "Immediately"
    assert data["work_preference"] == "Remote"
    assert data["salary_min"] == 3000
    assert data["salary_max"] == 5000


def test_candidate_profile_comprehensive_defaults(
    client, auth_headers, seeded_application
):
    response = client.get(
        "/api/v1/candidate/profile/comprehensive", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["availability"] == "Available Immediately"
    assert data["work_preference"] == "Full-time, Remote or Hybrid"
    assert data["salary_min"] == 4000
    assert data["salary_max"] == 8000


def test_candidate_interview_history(client, auth_headers, seeded_application):
    response = client.get("/api/v1/candidate/interviews/history", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == seeded_application.id


def test_candidate_interview_analysis(client, auth_headers, seeded_application):
    response = client.get(
        f"/api/v1/candidate/interviews/{seeded_application.id}/analysis",
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == seeded_application.id
    assert "score" in data
    assert "questions" in data
    assert "metrics" in data


def test_candidate_badges(client, auth_headers, seeded_application):
    response = client.get("/api/v1/candidate/badges", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "badges" in data
    assert "total_interviews" in data
    assert "highest_score" in data


def test_candidate_reset_interview(
    client, auth_headers, seeded_application, db_session
):
    print("\n=== DEBUG BEFORE RESET ===")
    print("Application id:", seeded_application.id)

    sessions = (
        db_session.query(EvaluationSession)
        .filter(EvaluationSession.application_id == seeded_application.id)
        .order_by(EvaluationSession.id.asc())
        .all()
    )

    for es in sessions:
        print(
            "ES:",
            es.id,
            "state=", es.interview_state,
            "progress=", es.interview_progress,
            "log=", es.interview_log,
        )

    print(
        "latest helper:",
        seeded_application._latest_eval_session().id
        if seeded_application._latest_eval_session()
        else None,
    )

    sync_ai_interview_session(
        db_session,
        seeded_application,
        interview_state="in_progress",
        interview_log=[{"role": "assistant", "content": "Q1"}],
        interview_progress=3,
    )

    response = client.post(
        "/api/v1/candidate/reset-interview",
        headers=auth_headers,
        json={"application_id": seeded_application.id},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Interview reset successfully"

    db_session.refresh(seeded_application)
    db_session.expire(seeded_application, ["evaluation_sessions"])

    assert seeded_application.interview_log == []
    assert seeded_application.interview_state == "not_started"
    assert seeded_application.interview_progress == 0


def test_candidate_builder_data_crud(client, auth_headers, seeded_application):
    update_response = client.put(
        "/api/v1/candidate/builder-data",
        headers=auth_headers,
        json={
            "summary": "Updated summary",
            "experience": [{"role": "Dev", "company": "TestCo"}],
            "skills": ["Python", "FastAPI"],
        },
    )
    assert update_response.status_code == status.HTTP_200_OK

    get_response = client.get("/api/v1/candidate/cv-data", headers=auth_headers)
    assert get_response.status_code == status.HTTP_200_OK
    data = get_response.json()
    assert data["found"] is True
    assert data["data"]["summary"] == "Updated summary"


def test_candidate_builder_save_requires_content(client, auth_headers):
    response = client.post(
        "/api/v1/candidate/applications",
        headers=auth_headers,
        json={"declared_role": "General"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Please provide at least one section of your CV" in response.json().get(
        "detail", ""
    )


def test_recruiter_cannot_download_unrelated_candidate_pdf(
    client, recruiter_headers, db_session
):
    from backend.database import Application, User

    other_candidate = User(
        email="other@example.com",
        name="Other Candidate",
        hashed_password=pwd_context.hash("password123"),
        role="candidate",
        email_verified=True,
    )
    db_session.add(other_candidate)
    db_session.commit()
    db_session.refresh(other_candidate)

    app = Application(
        user_id=other_candidate.id,
        full_name=other_candidate.name,
        email=other_candidate.email,
        status="analyzed",
        cv_text_anonymized="Candidate CV text.",
        analysis_json="{}",
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    response = client.get(
        f"/api/v1/candidate/applications/{app.id}/pdf",
        headers=recruiter_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_candidate_invitations(client, auth_headers, seeded_application, db_session):
    seeded_application.status = "invited"
    db_session.commit()

    response = client.get("/api/v1/candidate/invitations", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)


def test_candidate_profile_visitors(client, auth_headers):
    response = client.get("/api/v1/candidate/profile-visitors", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_candidate_application_history(client, auth_headers, seeded_application):
    response = client.get(
        "/api/v1/candidate/applications/me/history", headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == seeded_application.id


def test_idor_prevention_on_application(client, auth_headers, db_session, test_company):
    other_user = User(
        email="other@example.com",
        name="Other User",
        hashed_password=pwd_context.hash("otherpass123"),
        role="candidate",
        email_verified=True,
    )
    db_session.add(other_user)
    db_session.commit()

    other_app = Application(
        user_id=other_user.id,
        company_id=test_company.id,
        full_name=other_user.name,
        email=other_user.email,
        declared_role="Other Role",
        status="analyzed",
    )
    db_session.add(other_app)
    db_session.commit()
    db_session.refresh(other_app)

    response = client.get(
        f"/api/v1/candidate/applications/{other_app.id}", headers=auth_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_e2e_full_candidate_flow(client, db_session):
    """
    End-to-end test: Login → Profile → CV Save → Dashboard → Interview → Analysis
    Covers the complete candidate journey without external AI services.
    """
    csrf_token = _fetch_csrf_token(client)

    user = User(
        email="e2e@example.com",
        name="E2E Candidate",
        hashed_password=pwd_context.hash("e2epassword123"),
        role="candidate",
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "e2e@example.com", "password": "e2epassword123"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert login_resp.status_code == status.HTTP_200_OK
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}

    me_resp = client.get("/api/v1/candidate/me", headers=headers)
    assert me_resp.status_code == status.HTTP_200_OK
    assert me_resp.json()["email"] == "e2e@example.com"

    profile_resp = client.put(
        "/api/v1/candidate/profile",
        headers=headers,
        json={"headline": "Full Stack Developer", "location": "Tunis"},
    )
    assert profile_resp.status_code == status.HTTP_200_OK

    dashboard_resp = client.get("/api/v1/candidate/applications/me", headers=headers)
    assert dashboard_resp.status_code == status.HTTP_200_OK

    cv_data_resp = client.put(
        "/api/v1/candidate/builder-data",
        headers=headers,
        json={
            "summary": "Experienced developer",
            "skills": ["Python", "FastAPI", "React"],
            "experience": [{"role": "Developer", "company": "TechCo"}],
        },
    )
    assert cv_data_resp.status_code == status.HTTP_200_OK

    cv_get_resp = client.get("/api/v1/candidate/cv-data", headers=headers)
    assert cv_get_resp.status_code == status.HTTP_200_OK
    assert cv_get_resp.json()["found"] is True

    dashboard_after_cv = client.get(
        "/api/v1/candidate/applications/me", headers=headers
    )
    assert dashboard_after_cv.status_code == status.HTTP_200_OK

    history_resp = client.get(
        "/api/v1/candidate/applications/me/history", headers=headers
    )
    assert history_resp.status_code == status.HTTP_200_OK

    talent_graph_resp = client.get("/api/v1/candidate/talent-graph", headers=headers)
    assert talent_graph_resp.status_code == status.HTTP_200_OK
    assert "labels" in talent_graph_resp.json()

    badges_resp = client.get("/api/v1/candidate/badges", headers=headers)
    assert badges_resp.status_code == status.HTTP_200_OK

    export_resp = client.get("/api/v1/candidate/export", headers=headers)
    assert export_resp.status_code == status.HTTP_200_OK
    assert export_resp.json()["user_info"]["email"] == "e2e@example.com"


def test_candidate_upload_cv_normalizes_analysis_json(
    client, auth_headers, test_user, db_session, monkeypatch
):
    """Regression: legacy json.dumps(result) must be stored as a JSON object."""

    # This test exercises CV analysis itself, not subscription enforcement.
    # Give the candidate an isolated test plan with enough AI-analysis quota.
    from backend.candidate_subscription_service import CandidateSubscriptionService
    from backend.models.evaluation.profile import CandidateProfile
    from backend.models.foundation.subscription import SubscriptionPlan

    profile = (
        db_session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == test_user.id)
        .first()
    )

    if profile is None:
        profile = CandidateProfile(
            user_id=test_user.id,
            candidate_ai_analyses_this_month=0,
        )
        db_session.add(profile)
    else:
        profile.candidate_ai_analyses_this_month = 0

    test_plan = SubscriptionPlan(
        name="CV Upload Test Plan",
        slug="cv-upload-test",
        target_audience="candidate",
        candidate_ai_analyses_limit=10,
        candidate_cv_uploads_limit=10,
        is_active=True,
    )
    db_session.add(test_plan)
    db_session.flush()

    test_user.current_plan_id = test_plan.id
    db_session.commit()

    monkeypatch.setattr(
        CandidateSubscriptionService,
        "reset_usage_if_needed",
        staticmethod(lambda user, db: None),
    )

    import backend.ai as backend_ai
    import backend.file_security as file_security
    import backend.cv_service as cv_service

    async def fake_analyze_cv(text, role):
        return {
            "detected_role": "Python Developer",
            "score": 91,
            "verdict": "qualified",
            "summary": "Mock CV analysis",
            "skill_metrics": {
                "Python": 95,
                "FastAPI": 90,
            },
        }

    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    monkeypatch.setattr(
        file_security,
        "scan_for_malware",
        lambda content, filename: (True, "clean"),
    )

    monkeypatch.setattr(
        cv_service,
        "extract_text_from_file",
        lambda content, filename: (
            "Experienced Python developer with FastAPI and SQLAlchemy. "
            "Built production APIs and automated tests."
        ),
    )

    response = client.post(
        "/api/v1/candidate/upload-cv",
        headers=auth_headers,
        files={
            "file": (
                "resume.txt",
                b"fake CV content",
                "text/plain",
            )
        },
        data={"declared_role": "Python Developer"},
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["success"] is True
    assert payload["status"] == "analyzed"
    assert payload["detected_role"] == "Python Developer"

    app_id = payload["application_id"]

    from backend.database import CvDocument
    from backend.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        cv_doc = (
            db.query(CvDocument)
            .filter(CvDocument.application_id == app_id)
            .one()
        )

        assert isinstance(cv_doc.analysis_json, dict)
        assert cv_doc.analysis_json["score"] == 91
        assert cv_doc.analysis_json["detected_role"] == "Python Developer"
        assert cv_doc.analysis_json["skill_metrics"]["Python"] == 95
    finally:
        db.close()
