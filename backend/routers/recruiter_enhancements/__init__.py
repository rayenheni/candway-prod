from fastapi import APIRouter

router = APIRouter(
    prefix="/recruiter/enhancements", tags=["Recruiter Enhancements v5.0"]
)

from backend.routers.recruiter_enhancements import (  # noqa: E402
    actions,
    analytics,
    automation,
    notes,
    previews,
    scorecards,
    stages,
    webhook_events,
    webhooks,
)

router.include_router(actions.router)
router.include_router(previews.router)
router.include_router(stages.router)
router.include_router(automation.router)
router.include_router(notes.router)
router.include_router(scorecards.router)
router.include_router(webhooks.router)
router.include_router(webhook_events.router)
router.include_router(analytics.router)

__all__ = ["router"]
