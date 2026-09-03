import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from backend.authz import get_application_for_recruiter
from backend.database import (
    ActivityLog,
    TaggedNote,
    User,
)
from backend.dependencies import get_db, require_recruiter
from backend.security import sanitize_content

router = APIRouter(tags=["Recruiter Enhancements - Tagged Notes"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class TaggedNoteCreate(BaseModel):
    application_id: int
    content: str
    tags: List[str] = []
    priority: str = "normal"


class TaggedNoteUpdate(BaseModel):
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_resolved: Optional[bool] = None


@router.get("/notes/{application_id}")
def get_tagged_notes(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Get all tagged notes for an application"""
    get_application_for_recruiter(application_id, recruiter, db)

    notes = (
        db.query(TaggedNote)
        .options(joinedload(TaggedNote.author))
        .filter(TaggedNote.application_id == application_id)
        .order_by(desc(TaggedNote.is_pinned), desc(TaggedNote.created_at))
        .all()
    )

    return [
        {
            "id": n.id,
            "application_id": n.application_id,
            "author_name": n.author.name if n.author else "Unknown",
            "content": n.content,
            "tags": json.loads(n.tags) if n.tags else [],
            "priority": n.priority,
            "is_pinned": n.is_pinned,
            "is_resolved": n.is_resolved,
            "resolved_at": n.resolved_at.isoformat() if n.resolved_at else None,
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n in notes
    ]


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def create_tagged_note(
    data: TaggedNoteCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Create a tagged note on an application"""
    app = get_application_for_recruiter(data.application_id, recruiter, db)

    note = TaggedNote(
        application_id=data.application_id,
        user_id=recruiter.id,
        company_id=app.company_id,
        content=sanitize_content(data.content),
        tags=json.dumps(data.tags),
        priority=data.priority,
    )
    db.add(note)

    # Log activity
    log = ActivityLog(
        user_id=recruiter.id,
        company_id=app.company_id,
        action="note_added",
        application_id=data.application_id,
        details=json.dumps({"tags": data.tags, "priority": data.priority}),
    )
    db.add(log)

    db.commit()
    db.refresh(note)

    return {"success": True, "note_id": note.id}


@router.patch("/notes/{note_id}")
def update_tagged_note(
    note_id: int,
    data: TaggedNoteUpdate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Update a tagged note"""
    note = (
        db.query(TaggedNote)
        .filter(TaggedNote.id == note_id, TaggedNote.user_id == recruiter.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if data.content is not None:
        note.content = sanitize_content(data.content)
    if data.tags is not None:
        note.tags = json.dumps(data.tags)
    if data.priority is not None:
        note.priority = data.priority
    if data.is_pinned is not None:
        note.is_pinned = data.is_pinned
    if data.is_resolved is not None:
        note.is_resolved = data.is_resolved
        if data.is_resolved:
            note.resolved_at = _utcnow()
            note.resolved_by = recruiter.id

    db.commit()
    return {"success": True}


@router.delete("/notes/{note_id}")
def delete_tagged_note(
    note_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    """Delete a tagged note"""
    note = (
        db.query(TaggedNote)
        .filter(TaggedNote.id == note_id, TaggedNote.user_id == recruiter.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    db.delete(note)
    db.commit()
    return {"success": True}
