"""Scoring / Rubric domain models."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow


class Rubric(Base, TenantMixin):
    """Assessment rubric — renamed from JobRubric (mapped to rubrics table)."""

    __tablename__ = "rubrics"
    __table_args__ = (
        Index("idx_rubric_job", "job_id"),
        Index("idx_rubric_version", "job_id", "version"),
        Index("idx_rubrics_created_by", "created_by"),
        CheckConstraint(
            "passing_score IS NULL OR passing_score >= 0",
            name="ck_rubric_passing_score_non_negative",
        ),
        CheckConstraint(
            "max_score IS NULL OR max_score >= 0",
            name="ck_rubric_max_score_non_negative",
        ),
        CheckConstraint(
            "weight IS NULL OR weight >= 0", name="ck_rubric_weight_non_negative"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", name="fk_rubrics_job_id"),
        nullable=True,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)

    title = Column(String(255))
    description = Column(Text)

    passing_score = Column(Float, default=0.0)
    max_score = Column(Float, default=100.0)
    weight = Column(Float, default=1.0)

    # JSON: criteria, skill_weights, complexity
    criteria_json = deferred(Column(Text, nullable=True))
    skill_weights = deferred(Column(Text, nullable=True))
    complexity = Column(String(50), default="intermediate")

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Integer, default=1)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("Job", foreign_keys=[job_id])
    creator = relationship("User", foreign_keys=[created_by])


class RubricScoringDetail(Base, TenantMixin):
    """Individual criterion scores for an evaluation result.

    High cardinality — always queried via evaluation_result_id.
    Renamed from RubricScoringResult.
    """

    __tablename__ = "rubric_scoring_details"
    __table_args__ = (
        Index("idx_rsd_result", "evaluation_result_id"),
        CheckConstraint(
            "score >= 0 AND score <= 100", name="ck_rubric_scoring_detail_score_range"
        ),
        CheckConstraint(
            "max_score IS NULL OR max_score >= 0",
            name="ck_rubric_scoring_detail_max_score_non_negative",
        ),
        CheckConstraint(
            "weight IS NULL OR weight >= 0",
            name="ck_rubric_scoring_detail_weight_non_negative",
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    evaluation_result_id = Column(
        Integer, ForeignKey("evaluation_results.id"), nullable=False, index=True
    )

    criterion_name = Column(String(255), nullable=False)
    criterion_key = Column(String(100), nullable=True)
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    score = Column(Float, nullable=False)
    weight = Column(Float, default=1.0)
    max_score = Column(Float, default=100.0)
    feedback = Column(Text, nullable=True)
    source = Column(String(20), nullable=True)

    # Standalone candidates may be evaluated before acquiring
    # company context. Keep this aligned with the nullable DB column
    # introduced by migration m77.
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    evaluation_result = relationship(
        "EvaluationResult",
        back_populates="rubric_scoring_details",
    )
