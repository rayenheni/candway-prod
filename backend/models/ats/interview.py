"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Interview(Base, TenantMixin):
    """Interview scheduling for candidates"""

    __tablename__ = "interviews"
    __table_args__ = (
        Index("idx_interviews_scheduled_time", "scheduled_time"),
        Index("idx_interviews_status", "status"),
        Index("idx_interviews_scheduled_by", "scheduled_by"),
        UniqueConstraint(
            "application_id", "scheduled_time", name="uq_interviews_app_scheduled"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    # Scheduling Details
    scheduled_time = Column(DateTime, index=True)
    duration_minutes = Column(Integer, default=60)

    # Interview Type
    type = Column(
        String(50), index=True
    )  # "phone", "video", "onsite", "technical", "behavioral"

    # Meeting Details
    meeting_link = Column(String(500), nullable=True)  # Zoom/Google Meet/Teams
    location = Column(String(255), nullable=True)  # For onsite interviews

    # Status
    status = Column(
        String(50), default="scheduled", index=True
    )  # scheduled, completed, cancelled, rescheduled, no_show

    # Notes & Agenda
    agenda = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)  # Private notes for hiring team

    # Reminders
    reminder_sent_24h = Column(Boolean, default=False)
    reminder_sent_1h = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    cancelled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="interviews_list")
    scheduler = relationship("User", foreign_keys=[scheduled_by])
    participants = relationship(
        "InterviewParticipant", back_populates="interview", cascade="all, delete-orphan"
    )
    feedback = relationship(
        "InterviewFeedback", back_populates="interview", cascade="all, delete-orphan"
    )


class InterviewParticipant(Base, TenantMixin):
    """Interviewers and observers for an interview"""

    __tablename__ = "interview_participants"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(
        Integer, ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)

    role = Column(
        String(50)
    )  # "interviewer", "observer", "hiring_manager", "panel_member"
    attendance_status = Column(
        String(50), default="pending"
    )  # pending, accepted, declined, attended, no_show

    # Calendar Integration
    calendar_event_id = Column(String(255), nullable=True)  # Google Calendar event ID

    created_at = Column(DateTime, default=utcnow)

    # Relationships
    interview = relationship("Interview", back_populates="participants")
    user = relationship("User")


class InterviewFeedback(Base, TenantMixin):
    """Feedback from interviewers after interview completion"""

    __tablename__ = "interview_feedback"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(
        Integer, ForeignKey("interviews.id", ondelete="CASCADE"), index=True
    )
    interviewer_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Ratings (1-5 scale)
    technical_rating = Column(Integer, nullable=True)
    communication_rating = Column(Integer, nullable=True)
    culture_fit_rating = Column(Integer, nullable=True)
    problem_solving_rating = Column(Integer, nullable=True)
    overall_rating = Column(Integer, nullable=True)

    # Detailed Feedback
    strengths = Column(Text, nullable=True)
    concerns = Column(Text, nullable=True)
    additional_notes = Column(Text, nullable=True)

    # Recommendation
    recommendation = Column(
        String(50), nullable=True
    )  # "strong_yes", "yes", "maybe", "no", "strong_no"

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, onupdate=utcnow)

    # Relationships
    interview = relationship("Interview", back_populates="feedback")
    interviewer = relationship("User")


# ============================================
# TEAM COLLABORATION MODELS (ATS 2.0)
# ============================================


class InterviewScorecard(Base, TenantMixin):
    """Pre-built interview scorecards per role"""

    __tablename__ = "interview_scorecards"
    __table_args__ = (
        Index("idx_scorecards_recruiter", "recruiter_id"),
        Index("idx_scorecards_role", "role_type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # null = system template
    role_type = Column(
        String(100), nullable=False
    )  # e.g. "software_engineer", "sales_rep"

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Evaluation criteria (JSON)
    # e.g. [{"name": "Technical Depth", "weight": 30, "max_score": 5, "questions": ["..."]}]
    criteria_json = Column(Text, nullable=False)

    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User", foreign_keys=[recruiter_id])


class ScorecardSubmission(Base, TenantMixin):
    """Completed interview scorecard evaluations"""

    __tablename__ = "scorecard_submissions"
    __table_args__ = (
        Index("idx_scorecard_sub_interview", "interview_id"),
        Index("idx_scorecard_sub_evaluator", "evaluator_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    scorecard_id = Column(
        Integer, ForeignKey("interview_scorecards.id"), nullable=False
    )
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    evaluator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Scores per criterion (JSON)
    # e.g. {"technical_depth": 4, "communication": 3, "problem_solving": 5}
    scores_json = Column(Text, nullable=False)

    # Overall assessment
    overall_score = Column(Float, nullable=True)  # Weighted average
    recommendation = Column(
        String(50), nullable=True
    )  # strong_yes, yes, maybe, no, strong_no
    notes = Column(Text, nullable=True)

    submitted_at = Column(DateTime, default=utcnow)

    scorecard = relationship("InterviewScorecard")
    interview = relationship("Interview")
    application = relationship("Application", back_populates="scorecard_submissions")
    evaluator = relationship("User", foreign_keys=[evaluator_id])
