"""Tests for backend/ai/schemas.py — Pydantic model for AI evaluation output."""

import pytest
from pydantic import ValidationError

# The schema module has no heavy dependencies; import directly.
from backend.ai.schemas import EvaluationResponse

# ---------------------------------------------------------------------------
# Valid data
# ---------------------------------------------------------------------------


def test_valid_full_response():
    raw = {
        "final_score": 85.0,
        "strengths": ["Good communication", "Technical depth"],
        "weaknesses": ["Needs more experience with cloud"],
        "skill_metrics": {"Python": 90, "SQL": 70},
        "recommendation": "Hire",
        "detailed_feedback": "Strong candidate overall.",
        "explainability": {
            "why_this_score": "Strong technical performance",
            "gap_analysis": [],
        },
        "question_scores": [80, 90, 85],
        "role_fit_score": 88.0,
    }
    parsed = EvaluationResponse(**raw)
    assert parsed.final_score == 85.0
    assert parsed.recommendation == "Hire"
    assert parsed.role_fit_score == 88.0


def test_valid_minimal_response():
    """Only ``final_score`` should be required."""
    raw = {"final_score": 72.0}
    parsed = EvaluationResponse(**raw)
    assert parsed.final_score == 72.0
    assert parsed.strengths == []
    assert parsed.weaknesses == []
    assert parsed.skill_metrics == {}
    assert parsed.recommendation == "Error"
    assert parsed.detailed_feedback == ""
    assert parsed.explainability is None
    assert parsed.question_scores == []
    assert parsed.role_fit_score == 0.0


def test_valid_boundary_scores():
    """Scores at the extreme valid values (0 and 100)."""
    assert EvaluationResponse(final_score=0).final_score == 0.0
    assert EvaluationResponse(final_score=100).final_score == 100.0


# ---------------------------------------------------------------------------
# Missing / bad required field
# ---------------------------------------------------------------------------


def test_missing_final_score():
    with pytest.raises(ValidationError):
        EvaluationResponse()


def test_none_final_score():
    with pytest.raises(ValidationError):
        EvaluationResponse(final_score=None)


# ---------------------------------------------------------------------------
# Out-of-range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_score", [-1, -0.01, 100.01, 101, 999])
def test_final_score_out_of_range(bad_score):
    with pytest.raises(ValidationError):
        EvaluationResponse(final_score=bad_score)


@pytest.mark.parametrize("bad_score", [-1, 100.01])
def test_role_fit_score_out_of_range(bad_score):
    with pytest.raises(ValidationError):
        EvaluationResponse(final_score=50, role_fit_score=bad_score)


# ---------------------------------------------------------------------------
# Wrong field name (common AI mistake)
# ---------------------------------------------------------------------------


def test_wrong_field_name_score_instead_of_final_score():
    """AI returned ``score`` instead of ``final_score`` → should fail."""
    with pytest.raises(ValidationError):
        EvaluationResponse(score=85)


# ---------------------------------------------------------------------------
# Malformed types
# ---------------------------------------------------------------------------


def test_skill_metrics_not_a_dict():
    with pytest.raises(ValidationError):
        EvaluationResponse(final_score=50, skill_metrics="not_a_dict")


def test_strengths_not_a_list():
    with pytest.raises(ValidationError):
        EvaluationResponse(final_score=50, strengths="not_a_list")


def test_question_scores_not_a_list():
    with pytest.raises(ValidationError):
        EvaluationResponse(final_score=50, question_scores="not_a_list")


# ---------------------------------------------------------------------------
# Extra unknown fields are silently ignored (Pydantic v2 default)
# ---------------------------------------------------------------------------


def test_extra_fields_ignored():
    raw = {
        "final_score": 65,
        "score": 85,
        "unknown_field": "should be ignored",
    }
    parsed = EvaluationResponse(**raw)
    assert parsed.final_score == 65.0
    # Unknown fields should not cause an error
