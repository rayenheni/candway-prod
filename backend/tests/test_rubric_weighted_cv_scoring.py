"""P0 deterministic rubric-weighted CV scoring tests.

Covers the deterministic rubric-weighted CV scorer (no AI per-skill scoring):
  - weight normalization (sum == 1),
  - weighted score matches the formula sum(skill_score * normalized_weight),
  - missing skills score 0 and land in missing_skills,
  - nested AND flat criteria_json shapes both parse,
  - RubricScoringDetail rows with source="cv" are created on apply,
  - run_cv_analysis uses the rubric-weighted cv_score when a rubric exists,
  - the no-rubric path is unchanged (generic AI score, no rubric flags).
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
    RubricScoringDetail,
)
from backend.entity_writer import sync_cv_document
from backend.models.evaluation.profile import CandidateProfile
from backend.services.rubric_match_service import (
    _normalize_weights,
    compute_rubric_weighted_cv_score,
)

NESTED_CRITERIA_JSON = json.dumps(
    {
        "categories": [
            {
                "name": "Backend",
                "subcategories": [
                    {
                        "name": "Core",
                        "skills": [
                            {"name": "Python", "weight": 2, "level": "advanced"},
                            {"name": "FastAPI", "weight": 1, "level": "intermediate"},
                        ],
                    }
                ],
            },
            {
                "name": "Databases",
                "subcategories": [
                    {
                        "name": "Storage",
                        "skills": [
                            {"name": "PostgreSQL", "weight": 1, "level": "intermediate"}
                        ],
                    }
                ],
            },
        ]
    }
)

FLAT_CRITERIA_JSON = json.dumps(
    {
        "categories": [
            {
                "name": "Frontend",
                "skills": [
                    {"name": "React", "weight": 3},
                    {"name": "TypeScript", "weight": 2},
                ],
            }
        ]
    }
)


class _FakeRubric:
    def __init__(self, criteria_json):
        self.criteria_json = criteria_json


# ─────────────────────────── unit tests ───────────────────────────


def test_weights_normalized_to_one():
    skills = _normalize_weights(
        [
            {"name": "a", "weight": 2.0},
            {"name": "b", "weight": 1.0},
            {"name": "c", "weight": 1.0},
        ]
    )
    assert round(sum(s["normalized_weight"] for s in skills), 6) == 1.0
    assert skills[0]["normalized_weight"] == pytest.approx(0.5)
    assert skills[1]["normalized_weight"] == pytest.approx(0.25)
    assert skills[2]["normalized_weight"] == pytest.approx(0.25)


def test_weighted_score_matches_formula():
    # A: demonstrated (75, weight 2), B: direct (50, weight 1), C: missing (0, weight 1)
    # cv_score = 75*0.5 + 50*0.25 + 0*0.25 = 50.0
    cv_text = (
            "Built production A systems for over 3 years of strong hands-on experience. "
            + "filler filler filler filler filler filler filler filler filler filler "
            + "filler filler filler filler filler filler filler filler filler filler. "
            + "B appears plainly. "
            + "filler filler filler filler filler filler filler filler filler filler "
            + "filler filler filler filler filler filler filler filler filler filler."
        )
    rubric = _FakeRubric(
        {
            "categories": [
                {
                    "name": "Tech",
                    "skills": [
                        {"name": "A", "weight": 2},
                        {"name": "B", "weight": 1},
                        {"name": "C", "weight": 1},
                    ],
                }
            ]
        }
    )
    result = compute_rubric_weighted_cv_score(cv_text, rubric)
    assert result is not None
    assert result["cv_score"] == pytest.approx(50.0)
    assert result["scoring_method"] == "deterministic_keyword_weighted"
    assert result["skill_scores"]["A"]["score"] == 75.0
    assert result["skill_scores"]["B"]["score"] == 50.0
    assert result["skill_scores"]["C"]["score"] == 0.0


def test_missing_skills_zero_and_listed():
    rubric = _FakeRubric(
        {
            "categories": [
                {
                    "name": "Tech",
                    "skills": [
                        {"name": "Python", "weight": 1},
                        {"name": "Kubernetes", "weight": 1},
                    ],
                }
            ]
        }
    )
    result = compute_rubric_weighted_cv_score("Python and FastAPI experience.", rubric)
    assert result["missing_skills"] == ["Kubernetes"]
    assert result["skill_scores"]["Kubernetes"]["score"] == 0.0
    assert result["coverage_pct"] == 50.0


def test_nested_criteria_parsed_with_weights():
    rubric = _FakeRubric(NESTED_CRITERIA_JSON)
    result = compute_rubric_weighted_cv_score(
        "6 years of Python and FastAPI experience. "
        "Shipped PostgreSQL-backed services at scale.",
        rubric,
    )
    assert result is not None
    assert set(result["skill_scores"].keys()) == {"Python", "FastAPI", "PostgreSQL"}
    # weights preserved from nested criteria_json: Python 2 / FastAPI 1 / PostgreSQL 1
    assert result["skill_scores"]["Python"]["weight"] == 2.0
    assert result["normalized_weights"]["Python"] == pytest.approx(0.5)


def test_flat_criteria_parsed():
    rubric = _FakeRubric(FLAT_CRITERIA_JSON)
    result = compute_rubric_weighted_cv_score(
        "Built React dashboards with TypeScript for 3 years.",
        rubric,
    )
    assert result is not None
    assert set(result["skill_scores"].keys()) == {"React", "TypeScript"}
    assert result["skill_scores"]["React"]["score"] == 75.0
    assert result["normalized_weights"]["React"] == pytest.approx(0.6)


def test_empty_rubric_returns_none():
    rubric = _FakeRubric(json.dumps({"categories": []}))
    assert compute_rubric_weighted_cv_score("anything", rubric) is None


def test_extracted_skills_boost_weak_evidence():
    # Skill only present via AI-extracted skills (not in CV text) -> weak 25.
    rubric = _FakeRubric(
        {
            "categories": [
                {
                    "name": "Tech",
                    "skills": [{"name": "Docker", "weight": 1}],
                }
            ]
        }
    )
    result = compute_rubric_weighted_cv_score(
        "Backend developer", rubric, extracted_skills=["docker", "python"]
    )
    assert result["skill_scores"]["Docker"]["score"] == 25.0
    assert result["missing_skills"] == []


# ─────────────────────────── integration tests ───────────────────────────


@pytest.fixture
def rubric(db_session, test_company):
    r = Rubric(
        company_id=test_company.id,
        title="Backend Engineer Rubric",
        criteria_json=NESTED_CRITERIA_JSON,
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
def job_no_rubric(db_session, test_recruiter, test_company):
    job = Job(
        recruiter_id=test_recruiter.id,
        company_id=test_company.id,
        title="General Developer",
        company_name="Test Company",
        location="Tunis",
        type="Full-time",
        description="General role",
        required_skills="Git",
        is_active=True,
        rubric_id=None,
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


CV_TEXT = (
    "Senior backend engineer with 6 years of Python and FastAPI experience. "
    "Designed and shipped PostgreSQL-backed services at scale for multiple teams."
)


def _apply(client, auth_headers, job_id, monkeypatch, captured=None):
    async def fake_extract_cv_details(text, role, rubric_context):
        if captured is not None:
            captured["text"] = text
            captured["role"] = role
            captured["rubric_context"] = rubric_context
        return {
            "score": 84,
            "detected_role": "Senior Backend Engineer",
            "skills": ["python", "fastapi", "postgresql"],
            "verdict": "qualified",
            "summary": "Rubric-aware extraction",
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


def _analysis(app):
    _cv = app.cv_document
    _a = getattr(_cv, "analysis_json", None) or app.analysis_json
    return json.loads(_a) if isinstance(_a, str) else (_a or {})


def test_run_cv_analysis_uses_weighted_score(
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
    app = db_session.query(Application).filter(Application.id == app_id).first()

    analysis = _analysis(app)
    # Deterministic weighted cv_score replaces the raw AI 84.
    assert analysis.get("cv_rubric_weighted") is True
    assert analysis.get("scoring_method") == "deterministic_keyword_weighted"
    assert analysis["score"] == 75.0
    assert analysis["coverage_pct"] == 100.0
    assert analysis["missing_skills"] == []
    assert set(analysis["skill_scores"].keys()) == {
        "Python",
        "FastAPI",
        "PostgreSQL",
    }

    detail = client.get(
        f"/api/v1/recruiter/applications/{app_id}", headers=recruiter_headers
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["cv_score"] == 75.0
    rm = (data.get("analysis") or {}).get("rubric_match") or {}
    assert rm.get("match_percentage") == 75


def test_rubric_scoring_detail_rows_created(
    client,
    auth_headers,
    job_with_rubric,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    rows = (
        db_session.query(RubricScoringDetail)
        .join(
            EvaluationResult,
            RubricScoringDetail.evaluation_result_id == EvaluationResult.id,
        )
        .join(
            EvaluationSession,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(EvaluationSession.application_id == app_id)
        .filter(RubricScoringDetail.source == "cv")
        .all()
    )
    assert len(rows) == 3
    by_name = {r.criterion_name: r for r in rows}
    assert "Python" in by_name and "FastAPI" in by_name and "PostgreSQL" in by_name
    assert all(r.source == "cv" for r in rows)
    assert all(r.score == 75.0 for r in rows)
    assert all(r.weight is not None for r in rows)


def test_no_rubric_path_unchanged(
    client,
    auth_headers,
    job_no_rubric,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    resp = _apply(client, auth_headers, job_no_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]
    app = db_session.query(Application).filter(Application.id == app_id).first()

    analysis = _analysis(app)
    # Generic AI path: score is the AI's 60, no rubric flags, no scoring_method.
    assert analysis.get("score") == 60
    assert analysis.get("cv_rubric_weighted") is None
    assert analysis.get("rubric_match") is None

    # Canonical score persisted with the generic AI score (no weighted override).
    er = (
        db_session.query(EvaluationResult)
        .join(
            EvaluationSession,
            EvaluationResult.evaluation_session_id == EvaluationSession.id,
        )
        .filter(EvaluationSession.application_id == app_id)
        .first()
    )
    assert er is not None
    assert er.cv_score == 60.0
    breakdown = er.score_breakdown or {}
    assert breakdown.get("cv_rubric_weighted") is None
    assert breakdown.get("scoring_method") is None


def test_scores_endpoint_exposes_cv_breakdown(
    client,
    auth_headers,
    recruiter_headers,
    job_with_rubric,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    """P1: GET /recruiter/applications/{id}/scores surfaces the rubric-weighted
    CV breakdown (cv_rubric_weighted, cv_scoring_method, cv_coverage_pct,
    cv_skill_breakdown, cv_evidence, cv_missing_skills)."""
    resp = _apply(client, auth_headers, job_with_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    scores = client.get(
        f"/api/v1/recruiter/applications/{app_id}/scores", headers=recruiter_headers
    )
    assert scores.status_code == 200
    data = scores.json()

    assert data["cv_score"] == 75.0
    assert data["cv_rubric_weighted"] is True
    assert data["cv_scoring_method"] == "deterministic_keyword_weighted"
    assert data["cv_coverage_pct"] == 100.0
    assert data["cv_missing_skills"] == []

    skills = data["cv_skill_breakdown"]
    assert len(skills) == 3
    by_name = {s["name"]: s for s in skills}
    assert set(by_name.keys()) == {"Python", "FastAPI", "PostgreSQL"}
    assert all(s["score"] == 75.0 for s in skills)
    assert all(s["normalized_weight"] is not None for s in skills)
    assert all(s["feedback"] for s in skills)

    assert len(data["cv_evidence"]) == 3
    assert all(e["skill_name"] in by_name for e in data["cv_evidence"])
    assert all(e["feedback"] for e in data["cv_evidence"])


def test_scores_endpoint_generic_fallback_flags(
    client,
    auth_headers,
    recruiter_headers,
    job_no_rubric,
    prior_analyzed_app,
    db_session,
    monkeypatch,
):
    """P1: no-rubric apps report cv_rubric_weighted as None (no rubric attached)
    and an empty breakdown instead of fabricated per-skill data."""
    resp = _apply(client, auth_headers, job_no_rubric.id, monkeypatch)
    assert resp.status_code == 200
    app_id = resp.json()["application_id"]

    scores = client.get(
        f"/api/v1/recruiter/applications/{app_id}/scores", headers=recruiter_headers
    )
    assert scores.status_code == 200
    data = scores.json()

    assert data["cv_rubric_weighted"] is None
    assert data["cv_skill_breakdown"] == []
    assert data["cv_evidence"] == []
    assert data["cv_missing_skills"] == []
