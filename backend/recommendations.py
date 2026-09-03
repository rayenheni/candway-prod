"""
AI-Powered Course and Internship Recommendation System
Analyzes candidate profile and interview results to recommend relevant opportunities
SECURITY: Added sanitization for all user-controllable content
"""

import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.ai.security import AISecurity
from backend.database import Course, Job, User
from backend.logger import logger
from backend.profile_helpers import get_user_name


async def get_ai_recommendations(
    db: Session, user_id: int, interview_results: Dict[str, Any] = None, limit: int = 5
) -> Dict[str, Any]:
    """
    Get AI-powered recommendations for courses and internships based on:
    - User's profile (CV, skills, target role)
    - Interview performance
    - Identified weaknesses

    Args:
        db: Database session
        user_id: User ID
        interview_results: Interview analysis (score, weaknesses, strengths)
        limit: Number of recommendations per category

    Returns:
        Dict with recommended courses and internships
    """

    # 1. Get user profile
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"courses": [], "internships": [], "error": "User not found"}

    # 2. Get all available courses and jobs
    all_courses = db.query(Course).filter(Course.status == "published").all()
    all_jobs = (
        db.query(Job)
        .filter(Job.is_active, Job.type.in_(["Internship", "Entry Level"]))
        .all()
    )

    if not all_courses and not all_jobs:
        return {
            "courses": [],
            "internships": [],
            "message": "No opportunities available yet",
        }

    # 3. Build context for AI
    user_context = _build_user_context(user, interview_results)
    courses_context = _build_courses_context(all_courses)
    jobs_context = _build_jobs_context(all_jobs)

    # 4. Ask AI to recommend
    prompt = f"""
You are an expert Career Advisor AI. Your goal is to recommend courses and jobs that match the candidate's DECLARED ROLE and industry to help them grow.

CANDIDATE PROFILE:
{user_context}

AVAILABLE COURSES:
{courses_context}

AVAILABLE INTERNSHIPS/JOBS:
{jobs_context}

🚨 CORE GUIDELINES:

1. **ROLE MATCHING**:
   - The candidate's DECLARED ROLE is the primary guide.
   - Recommend courses/jobs that are DIRECTLY relevant to their declared role.

2. **PROACTIVE GROWTH**:
   - If weaknesses or skill gaps are identified from the interview, prioritize courses that address them.
   - If NO weaknesses are listed, recommend high-quality courses for their role that will help them advance from their current level.
   - NEVER return empty arrays just because there are no "weaknesses" - help them stay ahead.

3. **JOB MATCHING**:
   - Recommend jobs that match the declared role and experience level.

4. **QUALITY MATCHING**:
   - Maximum {limit} recommendations per category.
   - Ensure the "reason" is compelling and specific to their profile.

Return ONLY valid JSON in this format:
{{
    "recommended_courses": [
        {{
            "course_id": 123,
            "title": "Course Title",
            "reason": "Explain why this helps them in their [DECLARED ROLE]",
            "priority": "high/medium",
            "addresses_weakness": "[IF APPLICABLE, THE WEAKNESS IT FIXES]"
        }}
    ],
    "recommended_internships": [
        {{
            "job_id": 456,
            "title": "Job Title",
            "company": "Company Name",
            "reason": "Why this is a good fit",
            "match_score": 85
        }}
    ],
    "learning_path_summary": "A brief summary of their next steps to hit their [DECLARED ROLE] goal"
}}
"""

    try:
        # Call AI
        logger.info("Calling AI for recommendations...")

        messages = [{"role": "user", "content": prompt}]
        response = await call_groq_cascade(messages, temperature=0.3, max_tokens=1500)

        # Parse response
        recommendations = {}
        if isinstance(response, dict) and (
            "recommended_courses" in response or "learning_path_summary" in response
        ):
            recommendations = response
        elif response:
            content = ""
            if isinstance(response, str):
                content = response
            elif isinstance(response, dict) and "content" in response:
                content = response["content"]
            else:
                content = str(response)

            # CLEAN JSON (Remove markdown backticks and preamble)
            import re

            content = content.strip()

            # Handle cases where AI adds preamble before the code block
            json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
            match = re.search(json_pattern, content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                # Try to find the first { and last }
                first_brace = content.find("{")
                last_brace = content.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    content = content[first_brace : last_brace + 1].strip()

            try:
                if content and content != "None":
                    recommendations = json.loads(content)
            except Exception as json_err:
                logger.warning(
                    f"JSON Parse Error: {json_err}. Content: {content[:100]}..."
                )
                # Last ditch attempt with regex to find internal fields if structure is broken
                try:
                    # If it's a list but expected a dict, wrap it
                    if content.startswith("["):
                        arr = json.loads(content)
                        recommendations = {
                            "recommended_courses": arr[:3],
                            "recommended_internships": [],
                            "learning_path_summary": "Recommendations generated from list output.",
                        }
                    else:
                        recommendations = {}
                except Exception:
                    recommendations = {}

        if not recommendations or not isinstance(recommendations, dict):
            recommendations = {
                "recommended_courses": [],
                "recommended_internships": [],
                "learning_path_summary": "",
            }

        # Validate and enrich recommendations
        enriched = _enrich_recommendations(db, recommendations, all_courses, all_jobs)

        # --- FALLBACK LOGIC ---
        # If AI returned nothing, find the most relevant courses based on role
        if not enriched.get("courses") or len(enriched["courses"]) < 2:
            logger.info("Applying fallback recommendations...")
            role = (
                interview_results.get("declared_role", "").lower()
                if interview_results
                else ""
            )

            # Find courses where title or category matches the role
            fallback_courses = []
            for c in all_courses:
                if role and (role in c.title.lower() or role in c.category.lower()):
                    fallback_courses.append(
                        {
                            "id": c.id,
                            "title": c.title,
                            "category": c.category,
                            "difficulty": c.difficulty,
                            "thumbnail_url": c.thumbnail_url,
                            "reason": f"Top-rated course for your {interview_results.get('declared_role', 'role')} profile"
                            if interview_results
                            else "Recommended skill booster",
                            "priority": "medium",
                        }
                    )

            # If still nothing, take ANY top courses
            if not fallback_courses:
                fallback_courses = [
                    {
                        "id": c.id,
                        "title": c.title,
                        "category": c.category,
                        "difficulty": c.difficulty,
                        "thumbnail_url": c.thumbnail_url,
                        "reason": "Featured skill booster",
                    }
                    for c in all_courses[:3]
                ]

            # Merge (don't duplicate)
            existing_ids = {c["id"] for c in enriched["courses"]}
            for fc in fallback_courses:
                if fc["id"] not in existing_ids:
                    enriched["courses"].append(fc)
                    existing_ids.add(fc["id"])
                    if len(enriched["courses"]) >= limit:
                        break

        # Same for internships
        if not enriched.get("internships") or len(enriched["internships"]) < 1:
            role = (
                interview_results.get("declared_role", "").lower()
                if interview_results
                else ""
            )
            fallback_jobs = []
            for j in all_jobs:
                if role and (role in j.title.lower() or role in j.description.lower()):
                    fallback_jobs.append(
                        {
                            "id": j.id,
                            "title": j.title,
                            "company": j.company_name
                            or (j.company.name if j.company else "Unknown"),
                            "location": j.location,
                            "type": j.type,
                            "reason": "Matching your target career path",
                            "match_score": 80,
                        }
                    )

            # Merge
            existing_ids = {j["id"] for j in enriched["internships"]}
            for fj in fallback_jobs:
                if fj["id"] not in existing_ids:
                    enriched["internships"].append(fj)
                    if len(enriched["internships"]) >= limit:
                        break
        if (
            not enriched["learning_path_summary"]
            or "No specific" in enriched["learning_path_summary"]
        ):
            role_name = (
                interview_results.get("declared_role", "your career")
                if interview_results
                else "your career"
            )
            enriched["learning_path_summary"] = (
                f"Explore these hand-picked opportunities to accelerate your growth as a {role_name}."
            )

        return enriched

    except Exception as e:
        logger.error(f"AI Recommendation Error: {e}", exc_info=True)

        # Return empty instead of generic fallback
        return {
            "courses": [],
            "internships": [],
            "learning_path_summary": "Unable to generate recommendations. Please try again later.",
        }


def _build_user_context(user: User, interview_results: Dict = None) -> str:
    """Build user context for AI with security sanitization"""

    # SECURITY: Sanitize all user-controllable content
    user_name = AISecurity.sanitize_input(get_user_name(user) or "Not specified")
    experience_level = AISecurity.sanitize_input(
        getattr(user, "experience_level", "Entry Level")
    )

    context = f"""
Name: {user_name}
Experience Level: {experience_level}
"""

    if interview_results:
        # Sanitize CV text
        cv_text = interview_results.get("cv_text", "No CV provided")
        if cv_text and cv_text != "No CV provided":
            cv_text = AISecurity.sanitize_input(cv_text)[:500]

        declared_role = AISecurity.sanitize_input(
            interview_results.get("declared_role", "Not specified")
        )

        context += f"""

DECLARED ROLE: {declared_role}

CV/RESUME SUMMARY:
{cv_text[:500]}...

INTERVIEW RESULTS:
Score: {interview_results.get("final_score", "N/A")}/100
Strengths: {", ".join(interview_results.get("strengths", [])) or "Not analyzed yet"}
Weaknesses: {", ".join(interview_results.get("weaknesses", [])) or "Not analyzed yet"}
Skill Gaps: {", ".join(interview_results.get("skill_gaps", [])) or "Not analyzed yet"}
"""

    return context


def _build_courses_context(courses: List[Course]) -> str:
    """Build courses context for AI"""

    if not courses:
        return "No courses available"

    courses_list = []
    for course in courses[:20]:  # Limit to top 20 to avoid token overflow
        desc = (course.description or "No description available")[:150]
        courses_list.append(f"""
ID: {course.id}
Title: {course.title}
Category: {course.category or "General"}
Difficulty: {course.difficulty or "Beginner"}
Description: {desc}...
Skills: {course.target_audience or "General"}
""")

    return "\n---\n".join(courses_list)


def _build_jobs_context(jobs: List[Job]) -> str:
    """Build jobs context for AI"""

    if not jobs:
        return "No internships available"

    jobs_list = []
    for job in jobs[:20]:  # Limit to top 20
        desc = (job.description or "No description available")[:150]
        jobs_list.append(f"""
ID: {job.id}
Title: {job.title}
Company: {job.company_name or "Unknown"}
Type: {job.type or "Full-time"}
Location: {job.location or "Remote"}
Required Skills: {job.required_skills or "General"}
Description: {desc}...
""")

    return "\n---\n".join(jobs_list)


def _enrich_recommendations(
    db: Session, recommendations: Dict, all_courses: List[Course], all_jobs: List[Job]
) -> Dict:
    """Enrich recommendations with full database objects"""

    enriched = {
        "courses": [],
        "internships": [],
        "learning_path_summary": recommendations.get("learning_path_summary", ""),
    }

    # Enrich courses
    seen_course_ids = set()
    for rec in recommendations.get("recommended_courses", []):
        course_id = rec.get("course_id")
        if course_id in seen_course_ids:
            continue

        course = next((c for c in all_courses if c.id == course_id), None)

        if course:
            seen_course_ids.add(course_id)
            enriched["courses"].append(
                {
                    "id": course.id,
                    "title": course.title,
                    "category": course.category,
                    "difficulty": course.difficulty,
                    "thumbnail_url": course.thumbnail_url,
                    "duration": getattr(course, "duration", "N/A"),
                    "price": getattr(course, "price", 0),
                    "reason": rec.get("reason", "Recommended for you"),
                    "priority": rec.get("priority", "medium"),
                    "addresses_weakness": rec.get("addresses_weakness", ""),
                }
            )

    # Enrich internships
    seen_job_ids = set()
    for rec in recommendations.get("recommended_internships", []):
        job_id = rec.get("job_id")
        if job_id in seen_job_ids:
            continue

        job = next((j for j in all_jobs if j.id == job_id), None)

        if job:
            seen_job_ids.add(job_id)
            enriched["internships"].append(
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company_name,
                    "location": job.location,
                    "type": job.type,
                    "salary_range": job.salary_range,
                    "required_skills": job.required_skills,
                    "reason": rec.get("reason", "Matches your profile"),
                    "match_score": rec.get("match_score", 75),
                }
            )

    return enriched


def _get_fallback_recommendations(
    courses: List[Course], jobs: List[Job], limit: int
) -> Dict:
    """Fallback recommendations if AI fails"""

    return {
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "category": c.category,
                "difficulty": c.difficulty,
                "thumbnail_url": c.thumbnail_url,
                "reason": "Popular course in your field",
            }
            for c in courses[:limit]
        ],
        "internships": [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company_name
                or (j.company.name if j.company else "Unknown"),
                "location": j.location,
                "type": j.type,
                "reason": "Entry-level opportunity",
            }
            for j in jobs[:limit]
        ],
        "learning_path_summary": "Explore these opportunities to advance your career.",
    }
