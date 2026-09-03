import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import Notification, User, get_db
from backend.dependencies import get_current_user
from backend.logger import logger

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/latest")
async def get_latest_notifications(
    limit: int = 10,
    offset: int = 0,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest notifications for the current user"""
    try:
        query = db.query(Notification).filter(Notification.user_id == current_user.id)

        if unread_only:
            query = query.filter(not Notification.is_read)

        notifications = (
            query.order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for notif in notifications:
            payload = {}
            if notif.payload_json:
                try:
                    payload = json.loads(notif.payload_json)
                except (json.JSONDecodeError, TypeError):
                    payload = {}

            result.append(
                {
                    "id": notif.id,
                    "type": notif.type,
                    "title": notif.title,
                    "message": notif.message,
                    "level": notif.level,
                    "related_type": notif.related_type,
                    "related_id": notif.related_id,
                    "is_read": notif.is_read,
                    "created_at": notif.created_at.isoformat()
                    if notif.created_at
                    else None,
                    "payload": payload,
                }
            )

        return result

    except Exception as e:
        logger.error(f"Failed to fetch notifications: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications",
        )


@router.get("/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of unread notifications"""
    try:
        count = (
            db.query(Notification)
            .filter(Notification.user_id == current_user.id, not Notification.is_read)
            .count()
        )
        return {"unread_count": count}
    except Exception as e:
        logger.error(f"Failed to get unread count: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count",
        )


@router.post("/{notification_id}/mark-read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a specific notification as read"""
    try:
        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
            .first()
        )

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )

        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        db.commit()

        return {"success": True, "message": "Notification marked as read"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark notification as read: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read",
        )


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read"""
    try:
        (
            db.query(Notification)
            .filter(Notification.user_id == current_user.id, not Notification.is_read)
            .update({"is_read": True, "read_at": datetime.now(UTC)})
        )
        db.commit()

        return {"success": True, "message": "All notifications marked as read"}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark all notifications as read: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read",
        )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific notification"""
    try:
        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
            .first()
        )

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )

        db.delete(notification)
        db.commit()

        return {"success": True, "message": "Notification deleted"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification",
        )
