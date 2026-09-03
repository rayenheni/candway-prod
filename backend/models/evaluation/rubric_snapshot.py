"""RubricSnapshot — immutable copy of rubric at time of evaluation.

Ensures historical evaluations NEVER change when a recruiter edits a rubric.
"""

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class RubricSnapshot(Base, TenantMixin):
    """Immutable rubric state captured when an evaluation session is scored.

    Once created, this row is never modified.  The evaluation always
    refers back to this snapshot, not the live Rubric row.
    """

    __tablename__ = "rubric_snapshots"
    __table_args__ = (
        Index("idx_rubric_snapshot_original", "original_rubric_id"),
        Index("idx_rubric_snapshot_job", "job_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)

    original_rubric_id = Column(
        Integer, ForeignKey("rubrics.id"), nullable=True, index=True
    )
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)

    version = Column(Integer, nullable=False, default=1)

    criteria_json = Column(JSON, nullable=True)
    skill_weights_json = Column(JSON, nullable=True)
    scoring_rules_json = Column(JSON, nullable=True)

    rubric_title = Column(String(255), nullable=True)
    passing_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    original_rubric = relationship("Rubric", foreign_keys=[original_rubric_id])

    evaluation_sessions = relationship(
        "EvaluationSession",
        back_populates="rubric_snapshot",
    )
