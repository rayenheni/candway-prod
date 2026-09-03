from typing import List, Optional
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.authz import get_batch_for_recruiter
from backend.database import CompanyMember, User
from backend.dependencies import get_db, require_recruiter
from backend.logger import logger
from backend.profile_helpers import get_user_name

from . import router


class TeamMemberResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    role: str
    is_active: bool
    joined_at: Optional[str] = None


class AddTeamMemberRequest(BaseModel):
    email: str
    role: str = "member"  # admin, member, viewer


@router.get("/{batch_id}/team")
def get_campaign_team(
    batch_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """List team members associated with the company managing this campaign."""
    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    company_id = batch.company_id

    members = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == company_id, CompanyMember.is_active.is_(True))
        .all()
    )

    res = []
    for cm in members:
        user = cm.user
        if not user:
            continue
        res.append({
            "id": cm.id,
            "user_id": user.id,
            "name": get_user_name(user),
            "email": user.email,
            "role": cm.role or "member",
            "is_active": cm.is_active,
            "joined_at": cm.joined_at.isoformat() if cm.joined_at else (cm.created_at.isoformat() if cm.created_at else None),
        })

    return {"team": res, "campaign_id": batch_id, "campaign_title": batch.title}


@router.post("/{batch_id}/team")
def add_campaign_team_member(
    batch_id: int,
    payload: AddTeamMemberRequest,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Add or update a team member's role for the company managing this campaign."""
    batch = get_batch_for_recruiter(batch_id, recruiter, db)
    company_id = batch.company_id

    email = payload.email.lower().strip()
    target_user = db.query(User).filter(User.email == email).first()

    if not target_user:
        raise HTTPException(
            status_code=404,
            detail=f"User with email '{email}' not found. Please ask them to sign up first.",
        )

    member = (
        db.query(CompanyMember)
        .filter(
            CompanyMember.company_id == company_id,
            CompanyMember.user_id == target_user.id,
        )
        .first()
    )

    if member:
        member.role = payload.role
        member.is_active = True
        db.commit()
        return {
            "success": True,
            "message": f"Updated role to '{payload.role}' for {target_user.email}.",
            "member_id": member.id,
        }

    new_member = CompanyMember(
        company_id=company_id,
        user_id=target_user.id,
        role=payload.role,
        is_active=True,
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return {
        "success": True,
        "message": f"Added {target_user.email} to the campaign team as '{payload.role}'.",
        "member_id": new_member.id,
    }
