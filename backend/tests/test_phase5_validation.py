"""
Phase 5: AI output schema validation — needs_review flag, validator, safe fallbacks
"""

import pytest

from backend.ai.output_schema import (
    AnswerEvaluation,
    CareerRoadmap,
    CVAnalysis,
    FinalEvaluation,
    QuestionGeneration,
)
from backend.ai.validation import (
    AIOutputValidator,
    AIValidationContext,
    _mark_needs_review,
    get_default_safe,
)
from backend.database import EvaluationResult, EvaluationSession


class TestOutputSchemas:
    """Pydantic schemas parse valid data and reject invalid data."""

    def test_answer_evaluation_valid(self):
        m = AnswerEvaluation(score=75, feedback="Good")
        assert m.score == 75
        assert m.feedback == "Good"
        assert m.extracted_skills == []

    def test_answer_evaluation_defaults(self):
        m = AnswerEvaluation()
        assert m.score == 50.0
        assert m.cheat_detected is False
        assert m.answer_quality == "adequate"

    def test_answer_evaluation_clamps_score(self):
        """score must be 0-100."""
        with pytest.raises(Exception):
            AnswerEvaluation(score=999)

    def test_final_evaluation_valid(self):
        m = FinalEvaluation(final_score=80, strengths=["Python"], weaknesses=["Docker"])
        assert m.final_score == 80
        assert m.strengths == ["Python"]

    def test_final_evaluation_defaults(self):
        m = FinalEvaluation()
        assert m.final_score == 50.0
        assert m.strengths == []
        assert m.detailed_feedback is None

    def test_cv_analysis_defaults(self):
        m = CVAnalysis()
        assert m.overall_score == 50.0
        assert m.skills == []

    def test_question_generation_defaults(self):
        m = QuestionGeneration()
        assert m.question == ""
        assert m.difficulty == "medium"

    def test_career_roadmap_defaults(self):
        m = CareerRoadmap()
        assert m.overall_score == 50.0
        assert m.recommendations == []


class TestAIOutputValidator:
    """Validator correctly validates or rejects AI responses."""

    def test_valid_dict_passes(self, db_session):
        ctx = AIValidationContext(application_id=1, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate(
            "final_evaluation",
            {
                "final_score": 75,
                "strengths": ["Python"],
                "weaknesses": [],
                "skill_metrics": {"Technical": 75},
            },
        )
        assert result is not None
        assert result.final_score == 75
        assert result.strengths == ["Python"]

    def test_invalid_dict_fails_and_marks_needs_review(self, db_session):
        _es = EvaluationSession(application_id=999, status="completed")
        db_session.add(_es)
        db_session.flush()
        app_score = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            final_score=50.0,
            scoring_model="rubric",
        )
        db_session.add(app_score)
        db_session.flush()

        ctx = AIValidationContext(application_id=999, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate(
            "final_evaluation",
            {
                "final_score": "not_a_number",
            },
        )
        assert result is None

        db_session.refresh(app_score)
        assert app_score.needs_review is True
        assert "final_score" in (app_score.needs_review_reason or "")

    def test_non_dict_fails(self, db_session):
        _es = EvaluationSession(application_id=888, status="completed")
        db_session.add(_es)
        db_session.flush()
        app_score = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            final_score=50.0,
            scoring_model="rubric",
        )
        db_session.add(app_score)
        db_session.flush()

        ctx = AIValidationContext(application_id=888, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate("final_evaluation", "not a dict")
        assert result is None

        db_session.refresh(app_score)
        assert app_score.needs_review is True

    def test_non_dict_fails_list(self, db_session):
        _es = EvaluationSession(application_id=777, status="completed")
        db_session.add(_es)
        db_session.flush()
        app_score = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            final_score=50.0,
            scoring_model="rubric",
        )
        db_session.add(app_score)
        db_session.flush()

        ctx = AIValidationContext(application_id=777, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate("final_evaluation", [1, 2, 3])
        assert result is None

        db_session.refresh(app_score)
        assert app_score.needs_review is True

    def test_unknown_schema_skips_validation(self, db_session):
        ctx = AIValidationContext(application_id=1, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate("nonexistent_schema", {"foo": "bar"})
        assert result is None  # returns None for unknown schema

    def test_answer_evaluation_schema(self, db_session):
        ctx = AIValidationContext(application_id=1, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate(
            "answer_evaluation",
            {
                "score": 80,
                "feedback": "Good answer",
                "extracted_skills": [
                    {"skill_name": "Python", "evidence_sentences": ["wrote code"]}
                ],
            },
        )
        assert result is not None
        assert result.score == 80

    def test_cv_analysis_schema(self, db_session):
        ctx = AIValidationContext(application_id=1, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate(
            "cv_analysis",
            {
                "overall_score": 65,
                "summary": "Strong candidate",
                "skills": [{"name": "Python", "level": "senior"}],
            },
        )
        assert result is not None
        assert result.overall_score == 65

    def test_question_generation_schema(self, db_session):
        ctx = AIValidationContext(application_id=1, db=db_session)
        validator = AIOutputValidator(ctx)
        result = validator.validate(
            "question_generation",
            {
                "question": "What is Python?",
                "difficulty": "hard",
            },
        )
        assert result is not None
        assert result.question == "What is Python?"

    def test_validate_answer_evaluation_creates_app_score_if_missing(self, db_session):
        """When EvaluationResult does not exist, _mark_needs_review creates one."""
        from backend.ai.validation import _mark_needs_review

        existing = (
            db_session.query(EvaluationResult)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == 5555)
            .first()
        )
        assert existing is None

        _mark_needs_review(db_session, 5555, "test failure reason")

        created = (
            db_session.query(EvaluationResult)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == 5555)
            .first()
        )
        assert created is not None
        assert created.needs_review is True
        assert created.needs_review_reason == "test failure reason"


class TestGetDefaultSafe:
    """get_default_safe returns safe fallback dicts."""

    def test_known_schema(self):
        safe = get_default_safe("final_evaluation")
        assert safe["final_score"] == 50.0
        assert safe["strengths"] == []

    def test_unknown_schema(self):
        safe = get_default_safe("unknown")
        assert safe == {}


class TestMarkNeedsReview:
    """_mark_needs_review sets flag on existing EvaluationResult."""

    def test_marks_existing_record(self, db_session):
        _es = EvaluationSession(application_id=111, status="completed")
        db_session.add(_es)
        db_session.flush()
        app_score = EvaluationResult(
            evaluation_session_id=_es.id,
            scoring_status="SCORED",
            final_score=50.0,
            scoring_model="rubric",
        )
        db_session.add(app_score)
        db_session.flush()

        _mark_needs_review(db_session, 111, "validation error: missing final_score")

        db_session.refresh(app_score)
        assert app_score.needs_review is True
        assert app_score.needs_review_reason == "validation error: missing final_score"

    def test_creates_record_if_missing(self, db_session):
        existing = (
            db_session.query(EvaluationResult)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == 222)
            .first()
        )
        assert existing is None

        _mark_needs_review(db_session, 222, "test create")

        created = (
            db_session.query(EvaluationResult)
            .join(
                EvaluationSession,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(EvaluationSession.application_id == 222)
            .first()
        )
        assert created is not None
        assert created.needs_review is True


def test_needs_review_preserves_existing_final_score(db_session):
    """Validation review flag must preserve an already computed canonical score."""
    _es = EvaluationSession(application_id=333, status="completed")
    db_session.add(_es)
    db_session.flush()

    app_score = EvaluationResult(
        evaluation_session_id=_es.id,
        scoring_status="SCORED",
        final_score=82.5,
        scoring_model="rubric",
    )
    db_session.add(app_score)
    db_session.flush()

    _mark_needs_review(db_session, 333, "validation failure")

    db_session.refresh(app_score)

    # An existing canonical score must remain SCORED.
    # Human review is represented independently by needs_review.
    assert app_score.scoring_status == "SCORED"
    assert app_score.final_score == 82.5
    assert app_score.needs_review is True
    assert app_score.needs_review_reason == "validation failure"
