"""SQLAlchemy model definitions."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import deferred, relationship

from backend.encryption import EncryptedText
from backend.models.base import Base, TenantMixin, utcnow


class InterviewTurn(Base, TenantMixin):
    """One row per candidate answer during an AI interview.

    The dedicated table replaces the legacy
    ``Application.interview_qa_structured`` JSON bag (removed in
    Phase 3B, June 2026).

    Benefits over the bag:
      * ``Application`` reads stay slim (turns come from a join).
      * Per-turn indexing (e.g. ``WHERE score < 60`` to surface
        weak turns on the recruiter review page).
      * Survives a CV reanalysis — the bag used to be wiped
        whenever the user re-ran CV parsing, losing the QA history.

    Schema choices:
      * ``turn_number`` is the 1-based position; combined with
        ``application_id`` it is unique (a candidate can't answer
        the same turn twice).
      * PII columns (question, answer, feedback) are stored as
        ``EncryptedText`` so the same encryption boundary as the
        legacy bag applies.
      * ``score``, ``response_time_seconds``, ``quality`` are
        queryable numbers — the bag forced every consumer to
        ``json.loads`` + walk the list.
    """

    __tablename__ = "interview_turns"
    __table_args__ = (
        Index("idx_turns_eval_session", "evaluation_session_id"),
        Index("idx_turns_user", "user_id"),
        Index("idx_turns_score", "score"),
        Index("idx_turns_company", "company_id"),
        UniqueConstraint(
            "evaluation_session_id",
            "turn_number",
            name="uq_turns_eval_number",
        ),
        CheckConstraint(
            "((application_id IS NULL AND evaluation_session_id IS NOT NULL) OR "
            "(application_id IS NOT NULL AND evaluation_session_id IS NULL))",
            name="ck_interview_turn_owner_xor",
        ),
        CheckConstraint(
            "status IS NULL OR status IN ('answered', 'pending', 'skipped')",
            name="ck_interview_turn_status",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_interview_turn_score_range",
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=False,
    )
    evaluation_session_id = Column(
        Integer,
        ForeignKey("evaluation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    turn_number = Column(Integer, nullable=False)
    question = Column(EncryptedText(8192), nullable=True)
    answer = Column(EncryptedText(16384), nullable=True)
    score = Column(Float, nullable=True)
    feedback = Column(EncryptedText(4096), nullable=True)
    reasoning = Column(EncryptedText(4096), nullable=True)
    quality = Column(String(32), nullable=True)
    type = Column(String(64), nullable=True)
    difficulty = Column(String(32), nullable=True)
    response_time_seconds = Column(Float, nullable=True)
    status = Column(String(32), nullable=True)  # answered / pending / skipped
    question_timestamp = Column(DateTime, nullable=True)
    answer_timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    application = relationship(
        "Application", back_populates="interview_turns", foreign_keys=[application_id]
    )
    evaluation_session = relationship(
        "EvaluationSession",
        back_populates="interview_turns",
        foreign_keys=[evaluation_session_id],
    )
    user = relationship("User", foreign_keys=[user_id])


class AIAuditLog(Base, TenantMixin):
    __tablename__ = "ai_audit_logs"
    __table_args__ = (
        Index("idx_ai_audit_app", "application_id"),
        Index("idx_ai_audit_created", "created_at"),
        Index("idx_ai_audit_model", "model_version"),
        Index("idx_ai_audit_logs_company", "company_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    turn_number = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)

    prompt_used = deferred(Column(Text, nullable=True))
    model_version = Column(String(128), nullable=True)
    response_content = deferred(Column(Text, nullable=True))

    scoring_breakdown = Column(Text, nullable=True)
    prompt_version = Column(String(20), nullable=True)

    input_snapshot = Column(Text, nullable=True)

    prompt_injection_blocked = Column(Boolean, default=False, nullable=True)
    previous_hash = Column(String(64), nullable=True, index=True)
    record_hash = Column(String(64), nullable=True, index=True)

    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    application = relationship("Application", back_populates="ai_audit_logs")


class CalibrationSample(Base, TenantMixin):
    __tablename__ = "calibration_samples"
    __table_args__ = (
        Index("idx_calibration_app", "application_id"),
        Index("idx_calibration_created", "created_at"),
        Index("idx_calibration_samples_company", "company_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String(64), unique=True, nullable=False, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )

    role = Column(String(128), nullable=True)
    seniority = Column(String(50), nullable=True)

    ai_scores = Column(Text, nullable=False)
    human_ratings = Column(Text, nullable=True)

    ai_human_correlation = Column(Float, nullable=True)
    score_delta = Column(Float, nullable=True)

    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    application = relationship("Application", back_populates="calibration_samples")


class DriftSnapshot(Base, TenantMixin):
    __tablename__ = "drift_snapshots"
    __table_args__ = (
        Index("ix_drift_snapshot_company", "company_id"),
        Index("ix_drift_snapshot_metric", "metric_name"),
        Index("ix_drift_snapshot_time", "snapshot_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    baseline_value = Column(Float, nullable=True)
    drift_score = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=True)
    snapshot_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)


class ABExperiment(Base, TenantMixin):
    """DEPRECATED: Use ABTestExperiment instead. Will be removed in next major version."""

    __tablename__ = "ab_experiments"
    __table_args__ = (
        Index("idx_ab_company", "company_id"),
        Index("idx_ab_active", "is_active"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String(64), unique=True, nullable=False, index=True)

    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)

    variant_a_config = Column(Text, nullable=True)
    variant_b_config = Column(Text, nullable=True)

    variant_a_results = Column(Text, nullable=True)
    variant_b_results = Column(Text, nullable=True)

    winner = Column(String(8), nullable=True)
    confidence_level = Column(Float, nullable=True)

    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


# =============================================================================
# ENTERPRISE: Audit Trail
# =============================================================================


class ABTestExperiment(Base, TenantMixin):
    """A/B experiment comparing two scoring variants."""

    __tablename__ = "ab_test_experiments"
    __table_args__ = (
        Index("idx_ab_test_job", "job_id"),
        Index("idx_ab_test_experiments_created_by", "created_by"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    variant_a_json = Column(JSON, nullable=False)
    variant_b_json = Column(JSON, nullable=False)
    traffic_split = Column(Integer, default=50)

    status = Column(String(20), default="draft")  # draft | running | paused | completed

    min_sample_size = Column(Integer, default=50)
    current_sample_size = Column(Integer, default=0)

    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    creator = relationship("User", foreign_keys=[created_by])


class ABTestAssignment(Base, TenantMixin):
    """Assignment of a user/candidate to an experiment variant."""

    __tablename__ = "ab_test_assignments"
    __table_args__ = (
        Index("idx_ab_assign_exp_user", "experiment_id", "user_id", unique=True),
        Index(
            "idx_ab_assign_exp_candidate", "experiment_id", "candidate_id", unique=True
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(
        Integer,
        ForeignKey("ab_test_experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    candidate_id = Column(
        Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )

    variant = Column(String(10), nullable=False)  # "a" | "b"
    assigned_at = Column(DateTime, default=utcnow)


class ScoringVariantResult(Base, TenantMixin):
    """Stores both variant scores for comparison."""

    __tablename__ = "scoring_variant_results"
    __table_args__ = (
        Index("idx_svr_experiment", "experiment_id"),
        Index("idx_svr_candidate", "candidate_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(
        Integer,
        ForeignKey("ab_test_experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )

    variant_a_score = Column(Integer, nullable=False)
    variant_b_score = Column(Integer, nullable=False)
    variant_a_json = Column(JSON, default=dict)
    variant_b_json = Column(JSON, default=dict)

    score_delta = Column(Integer, nullable=True)
    recruiter_preference = Column(String(10), nullable=True)
    hiring_outcome = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=utcnow)


class PromptTest(Base, TenantMixin):
    __tablename__ = "prompt_tests"
    __table_args__ = (
        Index("idx_prompt_tests_created_by", "created_by"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    prompt_type = Column(String(100), index=True)
    version = Column(String(20))
    variant = Column(String(20))
    test_name = Column(String(255))
    description = Column(Text)
    prompt_content = Column(Text)
    expected_output = Column(Text)

    # Test configuration
    test_cases_count = Column(Integer, default=0)

    # Results
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=0)
    avg_score = Column(Float, default=0)

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_active = Column(Boolean, default=True)

    creator = relationship("User")


class PromptVariant(Base, TenantMixin):
    __tablename__ = "prompt_variants"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    prompt_type = Column(String(100), index=True)
    version = Column(String(20))
    variant_name = Column(String(100))
    content = deferred(Column(Text))
    description = Column(Text)

    # Performance metrics
    times_used = Column(Integer, default=0)
    success_rate = Column(Float, default=0)
    avg_latency = Column(Float, default=0)

    # Configuration
    is_enabled = Column(Boolean, default=True)
    traffic_percentage = Column(Float, default=0)  # For A/B testing

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class DBTestResult(Base, TenantMixin):
    __tablename__ = "prompt_test_results"
    __table_args__ = (
        Index("idx_prompt_test_results_test", "test_id"),
        Index("idx_prompt_test_results_variant", "variant_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("prompt_tests.id", ondelete="CASCADE"))
    variant_id = Column(
        Integer, ForeignKey("prompt_variants.id", ondelete="SET NULL"), nullable=True
    )

    # Version tracking (needed for grouping in statistics)
    version = Column(String(20))
    variant = Column(String(20))

    # Test execution
    status = Column(String(50))  # success, failure, error
    response_time_ms = Column(Float)

    # Output quality metrics
    output_score = Column(Float, nullable=True)
    quality_metrics = Column(Text)  # JSON

    # Actual vs expected
    actual_output = deferred(Column(Text))
    similarity_score = Column(Float, nullable=True)

    # Metadata
    executed_at = Column(DateTime, default=utcnow)

    test = relationship("PromptTest")
    variant_rel = relationship("PromptVariant")


# ============================================
# MESSAGING SYSTEM MODELS
# ============================================


class SkillDefinition(Base, TenantMixin):
    """Normalized skill definition — source of truth for scoring data.

    Every skill used in rubrics MUST have a row here with a UUID.
    Stores both catalog metadata and full scoring definition
    (keywords, levels, is_required) synced from rubric_json.
    """

    __tablename__ = "skill_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_skill_def_company_name"),
        Index("idx_skill_def_category", "category_id"),
        {"extend_existing": True},
    )

    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}

    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(100), nullable=False)
    category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description = Column(Text, nullable=True)

    expected_proficiency = Column(String(20), default="mid")
    weight = Column(Float, default=1.0)

    keywords = Column(JSON, nullable=True)  # synced from rubric_json skill.keywords
    levels = Column(JSON, nullable=True)  # synced from rubric_json skill.levels
    is_required = Column(
        Boolean, default=False
    )  # synced from rubric_json skill.is_required

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    category = relationship("Category", foreign_keys=[category_id])


# JobRubric is the single source of truth for both published rubrics
# and recruiter drafts.  The old RubricDraft and Rubric models have
# been removed — see migration C4 for table cleanup.
