from fastapi import APIRouter

router = APIRouter(prefix="/recruiter/collaboration", tags=["Recruiter Collaboration"])

from backend.routers.recruiter_collaboration import (  # noqa: E402
    activity,
    comments,
    ratings,
    team,
)

router.include_router(comments.router)
router.include_router(ratings.router)
router.include_router(activity.router)
router.include_router(team.router)

__all__ = ["router"]
