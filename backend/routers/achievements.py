from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.achievement import Achievement, seed_achievements_for_user

router = APIRouter()


@router.get("/achievements")
def list_achievements(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seed_achievements_for_user(user.id, db)
    items = (
        db.query(Achievement)
        .filter(Achievement.user_id == user.id)
        .order_by(Achievement.created_at)
        .all()
    )
    return {
        "data": [
            {
                "id": a.id,
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "icon_slug": a.icon_slug,
                "category": a.category,
                "progress_max": a.progress_max,
                "progress_current": a.progress_current,
                "unlocked": a.unlocked,
                "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None,
            }
            for a in items
        ]
    }


@router.get("/achievements/stats")
def achievement_stats(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    seed_achievements_for_user(user.id, db)
    total = db.query(Achievement).filter(Achievement.user_id == user.id).count()
    unlocked = (
        db.query(Achievement)
        .filter(Achievement.user_id == user.id, Achievement.unlocked)
        .count()
    )
    return {
        "total": total,
        "unlocked": unlocked,
    }
