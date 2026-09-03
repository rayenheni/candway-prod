"""
Candidate Assignment and Interaction API Endpoints
Phase 1 Enhancement - Complete Communication Tracking
"""

from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session, selectinload, undefer

from backend.authz import get_application_for_recruiter
from backend.database import Application, CandidateInteraction, CompanyMember, User
from backend.dependencies import get_db, require_recruiter
from backend.enums import InteractionType
from backend.profile_helpers import get_user_email, get_user_name

router = APIRouter(prefix="/recruiter/candidates", tags=["Candidate Management"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ============================================
# SCHEMAS
# ============================================


class AssignCandidateRequest(BaseModel):
    """Request to assign a candidate to a recruiter"""

    assigned_to_id: int  # User ID of the recruiter to assign to


class BulkAssignRequest(BaseModel):
    """Request to bulk-assign multiple candidates to a recruiter"""

    application_ids: list[int]
    assigned_to_id: int


class CreateInteractionRequest(BaseModel):
    """Request to log a new interaction with a candidate"""

    type: str  # email, call, note, interview, offer, message, meeting
    subject: Optional[str] = None
    content: Optional[str] = None
    direction: Optional[str] = None  # inbound, outbound
    channel: Optional[str] = None  # email, phone, linkedin, whatsapp
    is_automated: bool = False
    parent_interaction_id: Optional[int] = None  # For threading


class InteractionResponse(BaseModel):
    """Response model for interaction"""

    id: int
    type: str
    subject: Optional[str]
    content: Optional[str]
    direction: Optional[str]
    channel: Optional[str]
    is_automated: bool
    created_at: datetime
    user_name: str  # Name of person who created interaction

    model_config = ConfigDict(from_attributes=True)


# ============================================
# ASSIGNMENT ENDPOINTS
# ============================================


@router.post("/{app_id}/assign")
def assign_candidate(
    app_id: int,
    request: AssignCandidateRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Assign a candidate to a specific recruiter.
    Only recruiters and admins can assign candidates.
    SECURITY: Verify ownership of the application before allowing assignment.
    """
    app = get_application_for_recruiter(app_id, recruiter, db)

    # Verify the target user exists and is a recruiter
    target_user = db.query(User).filter(User.id == request.assigned_to_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    if target_user.role not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=400, detail="Can only assign to recruiters or admins"
        )

    # Update assignment
    app.assigned_to = request.assigned_to_id
    app.assigned_at = _utcnow()

    # Log the assignment as an interaction
    interaction = CandidateInteraction(
        application_id=app_id,
        user_id=recruiter.id,
        company_id=app.company_id,
        type="note",
        subject="Candidate Assigned",
        content=f"Assigned to {get_user_name(target_user) or get_user_email(target_user)}",
        is_automated=False,
    )
    db.add(interaction)

    db.commit()
    db.refresh(app)

    return {
        "message": "Candidate assigned successfully",
        "assigned_to": {
            "id": target_user.id,
            "name": get_user_name(target_user),
            "email": get_user_email(target_user),
        },
        "assigned_at": app.assigned_at,
    }


class AssignResult(BaseModel):
    application_id: int
    success: bool
    error: str | None = None


@router.post("/bulk-assign")
def bulk_assign_candidates(
    request: BulkAssignRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Bulk-assign multiple candidates to a recruiter.
    Uses a single transaction; partial failures are reported per-application.
    """
    if not request.application_ids:
        raise HTTPException(status_code=400, detail="No application IDs provided")

    target_user = db.query(User).filter(User.id == request.assigned_to_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    if target_user.role not in ("recruiter", "admin"):
        raise HTTPException(
            status_code=400, detail="Can only assign to recruiters or admins"
        )

    # Fetch all apps in one query — tenant isolation applied per-app
    apps = (
        db.query(Application).filter(Application.id.in_(request.application_ids)).all()
    )
    found_ids = {a.id for a in apps}
    missing = [aid for aid in request.application_ids if aid not in found_ids]

    # Validate tenant ownership for each found application
    results: List[AssignResult] = []
    valid_apps = []
    for app in apps:
        try:
            owned = get_application_for_recruiter(app.id, recruiter, db)
            valid_apps.append(owned)
            results.append(AssignResult(application_id=app.id, success=True))
        except HTTPException:
            results.append(
                AssignResult(
                    application_id=app.id,
                    success=False,
                    error="Not found or tenant mismatch",
                )
            )

    for mid in missing:
        results.append(
            AssignResult(
                application_id=mid, success=False, error="Application not found"
            )
        )

    if not valid_apps:
        db.rollback()
        return {"results": results, "total_assigned": 0}

    # Bulk update
    now = _utcnow()
    db.execute(
        sa_update(Application)
        .where(Application.id.in_([a.id for a in valid_apps]))
        .values(assigned_to=request.assigned_to_id, assigned_at=now)
    )

    # Log interactions
    for app in valid_apps:
        db.add(
            CandidateInteraction(
                application_id=app.id,
                user_id=recruiter.id,
                company_id=app.company_id,
                type="note",
                subject="Candidate Assigned",
                content=f"Assigned to {get_user_name(target_user) or get_user_email(target_user)} (bulk)",
                is_automated=False,
            )
        )

    db.commit()

    return {
        "results": results,
        "total_assigned": len(valid_apps),
        "total_requested": len(request.application_ids),
        "assigned_to": {
            "id": target_user.id,
            "name": get_user_name(target_user),
            "email": get_user_email(target_user),
        },
    }


@router.delete("/{app_id}/assign")
def unassign_candidate(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Remove assignment from a candidate.
    """
    app = get_application_for_recruiter(app_id, recruiter, db)

    if not app.assigned_to:
        raise HTTPException(status_code=400, detail="Candidate is not assigned")

    # Log the unassignment
    interaction = CandidateInteraction(
        application_id=app_id,
        user_id=recruiter.id,
        company_id=app.company_id,
        type="note",
        subject="Candidate Unassigned",
        content="Assignment removed",
        is_automated=False,
    )
    db.add(interaction)

    # Remove assignment
    app.assigned_to = None
    app.assigned_at = None

    db.commit()

    return {"message": "Candidate unassigned successfully"}


@router.get("/{app_id}/assignment")
def get_candidate_assignment(
    app_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Get current assignment status of a candidate.
    """
    app = get_application_for_recruiter(app_id, recruiter, db)

    if not app.assigned_to:
        return {"assigned": False, "assigned_to": None, "assigned_at": None}

    assigned_user = db.query(User).filter(User.id == app.assigned_to).first()

    return {
        "assigned": True,
        "assigned_to": {
            "id": assigned_user.id,
            "name": get_user_name(assigned_user),
            "email": get_user_email(assigned_user),
        },
        "assigned_at": app.assigned_at,
    }


# ============================================
# INTERACTION ENDPOINTS
# ============================================


@router.get("/{app_id}/interactions")
def get_candidate_interactions(
    app_id: int,
    interaction_type: Optional[str] = None,
    limit: int = 50,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Get all interactions for a candidate.
    Returns chronological timeline of all touchpoints.
    """
    _app = get_application_for_recruiter(app_id, recruiter, db)

    # Build query
    query = db.query(CandidateInteraction).filter(
        CandidateInteraction.application_id == app_id
    )

    # Filter by type if specified
    if interaction_type:
        query = query.filter(CandidateInteraction.type == interaction_type)

    # Order by most recent first
    interactions = (
        query.order_by(CandidateInteraction.created_at.desc()).limit(limit).all()
    )

    # Format response with user details
    results = []
    for interaction in interactions:
        user = db.query(User).filter(User.id == interaction.user_id).first()

        results.append(
            {
                "id": interaction.id,
                "type": interaction.type,
                "subject": interaction.subject,
                "content": interaction.content,
                "direction": interaction.direction,
                "channel": interaction.channel,
                "is_automated": interaction.is_automated,
                "created_at": interaction.created_at,
                "user": {
                    "id": user.id if user else None,
                    "name": get_user_name(user) if user else "System",
                    "email": get_user_email(user) if user else None,
                },
                "parent_interaction_id": interaction.parent_interaction_id,
            }
        )

    return {
        "application_id": app_id,
        "total_interactions": len(results),
        "interactions": results,
    }


@router.post("/{app_id}/interactions")
def create_candidate_interaction(
    app_id: int,
    request: CreateInteractionRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Log a new interaction with a candidate.
    Use this to track emails, calls, notes, meetings, etc.
    """
    app = get_application_for_recruiter(app_id, recruiter, db)

    # Validate interaction type
    valid_types = [t.value for t in InteractionType]
    if request.type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interaction type. Must be one of: {', '.join(valid_types)}",
        )

    # Create interaction
    interaction = CandidateInteraction(
        application_id=app_id,
        user_id=recruiter.id,
        company_id=app.company_id,
        type=request.type,
        subject=request.subject,
        content=request.content,
        direction=request.direction,
        channel=request.channel,
        is_automated=request.is_automated,
        parent_interaction_id=request.parent_interaction_id,
    )

    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    return {
        "message": "Interaction logged successfully",
        "interaction": {
            "id": interaction.id,
            "type": interaction.type,
            "subject": interaction.subject,
            "created_at": interaction.created_at,
            "user": {
                "id": recruiter.id,
                "name": get_user_name(recruiter),
                "email": get_user_email(recruiter),
            },
        },
    }


@router.get("/{app_id}/interactions/{interaction_id}")
def get_interaction_details(
    app_id: int,
    interaction_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific interaction.
    """
    get_application_for_recruiter(app_id, recruiter, db)
    interaction = (
        db.query(CandidateInteraction)
        .filter(
            CandidateInteraction.id == interaction_id,
            CandidateInteraction.application_id == app_id,
        )
        .first()
    )

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")

    user = db.query(User).filter(User.id == interaction.user_id).first()

    # Get replies if this is a parent interaction
    replies = (
        db.query(CandidateInteraction)
        .filter(CandidateInteraction.parent_interaction_id == interaction_id)
        .order_by(CandidateInteraction.created_at.asc())
        .all()
    )

    return {
        "id": interaction.id,
        "type": interaction.type,
        "subject": interaction.subject,
        "content": interaction.content,
        "direction": interaction.direction,
        "channel": interaction.channel,
        "is_automated": interaction.is_automated,
        "created_at": interaction.created_at,
        "user": {
            "id": user.id if user else None,
            "name": get_user_name(user) if user else "System",
            "email": get_user_email(user) if user else None,
        },
        "parent_interaction_id": interaction.parent_interaction_id,
        "replies": [
            {
                "id": r.id,
                "content": r.content,
                "created_at": r.created_at,
                "user_id": r.user_id,
            }
            for r in replies
        ],
    }


@router.get("/assigned-to-me")
def get_my_assigned_candidates(
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Get all candidates assigned to the current recruiter.
    Supports filtering by status and pagination.
    """
    from backend.dependencies import get_pagination_meta, paginate

    # Build query
    company_id = getattr(recruiter, "_company_id", None)
    query = (
        db.query(Application)
        .options(selectinload(Application.evaluation_sessions))
        .filter(
            Application.assigned_to == recruiter.id,
            Application.company_id == company_id,
        )
    )

    # Filter by status if provided
    if status:
        query = query.filter(Application.status == status)

    # Get total count
    total_count = query.count()

    # Get paginated results
    query = query.order_by(Application.assigned_at.desc())
    applications = paginate(query, page, per_page).all()

    # Format response
    results = []
    for app in applications:
        _er_cm = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        results.append(
            {
                "id": app.id,
                "full_name": app.full_name,
                "email": app.email,
                "declared_role": app.declared_role,
                "status": app.status,
                "overall_score": _er_cm.final_score if _er_cm else None,
                "assigned_at": app.assigned_at,
                "created_at": app.created_at,
            }
        )

    return {
        "candidates": results,
        "pagination": get_pagination_meta(total_count, page, per_page),
    }


@router.get("")
def list_recruiter_candidates(
    status: Optional[str] = Query(None, description="Filter by application status"),
    job_id: Optional[int] = Query(None, description="Filter by job ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    List all candidates for jobs owned by the recruiter.
    Returns candidates with their job title and application status.
    """
    from backend.database import Job
    from backend.dependencies import get_pagination_meta, paginate

    # Get all job IDs owned by this recruiter
    company_id = getattr(recruiter, "_company_id", None)
    job_ids = (
        db.query(Job.id)
        .join(CompanyMember, CompanyMember.user_id == Job.recruiter_id)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.is_active,
        )
        .all()
    )
    job_ids = [j.id for j in job_ids]

    if not job_ids:
        return {
            "candidates": [],
            "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0},
        }

    # Build query for applications to these jobs
    query = (
        db.query(Application)
        .options(
            selectinload(Application.evaluation_sessions),
            undefer(Application.decline_reason),
        )
        .filter(Application.job_id.in_(job_ids))
    )

    # Apply filters
    if status:
        # Bug U-07: accept "declined" as an alias for "rejected" so
        # the recruiter UI can filter by a friendly label without
        # having to know the internal status enum.
        if status == "declined":
            query = query.filter(Application.status == "rejected")
        else:
            query = query.filter(Application.status == status)
    if job_id:
        query = query.filter(Application.job_id == job_id)

    # Get total count
    total_count = query.count()

    # Get paginated results with job info
    applications = paginate(
        query.order_by(Application.created_at.desc()), page, per_page
    ).all()

    # Fetch job titles
    job_map = {
        j.id: j
        for j in db.query(Job)
        .filter(Job.id.in_([app.job_id for app in applications]))
        .all()
    }

    results = []
    for app in applications:
        job = job_map.get(app.job_id)
        # Bug U-07: include structured decline metadata so the
        # recruiter UI can render a "Declined — reason: X" badge
        # without having to parse recruiter_notes.
        is_declined = (app.status == "rejected") or bool(app.declined_at)
        decline_reason = app.decline_reason if is_declined else None
        declined_at = (
            app.declined_at.isoformat() if is_declined and app.declined_at else None
        )
        _er_lr = (
            app.evaluation_sessions[0].evaluation_result
            if app.evaluation_sessions and app.evaluation_sessions[0].evaluation_result
            else None
        )
        results.append(
            {
                "id": app.id,
                "full_name": app.full_name,
                "email": app.email,
                "phone": app.phone,
                "declared_role": app.declared_role,
                "status": app.status,
                "is_declined": is_declined,
                "decline_reason": decline_reason,
                "declined_at": declined_at,
                "overall_score": _er_lr.final_score if _er_lr else None,
                "job_id": app.job_id,
                "job_title": job.title if job else None,
                "company": job.company_name if job else None,
                "created_at": app.created_at,
                "updated_at": app.updated_at,
            }
        )

    return {
        "candidates": results,
        "pagination": get_pagination_meta(total_count, page, per_page),
    }
