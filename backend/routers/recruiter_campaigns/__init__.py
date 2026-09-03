from fastapi import APIRouter

router = APIRouter(prefix="/recruiter/campaigns", tags=["Recruiter Campaigns"])

# Import sub-modules to register routes on the shared router
from . import (  # noqa: E402
    candidates,  # noqa: F401, E402
    management,  # noqa: F401, E402
    team,  # noqa: F401, E402
    templates,  # noqa: F401, E402
    tracking,  # noqa: F401, E402
    upload,  # noqa: F401, E402
)
