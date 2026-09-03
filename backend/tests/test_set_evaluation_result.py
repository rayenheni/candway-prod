"""
Tests for ScoringService.set_evaluation_result — the AI interview final
evaluation persistence path.

Regression for: ``run_background_final_evaluation`` called a non-existent
``ScoringService.set_evaluation_result`` which raised AttributeError and
marked the evaluation ``failed`` instead of persisting the result.
"""

import pytest

from backend.database import (
    Application,
    EvaluationResult,
    EvaluationSession,
)
from backend.scoring_service import ScoringService


@pytest.fixture
def test_company(db_session):
    from backend.database import Company

    c = Company(name="Test Corp", slug="test-corp")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def test_app(db_session, test_user, test_company):
    app = Application(
        user_id=test_user.id,
        company_id=test_company.id,
        declared_role="Python Developer",
        full_name=test_user.name,
        email=test_user.email,
        status="analyzed",
        language="English",
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)
    return app


@pytest.fixture
def eval_session(db_session, test_app):
    es = EvaluationSession(
        application_id=test_app.id,
        company_id=test_app.company_id,
        status="pending",
        interview_state="completed",
    )
    db_session.add(es)
    db_session.commit()
    db_session.refresh(es)
    return es


class TestSetEvaluationResult:
    def test_rubric_aggregation_path_persists(self, db_session, test_app, eval_session):
        """Rubric-aggregation results (score + breakdown) are persisted."""
        result = ScoringService.set_evaluation_result(
            app=test_app,
            db=db_session,
            eval_score=78.5,
            skill_metrics={"Technical": 80, "Communication": 70},
            scored_by="ai",
            cv_score=65.0,
            rubric_score=82.0,
            rubric_coverage_pct=67,
            rubric_version=3,
            score_breakdown={
                "overall_score": 82.0,
                "categories": [
                    {"name": "Backend", "score": 85, "weight": 50, "children": []}
                ],
                "skill_scores": {"python": {"final_score": 85}},
                "gaps": [],
                "overall_coverage_pct": 67,
            },
            raw_analysis={"final_score": 78.5, "skill_metrics": {}},
            verdict="Recommended",
        )

        assert result.id is not None
        assert result.id is not None
        # Canonical formula: 65*0.25 + 82*0.50 + 67*0.25 = 16.25 + 41.0 + 16.75 = 74.0
        assert result.final_score == 74.0
        assert result.scoring_status == "SCORED"
        assert result.cv_score == 65.0
        assert result.rubric_score == 82.0
        assert result.rubric_coverage_pct == 67.0
        assert result.rubric_version == 3
        assert result.verdict == "Recommended"
        assert result.computed_by == "ai"

        # score_breakdown: categories normalized to category_scores for endpoints
        breakdown = result.score_breakdown or {}
        assert "categories" not in breakdown
        assert breakdown["category_scores"][0]["name"] == "Backend"
        assert breakdown["final_score"] == 74.0
        assert breakdown["skill_metrics"] == {
            "Technical": 80,
            "Communication": 70,
        }
        assert breakdown["raw_analysis"]["final_score"] == 78.5

        db_session.refresh(test_app)
        assert ScoringService.get_canonical_score(test_app.id, db_session) is not None

    def test_llm_fallback_path_persists(self, db_session, test_app, eval_session):
        """LLM-fallback results (no rubric) are persisted as cv_only."""
        result = ScoringService.set_evaluation_result(
            app=test_app,
            db=db_session,
            eval_score=64.2,
            skill_metrics={"Technical": 70},
            scored_by="ai",
        )

        assert result.id is not None
        assert result.scoring_status == "SCORED"
        assert result.rubric_score == 64.2
        breakdown = result.score_breakdown or {}

    def test_idempotent_upsert(self, db_session, test_app, eval_session):
        """Calling twice updates the same row (no duplicate)."""
        ScoringService.set_evaluation_result(app=test_app, db=db_session, eval_score=70.0)
        ScoringService.set_evaluation_result(app=test_app, db=db_session, eval_score=90.0)

        rows = (
            db_session.query(EvaluationResult)
            .filter(EvaluationResult.evaluation_session_id == eval_session.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].rubric_score == 90.0

    def test_creates_session_when_missing(self, db_session, test_app):
        """set_evaluation_result ensures an EvaluationSession exists."""
        result = ScoringService.set_evaluation_result(
            app=test_app, db=db_session, eval_score=75.0
        )
        session = (
            db_session.query(EvaluationSession)
            .filter(EvaluationSession.application_id == test_app.id)
            .first()
        )
        assert session is not None
        assert result.evaluation_session_id == session.id
        assert result.company_id == test_app.company_id

    def test_rejects_fraud_failed_state(self, db_session, test_app, eval_session):
        """scoring_status == FAILED must not be silently re-scored."""
        ScoringService.set_evaluation_result(app=test_app, db=db_session, eval_score=80.0)
        es = (
            db_session.query(EvaluationResult)
            .filter(EvaluationResult.evaluation_session_id == eval_session.id)
            .first()
        )
        es.scoring_status = "FAILED"
        es.final_score = None
        db_session.add(es)
        db_session.commit()

        with pytest.raises(ValueError, match="scoring_status is FAILED"):
            ScoringService.set_evaluation_result(
                app=test_app, db=db_session, eval_score=90.0
            )

    def test_score_clamped_to_0_100(self, db_session, test_app, eval_session):
        """Out-of-range eval scores are clamped, never fabricated."""
        result = ScoringService.set_evaluation_result(
            app=test_app, db=db_session, eval_score=150.0
        )
        assert result.rubric_score == 100.0
        # Canonical final_score: cv=0, rubric=100, cov=100 (default): 0*0.25 + 100*0.50 + 100*0.25 = 75.0
        assert result.final_score == 75.0


class TestSetEvaluationResultEndpoints:
    def _setup_scored_app(self, db_session, app_obj, eval_session, score=72.0):
        ScoringService.set_evaluation_result(
            app=app_obj,
            db=db_session,
            eval_score=score,
            cv_score=60.0,
            skill_metrics={"Technical": 75},
            scored_by="ai",
            rubric_score=70.0,
            rubric_coverage_pct=60,
            rubric_version=2,
            score_breakdown={
                "overall_score": 70.0,
                "categories": [
                    {"name": "Backend", "score": 70, "weight": 100, "children": []}
                ],
                "skill_scores": {"python": {"final_score": 70}},
                "gaps": [],
                "overall_coverage_pct": 60,
            },
        )
        db_session.commit()

    def test_recruiter_scores_endpoint_reads_result(
        self, client, db_session, test_app, eval_session, recruiter_headers
    ):
        self._setup_scored_app(db_session, test_app, eval_session)
        resp = client.get(
            f"/api/v1/recruiter/applications/{test_app.id}/scores",
            headers=recruiter_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] is not None
        assert data["rubric_score"] == 70.0
        assert data["rubric_coverage_pct"] == 60.0
        assert data["rubric_available"] is True
        assert data["is_rubric_driven"] is True
        assert len(data["category_breakdown"]) == 1
        assert data["category_breakdown"][0]["name"] == "Backend"
        assert len(data["skill_breakdown"]) == 1
        assert data["recommendation"]["label"] in ("Consider", "Hire")
        assert data["cv_score"] == 60.0

    def test_candidate_analysis_endpoint_reads_result(
        self, client, db_session, test_app, eval_session, auth_headers
    ):
        self._setup_scored_app(db_session, test_app, eval_session)
        resp = client.get(
            f"/api/v1/candidate/interviews/{test_app.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] is not None
        assert data["rubric_score"] == 70.0
        assert data["rubric_coverage_pct"] == 60.0
        assert len(data["skill_breakdown"]) == 1
