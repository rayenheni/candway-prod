from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import SubscriptionPlan, SupportTicket, Ticket, User
from backend.dependencies import get_current_user, get_db
from backend.email_service import email_service
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name
from backend.routers.admin.common import check_permission, paginate
from backend.schemas import TicketReply

router = APIRouter(tags=["admin"])


@router.get("/tickets")
def list_all_tickets(
    status: str = "all",
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all support tickets (the ``Ticket`` table)."""
    check_permission(current_user, "manage_admins")
    query = db.query(Ticket).order_by(Ticket.created_at.desc())
    if status != "all":
        query = query.filter(Ticket.status == status)
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "tickets": [
            {
                "id": t.id,
                "user_id": t.user_id,
                "subject": t.subject,
                "message": t.message,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in result["items"]
        ],
    }


@router.get("/upgrade-requests")
def list_upgrade_requests(
    status: str = "open",
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    query = db.query(SupportTicket).filter(SupportTicket.category == "upgrade")
    if status != "all":
        query = query.filter(SupportTicket.status == status)

    query = query.order_by(SupportTicket.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "upgrade_requests": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_name": get_user_name(r.user) if r.user else "Unknown",
                "user_email": get_user_email(r.user) if r.user else "Unknown",
                "subject": r.subject,
                "description": r.description,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in result["items"]
        ],
    }


@router.post("/upgrade-requests/{ticket_id}/approve")
def approve_upgrade_request(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .with_for_update()
        .first()
    )
    if not ticket or ticket.category != "upgrade":
        raise HTTPException(status_code=404, detail="Upgrade request not found")

    user = db.query(User).filter(User.id == ticket.user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan_name = ticket.subject.replace("UPGRADE REQUEST: ", "").strip()
    try:
        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.name == plan_name)
            .first()
        )
    except Exception as e:
        logger.warning(
            f"Plan lookup by name '{plan_name}' failed: {e}, falling back to slug"
        )
        plan = None

    if not plan:
        try:
            fallback_slug = "pro" if user.role == "recruiter" else "pro-candidate"
            plan = (
                db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.slug == fallback_slug)
                .first()
            )
        except Exception as e:
            logger.error(f"Fallback plan lookup failed: {e}", exc_info=True)
            plan = None

    if not plan:
        raise HTTPException(
            status_code=404, detail="Requested subscription plan not found"
        )

    from backend.models.evaluation.profile import RecruiterProfile

    rp = db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user.id).first()
    if rp:
        rp.tier = "pro"
        rp.subscription_status = "active"
        rp.current_plan_id = plan.id
        rp.subscription_end = datetime.now(UTC) + timedelta(days=365)

    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(UTC)
    ticket.admin_response = (
        f"Your upgrade to {plan.name} has been approved. Enjoy your Pro features!"
    )

    db.commit()

    return {"message": f"User {user.email} upgraded to {plan.name} successfully."}


@router.post("/upgrade-requests/{ticket_id}/reject")
def reject_upgrade_request(
    ticket_id: int,
    reason: str = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_admins")

    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket or ticket.category != "upgrade":
        raise HTTPException(status_code=404, detail="Upgrade request not found")

    ticket.status = "rejected"
    ticket.resolved_at = datetime.now(UTC)
    ticket.admin_response = reason or "Your upgrade request has been declined."

    db.commit()

    return {"message": f"Upgrade request {ticket_id} has been rejected."}


@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(
    ticket_id: int,
    reply: TicketReply,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_support")
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = db.query(User).filter(User.id == ticket.user_id).first()

    if reply.close_ticket:
        ticket.status = "resolved"

    db.commit()

    if user and user.email:
        email_service.send_ticket_reply_email(user.email, ticket.subject, reply.message)

    return {"message": "Reply sent"}
