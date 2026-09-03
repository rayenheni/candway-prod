from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from backend.models.base import Base, utcnow

CATALOG = [
    {
        "slug": "first-application",
        "name": "First Application",
        "description": "Submit your first job application",
        "icon_slug": "crosshair",
        "category": "Applications",
        "progress_max": 1,
    },
    {
        "slug": "interview-pro",
        "name": "Interview Pro",
        "description": "Complete 5 interviews",
        "icon_slug": "mic",
        "category": "Interviews",
        "progress_max": 5,
    },
    {
        "slug": "quick-learner",
        "name": "Quick Learner",
        "description": "Complete your first course",
        "icon_slug": "zap",
        "category": "Learning",
        "progress_max": 1,
    },
    {
        "slug": "skill-master",
        "name": "Skill Master",
        "description": "Reach 90+ in any skill assessment",
        "icon_slug": "trophy",
        "category": "Skills",
        "progress_max": 1,
    },
    {
        "slug": "networker",
        "name": "Networker",
        "description": "Connect with 10 recruiters",
        "icon_slug": "handshake",
        "category": "Social",
        "progress_max": 10,
    },
    {
        "slug": "top-candidate",
        "name": "Top Candidate",
        "description": "Get AI score above 95",
        "icon_slug": "star",
        "category": "Performance",
        "progress_max": 95,
    },
    {
        "slug": "bookworm",
        "name": "Bookworm",
        "description": "Complete 5 courses",
        "icon_slug": "book-open",
        "category": "Learning",
        "progress_max": 5,
    },
    {
        "slug": "hired",
        "name": "Hired!",
        "description": "Accept your first job offer",
        "icon_slug": "briefcase",
        "category": "Applications",
        "progress_max": 1,
    },
    {
        "slug": "feedback-champion",
        "name": "Feedback Champion",
        "description": "Leave feedback for 10 interviews",
        "icon_slug": "message-square",
        "category": "Engagement",
        "progress_max": 10,
    },
    {
        "slug": "profile-star",
        "name": "Profile Star",
        "description": "Complete 100% of your profile",
        "icon_slug": "sparkles",
        "category": "Profile",
        "progress_max": 100,
    },
    {
        "slug": "early-bird",
        "name": "Early Bird",
        "description": "Apply within 1 hour of job posting",
        "icon_slug": "bird",
        "category": "Applications",
        "progress_max": 1,
    },
    {
        "slug": "polyglot",
        "name": "Polyglot",
        "description": "Add 5+ programming languages",
        "icon_slug": "globe",
        "category": "Skills",
        "progress_max": 5,
    },
]


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    slug = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    icon_slug = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False)
    progress_max = Column(Integer, default=1)
    progress_current = Column(Integer, default=0)
    unlocked = Column(Boolean, default=False)
    unlocked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


def seed_achievements_for_user(user_id: int, db: Session):
    existing = db.query(Achievement).filter(Achievement.user_id == user_id).count()
    if existing > 0:
        return
    now = datetime.utcnow()
    for entry in CATALOG:
        db.add(
            Achievement(
                user_id=user_id,
                slug=entry["slug"],
                name=entry["name"],
                description=entry["description"],
                icon_slug=entry["icon_slug"],
                category=entry["category"],
                progress_max=entry["progress_max"],
                progress_current=0,
                unlocked=False,
                unlocked_at=None,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
