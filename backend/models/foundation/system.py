"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow


class Ticket(Base, TenantMixin):
    """DEPRECATED: Use SupportTicket instead. Will be removed in next major version."""

    __tablename__ = "tickets"
    __table_args__ = (
        Index("idx_tickets_user", "user_id"),
        Index("idx_tickets_status", "status"),
        Index("idx_tickets_created", "created_at"),
        Index("idx_tickets_priority_status", "priority", "status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    subject = Column(String(255))
    message = Column(Text)
    priority = Column(String(255))
    status = Column(String(255), default="Open")
    created_at = Column(DateTime, default=utcnow)


class SupportTicket(Base, TenantMixin):
    """Support ticket system for candidates to report issues and request help"""

    __tablename__ = "support_tickets"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    category = Column(
        String(50), nullable=False
    )  # 'bug', 'feature', 'account', 'other'
    priority = Column(String(20), default="medium")  # 'low', 'medium', 'high'
    description = Column(Text, nullable=False)
    status = Column(
        String(20), default="open", index=True
    )  # 'open', 'in_progress', 'resolved', 'closed'

    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime, nullable=True)
    admin_response = Column(Text, nullable=True)

    user = relationship("User")


# ============================================
# TUNISIAN ADMIN COMPLIANCE (PHASE 1)
# ============================================


class SystemConfig(Base):
    __tablename__ = "system_config"
    __table_args__ = {"extend_existing": True}

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=True)  # Upgraded from String(255) to Text
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class SystemPrompt(Base):
    __tablename__ = "system_prompts"

    key = Column(String(255), primary_key=True, index=True)  # e.g. "recruiter_persona"
    content = Column(Text)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utcnow)


class TranslationCache(Base):
    """
    Stores AI-generated translations to prevent redundant API calls.
    Follows the 'One-Time' translation rule.
    """

    __tablename__ = "translation_cache"

    id = Column(Integer, primary_key=True, index=True)
    source_hash = Column(String(64), index=True)  # SHA-256 of source text + context
    target_lang = Column(String(10), index=True)  # en, fr, ar
    source_text = deferred(Column(Text))  # Original text for reference
    translated_text = deferred(Column(Text))  # Cached result
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "source_hash", "target_lang", name="uq_translation_source_target"
        ),
        {"extend_existing": True},
    )


class PageSection(Base):
    __tablename__ = "page_sections"

    id = Column(Integer, primary_key=True, index=True)
    page_slug = Column(String(50), index=True)  # e.g. 'home', 'recruiter'
    section_slug = Column(String(50), index=True)  # e.g. 'hero', 'pricing'

    # Store dynamic content structure: { "title": "...", "subtitle": "...", "image": "..." }
    content_json = deferred(Column(Text))

    updated_at = Column(DateTime, default=utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
