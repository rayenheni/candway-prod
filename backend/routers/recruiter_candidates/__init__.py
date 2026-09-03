from fastapi import APIRouter

from backend.routers.recruiter_candidates.applications import (
    router as applications_router,
)
from backend.routers.recruiter_candidates.email import router as email_router
from backend.routers.recruiter_candidates.integrations import (
    router as integrations_router,
)
from backend.routers.recruiter_candidates.invitations import (
    router as invitations_router,
)
from backend.routers.recruiter_candidates.scoring import router as scoring_router
from backend.routers.recruiter_candidates.search import router as search_router

router = APIRouter(prefix="/recruiter", tags=["Recruiter Candidates"])

router.include_router(applications_router)
router.include_router(email_router)
router.include_router(integrations_router)
router.include_router(invitations_router)
router.include_router(scoring_router)
router.include_router(search_router)
