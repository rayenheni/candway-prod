"""P1-06 FIX: GDPR right-to-erasure endpoint.

Allows a user to erase their own data (Art. 17) and lets an admin
trigger an erasure on a user's behalf. The endpoint is
intentionally synchronous for the caller's own row and returns a
report. The full scrub runs in a background task for production
deploys via :func:`backend.gdpr_erasure.request_erasure`.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_current_user, get_db
from backend.gdpr_erasure import request_erasure
from backend.profile_helpers import get_user_admin_permissions, get_user_is_super_admin

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


class ErasureRequest(BaseModel):
    reason: str | None = None
    hard_delete: bool = False


@router.post("/erasure/{user_id}")
def gdpr_erasure(
    user_id: int,
    body: ErasureRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Request erasure of ``user_id``'s data.

    A user may erase their own account (``user_id == current_user.id``).
    An admin with the ``manage_users`` permission may erase any
    user. Anyone else gets a 403.
    """
    is_self = user_id == current_user.id
    is_admin = (
        get_user_is_super_admin(current_user)
        or (get_user_admin_permissions(current_user) or "").find("manage_users") != -1
    )

    if not (is_self or is_admin):
        raise HTTPException(
            status_code=403,
            detail="You can only erase your own data; admins with "
            "manage_users can erase any user.",
        )

    # Admin hard-delete is gated by an explicit body flag so a
    # benign client cannot trigger row deletion by accident.
    if body.hard_delete and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins may hard-delete a user row.",
        )

    requester_role = "admin" if is_admin else "self"
    if body.hard_delete:
        requester_role = "admin_hard_delete"

    # Run the full scrub inline for a single user. For a
    # multi-tenant purge, schedule a background task instead.
    report = request_erasure(
        db,
        user_id=user_id,
        requester_id=current_user.id,
        requester_role=requester_role,
        reason=body.reason,
        hard_delete=body.hard_delete,
    )

    if report.error and report.rows_erased == 0:
        raise HTTPException(
            status_code=500,
            detail=f"Erasure failed: {report.error}",
        )

    return {
        "message": "Erasure completed",
        "report": report.to_dict(),
    }
