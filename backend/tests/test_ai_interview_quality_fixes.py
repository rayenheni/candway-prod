"""Regression tests for AI interview scoring fixes:
1. Morphological / word-form keyword matching (redesign ↔ redesigned, analyze ↔ analyzed, lead ↔ leading, manage ↔ managed)
2. Negative morphological matching (design ↔ designation MUST NOT match)
3. Concise evidence-backed answers (e.g. "Reduced churn 32% by redesigning onboarding.") without unjustified anti-cheat penalty
4. Empty answer score = 0
5. Keyword stuffing resistance
6. Long irrelevant answer handling
7. Strong concise answer without exact rubric keywords
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from backend.rubric.rubric_engine import _keyword_matches_in_text, _find_best_level, score_answer
from backend.rubric.rubric_schema import JobRubric
from backend.rubric.config_reader import ParsedRubric
from backend.ai.anti_cheat import AntiCheatDetector
from backend.ai.interview import evaluate_answer


# -------------------------------------------------------------------------
# Test 1 & 7: Morphological matching and negative morphological case
# -------------------------------------------------------------------------
def test_morphological_matching_positive_and_negative():
    # Positive morphological variants
    assert _keyword_matches_in_text("redesign", "We redesigned the signup flow") is True
    assert _keyword_matches_in_text("analyze", "I analyzed the customer behavior metrics") is True
    assert _keyword_matches_in_text("lead", "I am leading cross-functional alignment sessions") is True
    assert _keyword_matches_in_text("manage", "I managed the product roadmap effectively") is True
    assert _keyword_matches_in_text("develop", "We developed a microservices platform") is True
    assert _keyword_matches_in_text("improve", "I improved API performance by 40%") is True
    assert _keyword_matches_in_text("communicate", "Effective communication with executives") is True

    # Negative morphological case: design vs designation MUST NOT match
    assert _keyword_matches_in_text("design", "Candidate holds the official designation of lead") is False


# -------------------------------------------------------------------------
# Setup Test Rubric Fixture
# -------------------------------------------------------------------------
RUBRIC_DICT = {
    "job_id": 1,
    "version": 1,
    "seniority": "senior",
    "categories": [
        {
            "name": "Problem Solving",
            "weight": 1.0,
            "subcategories": [
                {
                    "name": "Analytical",
                    "skills": [
                        {
                            "name": "Problem Solving",
                            "level": "advanced",
                            "description": "Root cause analysis and metric optimization",
                            "keywords": ["churn", "redesign", "onboarding", "metric"],
                            "levels": {
                                "senior": [
                                    {"score_threshold": 90, "keywords": ["churn", "redesign", "onboarding", "metric"], "description": "Solves root cause with proxy metrics"}
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    ]
}

job_rubric = JobRubric(**RUBRIC_DICT)
parsed_rubric = ParsedRubric(
    id="test_fixes_rubric",
    version=1,
    categories=RUBRIC_DICT["categories"],
    skills=["Problem Solving"],
    seniority="senior",
    raw_json=RUBRIC_DICT
)

mock_eval_res = type("EvalResult", (), {"rubric_seniority": "senior"})()
mock_eval_sess = type("EvalSession", (), {"evaluation_result": mock_eval_res})()
mock_app = type("MockApp", (), {"id": 1, "company_id": 1, "evaluation_sessions": [mock_eval_sess]})()


# -------------------------------------------------------------------------
# Test 2: Concise Strong Evidence without anti-cheat penalty
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concise_strong_evidence_no_cheat_penalty():
    answer = "Reduced churn 32% by redesigning onboarding."
    
    # 1. AntiCheat check
    cheat_res = AntiCheatDetector.calculate_cheat_score(answer)
    assert cheat_res["cheat_score"] == 0, f"Unjustified cheat penalty: {cheat_res}"

    # 2. Pipeline evaluation
    mock_llm_res = {
        "extracted_skills": [
            {
                "skill_name": "Problem Solving",
                "evidence_sentences": ["Reduced churn 32% by redesigning onboarding."]
            }
        ],
        "feedback": "Concise evidence-backed answer."
    }

    with patch("backend.ai.interview.call_groq_cascade", new_callable=AsyncMock, return_value=mock_llm_res):
        res = await evaluate_answer(
            question="How do you handle churn?",
            answer=answer,
            focus="Problem Solving",
            history_summary="",
            declared_role="Senior Product Manager",
            app=mock_app,
            job_rubric=job_rubric,
        )

    assert res["score"] >= 70, f"Expected high score for concise evidence, got {res['score']}"
    assert "Problem Solving" in res["skills"] or "problem solving" in res["skills"]


# -------------------------------------------------------------------------
# Test 3: Empty / Non-Answer
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_answer_scores_zero():
    answer = "I don't know."
    mock_llm_res = {
        "extracted_skills": [],
        "feedback": "No evidence."
    }

    with patch("backend.ai.interview.call_groq_cascade", new_callable=AsyncMock, return_value=mock_llm_res):
        res = await evaluate_answer(
            question="Tell me about problem solving",
            answer=answer,
            focus="Problem Solving",
            history_summary="",
            declared_role="Senior Product Manager",
            app=mock_app,
            job_rubric=job_rubric,
        )

    assert res["score"] == 0, f"Expected score 0 for 'I don't know', got {res['score']}"


# -------------------------------------------------------------------------
# Test 4: Keyword Stuffing Resistance
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_keyword_stuffing_resistance():
    answer = "communication communication communication leadership leadership problem solving"
    mock_llm_res = {
        "extracted_skills": [],
        "feedback": "Keyword repetition detected."
    }

    with patch("backend.ai.interview.call_groq_cascade", new_callable=AsyncMock, return_value=mock_llm_res):
        res = await evaluate_answer(
            question="Tell me about your leadership",
            answer=answer,
            focus="Leadership",
            history_summary="",
            declared_role="Senior Product Manager",
            app=mock_app,
            job_rubric=job_rubric,
        )

    assert res["score"] == 0, f"Expected score 0 for keyword stuffing, got {res['score']}"


# -------------------------------------------------------------------------
# Test 5: Long Irrelevant Answer
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_long_irrelevant_answer_not_high_scoring():
    answer = "I love playing open-world video games on my computer. " * 10
    mock_llm_res = {
        "extracted_skills": [],
        "feedback": "Irrelevant content."
    }

    with patch("backend.ai.interview.call_groq_cascade", new_callable=AsyncMock, return_value=mock_llm_res):
        res = await evaluate_answer(
            question="Tell me about problem solving",
            answer=answer,
            focus="Problem Solving",
            history_summary="",
            declared_role="Senior Product Manager",
            app=mock_app,
            job_rubric=job_rubric,
        )

    assert res["score"] <= 20, f"Expected low score for long irrelevant answer, got {res['score']}"


# -------------------------------------------------------------------------
# Test 6: Strong Concise Answer Without Exact Rubric Keywords (Morphological Match)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_strong_concise_answer_with_morphological_keywords():
    # Evidence uses "redesigned" (variant of rubric keyword "redesign")
    answer = "We redesigned our onboarding funnel and reduced user churn by 25%."
    mock_llm_res = {
        "extracted_skills": [
            {
                "skill_name": "Problem Solving",
                "evidence_sentences": ["We redesigned our onboarding funnel and reduced user churn by 25%."]
            }
        ],
        "feedback": "Clear outcome and action."
    }

    with patch("backend.ai.interview.call_groq_cascade", new_callable=AsyncMock, return_value=mock_llm_res):
        res = await evaluate_answer(
            question="How did you fix onboarding drop-off?",
            answer=answer,
            focus="Problem Solving",
            history_summary="",
            declared_role="Senior Product Manager",
            app=mock_app,
            job_rubric=job_rubric,
        )

    assert res["score"] > 0, f"Morphological match failed, got score {res['score']}"
