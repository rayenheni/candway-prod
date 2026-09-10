"""
Phase 4: Rubric breakdown in scores API + recruiter UI
"""

import pytest

from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
    Job,
    RubricScoringDetail,
    User,
)
from backend.database import (
    Rubric as RubricDB,
)
from backend.rubric.rubric_schema import (
    CategoryDefinition,
    JobRubric,
    LevelDescriptor,
    SkillDefinition,
    SubcategoryDefinition,
)


def _make_rubric(job_id: int) -> JobRubric:
    return JobRubric(
        job_id=job_id,
        version=2,
        seniority="mid",
        categories=[
            CategoryDefinition(
                name="Technical",
                weight=1.0,
                subcategories=[
                    SubcategoryDefinition(
                        name="Backend",
                        weight=1.0,
                        skills=[
                            SkillDefinition(
                                name="Python",
                                weight=1.0,
                                is_required=True,
                                levels={
                                    "junior": [],
                                    "mid": [
                                        LevelDescriptor(
                                            score_threshold=100,
                                            description="Builds production APIs",
                                            keywords=["python", "api"],
                                        )
                                    ],
                                    "senior": [],
                                },
                            )
                        ],
                    )
                ],
            )
        ],
    )


def _seed_rubric_summary(db_session, evaluation_result):
    """Populate the rubric breakdown on EvaluationResult.score_breakdown.

    In the current schema the rubric "summary" (category/skill/gap breakdown)
    is the EvaluationResult.score_breakdown JSON column — the single source of
    truth written by ScoringService.set_evaluation_result. RubricScoringDetail
    rows hold per-criterion evidence only, keyed by evaluation_result_id.
    """
    evaluation_result.score_breakdown = {
        "category_scores": [
            {
                "name": "Technical",
                "score": 72,
                "weight": 1.0,
                "confidence_range": [60, 85],
                "coverage_pct": 50,
                "skills_scored": 1,
                "skills_total": 2,
                "children": [
                    {
                        "name": "Backend",
                        "score": 72,
                        "weight": 1.0,
                        "confidence_range": [60, 85],
                        "coverage_pct": 100,
                        "skills_scored": 1,
                        "skills_total": 1,
                        "children": None,
                    }
                ],
            }
        ],
        "skill_scores": {
            "python": {
                "skill_name": "python",
                "final_score": 72,
                "is_required": True,
                "category": "Technical",
                "confidence_lower": 60,
                "confidence_upper": 85,
                "explanation": "Demonstrated solid Python skills",
            }
        },
        "gaps": [
            {
                "category": "Technical",
                "score": 30,
                "expected": 55,
                "gap_pct": 45,
                "severity": "critical",
            }
        ],
    }
    db_session.flush()
    return evaluation_result


def _seed_scoring_results(db_session, evaluation_result):
    r1 = RubricScoringDetail(
        evaluation_result_id=evaluation_result.id,
        criterion_name="Python",
        criterion_key="python",
        score=70.0,
        weight=1.0,
        feedback="Candidate demonstrated basic Python but missing async patterns.",
        source="interview",
    )
    db_session.add(r1)
    db_session.flush()


@pytest.mark.usefixtures("db_session")
class TestPhase4RubricUI:
    """Phase 4: Rubric breakdown in scores API response."""

    def test_scores_api_returns_category_breakdown(
        self, db_session, client, recruiter_headers
    , test_company):
        """API returns category_breakdown when InterviewRubricSummary exists."""
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Backend Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            job_id=job.id,
            company_id=job.company_id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            declared_role="Backend Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="rubric",
            rubric_version=2,
            rubric_score=72.0,
            rubric_coverage_pct=50.0,
            cv_score=65.0,
            final_score=70.0,
        )
        db_session.add(_er)
        db_session.flush()

        _seed_rubric_summary(db_session, _er)
        _seed_scoring_results(db_session, _er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["rubric_available"] is True
        assert len(data["category_breakdown"]) == 1
        assert data["category_breakdown"][0]["name"] == "Technical"
        assert data["category_breakdown"][0]["score"] == 72
        assert data["rubric_score"] == 72.0
        assert data["rubric_coverage_pct"] == 50.0
        assert data["scoring_model"] == "rubric"
        assert data["rubric_version"] == 2

    def test_scores_api_returns_empty_arrays_when_no_rubric_summary(
        self, db_session, client, recruiter_headers
    , test_company):
        """API returns empty arrays (not null) when no rubric summary exists."""
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["rubric_available"] is False
        assert data["category_breakdown"] == []
        assert data["skill_breakdown"] == []
        assert data["gaps"] == []
        assert data["evidence"] == []
        assert data["rubric_score"] is None

    def test_scores_api_returns_skill_breakdown(
        self, db_session, client, recruiter_headers
    , test_company):
        """API returns skill_breakdown when rubric summary has skill_scores."""
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            job_id=job.id,
            company_id=job.company_id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="rubric",
            rubric_version=2,
            rubric_score=72.0,
            final_score=70.0,
        )
        db_session.add(_er)
        db_session.flush()

        _seed_rubric_summary(db_session, _er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert len(data["skill_breakdown"]) == 1
        sk = data["skill_breakdown"][0]
        assert sk["name"] == "python"
        assert sk["score"] == 72
        assert sk["assessed"] is True

    def test_scores_api_returns_gaps(self, db_session, client, recruiter_headers, test_company):
        """API returns gaps from InterviewRubricSummary."""
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            job_id=job.id,
            company_id=job.company_id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="rubric",
            final_score=70.0,
        )
        db_session.add(_er)
        db_session.flush()

        _seed_rubric_summary(db_session, _er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert len(data["gaps"]) == 1
        gap = data["gaps"][0]
        assert gap["category"] == "Technical"
        assert gap["severity"] == "critical"
        assert gap["gap_pct"] == 45

    def test_scores_api_returns_evidence(self, db_session, client, recruiter_headers, test_company):
        """API returns evidence from RubricScoringResult rows."""
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        rubric = _make_rubric(job.id)
        db_rubric = RubricDB(
            job_id=job.id,
            company_id=job.company_id,
            version=rubric.version,
            is_active=1,
            criteria_json=rubric.model_dump_json(),
            created_by=recruiter.id,
        )
        db_session.add(db_rubric)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="rubric",
            final_score=70.0,
        )
        db_session.add(_er)
        db_session.flush()

        _seed_rubric_summary(db_session, _er)
        _seed_scoring_results(db_session, _er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert len(data["evidence"]) == 1
        ev = data["evidence"][0]
        assert ev["skill_name"] == "Python"
        assert ev["turn_number"] == 1
        assert ev["matched_keywords"] == []
        assert ev["missing_competencies"] == []
        assert (
            ev["explanation"]
            == "Candidate demonstrated basic Python but missing async patterns."
        )
        assert ev["final_score"] == 70

    def test_scores_api_legacy_backward_compat(
        self, db_session, client, recruiter_headers
    , test_company):
        """Existing fields remain unchanged when rubric fields are added."""
        recruiter = db_session.query(User).filter_by(role="recruiter").first()
        job = Job(recruiter_id=recruiter.id, company_id=test_company.id, title="Engineer")
        db_session.add(job)
        db_session.flush()

        app = Application(
            user_id=recruiter.id,
            job_id=job.id,
            company_id=job.company_id,
            declared_role="Engineer",
            assigned_to=recruiter.id,
        )
        db_session.add(app)
        db_session.flush()

        _es = EvaluationSession(application_id=app.id, status="completed")
        db_session.add(_es)
        db_session.flush()
        _er = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            scoring_model="legacy",
            final_score=65.0,
            cv_score=60.0,
        )
        db_session.add(_er)
        db_session.commit()

        resp = client.get(
            f"/api/v1/recruiter/applications/{app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Legacy fields are preserved
        assert data["application_id"] == app.id
        assert data["overall_score"] == 65.0
        assert data["cv_score"] == 60.0
        assert data["scores"]["interview"] == 65.0
        assert data["scores"]["cv"] == 60.0
        # New fields are present; rubric_available reflects "has a result row"
        assert data["rubric_available"] is True
        assert data["category_breakdown"] == []
        assert data["rubric_score"] is None
