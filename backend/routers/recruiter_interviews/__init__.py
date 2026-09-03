from fastapi import APIRouter

router = APIRouter(prefix="/recruiter/interviews", tags=["Interview Scheduling"])

from . import (  # noqa: E402
    feedback,  # noqa: F401, E402
    scheduling,  # noqa: F401, E402
    management,  # noqa: F401, E402
)
