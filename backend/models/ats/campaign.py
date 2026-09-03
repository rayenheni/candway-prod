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
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow


class WebhookIntegration(Base, TenantMixin):
    """External webhook integrations (Slack, Teams, etc.)"""

    __tablename__ = "webhook_integrations"
    __table_args__ = (
        Index("idx_webhooks_recruiter", "recruiter_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False)  # slack, teams, discord, custom
    webhook_url = Column(String(500), nullable=False)

    # Event filters (JSON)
    # e.g. ["application_created", "interview_completed", "offer_accepted"]
    events_json = Column(Text, nullable=False)

    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User", foreign_keys=[recruiter_id])


class BotIntegration(Base, TenantMixin):
    __tablename__ = "bot_integrations"
    __table_args__ = (
        Index("idx_bot_recruiter", "recruiter_id"),
        Index("idx_bot_platform", "platform", "platform_user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String(20), nullable=False)
    platform_user_id = Column(String(255), nullable=False)
    platform_team_id = Column(String(255), nullable=True)
    conversation_ref = Column(Text, nullable=True)
    access_token = Column(String(500), nullable=True)
    refresh_token = Column(String(500), nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User", foreign_keys=[recruiter_id])


class CampaignTemplate(Base, TenantMixin):
    """Pre-built campaign templates for common roles"""

    __tablename__ = "campaign_templates"
    __table_args__ = (
        Index("idx_campaign_templates_recruiter", "recruiter_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # null = system templates

    name = Column(String(255))  # e.g. "Software Engineer", "Sales Rep"
    role = Column(String(255))  # Target role
    description = Column(Text)  # Template description

    # Email content (with placeholders)
    subject_template = Column(String(500))  # Email subject
    body_template = Column(Text)  # Email body with {{name}}, {{role}}, etc.

    # Settings
    is_default = Column(Boolean, default=False)  # System default templates
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User")


class EmailTemplate(Base, TenantMixin):
    __tablename__ = "email_templates"
    __table_args__ = (
        Index("idx_email_templates_recruiter", "recruiter_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"))

    name = Column(String(255))  # e.g. "Standard Invite"
    subject = Column(String(255))
    body_html = deferred(
        Column(Text)
    )  # The HTML content with placeholders like {{candidate_name}}
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User", backref="email_templates")


# ============================================
# SUBSCRIPTION & BILLING MODELS
# ============================================


class EmailSequenceLog(Base, TenantMixin):
    __tablename__ = "email_sequence_logs"
    __table_args__ = (
        Index("idx_email_seq_app", "application_id"),
        Index("idx_email_seq_batch", "batch_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    batch_id = Column(Integer, ForeignKey("batch_jobs.id"), nullable=True)

    step_number = Column(Integer, nullable=False)
    subject = Column(String(500), nullable=True)
    sent_at = Column(DateTime, default=utcnow)

    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    unsubscribed_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="email_sequence_logs")
    batch = relationship("BatchJob")


class ReEngagementCampaign(Base, TenantMixin):
    __tablename__ = "reengagement_campaigns"
    __table_args__ = (
        Index("idx_re_campaign_recruiter", "recruiter_id"),
        Index("idx_re_campaign_job", "job_id"),
        Index("idx_re_campaign_status", "status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    total_candidates = Column(Integer, default=0)
    matched_candidates = Column(Integer, default=0)
    invited_count = Column(Integer, default=0)
    response_count = Column(Integer, default=0)
    avg_match_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="analyzing")

    recruiter = relationship("User", foreign_keys=[recruiter_id])
    job = relationship("Job", foreign_keys=[job_id])
    candidates_list = relationship(
        "ReEngagementCandidate", back_populates="campaign", cascade="all, delete-orphan"
    )


class ReEngagementCandidate(Base, TenantMixin):
    __tablename__ = "reengagement_candidates"
    __table_args__ = (
        Index("idx_re_candidate_campaign", "campaign_id"),
        Index("idx_re_candidate_application", "application_id"),
        Index("idx_re_candidate_response", "response_status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("reengagement_campaigns.id"))
    application_id = Column(Integer, ForeignKey("applications.id"))
    match_score = Column(Float)
    match_reason = Column(Text)
    invited_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    response_status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    campaign = relationship("ReEngagementCampaign", back_populates="candidates_list")
    application = relationship("Application", back_populates="reengagement_candidates")
