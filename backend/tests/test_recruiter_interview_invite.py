"""Recruiter-controlled AI interview invitation flow tests.

Covers the recruiter-controlled interview invite pipeline for self-applied
candidates (no campaign):

  - apply creates an application but NOT an interview session (resume False),
  - candidates cannot start the interview before the recruiter invites them,
  - single invite (POST /recruiter/applications/{app_id}/invite-interview)
    moves the app to "invited" and grants access,
  - candidates can start/resume once invited,
  - bulk invite (POST /recruiter/applications/invite-interviews) invites
    multiple selected applications,
  - qualified invite (POST /recruiter/jobs/{job_id}/invite-qualified) invites
    only applications whose CV score meets the threshold,
  - rejected candidates cannot start the interview,
  - a different candidate cannot access another candidate's application,
  - a recruiter from another company cannot invite/see the application.

Reuses the conftest client/auth fixtures; fixtures set company_id explicitly
(the pre-existing broken `seeded_application` pattern is avoided).
"""

import pytest

import backend.ai as backend_ai
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
)
from backend.entity_writer import sync_cv_document
from backend.models.evaluation.profile import CandidateProfile

CV_TEXT = (
    "Senior backend engineer with 6 years of Python and FastAPI experience. "
    "Designed and shipped PostgreSQL-backed services at scale for multiple teams."
)


@pytest.fixture
def job(db_session, test_recruiter, test_company):
    job = Job(
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        title="Senior Backend Engineer",
        company_name="Test Company",
        location="Tunis",
        salary_range="4000-6000 TND",
        type="Full-time",
        description="Backend API role using Python/FastAPI/PostgreSQL",
        required_skills="Python,FastAPI,PostgreSQL",
        is_active=True,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def candidate_profile(db_session, test_user):
    profile = CandidateProfile(
        user_id=test_user.id,
        name=test_user.name,
        phone=test_user.phone,
        email=test_user.email,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


@pytest.fixture
def prior_analyzed_app(db_session, test_user, test_company, candidate_profile):
    """An already-analyzed CV-builder application for the candidate.

    Satisfies the apply gate (latest app with a final_score) so the apply
    endpoint accepts the new job application.
    """
    app = Application(
        user_id=test_user.id,
        company_id=test_company.id,
        full_name=test_user.name,
        email=test_user.email,
        phone=test_user.phone,
        status="analyzed",
        cv_text_anonymized=CV_TEXT,
    )
    db_session.add(app)
    db_session.flush()
    sync_cv_document(
        db_session,
        app,
        declared_role="Python Developer",
        cv_text_anonymized=CV_TEXT,
        analysis_json={
            "match_score": 82,
            "detected_role": "Python Developer",
            "skills": ["python"],
            "builder_data": {"summary": "Python backend profile"},
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


def _apply(
    client, auth_headers, job_id, monkeypatch, captured=None, ai_error=None
):
    """POST apply with deterministic, mocked AI extraction."""

    async def fake_extract_cv_details(text, role, rubric_context):
        if captured is not None:
            captured["text"] = text
            captured["role"] = role
            captured["rubric_context"] = rubric_context
        if ai_error:
            return {"error": ai_error, "score": None}
        return {
            "score": 84,
            "detected_role": "Senior Backend Engineer",
            "skills": ["python", "fastapi", "postgresql"],
            "verdict": "qualified",
            "summary": "Rubric-aware extraction for Senior Backend Engineer",
        }

    async def fake_analyze_cv(text, role):
        return {
            "score": 60,
            "detected_role": "Backend Developer",
            "skills": ["python"],
            "verdict": "qualified",
            "summary": "Generic CV analysis",
        }

    monkeypatch.setattr(backend_ai, "extract_cv_details", fake_extract_cv_details)
    monkeypatch.setattr(backend_ai, "analyze_cv", fake_analyze_cv)

    return client.post(f"/api/v1/candidate/jobs/{job_id}/apply", headers=auth_headers)


def _seed_app_with_score(
    db_session, user, company, job, score, status="screening"
):
    """Seed an application directly with a CV score (for qualified/denial tests)."""
    app = Application(
        user_id=user.id,
        company_id=company.id,
        job_id=job.id,
        full_name=user.name,
        email=user.email,
        phone=user.phone,
        status=status,
        cv_text_anonymized=CV_TEXT,
    )
    db_session.add(app)
    db_session.flush()
    sync_cv_document(
        db_session,
        app,
        declared_role="Senior Backend Engineer",
        cv_text_anonymized=CV_TEXT,
        analysis_json={"score": score, "detected_role": "Senior Backend Engineer"},
    )
    es = EvaluationSession(
        application_id=app.id, company_id=company.id, status="completed"
    )
    db_session.add(es)
    db_session.flush()
    er = EvaluationResult(
        evaluation_session_id=es.id,
        company_id=company.id,
        scoring_status="SCORED",
        final_score=float(score),
        cv_score=float(score),
    )
    db_session.add(er)
    db_session.commit()
    db_session.refresh(app)
    return app


def test_apply_does_not_create_interview_session(
    client, auth_headers, job, candidate_profile, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    resume = client.post(
        "/api/v1/ai/interview/resume",
        headers=auth_headers,
        json={"application_id": app_id},
    )
    assert resume.status_code == 200
    assert resume.json()["can_resume"] is False

    app = db_session.query(Application).filter(Application.id == app_id).first()
    sessions = (
        db_session.query(EvaluationSession)
        .filter(EvaluationSession.application_id == app_id)
        .all()
    )
    # The CV-scoring EvaluationSession exists but no in-progress interview state.
    assert any(s.status == "completed" for s in sessions)


def test_pre_invite_resume_is_denied(
    client, auth_headers, job, candidate_profile, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    resume = client.post(
        "/api/v1/ai/interview/resume",
        headers=auth_headers,
        json={"application_id": app_id},
    )
    body = resume.json()
    assert body["can_resume"] is False


def test_single_invite_sets_status_invited(
    client, auth_headers, recruiter_headers, job, candidate_profile, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    invite = client.post(
        f"/api/v1/recruiter/applications/{app_id}/invite-interview",
        headers=recruiter_headers,
    )
    assert invite.status_code == 200
    body = invite.json()
    assert body["success"] is True
    assert body["application_id"] == app_id
    assert "access_url" in body
    assert "/auth/interview-access" in body["access_url"]

    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app.status == "invited"
    assert app.invited_at is not None


def test_post_invite_candidate_can_start(
    client, auth_headers, recruiter_headers, job, candidate_profile, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    client.post(
        f"/api/v1/recruiter/applications/{app_id}/invite-interview",
        headers=recruiter_headers,
    )

    app = db_session.query(Application).filter(Application.id == app_id).first()
    es = db_session.query(EvaluationSession).filter(
        EvaluationSession.application_id == app_id
    ).order_by(EvaluationSession.id.desc()).first()
    es.interview_state = "in_progress"
    db_session.commit()

    resume = client.post(
        "/api/v1/ai/interview/resume",
        headers=auth_headers,
        json={"application_id": app_id},
    )
    assert resume.status_code == 200
    assert resume.json()["can_resume"] is True


def test_bulk_invite_multiple_applications(
    client,
    auth_headers,
    recruiter_headers,
    test_user,
    test_recruiter,
    test_company,
    job,
    candidate_profile,
    db_session,
):
    import backend.database as _db_mod

    first = _seed_app_with_score(db_session, test_user, test_company, job, 80)
    second_user = _db_mod.User(
        email="bulk.second@example.com",
        name="Second Candidate",
        hashed_password="$2b$12$abcdefghijklmnopqrstuv",  # inert placeholder
        role="candidate",
        email_verified=True,
    )
    db_session.add(second_user)
    db_session.flush()
    second = _seed_app_with_score(db_session, second_user, test_company, job, 76)

    invite = client.post(
        "/api/v1/recruiter/applications/invite-interviews",
        headers=recruiter_headers,
        json={"application_ids": [first.id, second.id]},
    )
    assert invite.status_code == 200
    body = invite.json()
    assert body["invited"] and len(body["invited"]) >= 2

    app1 = db_session.query(Application).filter(Application.id == first.id).first()
    app2 = db_session.query(Application).filter(Application.id == second.id).first()
    assert app1.status == "invited"
    assert app2.status == "invited"


def test_invite_qualified_only_meets_threshold(
    client,
    auth_headers,
    recruiter_headers,
    test_user,
    test_recruiter,
    test_company,
    job,
    candidate_profile,
    db_session,
):
    strong = _seed_app_with_score(db_session, test_user, test_company, job, 85)
    # Weak app belongs to another candidate (same job) to prove thresholding.
    import backend.database as _db_mod

    other_user = _db_mod.User(
        email="weak.candidate@example.com",
        name="Weak Candidate",
        hashed_password="$2b$12$abcdefghijklmnopqrstuv",  # inert placeholder
        role="candidate",
        email_verified=True,
    )
    db_session.add(other_user)
    db_session.flush()
    weak = _seed_app_with_score(db_session, other_user, test_company, job, 50)

    invite = client.post(
        f"/api/v1/recruiter/jobs/{job.id}/invite-qualified",
        headers=recruiter_headers,
        json={"threshold": 70},
    )
    assert invite.status_code == 200
    body = invite.json()
    assert body["threshold"] == 70
    invited_ids = [i["application_id"] for i in body["invited"]]
    assert strong.id in invited_ids
    assert weak.id not in invited_ids

    db_app = db_session.query(Application).filter(Application.id == strong.id).first()
    assert db_app.status == "invited"
    weak_db = db_session.query(Application).filter(Application.id == weak.id).first()
    assert weak_db.status == "screening"


def test_rejected_candidate_cannot_start(
    client,
    auth_headers,
    recruiter_headers,
    test_user,
    test_company,
    job,
    candidate_profile,
    db_session,
):
    app = _seed_app_with_score(db_session, test_user, test_company, job, 80)
    app.status = "rejected"
    db_session.commit()

    resume = client.post(
        "/api/v1/ai/interview/resume",
        headers=auth_headers,
        json={"application_id": app.id},
    )
    assert resume.status_code == 200
    assert resume.json()["can_resume"] is False


def test_cross_account_denial(
    client,
    auth_headers,
    test_user,
    test_company,
    job,
    candidate_profile,
    db_session,
):
    app = _seed_app_with_score(db_session, test_user, test_company, job, 80)
    app.interview_state = "in_progress"
    db_session.commit()

    # Another candidate cannot access this application.
    import backend.database as _db_mod

    intruder = _db_mod.User(
        email="intruder@example.com",
        name="Intruder",
        hashed_password="$2b$12$abcdefghijklmnopqrstuv",
        role="candidate",
        email_verified=True,
    )
    db_session.add(intruder)
    db_session.flush()

    csrf_token = _fetch_csrf_token(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.com", "password": "wrongpass"},
        headers={"X-CSRF-Token": csrf_token},
    )
    # Cannot even log in with the wrong password; but we still verify the
    # application detail endpoint rejects a cross-account candidate via a
    # directly-issued token would be out of scope — instead assert the
    # application is not visible to the current (owner) user's sibling view.
    assert login.status_code == 401

    # The owner's own resume is fine; the cross-account guard is enforced at
    # the candidate app-detail endpoint (404/403) rather than resume (which
    # requires ownership). Simulate the intruder resolving the app directly.
    from backend.routers.ai_interview.session import _resolve_app_for_candidate

    resolved = _resolve_app_for_candidate(db_session, intruder, app.id)
    assert resolved is None


def _fetch_csrf_token(client):
    import hashlib
    import hmac
    import secrets
    import time

    from backend.dependencies import SECRET_KEY

    resp = client.get("/login")
    token = resp.headers.get("X-CSRF-Token") or resp.cookies.get("csrf_token")
    if token:
        return token
    session_id = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + 86400
    message = f"{session_id}:{expires_at}"
    token_hash = hmac.new(
        SECRET_KEY.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{session_id}:{expires_at}:{token_hash}"


def test_cross_company_recruiter_denial(
    client,
    auth_headers,
    recruiter_headers,
    recruiter_headers_b,
    test_user,
    test_company,
    job,
    candidate_profile,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    resp = _apply(client, auth_headers, job.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    # Recruiter from another company cannot invite the application.
    invite = client.post(
        f"/api/v1/recruiter/applications/{app_id}/invite-interview",
        headers=recruiter_headers_b,
    )
    assert invite.status_code == 404

    # Application status remains unchanged (not invited).
    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app.status == "screening"

