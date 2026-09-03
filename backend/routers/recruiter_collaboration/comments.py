import json
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.authz import get_application_for_recruiter
from backend.config import get_settings
from backend.database import (
    ActivityLog,
    Application,
    Comment,
    User,
)
from backend.dependencies import (
    get_db,
    require_recruiter,
)
from backend.email_utils import send_email
from backend.logger import logger
from backend.profile_helpers import get_user_email, get_user_name

router = APIRouter(tags=["Recruiter Collaboration - Comments"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    application_id: int = None,
    details: dict = None,
    company_id: int = None,
):
    try:
        activity = ActivityLog(
            user_id=user_id,
            application_id=application_id,
            company_id=company_id,
            action=action,
            details=json.dumps(details) if details else None,
        )
        db.add(activity)
        db.flush()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


def extract_mentions(content: str):
    import re

    mentions = re.findall(r"@([\w.@+-]+)", content)
    return mentions


def send_mention_notifications(db: Session, comment, mentioned_usernames):
    try:
        from sqlalchemy import func

        app = (
            db.query(Application)
            .filter(Application.id == comment.application_id)
            .first()
        )
        commenter = db.query(User).filter(User.id == comment.user_id).first()

        for username in mentioned_usernames:
            user = (
                db.query(User).filter(func.lower(User.name) == username.lower()).first()
            )

            if user and get_user_email(user):
                settings = get_settings()
                pipeline_url = f"{settings.frontend_url}/recruiter/pipeline"
                subject = f"{get_user_name(commenter)} mentioned you in a comment"
                body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #4f46e5;">You were mentioned!</h2>
                    <p><strong>{get_user_name(commenter)}</strong> mentioned you in a comment on <strong>{app.full_name}</strong>'s application:</p>

                    <div style="background: #f3f4f6; padding: 15px; border-left: 4px solid #4f46e5; margin: 20px 0;">
                        <p style="margin: 0;">{comment.content}</p>
                    </div>

                    <a href="{pipeline_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0;">
                        View Application
                    </a>
                </div>
                """
                send_email(get_user_email(user), subject, body)
    except Exception as e:
        logger.error(f"Failed to send mention notifications: {e}")


class CommentCreate(BaseModel):
    application_id: int
    content: str
    parent_id: Optional[int] = None


class CommentResponse(BaseModel):
    id: int
    application_id: int
    user_name: str
    user_email: str
    content: str
    parent_id: Optional[int]
    created_at: datetime
    replies: List[dict] = []

    model_config = ConfigDict(from_attributes=True)


def format_comment(comment: Comment, db: Session) -> dict:
    user = db.query(User).filter(User.id == comment.user_id).first()

    replies = (
        db.query(Comment)
        .filter(and_(Comment.parent_id == comment.id, Comment.deleted_at.is_(None)))
        .order_by(Comment.created_at)
        .all()
    )

    return {
        "id": comment.id,
        "application_id": comment.application_id,
        "user_name": get_user_name(user) if user else "Unknown",
        "user_email": get_user_email(user) if user else None,
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": comment.created_at,
        "replies": [format_comment(r, db) for r in replies],
    }


@router.post("/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    data: CommentCreate,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    get_application_for_recruiter(data.application_id, recruiter, db)

    mentions = extract_mentions(data.content)

    app = get_application_for_recruiter(data.application_id, recruiter, db)

    comment = Comment(
        application_id=data.application_id,
        user_id=recruiter.id,
        company_id=app.company_id,
        content=data.content,
        parent_id=data.parent_id,
        mentions=json.dumps(mentions) if mentions else None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    log_activity(
        db,
        recruiter.id,
        "comment_added",
        data.application_id,
        {"comment_id": comment.id, "content_preview": data.content[:100]},
        company_id=app.company_id,
    )

    if mentions:
        send_mention_notifications(db, comment, mentions)

    logger.info(
        f"Comment added by {get_user_email(recruiter)} on application {data.application_id}"
    )

    return {"success": True, "comment_id": comment.id}


@router.get("/comments/{application_id}", response_model=List[CommentResponse])
def get_comments(
    application_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    get_application_for_recruiter(application_id, recruiter, db)

    comments = (
        db.query(Comment)
        .filter(
            and_(
                Comment.application_id == application_id,
                Comment.parent_id.is_(None),
                Comment.deleted_at.is_(None),
            )
        )
        .order_by(Comment.created_at.desc())
        .all()
    )

    return [format_comment(c, db) for c in comments]


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    recruiter: User = Depends(require_recruiter),
    db: Session = Depends(get_db),
):
    comment = (
        db.query(Comment)
        .join(Application)
        .filter(
            Comment.id == comment_id,
            Application.company_id == getattr(recruiter, "_company_id", None),
        )
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != recruiter.id and recruiter.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    comment.deleted_at = _utcnow()
    db.commit()

    logger.info(f"Comment {comment_id} deleted by {get_user_email(recruiter)}")

    return {"success": True}
