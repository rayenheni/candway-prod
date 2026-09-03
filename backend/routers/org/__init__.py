"""Organization portal routers (org admin surface)."""

from fastapi import APIRouter

from backend.routers.org import analytics, billing, members

router = APIRouter()
router.include_router(members.router)
router.include_router(analytics.router)
router.include_router(billing.router)
