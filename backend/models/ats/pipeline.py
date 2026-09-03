"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class ApplicationStageHistory(Base, TenantMixin):
    """Track time spent in each pipeline stage for analytics"""

    __tablename__ = "application_stage_history"
    __table_args__ = (
        Index("idx_stage_history_app", "application_id"),
        Index("idx_stage_history_stage", "stage_slug"),
        Index("idx_stage_history_entered", "entered_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    stage_slug = Column(String(100), nullable=False, index=True)
    stage_name = Column(String(100))

    entered_at = Column(DateTime, default=utcnow, index=True)
    exited_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Computed on exit

    triggered_by = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Who moved it
    trigger_type = Column(String(30), default="manual")  # manual, auto_rule, system

    application = relationship(
        "Application", back_populates="application_stage_history"
    )
    trigger_user = relationship("User", foreign_keys=[triggered_by])


class TaggedNote(Base, TenantMixin):
    """Tagged notes for candidate collaboration"""

    __tablename__ = "tagged_notes"
    __table_args__ = (
        Index("idx_tagged_notes_app", "application_id"),
        Index("idx_tagged_notes_user", "user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    tags = Column(
        Text, nullable=True
    )  # JSON array: ["strength", "concern", "follow-up"]
    priority = Column(String(20), default="normal")  # low, normal, high, urgent

    is_pinned = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    application = relationship("Application", back_populates="tagged_notes")
    author = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


class Comment(Base, TenantMixin):
    """Comments on candidate applications for team collaboration"""

    __tablename__ = "comments"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Comment Content
    content = Column(Text, nullable=False)

    # Mentions (@username)
    mentions = Column(Text, nullable=True)  # JSON array of user IDs

    # Reply Threading
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, onupdate=utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="comments_list")
    user = relationship("User", foreign_keys=[user_id])
    parent = relationship("Comment", remote_side=[id], back_populates="replies")

    replies = relationship("Comment", back_populates="parent")


class CandidateRating(Base, TenantMixin):
    """Star ratings for candidates (1-5 stars)"""

    __tablename__ = "candidate_ratings"
    __table_args__ = (
        CheckConstraint(
            "rating >= 1 AND rating <= 5", name="ck_candidate_rating_rating"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Rating (1-5 stars)
    rating = Column(Integer, nullable=False)  # 1-5

    # Category (optional)
    category = Column(
        String(50), nullable=True
    )  # "technical", "cultural_fit", "communication"

    # Note
    note = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, onupdate=utcnow)

    # Relationships
    application = relationship("Application", back_populates="ratings_list")
    user = relationship("User")


class ActivityLog(Base, TenantMixin):
    """Activity feed for tracking all actions on candidates"""

    __tablename__ = "activity_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), index=True, nullable=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Activity Type
    action = Column(
        String(100), index=True
    )  # "status_changed", "comment_added", "interview_scheduled", etc.

    # Details (JSON)
    details = Column(Text, nullable=True)  # JSON object with action-specific data

    # Metadata
    entity_type = Column(String(50), nullable=True)  # "application", "interview", "job"
    entity_id = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=utcnow, index=True)

    # Relationships
    application = relationship("Application", back_populates="activity_logs_list")
    user = relationship("User")


# ============================================
# OFFER MANAGEMENT MODELS (ATS 2.0)
# ============================================


class TeamMember(Base, TenantMixin):
    """Team membership - recruiter can add team members"""

    __tablename__ = "team_members"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )  # The recruiter who owns the team
    member_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )  # The team member

    role = Column(String(50), default="member")  # 'member', 'admin'
    status = Column(String(50), default="active")  # 'active', 'inactive'

    added_at = Column(DateTime, default=utcnow)
    removed_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    member = relationship("User", foreign_keys=[member_id])


class CandidateInteraction(Base, TenantMixin):
    """Track all interactions with candidates for complete communication history"""

    __tablename__ = "candidate_interactions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), index=True
    )  # Who performed the interaction

    # Interaction Details
    type = Column(
        String(50), index=True
    )  # email, call, note, interview, offer, message, meeting
    subject = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)

    # Metadata
    direction = Column(String(20), nullable=True)  # inbound, outbound
    channel = Column(
        String(50), nullable=True
    )  # email, phone, linkedin, whatsapp, etc.

    # Tracking
    is_automated = Column(Boolean, default=False)  # Was this automated or manual?
    parent_interaction_id = Column(
        Integer, ForeignKey("candidate_interactions.id"), nullable=True
    )  # For threading

    # Timestamps
    created_at = Column(DateTime, default=utcnow, index=True)

    # Relationships
    application = relationship("Application", back_populates="interactions")
    user = relationship("User")
    parent = relationship(
        "CandidateInteraction", remote_side=[id], back_populates="replies"
    )

    replies = relationship("CandidateInteraction", back_populates="parent")
