"""
API Router for AI-Powered Recommendations
Provides endpoints for course and internship recommendations
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.recommendations import get_ai_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    """Request model for recommendations"""

    interview_score: Optional[int] = None
    strengths: Optional[list] = []
    weaknesses: Optional[list] = []
    skill_gaps: Optional[list] = []
    limit: Optional[int] = 5


@router.get("/me")
async def get_my_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 5,
):
    """
    Get AI-powered recommendations for current user

    Returns:
        - Recommended courses (based on weaknesses and skill gaps)
        - Recommended internships/jobs (based on profile and level)
        - Learning path summary
    """

    try:
        # Get user's latest interview results and CV data
        import json

        from backend.database import Application

        interview_results = None

        # Fetch latest application with interview data
        latest_app = (
            db.query(Application)
            .filter(Application.user_id == current_user.id)
            .order_by(Application.created_at.desc())
            .first()
        )

        if latest_app:
            # Parse analysis_json to extract weaknesses and strengths
            analysis = {}
            if latest_app.analysis_json:
                try:
                    analysis = json.loads(latest_app.analysis_json)
                except Exception as e:
                    from backend.logger import logger

                    logger.error(
                        f"Error parsing analysis JSON for user {current_user.id}: {e}"
                    )
                    analysis = {}

            # Extract interview analysis from latest application
            _er = (
                latest_app.evaluation_sessions[0].evaluation_result
                if latest_app.evaluation_sessions
                and latest_app.evaluation_sessions[0].evaluation_result
                else None
            )
            interview_results = {
                "final_score": (_er.final_score if _er else None) or 0,
                "declared_role": latest_app.declared_role or "Not specified",
                "cv_text": latest_app.cv_text_anonymized or "",
                "strengths": analysis.get("strengths", []),
                "weaknesses": analysis.get("missing_skills", [])
                or analysis.get("weaknesses", []),
                "skill_gaps": analysis.get("missing_skills", []) or [],
            }

        recommendations = await get_ai_recommendations(
            db=db,
            user_id=current_user.id,
            interview_results=interview_results,
            limit=limit,
        )

        return {"success": True, "data": recommendations}

    except Exception as e:
        logger.error(f"Recommendations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.post("/with-interview")
async def get_recommendations_with_interview(
    request: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get AI-powered recommendations based on interview results

    Body:
        - interview_score: Final interview score
        - strengths: List of identified strengths
        - weaknesses: List of identified weaknesses
        - skill_gaps: List of skill gaps
        - limit: Number of recommendations per category
    """

    try:
        # Build interview results context
        interview_results = {
            "final_score": request.interview_score,
            "strengths": request.strengths,
            "weaknesses": request.weaknesses,
            "skill_gaps": request.skill_gaps,
        }

        recommendations = await get_ai_recommendations(
            db=db,
            user_id=current_user.id,
            interview_results=interview_results,
            limit=request.limit,
        )

        return recommendations

    except Exception as e:
        logger.error(f"Recommendations with interview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.get("/courses/{course_id}/similar")
async def get_similar_courses(
    course_id: int, db: Session = Depends(get_db), limit: int = 3
):
    """
    Get similar courses based on a specific course
    Uses AI to find courses in same category or related topics
    """

    from backend.database import Course

    try:
        # Get the target course
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Get all other courses in same category
        similar = (
            db.query(Course)
            .filter(
                Course.category == course.category,
                Course.id != course_id,
                Course.status == "published",
            )
            .limit(limit)
            .all()
        )

        return {
            "success": True,
            "data": [
                {
                    "id": c.id,
                    "title": c.title,
                    "category": c.category,
                    "difficulty": c.difficulty,
                    "thumbnail_url": c.thumbnail_url,
                }
                for c in similar
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similar courses error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get similar courses")
