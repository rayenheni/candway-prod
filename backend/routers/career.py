import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.ai import generate_career_roadmap
from backend.database import Application, CareerRoadmap, Course
from backend.dependencies import User, get_current_user, get_db, require_credits
from backend.logger import logger
from backend.profile_helpers import get_user_skills

router = APIRouter(prefix="/career", tags=["career"])


class RoadmapRequest(BaseModel):
    target_role: str
    current_skills: list[str]


@router.post("/plan")
async def create_career_plan(
    req: RoadmapRequest,
    _credit_tx: object = Depends(require_credits("career_roadmap", credits=4)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a personalized AI Career Roadmap:
    - Analyzes gaps between current skills and target role.
    - Creates a weekly Calendar/ToDo list.
    - Recommends Platform Courses.
    - Persists the plan for progress tracking.
    """
    try:
        # 110s Timeout guard to ensure we return to frontend before its 120s limit
        async with asyncio.timeout(110):
            return await generate_and_save_roadmap(
                user_id=current_user.id,
                target_role=req.target_role,
                current_skills=req.current_skills,
                db=db,
            )
    except asyncio.TimeoutError:
        logger.error(f"Career Plan generation timed out for user {current_user.id}")
        raise HTTPException(
            status_code=504,
            detail="AI generation is taking longer than expected. Please try again or check back later.",
        )
    except Exception as e:
        logger.error(f"Career Plan generation failed: {str(e)}")
        # SECURITY FIX: Never expose raw exceptions to clients
        raise HTTPException(
            status_code=500,
            detail="Failed to generate career plan. Please try again or contact support.",
        )


async def generate_and_save_roadmap(
    user_id: int, target_role: str, current_skills: list, db: Session
):
    """
    Reusable core logic for roadmap generation.
    """
    # 1. Fetch Context (Courses & Latest Audit)
    courses = db.query(Course).filter(Course.status == "published").all()
    course_list = [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "difficulty": c.difficulty,
        }
        for c in courses
    ]

    # Find latest audit for context (if exists)
    latest_app = (
        db.query(Application)
        .filter(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
        .first()
    )
    audit_context = {}
    if latest_app:
        if latest_app.analysis_json:
            try:
                audit_context = json.loads(latest_app.analysis_json)
            except Exception as e:
                logger.error(f"Error parsing analysis JSON for user {user_id}: {e}")
                pass

        # KEY CHANGE: Inject raw CV text for deeper personalization
        if latest_app.cv_text_anonymized:
            audit_context["cv_raw_text"] = latest_app.cv_text_anonymized[:3000]

        # KEY CHANGE: Inject Interview Performance Data
        if latest_app.interview_log and latest_app.interview_log != "[]":
            try:
                audit_context["interview_log"] = json.loads(latest_app.interview_log)
            except Exception as e:
                logger.error(f"Error parsing interview log for user {user_id}: {e}")
                pass

        # SECURITY: Interview questions and answers intentionally NOT sent to roadmap AI
        # to prevent leaking the question bank through generated roadmap content.
        # Only the interview log (candidate's responses) is provided, not the answer key.
        pass

    # 2. Call AI Service (ASYNC)
    plan_data = await generate_career_roadmap(
        target_role=target_role,
        current_skills=current_skills,
        available_courses=course_list,
        audit_context=audit_context,
    )

    if not plan_data or not plan_data.get("roadmap"):
        return None

    # 3. Persist to DB
    # Deactivate old roadmaps
    db.query(CareerRoadmap).filter(
        CareerRoadmap.user_id == user_id, CareerRoadmap.status == "active"
    ).update({"status": "archived"})

    new_roadmap = CareerRoadmap(
        user_id=user_id,
        target_role=target_role,
        current_skills=json.dumps(current_skills),
        roadmap_json=json.dumps(plan_data),
        status="active",
    )

    db.add(new_roadmap)
    db.commit()
    db.refresh(new_roadmap)

    return plan_data


async def run_proactive_roadmap_generation(user_id: int, target_role: str, db: Session):
    """
    Background Task version of roadmap generation.
    """
    logger.info(f"[PROACTIVE] Starting roadmap generation for user {user_id}")
    # For proactive, we might not have 'current_skills' passed, so we use empty list or try to extract from bio
    user = db.query(User).filter(User.id == user_id).first()
    skills = []
    if user:
        skills_str = get_user_skills(user)
        if skills_str:
            skills = [s.strip() for s in skills_str.split(",") if s.strip()]

    await generate_and_save_roadmap(
        user_id=user_id, target_role=target_role, current_skills=skills, db=db
    )
    logger.info(f"[PROACTIVE] Successfully generated roadmap for user {user_id}")


class ProgressUpdate(BaseModel):
    action_id: str
    completed: bool


@router.put("/plan/active/progress")
def update_progress(
    update: ProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Syncs a checkbox state to the server.
    """
    roadmap = (
        db.query(CareerRoadmap)
        .filter(
            CareerRoadmap.user_id == current_user.id, CareerRoadmap.status == "active"
        )
        .order_by(CareerRoadmap.created_at.desc())
        .first()
    )

    if not roadmap:
        raise HTTPException(status_code=404, detail="No active roadmap found")

    # Update JSON
    try:
        progress = json.loads(roadmap.progress_json) if roadmap.progress_json else {}
    except Exception as e:
        logger.error(f"Error parsing progress JSON for user {current_user.id}: {e}")
        progress = {}

    if update.completed:
        progress[update.action_id] = True
    else:
        progress.pop(update.action_id, None)

    roadmap.progress_json = json.dumps(progress)

    # Update Percentage (Heuristic)
    # Ideally calculate total items from roadmap_json, but for now simple storage is enough

    db.commit()
    return {"status": "synced", "progress_state": progress}


@router.get("/plan/active")
def get_active_plan(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Retrieve the user's current active roadmap.
    """
    roadmap = (
        db.query(CareerRoadmap)
        .filter(
            CareerRoadmap.user_id == current_user.id, CareerRoadmap.status == "active"
        )
        .order_by(CareerRoadmap.created_at.desc())
        .first()
    )

    if not roadmap:
        # Return empty structure or 404
        return {"roadmap": [], "summary": "No active plan found."}

    data = json.loads(roadmap.roadmap_json)
    data["progress_state"] = (
        json.loads(roadmap.progress_json) if roadmap.progress_json else {}
    )
    return data


@router.get("/plan/user/{user_id}")
def get_user_plan(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific user's active roadmap.
    Restricted to: The User themselves OR a Recruiter who owns the candidate's job/campaign.
    """
    # Authorization Check
    if current_user.id != user_id and current_user.role != "recruiter":
        raise HTTPException(
            status_code=403, detail="Not authorized to view this roadmap"
        )

    # If recruiter, verify ownership of candidate's application
    if current_user.role == "recruiter" and current_user.id != user_id:
        from backend.database import Application, BatchJob, Job

        app = db.query(Application).filter(Application.user_id == user_id).first()
        if app:
            is_owner = False
            if app.job_id:
                job = db.query(Job).filter(Job.id == app.job_id).first()
                if job and job.recruiter_id == current_user.id:
                    is_owner = True
            if app.batch_id:
                batch = db.query(BatchJob).filter(BatchJob.id == app.batch_id).first()
                if batch and batch.recruiter_id == current_user.id:
                    is_owner = True
            if not is_owner:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this candidate's roadmap",
                )

    roadmap = (
        db.query(CareerRoadmap)
        .filter(CareerRoadmap.user_id == user_id, CareerRoadmap.status == "active")
        .order_by(CareerRoadmap.created_at.desc())
        .first()
    )

    if not roadmap:
        raise HTTPException(
            status_code=404, detail="No active roadmap found for this candidate"
        )

    data = json.loads(roadmap.roadmap_json)
    data["progress_state"] = (
        json.loads(roadmap.progress_json) if roadmap.progress_json else {}
    )
    return data
