from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import Announcement, AuditLog, CompanyVerification, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.profile_helpers import get_user_name
from backend.routers.admin.common import check_permission, paginate
from backend.schemas import AnnouncementCreate

router = APIRouter(tags=["admin"])


@router.get("/verifications")
def get_pending_verifications(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")
    query = db.query(CompanyVerification).filter(
        CompanyVerification.status == "pending"
    )
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "verifications": result["items"],
    }


@router.post("/verifications/{v_id}/approve")
def approve_verification(
    v_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")
    verification = (
        db.query(CompanyVerification).filter(CompanyVerification.id == v_id).first()
    )
    if not verification:
        raise HTTPException(status_code=404, detail="Verification request not found")

    verification.status = "approved"
    verification.verified_at = datetime.now(UTC)
    verification.verified_by = current_user.id

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="approve_verification",
            details=f"Approved company {verification.company_name} (MF: {verification.matricule_fiscale})",
            target_id=str(verification.user_id),
        )
    )

    db.commit()

    try:
        recruiter = db.query(User).filter(User.id == verification.user_id).first()
        if recruiter and recruiter.email:
            from backend.email_service import email_service

            subject = "Company Verification Approved - Candway"
            body = f"""
Dear {get_user_name(recruiter)},

Great news! Your company verification has been approved.

Company Details:
- Name: {verification.company_name}
- Matricule Fiscale: {verification.matricule_fiscale}

You now have full access to all recruiter features on the Candway platform.

Best regards,
The Candway Team
            """
            email_service.send_email(recruiter.email, subject, body)
            logger.info(f"Verification approval email sent to {recruiter.email}")
    except Exception as e:
        logger.error(f"Failed to send verification approval email: {e}")

    return {"message": "Company verified successfully"}


@router.post("/verifications/{v_id}/reject")
def reject_verification(
    v_id: int,
    reason: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")
    verification = (
        db.query(CompanyVerification).filter(CompanyVerification.id == v_id).first()
    )
    if not verification:
        raise HTTPException(status_code=404, detail="Verification request not found")

    verification.status = "rejected"
    verification.admin_notes = reason
    verification.verified_at = datetime.now(UTC)
    verification.verified_by = current_user.id

    db.commit()

    try:
        recruiter = db.query(User).filter(User.id == verification.user_id).first()
        if recruiter and recruiter.email:
            from backend.email_service import email_service

            subject = "Company Verification Update - Candway"
            body = f"""
Dear {get_user_name(recruiter)},

We regret to inform you that your company verification request has been rejected.

Company: {verification.company_name}
Reason: {reason}

If you believe this is an error or have questions, please contact our support team.

Best regards,
The Candway Team
            """
            email_service.send_email(recruiter.email, subject, body)
            logger.info(f"Verification rejection email sent to {recruiter.email}")
    except Exception as e:
        logger.error(f"Failed to send verification rejection email: {e}")

    return {"message": "Company verification rejected"}


@router.post("/announcements")
def create_announcement(
    announcement: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    new_announcement = Announcement(
        title=announcement.title,
        message=announcement.message,
        type=announcement.type,
        target_role=announcement.target_role,
        expires_at=announcement.expires_at,
        created_by=current_user.id,
    )
    db.add(new_announcement)
    db.commit()
    return {"message": "Announcement broadcasted"}


@router.put("/announcements/{announcement_id}")
def update_announcement(
    announcement_id: int,
    announcement: AnnouncementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    existing = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    existing.title = announcement.title
    existing.message = announcement.message
    existing.type = announcement.type
    existing.target_role = announcement.target_role
    existing.expires_at = announcement.expires_at
    db.commit()
    return {"message": "Announcement updated", "id": existing.id}


@router.post("/announcements/{announcement_id}/archive")
def archive_announcement(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    existing = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    existing.is_active = not existing.is_active
    db.commit()
    return {
        "message": "Announcement archived",
        "id": existing.id,
        "is_active": existing.is_active,
    }


@router.get("/announcements")
def get_all_announcements(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Announcement).order_by(Announcement.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "announcements": result["items"],
    }


@router.get("/announcements/active")
def get_active_announcements(
    page: int = 1,
    per_page: int = 30,
    db: Session = Depends(get_db),
):
    now = datetime.now(UTC)
    query = (
        db.query(Announcement)
        .filter(
            Announcement.is_active,
            ((Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)),
        )
        .order_by(Announcement.created_at.desc())
    )
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "announcements": result["items"],
    }
