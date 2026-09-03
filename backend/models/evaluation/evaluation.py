"""Evaluation domain models — replaces AIInterviewSession, ApplicationScore, InterviewRubricSummary, EvaluationState."""

from sqlalchemy import (
    JSON,
    Boolean,
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


class EvaluationSession(Base):
    """Canonical evaluation lifecycle — one per AI interview attempt.

    Replaces AIInterviewSession and EvaluationState.
    Multiple EvaluationSessions can exist per Application (re-evaluations).
    """

    __tablename__ = "evaluation_sessions"
    __table_args__ = (
        Index("idx_es_app", "application_id"),
        Index("idx_es_candidate", "candidate_id"),
        Index("idx_es_context", "context_type", "context_id"),
        Index("idx_es_status", "status"),
        Index("idx_es_company", "company_id"),
        Index("idx_es_app_status", "application_id", "status"),
        Index("idx_es_app_interview_state", "application_id", "interview_state"),
        CheckConstraint(
            "status IS NULL OR status IN ('created', 'in_progress', 'paused', 'completed', 'expired', 'failed', 'running', 'pending', 'flagged', 'needs_review')",
            name="ck_eval_session_status",
        ),
        CheckConstraint(
            "interview_state IS NULL OR interview_state IN ('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused')",
            name="ck_eval_session_interview_state",
        ),
        {"extend_existing": True},
    )

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    candidate_id = Column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    context_type = Column(String(50), nullable=False, default="job", index=True)
    context_id = Column(String(36), nullable=True, index=True)

    # Session lifecycle (replaces EvaluationState)
    status = Column(String(20), nullable=False, default="created", index=True)
    language = Column(String(50), default="English")
    source = Column(String(50), nullable=True)

    # AI Interview state (from AIInterviewSession)
    interview_state = Column(String(20), default="not_started", index=True)
    interview_progress = Column(Integer, default=0)
    interview_time_left = Column(Integer, default=1800)
    interview_last_saved = Column(DateTime, nullable=True)

    # Authoritative deadline: started_at + duration.  All timing decisions
    # derive from this single value.  Set once at interview start; never
    # mutated by resume/pause.  NULL means "not yet started".
    expires_at = Column(DateTime, nullable=True, index=True)

    interview_log = deferred(Column(JSON, default=list))
    interview_questions = deferred(Column(JSON, default=list))
    generated_questions = deferred(Column(JSON, default=list))

    proctoring_violations = deferred(Column(JSON, default=list))
    video_file_path = Column(String(512), nullable=True)
    video_transcript = deferred(Column(Text, nullable=True))
    video_analysis_json = deferred(Column(JSON, nullable=True))

    interview_reset_count = Column(Integer, default=0)
    interview_last_reset_at = Column(DateTime, nullable=True)
    interview_turn_seq = Column(Integer, default=0)

    # Calibration
    calibration_json = deferred(Column(JSON, nullable=True))
    calibration_score = Column(Float, nullable=True)
    calibration_verified_skills = deferred(Column(JSON, nullable=True))

    # Rubric pinning (legacy — will be replaced by config_snapshot)
    rubric_id = Column(
        Integer, ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True
    )
    rubric_version = Column(Integer, nullable=True)
    rubric_snapshot_id = Column(
        Integer,
        ForeignKey("rubric_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Evaluation config snapshot — SSOT for the AI engine
    evaluation_config_snapshot_id = Column(
        Integer,
        ForeignKey("evaluation_config_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    application = relationship(
        "Application",
        foreign_keys=[application_id],
        back_populates="evaluation_sessions",
    )
    company = relationship("Company")
    cv_document = relationship(
        "CvDocument",
        uselist=False,
        back_populates="evaluation_session",
        foreign_keys="CvDocument.evaluation_session_id",
    )
    interview_turns = relationship(
        "InterviewTurn",
        back_populates="evaluation_session",
        foreign_keys="InterviewTurn.evaluation_session_id",
        order_by="InterviewTurn.turn_number",
        cascade="all, delete-orphan",
    )
    evaluation_result = relationship(
        "EvaluationResult",
        uselist=False,
        back_populates="evaluation_session",
        cascade="all, delete-orphan",
    )
    rubric_snapshot = relationship(
        "RubricSnapshot",
        back_populates="evaluation_sessions",
        foreign_keys=[rubric_snapshot_id],
    )
    config_snapshot = relationship(
        "EvaluationConfigSnapshot",
        back_populates="evaluation_sessions",
        foreign_keys=[evaluation_config_snapshot_id],
    )


class EvaluationResult(Base, TenantMixin):
    """Canonical score record — replaces ApplicationScore + InterviewRubricSummary."""

    __tablename__ = "evaluation_results"
    __table_args__ = (
        Index("idx_er_session", "evaluation_session_id", unique=True),
        Index("idx_er_final_score", "final_score"),
        Index("idx_er_needs_review", "needs_review"),
        CheckConstraint(
            "cv_score IS NULL OR (cv_score >= 0 AND cv_score <= 100)",
            name="ck_eval_result_score_range",
        ),
        CheckConstraint(
            "rubric_score IS NULL OR (rubric_score >= 0 AND rubric_score <= 100)",
            name="ck_eval_result_rubric_score_range",
        ),
        CheckConstraint(
            "human_integrity_score IS NULL OR (human_integrity_score >= 0 AND human_integrity_score <= 100)",
            name="ck_eval_result_human_score_range",
        ),
        CheckConstraint(
            "rubric_coverage_pct IS NULL OR (rubric_coverage_pct >= 0 AND rubric_coverage_pct <= 100)",
            name="ck_eval_result_coverage_range",
        ),
        CheckConstraint(
            "final_score IS NULL OR (final_score >= 0 AND final_score <= 100)",
            name="ck_eval_result_final_score_range",
        ),
        CheckConstraint(
            "composite_score IS NULL OR (composite_score >= 0 AND composite_score <= 100)",
            name="ck_eval_result_composite_score_range",
        ),
        CheckConstraint(
            "fraud_score IS NULL OR (fraud_score >= 0 AND fraud_score <= 100)",
            name="ck_eval_result_fraud_score_range",
        ),
        CheckConstraint(
            "scoring_status IN ('PENDING', 'SCORED', 'FAILED', 'NEEDS_REVIEW')",
            name="ck_eval_result_scoring_status",
        ),
        CheckConstraint(
            "(scoring_status = 'SCORED' AND final_score IS NOT NULL) "
            "OR (scoring_status IN ('PENDING', 'FAILED', 'NEEDS_REVIEW') AND final_score IS NULL)",
            name="ck_eval_result_state_machine",
        ),
        {"extend_existing": True},
    )

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    # company_id is user-scoped for standalone job seekers (mirrors the
    # Application override): a CV analysis can be scored before any company
    # context exists. NULL until the candidate acquires a company context.
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    id = Column(Integer, primary_key=True, index=True)
    evaluation_session_id = Column(
        Integer,
        ForeignKey("evaluation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    rubric_id = Column(
        Integer, ForeignKey("rubrics.id", ondelete="SET NULL"), nullable=True
    )
    rubric_version = Column(Integer, nullable=True)
    rubric_snapshot_id = Column(
        Integer,
        ForeignKey("rubric_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Composite scores
    cv_score = Column(Float, nullable=True)
    rubric_score = Column(Float, nullable=True)
    human_integrity_score = Column(Float, default=100.0)
    rubric_coverage_pct = Column(Float, nullable=True)

    # Scoring state machine — replaces numeric sentinel values
    # PENDING = not yet scored (final_score is None)
    # SCORED = successfully scored (final_score is valid)
    # FAILED = scoring failed or fraud detected (final_score is None)
    # NEEDS_REVIEW = flagged for human review (final_score is None)
    scoring_status = Column(String(20), nullable=False, default="PENDING", index=True)

    # Canonical final score — ONLY valid when scoring_status == 'SCORED'
    final_score = Column(Float, nullable=True, index=True)
    composite_score = Column(
        Float, nullable=True
    )  # deprecated: identical to final_score, will be removed

    # Confidence interval (from InterviewRubricSummary)
    confidence_lower = Column(Float, nullable=True)
    confidence_upper = Column(Float, nullable=True)

    # Canonical verdict — single source of truth for business decision
    # Replaces score_breakdown["verdict"] as the canonical field.
    # score_breakdown["verdict"] is kept for backward compatibility during migration.
    verdict = Column(String(50), nullable=True, index=True)

    # Breakdown (JSON — replaces InterviewRubricSummary)
    score_breakdown = deferred(Column(JSON, nullable=True))

    # Fraud / integrity
    fraud_score = Column(Float, default=0.0)
    fraud_reported_by = Column(Integer, nullable=True)
    fraud_reported_at = Column(DateTime, nullable=True)

    # Metadata
    scoring_model = Column(String(50), default="rubric")
    needs_review = Column(Boolean, default=False, index=True)
    needs_review_reason = Column(String(500), nullable=True)
    computed_at = Column(DateTime, default=utcnow)
    computed_by = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    evaluation_session = relationship(
        "EvaluationSession",
        back_populates="evaluation_result",
    )
    rubric_scoring_details = relationship(
        "RubricScoringDetail",
        back_populates="evaluation_result",
        cascade="all, delete-orphan",
    )
