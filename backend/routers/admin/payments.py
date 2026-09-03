from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from backend.database import AuditLog, Course, Enrollment, PayoutRequest, User
from backend.dependencies import get_current_user, get_db
from backend.email_service import email_service
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name
from backend.routers.admin.common import check_permission, paginate
from backend.routers.admin.invoices import _create_invoice_internal

router = APIRouter(tags=["admin"])


@router.get("/payments")
def get_pending_payments(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    try:
        query = (
            db.query(Enrollment)
            .options(joinedload(Enrollment.user), joinedload(Enrollment.course))
            .filter(Enrollment.status == "pending_approval")
        )
        result = paginate(query, page, per_page)
        return {
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "total_pages": result["total_pages"],
            "payments": [
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "course_id": p.course_id,
                    "user_name": get_user_name(p.user) if p.user else "Unknown",
                    "user_email": get_user_email(p.user) if p.user else "Unknown",
                    "course_title": p.course.title if p.course else "Unknown",
                    "amount": p.amount_paid,
                    "proof_url": p.proof_url,
                    "date": p.enrolled_at,
                }
                for p in result["items"]
            ],
        }
    except Exception as e:
        logger.error(f"Failed to fetch pending payments: {e}", exc_info=True)
        return {"total": 0, "page": 1, "per_page": 30, "total_pages": 0, "payments": []}


@router.post("/payments/{enrollment_id}/approve")
def approve_payment(
    enrollment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    P0-05 FIX: Idempotent payment approval.

    Mirrors the Transaction logic: lock the row, check the current
    status, refuse to double-apply, and support the Idempotency-Key
    header for safe network retries.
    """
    check_permission(current_user, "manage_finance")
    idempotency_key = request.headers.get("Idempotency-Key")

    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.id == enrollment_id)
        .with_for_update()
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if idempotency_key and enrollment.idempotency_key == idempotency_key:
        return {
            "message": "Payment approved (idempotent replay)",
            "idempotent": True,
        }

    if enrollment.status == "active":
        if enrollment.approved_at and enrollment.approved_by:
            return {
                "message": "Payment already approved",
                "approved_at": enrollment.approved_at.isoformat(),
                "approved_by": enrollment.approved_by,
                "idempotent": True,
            }
        enrollment.approved_at = datetime.now(UTC)
        enrollment.approved_by = current_user.id
        if idempotency_key:
            enrollment.idempotency_key = idempotency_key
        db.commit()
        return {
            "message": "Payment already approved (metadata backfilled)",
            "idempotent": True,
        }

    if enrollment.status == "rejected":
        raise HTTPException(
            status_code=409,
            detail=(
                "Enrollment is in a terminal 'rejected' state. Create a "
                "new enrollment to retry."
            ),
        )

    enrollment.status = "active"
    enrollment.approved_at = datetime.now(UTC)
    enrollment.approved_by = current_user.id
    if idempotency_key:
        enrollment.idempotency_key = idempotency_key

    audit = AuditLog(
        user_id=current_user.id,
        action="approve_payment",
        target_id=str(enrollment_id),
        details=f"Admin {get_user_email(current_user)} approved payment for enrollment #{enrollment_id}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()

    try:
        _create_invoice_internal(db, enrollment.user_id, enrollment.amount_paid, company_id=enrollment.company_id)
    except Exception as inv_e:
        logger.error(
            f"Failed to generate auto-invoice for enrollment {enrollment_id}: {inv_e}"
        )

    user = db.query(User).filter(User.id == enrollment.user_id).first()
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if user and course:
        email_service.send_payment_status_email(user, "active", course.title)

    return {"message": "Payment approved"}


@router.post("/payments/{enrollment_id}/reject")
def reject_payment(
    enrollment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    idempotency_key = request.headers.get("Idempotency-Key")
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.id == enrollment_id)
        .with_for_update()
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if idempotency_key and enrollment.idempotency_key == idempotency_key:
        return {
            "message": "Payment rejected (idempotent replay)",
            "idempotent": True,
        }

    if enrollment.status == "active":
        raise HTTPException(
            status_code=409,
            detail="Payment is already approved. Create a new enrollment to retry.",
        )
    if enrollment.status == "rejected" and enrollment.rejected_at:
        return {
            "message": "Payment already rejected",
            "rejected_at": enrollment.rejected_at.isoformat(),
            "rejected_by": enrollment.rejected_by,
            "idempotent": True,
        }

    enrollment.status = "rejected"
    enrollment.rejected_at = datetime.now(UTC)
    enrollment.rejected_by = current_user.id
    if idempotency_key:
        enrollment.idempotency_key = idempotency_key

    audit = AuditLog(
        user_id=current_user.id,
        action="reject_payment",
        target_id=str(enrollment_id),
        details=f"Admin {get_user_email(current_user)} rejected payment for enrollment #{enrollment_id}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()

    user = db.query(User).filter(User.id == enrollment.user_id).first()
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if user and course:
        email_service.send_payment_status_email(user, "rejected", course.title)

    return {"message": "Payment rejected"}


@router.get("/payouts")
def get_payouts(
    status: str = "pending",
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    try:
        query = db.query(PayoutRequest)
        if status != "all":
            query = query.filter(PayoutRequest.status == status)
        result = paginate(query, page, per_page)
        return {
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "total_pages": result["total_pages"],
            "payouts": [
                {
                    "id": p.id,
                    "mentor_id": p.mentor_id,
                    "amount": p.amount,
                    "currency": p.currency,
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "processed_at": p.processed_at.isoformat()
                    if p.processed_at
                    else None,
                }
                for p in result["items"]
            ],
        }
    except Exception as e:
        logger.error(f"Payouts error: {e}", exc_info=True)
        return {"total": 0, "page": 1, "per_page": 30, "total_pages": 0, "payouts": []}


@router.post("/payouts/{payout_id}/pay")
def mark_payout_paid(
    payout_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_finance")
    payout = (
        db.query(PayoutRequest)
        .filter(PayoutRequest.id == payout_id)
        .with_for_update()
        .first()
    )
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    payout.status = "paid"
    payout.processed_at = datetime.now(UTC)

    audit = AuditLog(
        user_id=current_user.id,
        action="mark_payout_paid",
        target_id=str(payout_id),
        details=f"Admin {get_user_email(current_user)} marked payout #{payout_id} as paid",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": "Paid"}
