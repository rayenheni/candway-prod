import traceback

from backend.ai.llm import call_groq_cascade
from backend.ai.prompts import (
    get_career_roadmap_prompt,
    get_case_study_grading_prompt,
    get_case_study_prompt,
)
from backend.config import get_settings
from backend.logger import logger


async def generate_career_roadmap(
    target_role: str,
    current_skills: list,
    available_courses: list,
    audit_context: dict = None,
):
    settings = get_settings()
    if not settings.groq_api_key:
        return {
            "roadmap": [],
            "summary": "API Key Missing",
            "total_estimated_time": "Unknown",
        }

    # Truncate context aggressively to prevent token overflow
    if audit_context and "cv_raw_text" in audit_context:
        audit_context["cv_raw_text"] = audit_context["cv_raw_text"][:2000]

    system_prompt = get_career_roadmap_prompt(
        target_role, current_skills, audit_context, available_courses
    )

    try:
        # Request more tokens for roadmap
        resp = await call_groq_cascade(
            [{"role": "system", "content": system_prompt}],
            temperature=0.4,
            max_tokens=2048,
        )
        if not resp or not resp.get("roadmap"):
            raise Exception("Empty AI response")
        return resp
    except Exception:
        logger.error(f"Roadmap AI Failure: {traceback.format_exc()}")
        # SELF-HEALING: Return a high-quality static-ish roadmap so the user doesn't crash
        return {
            "summary": f"Your roadmap to {target_role} is being refined. Focus on strengthening your core technologies and building a portfolio project.",
            "total_estimated_time": "8-12 Weeks",
            "roadmap": [
                {
                    "milestone": "Foundations & Core Tech",
                    "weeks": "4",
                    "priority": "Critical",
                    "skills": current_skills[:3]
                    if current_skills
                    else ["Fundamentals"],
                    "course_id": None,
                    "action_items": [
                        "Build a small project using your core stack",
                        "Review best practices for current role",
                    ],
                },
                {
                    "milestone": "Advanced Gap Bridging",
                    "weeks": "4",
                    "priority": "High",
                    "skills": [target_role, "System Architecture"],
                    "course_id": None,
                    "action_items": [
                        "Deep dive into target role requirements",
                        "Connect with industry mentors",
                    ],
                },
            ],
        }


async def generate_case_study(
    skill: str, difficulty: str = "Intermediate", language: str = "English"
):
    system_prompt = get_case_study_prompt(skill, difficulty, language)
    try:
        return await call_groq_cascade(
            [{"role": "system", "content": system_prompt}], temperature=0.7
        )
    except Exception:
        return {
            "title": "Error",
            "scenario": "N/A",
            "challenge": "N/A",
            "key_areas": [],
        }


async def grade_case_study(
    skill: str, scenario: str, user_response: str, language: str = "English"
):
    system_prompt = get_case_study_grading_prompt(
        skill, scenario, user_response, language
    )
    try:
        return await call_groq_cascade(
            [{"role": "system", "content": system_prompt}], temperature=0.3
        )
    except Exception:
        return {"score": 0, "feedback": "Grading Error", "improvement_tips": []}


async def generate_course_syllabus(
    title: str, description: str, difficulty: str = "Intermediate"
):
    from backend.ai.prompts import get_course_syllabus_prompt

    system_prompt = get_course_syllabus_prompt(title, description, difficulty)
    try:
        return await call_groq_cascade(
            [{"role": "system", "content": system_prompt}],
            temperature=0.5,
            max_tokens=2048,
        )
    except Exception as e:
        logger.error(f"Syllabus AI Failure: {e}")
        return {"sections": []}


async def generate_quiz_questions(
    section_title: str, section_description: str, count: int = 5
):
    from backend.ai.prompts import get_quiz_generation_prompt

    system_prompt = get_quiz_generation_prompt(
        section_title, section_description, count
    )
    try:
        return await call_groq_cascade(
            [{"role": "system", "content": system_prompt}], temperature=0.4
        )
    except Exception as e:
        logger.error(f"Quiz AI Failure: {e}")
        return {"quiz_title": section_title, "questions": []}
