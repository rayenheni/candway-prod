from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import get_current_user, get_db
from backend.profile_helpers import get_user_is_super_admin
from backend.routers.admin.common import check_permission
from backend.services.admin_snapshot_service import AdminSnapshotService

router = APIRouter(tags=["admin"])


@router.get("/interviews/{session_id}/snapshot")
def get_interview_snapshot(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the EvaluationConfigSnapshot used by the given EvaluationSession.

    Admin-only endpoint. Requires the ``view_logs`` permission.
    Tenant isolation: admins can only see snapshots for their own company.
    Super admins bypass tenant isolation.
    """
    check_permission(current_user, "view_logs")
    is_super = get_user_is_super_admin(current_user)
    result = AdminSnapshotService.get_snapshot_for_session(
        db, session_id, current_user.id, is_super_admin=is_super
    )
    return result
