from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import SupportTicket, User
from backend.dependencies import get_current_user, get_db
from backend.email_service import email_service
from backend.profile_helpers import get_user_email

router = APIRouter(prefix="/support", tags=["support"])

import logging  # noqa: E402

logger = logging.getLogger(__name__)


# Schemas
class TicketCreate(BaseModel):
    subject: str
    category: str  # 'bug', 'feature', 'account', 'other'
    priority: str = "medium"  # 'low', 'medium', 'high'
    description: str


class TicketResponse(BaseModel):
    id: int
    subject: str
    category: str
    priority: str
    status: str
    created_at: str
    has_response: bool
    admin_response: Optional[str] = None


@router.post("/tickets")
async def create_ticket(
    ticket: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new support ticket.
    Candidates can report bugs, request features, or get help with account issues.
    """
    try:
        # Validate category
        valid_categories = ["bug", "feature", "account", "other"]
        if ticket.category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {valid_categories}",
            )

        # Validate priority
        valid_priorities = ["low", "medium", "high"]
        if ticket.priority not in valid_priorities:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority. Must be one of: {valid_priorities}",
            )

        # Create ticket
        new_ticket = SupportTicket(
            user_id=current_user.id,
            subject=ticket.subject,
            category=ticket.category,
            priority=ticket.priority,
            description=ticket.description,
            status="open",
        )

        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)

        logger.info(
            f"Support ticket created: ticket_id={new_ticket.id}, "
            f"user_id={current_user.id}, category={ticket.category}, "
            f"priority={ticket.priority}"
        )

        # Send email notification to admin
        try:
            # Fetch all admins
            admins = db.query(User).filter(User.role == "admin").all()
            for admin in admins:
                if admin.email:
                    email_service.send_email(
                        admin.email,
                        f"New Support Ticket: {ticket.subject} ({ticket.priority.upper()})",
                        f"User {get_user_email(current_user)} submitted a ticket:\n\n{ticket.description}\n\nCategory: {ticket.category}",
                    )
        except Exception as e:
            logger.error(f"Failed to notify admins of new ticket: {e}")

        return {
            "success": True,
            "ticket_id": new_ticket.id,
            "message": "Support ticket created successfully. Our team will respond soon.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating support ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create support ticket")


@router.get("/tickets/me")
async def get_my_tickets(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get all support tickets for the current user.
    Returns tickets ordered by creation date (newest first).
    """
    try:
        tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == current_user.id)
            .order_by(SupportTicket.created_at.desc())
            .all()
        )

        return [
            {
                "id": t.id,
                "subject": t.subject,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                "has_response": t.admin_response is not None,
                "admin_response": t.admin_response,
            }
            for t in tickets
        ]

    except Exception as e:
        logger.error(f"Error fetching support tickets: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch support tickets")


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific support ticket by ID"""
    ticket = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.id == ticket_id,
            SupportTicket.user_id == current_user.id,  # Ensure user owns the ticket
        )
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "description": ticket.description,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "admin_response": ticket.admin_response,
    }
