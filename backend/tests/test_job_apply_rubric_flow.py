"""P1 candidate job-apply rubric flow tests.

Covers the focused fixes to the self-apply pipeline:
  - the new application is linked to the job's rubric (modern Job.rubric_id,
    legacy Rubric.job_id fallback),
  - the previous application's analysis_json is NOT reused (fresh job-specific
    analysis is produced in the background),
  - the background analysis runs rubric-aware (extract_cv_details receives the
    rubric context), stores a recruiter-visible cv_score + rubric_match,
  - the application status becomes "screening" (job apply) / "analyzed"
    (CV-builder) after analysis, "analysis_failed" on AI error,
  - no AI interview session is auto-created on apply (resume returns
    can_resume False until the recruiter invites),
  - recruiter bulk-invite moves the app to "invited" (granting interview access).

The project's ``seeded_application`` fixture (test_candidate_features.py) is
broken pre-existing (EvaluationResult created without company_id) — these
fixtures set company_id explicitly.
"""

import json

import pytest

import backend.ai as backend_ai
from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    Rubric,
)
from backend.entity_writer import sync_cv_document
from backend.models.evaluation.profile import CandidateProfile

CRITERIA_JSON = json.dumps(
    {
        "categories": [
            {
                "name": "Backend",
                "subcategories": [
                    {
                        "name": "Core",
                        "skills": [
                            {"name": "Python", "level": "advanced"},
                            {"name": "FastAPI", "level": "intermediate"},
                        ],
                    }
                ],
            },
            {
                "name": "Databases",
                "subcategories": [
                    {
                        "name": "Storage",
                        "skills": [{"name": "PostgreSQL", "level": "intermediate"}],
                    }
                ],
            },
        ]
    }
)

CV_TEXT = (
    "Senior backend engineer with 6 years of Python and FastAPI experience. "
    "Designed and shipped PostgreSQL-backed services at scale for multiple teams."
)


@pytest.fixture
def rubric(db_session, test_company):
    r = Rubric(
        company_id=test_company.id,
        title="Backend Engineer Rubric",
        criteria_json=CRITERIA_JSON,
        is_active=1,
        version=1,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture
def job_with_rubric(db_session, test_recruiter, test_company, rubric):
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
        rubric_id=rubric.id,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


@pytest.fixture
def candidate_profile(db_session, test_user):
    """CandidateProfile mirror so profile_helpers returns name/phone.

    The conftest test_user has no CandidateProfile; the apply gate reads
    phone/name through profile_helpers (Profile-first).
    """
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

    Provides the "latest app with a final_score" required by the apply gate
    and carries the stale analysis_json that must NOT be reused on apply.
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


def test_apply_links_job_rubric(
    client, auth_headers, job_with_rubric, rubric, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]
    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app is not None
    assert app.rubric_id == rubric.id


def test_apply_does_not_reuse_old_analysis(
    client, auth_headers, job_with_rubric, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]
    app = db_session.query(Application).filter(Application.id == app_id).first()
    _cv = app.cv_document
    _a = getattr(_cv, "analysis_json", None) or app.analysis_json
    analysis = json.loads(_a) if isinstance(_a, str) else (_a or {})
    # Fresh rubric-aware analysis — NOT the prior app's match_score=82 payload.
    assert analysis.get("detected_role") == "Senior Backend Engineer"
    # P0: rubric-weighted deterministic score (75.0) replaces raw AI 84.
    assert analysis.get("score") == 75.0
    assert analysis.get("summary") != "Python backend profile"
    # Prior app's payload remains untouched.
    prior_app = db_session.query(Application).filter(
        Application.id == prior_analyzed_app.id
    ).first()
    prior_a = prior_app.cv_document.analysis_json
    if isinstance(prior_a, str):
        prior_a = json.loads(prior_a)
    assert prior_a.get("match_score") == 82


def test_apply_analysis_receives_rubric_context(
    client, auth_headers, job_with_rubric, rubric, prior_analyzed_app, monkeypatch
):
    captured = {}
    resp = _apply(
        client, auth_headers, job_with_rubric.id, monkeypatch, captured=captured
    )
    assert resp.status_code == 200
    # extract_cv_details was chosen (rubric-aware path) and got the context.
    assert captured.get("role") == "Senior Backend Engineer"
    ctx = captured.get("rubric_context") or ""
    assert "Python" in ctx and "FastAPI" in ctx and "PostgreSQL" in ctx


def test_apply_status_becomes_screening(
    client, auth_headers, job_with_rubric, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]
    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app.status == "screening"


def test_apply_ai_error_marks_analysis_failed(
    client, auth_headers, job_with_rubric, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(
        client, auth_headers, job_with_rubric.id, monkeypatch, ai_error="boom"
    )
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]
    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app.status == "analysis_failed"
    # The AI error payload is persisted via sync_cv_document into the
    # CvDocument.analysis_json (there is no analysis_error column).
    _a = app.cv_document.analysis_json
    analysis = json.loads(_a) if isinstance(_a, str) else (_a or {})
    assert analysis.get("error") == "boom"


def test_recruiter_sees_cv_score_and_rubric_match(
    client,
    auth_headers,
    recruiter_headers,
    job_with_rubric,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    detail = client.get(
        f"/api/v1/recruiter/applications/{app_id}", headers=recruiter_headers
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["id"] == app_id
    assert data["cv_score"] == 75.0
    analysis = data.get("analysis") or {}
    rm = analysis.get("rubric_match") or {}
    assert rm.get("rubric_id") == job_with_rubric.rubric_id
    assert rm.get("match_percentage") == 75
    assert rm.get("total_skills") == 3
    assert "Python" in [s.get("name") for s in rm.get("matched_skills", [])]


def test_apply_does_not_create_interview_session(
    client, auth_headers, job_with_rubric, prior_analyzed_app, db_session, monkeypatch
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    resume = client.post(
        "/api/v1/ai/interview/resume",
        headers=auth_headers,
        json={"application_id": app_id},
    )
    assert resume.status_code == 200
    body = resume.json()
    assert body["can_resume"] is False


def test_recruiter_invite_grants_interview_access(
    client,
    auth_headers,
    recruiter_headers,
    job_with_rubric,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    invite = client.post(
        "/api/v1/recruiter/applications/bulk-invite",
        headers=recruiter_headers,
        json={
            "application_ids": [app_id],
            "subject": "AI Interview Invitation",
            "email_template": "You are invited to a short AI interview.",
        },
    )
    assert invite.status_code == 200

    app = db_session.query(Application).filter(Application.id == app_id).first()
    assert app.status == "invited"
