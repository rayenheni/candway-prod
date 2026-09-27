"""Scoring policy (product decision) for evaluate_answer() with a rubric:

* no evidence for any rubric skill -> 0 (no word-count credit);
* evidence that maps to the rubric but cannot be scored (e.g. the rubric has
  no level for the candidate's seniority) keeps the heuristic, so a rubric
  configuration gap never zeroes a real answer;
* at the 90 ceiling, each additional evidenced rubric skill adds a bonus
  (5, or 2 for weak evidence), capped at 100.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.ai.interview import (
    BREADTH_BONUS_PER_SKILL,
    BREADTH_BONUS_PER_WEAK_SKILL,
    _breadth_bonus,
    evaluate_answer,
)
from backend.tests.test_ai_interview_quality_fixes import job_rubric, mock_app

# An application with no evaluation session is scored at the default "mid"
# seniority, for which the shared rubric defines no level.
app_without_session = type(
    "MockApp", (), {"id": 2, "company_id": 1, "evaluation_sessions": []}
)()


async def _evaluate(answer, extracted, app):
    with patch(
        "backend.ai.interview.call_groq_cascade",
        new_callable=AsyncMock,
        return_value={"extracted_skills": extracted, "feedback": "x"},
    ):
        return await evaluate_answer(
            question="How do you handle churn?",
            answer=answer,
            focus="Problem Solving",
            history_summary="",
            declared_role="Senior Product Manager",
            app=app,
            job_rubric=job_rubric,
        )


@pytest.mark.asyncio
async def test_skills_outside_the_rubric_score_zero():
    res = await _evaluate(
        "I am great at playing chess and I won three regional tournaments.",
        [
            {
                "skill_name": "Chess",
                "evidence_sentences": ["I won three regional tournaments."],
            }
        ],
        mock_app,
    )
    assert res["score"] == 0


@pytest.mark.asyncio
async def test_unscorable_rubric_evidence_is_not_zeroed():
    answer = "Reduced churn 32% by redesigning onboarding."
    res = await _evaluate(
        answer,
        [{"skill_name": "Problem Solving", "evidence_sentences": [answer]}],
        app_without_session,
    )
    assert res["score"] > 0


def _item(name, quality="strong", evidence=("did it",)):
    return {
        "skill_name": name,
        "evidence_sentences": list(evidence),
        "quality": quality,
    }


ANSWER = "I led the redesign of onboarding and reduced churn by 32 percent."


def test_bonus_only_at_the_ceiling():
    mapped = [_item("focus"), _item("other")]
    assert _breadth_bonus(89, ANSWER, mapped, {"focus"}) == 0
    assert _breadth_bonus(90, ANSWER, mapped, {"focus"}) == BREADTH_BONUS_PER_SKILL


def test_weak_evidence_counts_less_and_duplicates_count_once():
    mapped = [
        _item("focus"),
        _item("a", "weak"),
        _item("b", "medium"),
        _item("b", "weak"),  # same skill again: best quality wins, once
    ]
    assert (
        _breadth_bonus(90, ANSWER, mapped, {"focus"})
        == BREADTH_BONUS_PER_WEAK_SKILL + BREADTH_BONUS_PER_SKILL
    )


def test_bonus_ignores_empty_evidence_and_caps_at_100():
    mapped = [_item("focus"), _item("empty", evidence=("  ",))]
    assert _breadth_bonus(90, ANSWER, mapped, {"focus"}) == 0
    many = [_item("focus")] + [_item(f"s{i}") for i in range(10)]
    assert _breadth_bonus(95, ANSWER, many, {"focus"}) == 5


def test_no_bonus_for_trivial_answers():
    assert _breadth_bonus(90, "ok", [_item("focus"), _item("x")], {"focus"}) == 0
