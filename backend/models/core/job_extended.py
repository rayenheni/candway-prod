"""Extended job models — skill-first job definition tables.

These tables support the 6-step Skill-First Job Creation wizard:
1. Basic Information
2. Role & Outcomes
3. Choose or Create Skill Tree ⭐
4. Evaluation Configuration
5. Screening & Pipeline
6. Review & Publish
"""

from sqlalchemy import (
    JSON,
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


class JobSkill(Base, TenantMixin):
    """Structured skill definition for a job — replaces denormalized required_skills string."""

    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_name", name="uq_job_skill_name"),
        Index("idx_job_skills_job", "job_id"),
        Index("idx_job_skills_company_name", "company_id", "skill_name"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_name = Column(String(100), nullable=False)
    required_level = Column(String(20), nullable=False, default="intermediate")
    weight = Column(Integer, nullable=False, default=10)
    is_mandatory = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobEvaluationFramework(Base, TenantMixin):
    """Structured evaluation categories with weights — drives AI scoring."""

    __tablename__ = "job_evaluation_frameworks"
    __table_args__ = (
        Index("idx_job_ef_job", "job_id", unique=True),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    categories = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobScreeningQuestion(Base, TenantMixin):
    """Structured screening questions per job."""

    __tablename__ = "job_screening_questions"
    __table_args__ = (
        Index("idx_jsq_job", "job_id"),
        Index("idx_jsq_job_order", "job_id", "sort_order"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question = Column(Text, nullable=False)
    type = Column(String(20), nullable=False, default="text")
    options = Column(JSON, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobPipelineStage(Base, TenantMixin):
    """Per-job hiring pipeline stages with ordering."""

    __tablename__ = "job_pipeline_stages"
    __table_args__ = (
        UniqueConstraint("job_id", "slug", name="uq_job_pipeline_slug"),
        Index("idx_jps_job", "job_id"),
        Index("idx_jps_job_order", "job_id", "sort_order"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    color = Column(String(20), nullable=True)
    icon = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobAIConfig(Base, TenantMixin):
    """Per-job AI configuration — scoring thresholds, behavior flags."""

    __tablename__ = "job_ai_configs"
    __table_args__ = (
        Index("idx_jac_job", "job_id", unique=True),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ai_scoring_enabled = Column(Boolean, nullable=False, default=True)
    minimum_recommended_score = Column(Float, nullable=False, default=0.0)
    auto_shortlist_threshold = Column(Float, nullable=True)
    auto_reject_threshold = Column(Float, nullable=True)
    explain_ai_decisions = Column(Boolean, nullable=False, default=True)
    evidence_based_scoring = Column(Boolean, nullable=False, default=True)
    ignore_missing_cv = Column(Boolean, nullable=False, default=False)
    prioritize_verified_skills = Column(Boolean, nullable=False, default=True)
    custom_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobRoleOverview(Base, TenantMixin):
    """Structured role overview Q&A — one row per question-answer pair."""

    __tablename__ = "job_role_overviews"
    __table_args__ = (
        UniqueConstraint("job_id", "question_key", name="uq_job_role_q_key"),
        Index("idx_jro_job", "job_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_key = Column(String(50), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobNiceToHave(Base, TenantMixin):
    """Optional nice-to-have requirements — never dominate evaluation."""

    __tablename__ = "job_nice_to_haves"
    __table_args__ = (
        Index("idx_jnth_job", "job_id"),
        Index("idx_jnth_job_type", "job_id", "requirement_type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_type = Column(String(50), nullable=False)
    label = Column(String(255), nullable=False)
    is_preferred = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobCategory(Base, TenantMixin):
    """Company-scoped job categories — managed by admins, used in job wizard step 1."""

    __tablename__ = "job_categories"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_job_category_company_name"),
        Index("idx_job_categories_company", "company_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    jobs = relationship(
        "Job", foreign_keys="Job.job_category_id", back_populates="category"
    )
