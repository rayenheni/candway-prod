"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Job(Base, TenantMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_recruiter_active", "recruiter_id", "is_active", "deleted_at"),
        Index("idx_jobs_category", "category_id"),
        Index("idx_jobs_rubric", "rubric_id"),
        UniqueConstraint("company_id", "title", name="uq_jobs_company_title"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}
    recruiter_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    job_category_id = Column(Integer, ForeignKey("job_categories.id"), nullable=True)

    title = Column(String(255))
    company_name = Column(String(255))
    location = Column(String(255))
    salary_range = Column(String(255))
    type = Column(String(255), index=True)
    description = Column(Text)
    required_skills = Column(String(255))
    interview_instructions = Column(
        Text, nullable=True
    )  # Recruiter-defined custom interview instructions
    custom_question_prompt = Column(
        Text, nullable=True
    )  # Recruiter-defined custom question generation prompt
    total_questions = Column(Integer, nullable=True)  # Recruiter-chosen max questions
    time_limit_seconds = Column(Integer, nullable=True)  # Recruiter-chosen time limit (seconds)
    duration_minutes = Column(Integer, nullable=True)  # Recruiter-chosen duration (minutes)
    valid_through = Column(DateTime, nullable=True)
    rubric_id = Column(
        Integer, ForeignKey("rubrics.id", name="fk_jobs_rubric_id"), nullable=True
    )

    created_at = Column(DateTime, default=utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    views = Column(Integer, default=0)

    recruiter = relationship("User")
    category_rel = relationship("Category")
    category = relationship(
        "JobCategory", foreign_keys=[job_category_id], back_populates="jobs"
    )


class SavedJob(Base, TenantMixin):
    """Jobs saved by candidates for later"""

    __tablename__ = "saved_jobs"
    __table_args__ = (
        Index("idx_saved_jobs_user", "user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), index=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    job = relationship("Job")
    user = relationship("User", back_populates="saved_jobs")


class InterviewQuestion(Base, TenantMixin):
    __tablename__ = "interview_questions"
    __table_args__ = (
        Index("idx_iq_job", "job_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    type = Column(String(50), default="technical")  # technical, behavioral, scenario
    difficulty = Column(String(20), default="medium")  # junior, mid, senior
    skill_focus = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ChatbotLead(Base, TenantMixin):
    __tablename__ = "chatbot_leads"
    __table_args__ = (
        Index("idx_chatbot_lead_conv", "conversation_id"),
        Index("idx_chatbot_lead_company", "company_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(64), unique=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    role_interest = Column(String(255), nullable=True)
    experience_level = Column(String(100), nullable=True)
    skills = Column(Text, nullable=True)
    message_history = Column(Text)
    stage = Column(String(50), default="greeting")
    source_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    assigned_recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    contacted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    source_job = relationship("Job", foreign_keys=[source_job_id])
    assigned_recruiter = relationship("User", foreign_keys=[assigned_recruiter_id])
