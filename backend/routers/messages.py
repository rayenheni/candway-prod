"""
Messaging System Router
========================
Full messaging API for candidate-recruiter communication.
Supports 1:1 and group conversations, attachments, read receipts.
"""

import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.database import Conversation, ConversationParticipant, Message, User
from backend.dependencies import (
    get_current_user,
    get_db,
    require_candidate,
    require_recruiter,
)
from backend.realtime import manager as realtime_manager

router = APIRouter(prefix="/messages", tags=["messages"])


# ─── SCHEMAS ───


class ConversationCreate(BaseModel):
    participant_ids: List[int]
    subject: Optional[str] = None
    initial_message: Optional[str] = None


class MessageSend(BaseModel):
    content: str
    content_type: str = "text"
    reply_to_id: Optional[int] = None


class ConversationListResponse(BaseModel):
    id: int
    subject: Optional[str]
    type: str
    last_message_preview: Optional[str]
    last_message_at: datetime
    unread_count: int
    participant: dict  # the "other" participant info


# ─── HELPERS ───


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def _get_other_participant(
    conversation: Conversation, current_user_id: int
) -> Optional[User]:
    """Get the other participant in a direct conversation."""
    for p in conversation.participants:
        if p.user_id != current_user_id and not p.left_at:
            return p.user
    return None


def _serialize_message(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "sender_name": msg.sender.name if msg.sender else "Unknown",
        "sender_avatar": msg.sender.avatar_url if msg.sender else None,
        "content": msg.content,
        "content_type": msg.content_type,
        "attachments": json.loads(msg.attachments) if msg.attachments else [],
        "reply_to_id": msg.reply_to_id,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "created_at": msg.created_at.isoformat(),
        "is_deleted": msg.deleted_at is not None,
    }


def _serialize_conversation(
    conv: Conversation, current_user_id: int, unread_count: int = 0
) -> dict:
    other = _get_other_participant(conv, current_user_id)
    return {
        "id": conv.id,
        "subject": conv.subject,
        "type": conv.type,
        "last_message_preview": conv.last_message_preview,
        "last_message_at": conv.last_message_at.isoformat()
        if conv.last_message_at
        else None,
        "unread_count": unread_count,
        "participant": {
            "id": other.id if other else None,
            "name": other.name if other else "Unknown",
            "role": other.role if other else "user",
            "avatar_url": other.avatar_url if other else None,
        }
        if other
        else None,
        "created_at": conv.created_at.isoformat(),
    }


# ─── ENDPOINTS ───


@router.get("/conversations")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all conversations for the current user, ordered by most recent."""
    participant_rows = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id == current_user.id,
            ConversationParticipant.left_at.is_(None),
        )
        .all()
    )
    conv_ids = [p.conversation_id for p in participant_rows]
    if not conv_ids:
        return []

    conversations = (
        db.query(Conversation)
        .filter(Conversation.id.in_(conv_ids))
        .order_by(desc(Conversation.last_message_at))
        .all()
    )

    results = []
    for conv in conversations:
        unread = 0
        for p in conv.participants:
            if p.user_id == current_user.id:
                unread = (
                    db.query(Message)
                    .filter(
                        Message.conversation_id == conv.id,
                        Message.created_at > (p.last_read_at or conv.created_at),
                        Message.sender_id != current_user.id,
                    )
                    .count()
                )
                break
        results.append(_serialize_conversation(conv, current_user.id, unread))

    return results


@router.get("/users/search")
def search_users(
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search for users to start a conversation with."""
    if not q.strip():
        return []
    target_role = "recruiter" if current_user.role == "candidate" else "candidate"
    query = (
        db.query(User)
        .filter(User.id != current_user.id)
        .filter(User.role == target_role)
        .filter(User.name.ilike(f"%{q}%"))
        .limit(20)
        .all()
    )
    return [
        {
            "id": u.id,
            "name": u.name or "Unknown",
            "role": u.role or "user",
            "avatar_url": u.avatar_url,
            "headline": u.headline,
        }
        for u in query
    ]


@router.post("/conversations", status_code=201)
def create_conversation(
    req: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation with candidates. Recruiters only."""
    if not req.participant_ids:
        raise HTTPException(400, "At least one participant is required")

    # Validate all participants exist
    participants = db.query(User).filter(User.id.in_(req.participant_ids)).all()
    if len(participants) != len(req.participant_ids):
        raise HTTPException(400, "One or more participants not found")

    # Check if a direct conversation already exists between these users
    all_ids = sorted(set(req.participant_ids + [current_user.id]))
    if len(all_ids) == 2:
        existing = (
            db.query(Conversation)
            .join(ConversationParticipant)
            .filter(
                ConversationParticipant.user_id.in_(all_ids),
                Conversation.type == "direct",
            )
            .group_by(Conversation.id)
            .having(func.count(ConversationParticipant.id) == 2)
            .first()
        )
        if existing:
            # Re-join if left
            for p in existing.participants:
                if p.user_id == current_user.id and p.left_at:
                    p.left_at = None
                    p.last_read_at = _utcnow()
            db.commit()
            return _serialize_conversation(existing, current_user.id)

    conv = Conversation(
        subject=req.subject,
        type="direct" if len(all_ids) == 2 else "group",
        last_message_at=_utcnow(),
    )
    db.add(conv)
    db.flush()

    # Add all participants
    for uid in all_ids:
        cp = ConversationParticipant(
            conversation_id=conv.id,
            user_id=uid,
            last_read_at=_utcnow(),
        )
        db.add(cp)

    # Send initial message if provided
    if req.initial_message:
        msg = Message(
            conversation_id=conv.id,
            sender_id=current_user.id,
            content=req.initial_message,
        )
        db.add(msg)
        conv.last_message_preview = req.initial_message[:200]
        conv.last_message_at = _utcnow()

    db.commit()
    db.refresh(conv)

    # Notify other participants via WebSocket
    for uid in all_ids:
        if uid != current_user.id:
            realtime_manager.send_personal_message(
                {
                    "type": "new_conversation",
                    "conversation_id": conv.id,
                },
                uid,
            )

    return _serialize_conversation(conv, current_user.id)


@router.get("/conversations/{conv_id}")
def get_conversation(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation with paginated messages."""
    # Verify access
    participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conv_id,
            ConversationParticipant.user_id == current_user.id,
            ConversationParticipant.left_at.is_(None),
        )
        .first()
    )
    if not participant:
        raise HTTPException(403, "Not a participant in this conversation")

    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id, Message.deleted_at.is_(None))
        .order_by(Message.created_at)
        .limit(100)
        .all()
    )

    other = _get_other_participant(conv, current_user.id)
    return {
        "conversation": _serialize_conversation(conv, current_user.id),
        "other_participant": {
            "id": other.id if other else None,
            "name": other.name if other else "Unknown",
            "role": other.role if other else "user",
            "avatar_url": other.avatar_url if other else None,
            "headline": other.headline if other else None,
        }
        if other
        else None,
        "messages": [_serialize_message(m) for m in messages],
    }


@router.post("/conversations/{conv_id}/messages", status_code=201)
def send_message(
    conv_id: int,
    req: MessageSend,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message in a conversation."""
    participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conv_id,
            ConversationParticipant.user_id == current_user.id,
            ConversationParticipant.left_at.is_(None),
        )
        .first()
    )
    if not participant:
        raise HTTPException(403, "Not a participant in this conversation")

    if not req.content.strip():
        raise HTTPException(400, "Message content is required")

    msg = Message(
        conversation_id=conv_id,
        sender_id=current_user.id,
        content=req.content,
        content_type=req.content_type,
        reply_to_id=req.reply_to_id,
    )
    db.add(msg)

    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    conv.last_message_preview = req.content[:200]
    conv.last_message_at = _utcnow()

    # Auto-mark as read for sender
    participant.last_read_at = _utcnow()

    db.commit()
    db.refresh(msg)

    # Push to other participants via WebSocket
    serialized = _serialize_message(msg)
    for p in conv.participants:
        if p.user_id != current_user.id and not p.left_at:
            realtime_manager.send_personal_message(
                {
                    "type": "new_message",
                    "conversation_id": conv_id,
                    "message": serialized,
                },
                p.user_id,
            )

    return serialized


@router.post("/conversations/{conv_id}/read")
def mark_as_read(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all messages in a conversation as read."""
    participant = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.conversation_id == conv_id,
            ConversationParticipant.user_id == current_user.id,
        )
        .first()
    )
    if not participant:
        raise HTTPException(403, "Not a participant")
    participant.last_read_at = _utcnow()
    db.commit()
    return {"status": "ok"}


@router.delete("/messages/{msg_id}")
def delete_message(
    msg_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a message (only by sender)."""
    msg = db.query(Message).filter(Message.id == msg_id).first()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(403, "Can only delete your own messages")
    msg.deleted_at = _utcnow()
    db.commit()
    return {"status": "deleted"}


@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get total unread message count across all conversations."""
    participants = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id == current_user.id,
            ConversationParticipant.left_at.is_(None),
        )
        .all()
    )
    total = 0
    for p in participants:
        count = (
            db.query(Message)
            .filter(
                Message.conversation_id == p.conversation_id,
                Message.created_at > (p.last_read_at or p.created_at),
                Message.sender_id != current_user.id,
            )
            .count()
        )
        total += count
    return {"unread_count": total}


@router.post("/conversations/with-candidate/{candidate_id}")
def start_conversation_with_candidate(
    candidate_id: int,
    current_user: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """
    Recruiter-facing: start a conversation with a candidate.
    Creates or reuses an existing direct conversation.
    """
    candidate = (
        db.query(User).filter(User.id == candidate_id, User.role == "candidate").first()
    )
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    all_ids = sorted([current_user.id, candidate_id])
    existing = (
        db.query(Conversation)
        .join(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id.in_(all_ids),
            Conversation.type == "direct",
        )
        .group_by(Conversation.id)
        .having(func.count(ConversationParticipant.id) == 2)
        .first()
    )
    if existing:
        for p in existing.participants:
            if p.user_id == current_user.id and p.left_at:
                p.left_at = None
        db.commit()
        return {"conversation_id": existing.id}

    conv = Conversation(type="direct", last_message_at=_utcnow())
    db.add(conv)
    db.flush()
    for uid in all_ids:
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))
    db.commit()
    db.refresh(conv)

    return {"conversation_id": conv.id}


@router.post("/conversations/with-recruiter/{recruiter_id}")
def start_conversation_with_recruiter(
    recruiter_id: int,
    current_user: User = Depends(require_candidate),
    db: Session = Depends(get_db),
):
    """
    Candidate-facing: start a conversation with a recruiter.
    Creates or reuses an existing direct conversation.
    """
    recruiter = (
        db.query(User).filter(User.id == recruiter_id, User.role == "recruiter").first()
    )
    if not recruiter:
        raise HTTPException(404, "Recruiter not found")

    all_ids = sorted([current_user.id, recruiter_id])
    existing = (
        db.query(Conversation)
        .join(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id.in_(all_ids),
            Conversation.type == "direct",
        )
        .group_by(Conversation.id)
        .having(func.count(ConversationParticipant.id) == 2)
        .first()
    )
    if existing:
        for p in existing.participants:
            if p.user_id == current_user.id and p.left_at:
                p.left_at = None
        db.commit()
        return {"conversation_id": existing.id}

    conv = Conversation(type="direct", last_message_at=_utcnow())
    db.add(conv)
    db.flush()
    for uid in all_ids:
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))
    db.commit()
    db.refresh(conv)

    return {"conversation_id": conv.id}
