"""Profile models — extracted from User table for role-specific data."""

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
)
from sqlalchemy.orm import relationship

from backend.encryption import EncryptedText
from backend.models.base import Base, TenantMixin, utcnow


class CandidateProfile(Base, TenantMixin):
    """Candidate personal and professional data.

    Ownership: candidate's identity information, skills, preferences,
    usage tracking, and profile engagement metrics.
    See docs/entity-ownership.md for full boundary definitions.

    Note: company_id is overridden to nullable because candidates are
    user-scoped (not company-scoped). They belong to no company until
    they apply to a specific company's job.
    """

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        Index("idx_candidate_profiles_user", "user_id", unique=True),
        {"extend_existing": True},
    )

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    name = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)

    headline = Column(String(255))
    bio = Column(Text)
    skills = Column(Text)
    builder_data = Column(Text, nullable=True)
    languages = Column(String(255))
    availability = Column(String(255))
    work_preference = Column(String(255))
    salary_expectation_min = Column(Integer)
    salary_expectation_max = Column(Integer)
    relocation_willing = Column(Boolean, nullable=True)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    linkedin_url = Column(String(255))
    github_url = Column(String(255))
    portfolio_url = Column(String(255))
    avatar_url = Column(String(255))
    profile_views = Column(Integer, default=0)
    profile_views_growth = Column(Float, default=12.0)

    candidate_cv_uploads_this_month = Column(Integer, default=0)
    candidate_ai_analyses_this_month = Column(Integer, default=0)
    candidate_pdf_downloads_this_month = Column(Integer, default=0)
    candidate_usage_reset_date = Column(DateTime, nullable=True)

    subscription_status = Column(String(50), default="active")
    subscription_plan = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="candidate_profile")


class RecruiterProfile(Base, TenantMixin):
    """Recruiter company settings and operational data.

    Ownership: company branding, SMTP configuration, usage quotas,
    email and LinkedIn integration settings.
    See docs/entity-ownership.md for full boundary definitions.

    Note: company_id is overridden to nullable because profiles are
    user-scoped. Recruiters create their company during onboarding.
    """

    __tablename__ = "recruiter_profiles"
    __table_args__ = (
        Index("idx_recruiter_profiles_user", "user_id", unique=True),
        {"extend_existing": True},
    )

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    name = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)

    company_name = Column(String(255))
    company_description = Column(Text)
    company_logo_url = Column(String(255))
    avatar_url = Column(String(255))

    smtp_host = Column(String(255))
    smtp_port = Column(Integer)
    smtp_user = Column(String(255))
    smtp_password = Column(EncryptedText(512))

    usage_jobs = Column(Integer, default=0)
    usage_cvs = Column(Integer, default=0)
    usage_ai_interviews = Column(Integer, default=0)
    usage_reset_date = Column(DateTime, nullable=True)

    email_settings = Column(Text)
    linkedin_settings = Column(Text)

    tier = Column(String(50), nullable=True)
    subscription_status = Column(String(50), default="active")
    subscription_end = Column(DateTime, nullable=True)
    current_plan_id = Column(
        Integer, ForeignKey("subscription_plans.id"), nullable=True
    )
    subscription_plan = Column(String(255), nullable=True)
    calendar_settings = Column(Text)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="recruiter_profile")


class AdminProfile(Base, TenantMixin):
    __tablename__ = "admin_profiles"
    __table_args__ = (
        Index("idx_admin_profiles_user", "user_id", unique=True),
        {"extend_existing": True},
    )

    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    permissions = Column(Text)
    is_super_admin = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="admin_profile")
