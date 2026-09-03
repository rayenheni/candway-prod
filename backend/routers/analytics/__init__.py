from fastapi import APIRouter

router = APIRouter()

from .insights import router as insights_router  # noqa: E402
from .monitoring import router as monitoring_router  # noqa: E402
from .reports import router as reports_router  # noqa: E402

router.include_router(insights_router)
router.include_router(reports_router)
router.include_router(monitoring_router)
