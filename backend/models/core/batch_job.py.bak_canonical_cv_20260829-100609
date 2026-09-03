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
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow


class BatchJob(Base, TenantMixin):
    __tablename__ = "batch_jobs"
    __table_args__ = (
        Index("idx_batch_jobs_snapshot", "active_snapshot_id"),
        Index("idx_batch_jobs_template", "template_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    rubric_id = Column(Integer, ForeignKey("rubrics.id"), nullable=True, index=True)
    active_snapshot_id = Column(
        Integer, ForeignKey("evaluation_config_snapshots.id"), nullable=True
    )

    active_snapshot = relationship(
        "EvaluationConfigSnapshot", foreign_keys=[active_snapshot_id]
    )
    title = Column(String(255))  # e.g. "Software Engineer Campaign - Jan 2026"
    target_role = Column(String(255), nullable=True)  # Specific role for this campaign
    description = Column(Text, nullable=True)  # Job Description context for AI
    language = Column(
        String(255), default="English"
    )  # Recruiter's preferred interview language
    duration_minutes = Column(Integer, nullable=True)  # Recruiter-chosen duration
    difficulty = Column(String(50), nullable=True)  # easy, medium, hard, adaptive
    candidate_source = Column(
        String(50), nullable=True
    )  # upload, ats, referral, manual
    location = Column(String(255), nullable=True)  # Recruiter-chosen target location
    interview_instructions = Column(
        Text, nullable=True
    )  # Recruiter-defined custom interview instructions
    status = Column(String(50), default="active", index=True)  # active, archived

    # Campaign Templates & Sequences
    template_id = Column(Integer, ForeignKey("campaign_templates.id"), nullable=True)
    email_sequence_enabled = Column(Boolean, default=False)  # Enable follow-up sequence
    email_sequence_days = Column(
        Text, nullable=True
    )  # JSON: [3, 7, 14] days to send follow-ups

    # Campaign Analytics — DEPRECATED: now computed from child tables via batch_counters()
    # Dropped in migration m33: emails_sent, emails_opened, emails_clicked,
    # responses_received, application_count

    # Background Processing Tracking — DEPRECATED: use batch_counters() instead
    # Columns dropped in migration m37
    worker_status = Column(
        String(50), default="completed", index=True
    )  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    # Consent Tracking (GDPR)
    cv_processing_consent_confirmed = Column(Boolean, default=False, nullable=False)
    cv_processing_consent_confirmed_at = Column(DateTime, nullable=True)
    cv_processing_consent_confirmed_by = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    recruiter = relationship(
        "User", foreign_keys=[recruiter_id], back_populates="batch_jobs"
    )
    applications = relationship("Application", back_populates="batch_job")
    template = relationship("CampaignTemplate")

    @property
    def total_files(self) -> int:
        """Read-only — computed from child Application table (column dropped in m37)."""
        return 0

    @property
    def processed_files(self) -> int:
        """Read-only — computed from child Application table (column dropped in m37)."""
        return 0


def batch_counters(db, batch_id: int, qualified_threshold: float = 70.0) -> dict:
    """Compute campaign analytics from child tables instead of denormalized columns.

    Returns dict with keys: emails_sent, emails_opened, emails_clicked, responses_received,
    total_files, processed_files, failed_files, processing_status, application_count,
    qualified_count, qualified_threshold, avg_cv_score.
    """
    from backend.models.ats.application import Application

    apps = db.query(Application).filter(
        Application.batch_id == batch_id,
        Application.deleted_at.is_(None),
    )

    total_files = apps.count()

    processed_files = apps.filter(
        Application.status.isnot(None),
        Application.status != "pending",
    ).count()

    failed_files = apps.filter(
        Application.status.in_(["failed", "analysis_failed"])
    ).count()

    if total_files > 0 and processed_files >= total_files:
        processing_status = "completed"
    elif total_files > 0:
        processing_status = "processing"
    else:
        processing_status = "idle"

    emails_opened = apps.filter(Application.opened_at.isnot(None)).count()
    emails_clicked = apps.filter(Application.clicked_at.isnot(None)).count()

    # Qualified candidates threshold
    qualified_count = apps.filter(
        Application.analysis_score.isnot(None),
        Application.analysis_score >= qualified_threshold,
    ).count()

    # Avg CV Score
    scored_apps = [a.analysis_score for a in apps.all() if a.analysis_score is not None]
    avg_cv_score = round(sum(scored_apps) / len(scored_apps), 1) if scored_apps else None

    # EmailSequenceLog for emails_sent
    try:
        from backend.models.ats.campaign import EmailSequenceLog

        emails_sent = (
            db.query(EmailSequenceLog)
            .filter(EmailSequenceLog.batch_id == batch_id)
            .count()
        )
    except Exception:
        emails_sent = 0

    return {
        "emails_sent": emails_sent,
        "emails_opened": emails_opened,
        "emails_clicked": emails_clicked,
        "responses_received": 0,
        "total_files": total_files,
        "processed_files": processed_files,
        "failed_files": failed_files,
        "processing_status": processing_status,
        "application_count": total_files,
        "qualified_count": qualified_count,
        "qualified_threshold": qualified_threshold,
        "avg_cv_score": avg_cv_score,
    }


class PipelineStage(Base, TenantMixin):
    """Custom pipeline stages per recruiter/campaign"""

    __tablename__ = "pipeline_stages"
    __table_args__ = (
        Index("idx_pipeline_stages_recruiter", "recruiter_id"),
        Index("idx_pipeline_stages_order", "recruiter_id", "sort_order"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(
        Integer, ForeignKey("batch_jobs.id"), nullable=True, index=True
    )  # null = global stages

    name = Column(String(100), nullable=False)  # e.g. "Phone Screen", "Technical Test"
    slug = Column(String(100), nullable=False)  # e.g. "phone_screen"
    sort_order = Column(Integer, default=0)
    color = Column(String(20), default="#6366f1")  # Hex color for UI
    icon = Column(String(50), default="fa-circle")  # FontAwesome icon class
    is_default = Column(Boolean, default=False)  # Built-in stage
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User", foreign_keys=[recruiter_id])
    batch_job = relationship("BatchJob", foreign_keys=[batch_id])


class PipelineAutomationRule(Base, TenantMixin):
    """Smart automation rules for pipeline management"""

    __tablename__ = "pipeline_automation_rules"
    __table_args__ = (
        Index("idx_auto_rules_recruiter", "recruiter_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Trigger conditions (JSON)
    # e.g. {"type": "score_threshold", "field": "overall_score", "operator": ">=", "value": 80}
    trigger_json = deferred(Column(Text, nullable=False))

    # Action (JSON)
    # e.g. {"type": "move_stage", "target_stage": "interviewing", "send_notification": true}
    action_json = deferred(Column(Text, nullable=False))

    is_active = Column(Boolean, default=True)
    execution_count = Column(Integer, default=0)
    last_executed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User", foreign_keys=[recruiter_id])
