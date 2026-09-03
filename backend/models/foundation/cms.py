"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow


class BlogPost(Base, TenantMixin):
    __tablename__ = "blog_posts"
    __table_args__ = (
        Index("idx_blog_posts_author", "author_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    slug = Column(String(255), unique=True, index=True)
    content = deferred(Column(Text))  # HTML content
    author_id = Column(Integer, ForeignKey("users.id"))
    image_url = Column(String(255), nullable=True)
    tags = Column(String(255), nullable=True)  # JSON list e.g. ["career", "tech"]
    is_published = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    author = relationship("User")


class SalesLead(Base):
    __tablename__ = "sales_leads"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    company = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    role = Column(String(255), nullable=True)  # e.g. CEO, HR Manager
    source = Column(String(50))  # internal, search, linkedin_mock
    status = Column(
        String(50), default="new"
    )  # new, qualified, contacted, interested, converted, rejected
    score = Column(Integer, default=0)
    ai_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_contacted_at = Column(DateTime, nullable=True)


class DailyPlatformReport(Base):
    """Historical archive of AI-generated platform insights"""

    __tablename__ = "daily_platform_reports"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True)
    report_json = deferred(Column(Text))  # Summary, key wins, risks, recommendations
    created_at = Column(DateTime, default=utcnow)


class SalesCampaign(Base):
    __tablename__ = "sales_campaigns"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    niche = Column(String(255))  # e.g. "Fintech Tunisia"
    total_leads_found = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, completed, cancelled

    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)


def init_db():
    from backend.database import engine

    Base.metadata.create_all(bind=engine)


class Announcement(Base, TenantMixin):
    __tablename__ = "announcements"
    __table_args__ = (
        Index("idx_announcements_created_by", "created_by"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    message = Column(Text)
    type = Column(String(20))  # info, warning, critical
    target_role = Column(String(20))  # all, recruiter, candidate
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))


# ============================================
# TUNISIAN ADMIN FINANCIALS (PHASE 2)
# ============================================


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        Index("idx_opportunities_type", "type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    type = Column(String(255))  # scholarship, event, grant, hackathon
    description = Column(Text)  # HTML content or brief
    link = Column(String(255))
    image_url = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
