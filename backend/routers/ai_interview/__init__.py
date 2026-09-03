# Re-exports for external code (imported BEFORE sub-modules to break circular imports)
from fastapi import APIRouter

from backend.routers.ai_interview.chat import (
    router as chat_router,
    generate_skill_driven_turn,
)
from backend.routers.ai_interview.evaluation import router as evaluation_router
from backend.routers.ai_interview.media import router as media_router
from backend.routers.ai_interview.questions import router as questions_router
from backend.routers.ai_interview.session import router as session_router
from backend.routers.ai_interview.utils import (
    _extract_cv_focus_terms,
    _get_graceful_fallback,
    safe_user_role,
    strip_prompt_injections,
)

__all__ = [
    "chat_router",
    "generate_skill_driven_turn",
    "evaluation_router",
    "media_router",
    "questions_router",
    "session_router",
    "_extract_cv_focus_terms",
    "_get_graceful_fallback",
    "safe_user_role",
    "strip_prompt_injections",
]

router = APIRouter(prefix="/ai", tags=["ai-interview"])
router.include_router(questions_router)
router.include_router(media_router)
router.include_router(evaluation_router)
router.include_router(chat_router)
router.include_router(session_router)
