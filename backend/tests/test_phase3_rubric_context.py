import asyncio

import pytest

from backend.ai import interview as interview_module
from backend.ai.interview_customization import SkillFocus, select_next_focus
from backend.ai.prompts import get_question_generator_prompt
from backend.rubric.rubric_schema import (
    CategoryDefinition,
    JobRubric,
    LevelDescriptor,
    SkillDefinition,
    SubcategoryDefinition,
)


def _make_rubric_with_skills(job_id: int) -> JobRubric:
    return JobRubric(
        job_id=job_id,
        version=1,
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
                                description="Proficiency in Python and its ecosystem",
                                weight=1.0,
                                is_required=True,
                                keywords=["python", "flask", "fastapi", "async"],
                                levels={
                                    "junior": [],
                                    "mid": [
                                        LevelDescriptor(
                                            score_threshold=100,
                                            description="Builds production APIs",
                                            keywords=["production", "api"],
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


@pytest.mark.usefixtures("db_session")
class TestPhase3RubricContext:
    """Phase 3: rubric context injection into question generation prompt."""

    def test_select_next_focus_returns_skill_focus(self, db_session):
        """select_next_focus returns a SkillFocus dataclass when rubric skill is selected."""
        rubric = _make_rubric_with_skills(1)
        state = {"covered_skills": []}
        result = select_next_focus(
            state, "Backend Engineer", rubric_categories=rubric.categories
        )
        assert isinstance(result, SkillFocus)
        assert result.name == "Python"
        assert result.description == "Proficiency in Python and its ecosystem"
        assert "fastapi" in result.keywords
        assert result.is_required is True
        assert result.level_text == "Builds production APIs"
        assert "0 of 1 required skills" in result.coverage_context

    def test_prompt_contains_rubric_context_when_provided(self, db_session):
        """get_question_generator_prompt includes rubric_context block when passed."""
        rubric_context = (
            "<rubric_context>\n"
            "SKILL: Python\n"
            "DESCRIPTION: Proficiency in Python and its ecosystem\n"
            "LEVEL: mid — Builds production APIs\n"
            "REQUIRED: yes\n"
            "KEYWORDS: python, flask, fastapi, async\n"
            "</rubric_context>"
        )
        prompt = get_question_generator_prompt(
            declared_role="Backend Engineer",
            candidate_summary="Experienced developer",
            phase="CORE",
            q_index=2,
            total_questions=6,
            language="English",
            history_summary="Tested: Python",
            last_feedback="Good",
            rubric_context=rubric_context,
        )
        assert "<rubric_context>" in prompt
        assert "SKILL: Python" in prompt
        assert "DESCRIPTION: Proficiency in Python" in prompt
        assert "LEVEL: mid — Builds production APIs" in prompt
        assert "REQUIRED: yes" in prompt
        assert "KEYWORDS: python, flask, fastapi, async" in prompt
        assert "8. RUBRIC ALIGNMENT" in prompt

    def test_no_rubric_context_when_not_provided(self, db_session):
        """get_question_generator_prompt does NOT include rubric_context block when None."""
        prompt = get_question_generator_prompt(
            declared_role="Backend Engineer",
            candidate_summary="Experienced developer",
            phase="CORE",
            q_index=2,
            total_questions=6,
            language="English",
            history_summary="Tested: Python",
            last_feedback="Good",
        )
        assert "<rubric_context>" not in prompt
        assert "KEYWORDS:" not in prompt
        # Calibration-aware rule should still be present but no rubric rule
        assert "7. CALIBRATION AWARE" in prompt

    def test_generate_skill_driven_turn_injects_rubric_context(
        self, monkeypatch, db_session
    ):
        """generate_skill_driven_turn injects rubric_context when rubric is available."""
        rubric = _make_rubric_with_skills(1)

        async def fake_call_groq_cascade(*args, **kwargs):
            prompt = (
                args[0][0]["content"]
                if args[0]
                else kwargs.get("messages", [{}])[0].get("content", "")
            )
            assert "<rubric_context>" in prompt, "Prompt must contain rubric_context"
            assert "SKILL: Python" in prompt
            assert "LEVEL: mid — Builds production APIs" in prompt
            assert "KEYWORDS: python, flask, fastapi, async" in prompt
            return {
                "reply": "What Python async patterns have you used?",
                "hint_text": "",
            }

        monkeypatch.setattr(
            interview_module, "call_groq_cascade", fake_call_groq_cascade
        )
        state = {
            "turn": 1,
            "history": [],
            "skill_depth": {"Python": 0},
            "skill_scores": {"Python": []},
            "verified_skills": [],
            "covered_skills": [],
            "max_turns": 6,
            "strategy": "skill-driven",
            "focus_pool": ["Python"],
        }
        result = asyncio.run(
            interview_module.generate_skill_driven_turn(
                state=state,
                cv_context="Built APIs with Python",
                declared_role="Backend Engineer",
                rubric_categories=rubric.categories,
                rubric_seniority="mid",
            )
        )
        assert "reply" in result
        assert result["focus"] == "Python"

    def test_generate_skill_driven_turn_no_rubric_fallback(
        self, monkeypatch, db_session
    ):
        """generate_skill_driven_turn does NOT inject rubric_context when rubric is absent."""

        async def fake_call_groq_cascade(*args, **kwargs):
            prompt = (
                args[0][0]["content"]
                if args[0]
                else kwargs.get("messages", [{}])[0].get("content", "")
            )
            assert "<rubric_context>" not in prompt, "No rubric context for fallback"
            assert "KEYWORDS:" not in prompt
            return {"reply": "Tell me about your experience.", "hint_text": ""}

        monkeypatch.setattr(
            interview_module, "call_groq_cascade", fake_call_groq_cascade
        )
        state = {
            "turn": 1,
            "history": [],
            "skill_depth": {},
            "skill_scores": {},
            "verified_skills": [],
            "covered_skills": [],
            "max_turns": 6,
            "strategy": "skill-driven",
            "focus_pool": [],
        }
        result = asyncio.run(
            interview_module.generate_skill_driven_turn(
                state=state,
                cv_context="Built APIs",
                declared_role="Backend Engineer",
                rubric_categories=None,
            )
        )
        assert "reply" in result

    def test_select_next_focus_fallback_no_rubric(self, db_session):
        """select_next_focus returns SkillFocus with name-only when no rubric."""
        result = select_next_focus({}, "Backend Engineer", rubric_categories=None)
        assert isinstance(result, SkillFocus)
        assert result.name == "Backend Engineer"
        assert result.description == ""
        assert result.keywords == []
        assert result.level_text == ""
        assert result.coverage_context == ""

    def test_rubric_context_level_text_from_seniority(self, db_session):
        """select_next_focus picks level text matching the given seniority."""
        rubric = _make_rubric_with_skills(1)
        # Test mid seniority
        state = {"covered_skills": []}
        result_mid = select_next_focus(
            state, "Engineer", rubric_categories=rubric.categories, seniority="mid"
        )
        assert result_mid.level_text == "Builds production APIs"
        # Test senior with no levels defined
        result_senior = select_next_focus(
            state, "Engineer", rubric_categories=rubric.categories, seniority="senior"
        )
        assert result_senior.level_text == ""
