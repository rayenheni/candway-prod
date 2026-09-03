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
from sqlalchemy.orm import deferred, relationship

from backend.encryption import EncryptedText
from backend.models.base import Base, TenantMixin, utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_tier", "tier"),
        Index("idx_users_subscription", "subscription_status"),
        Index("idx_users_deleted_role", "deleted_at", "role"),
        Index("idx_users_subscription_end", "subscription_end"),
        Index("idx_users_current_plan", "current_plan_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for ghost users
    temp_password = Column(
        String(255), nullable=True
    )  # Auto-generated password for invited candidates
    role = Column(String(255))  # 'candidate', 'recruiter', 'mentor', 'admin'

    # Candway 2.0 - Access Tiers
    tier = Column(String(255), default="free")  # 'free' or 'pro'
    subscription_status = Column(
        String(255), default="active"
    )  # 'active', 'expired', 'pending_approval'
    subscription_plan = Column(String(255), default="free")  # Specific plan name
    subscription_end = Column(DateTime, nullable=True)
    payment_proof_path = Column(String(255), nullable=True)  # Manual payment proof

    # ── DEPRECATED: use CandidateProfile ──────────────────────────────
    # These columns still exist for backward compatibility during migration.
    # All new code MUST read/write through the profile relationship.
    # See docs/entity-ownership.md and PHASE-1 migration plan.
    name = Column(String(255))  # → CandidateProfile.name / RecruiterProfile.name
    phone = Column(String(255))  # → CandidateProfile.phone / RecruiterProfile.phone
    headline = Column(String(255))  # → CandidateProfile.headline
    bio = Column(Text)  # → CandidateProfile.bio
    location = Column(String(255))  # → CandidateProfile
    linkedin_url = Column(String(255))  # → CandidateProfile.linkedin_url
    github_url = Column(String(255))  # → CandidateProfile.github_url
    portfolio_url = Column(String(255))  # → CandidateProfile.portfolio_url
    avatar_url = Column(String(255))  # → CandidateProfile.avatar_url
    skills = Column(Text, nullable=True)  # → CandidateProfile.skills

    # ── DEPRECATED: use CandidateProfile ──────────────────────────────
    languages = Column(String(255), nullable=True)  # → CandidateProfile.languages
    availability = Column(String(255), nullable=True)  # → CandidateProfile.availability
    work_preference = Column(
        String(255), nullable=True
    )  # → CandidateProfile.work_preference
    salary_expectation_min = Column(
        Integer, nullable=True
    )  # → CandidateProfile.salary_expectation_min
    salary_expectation_max = Column(
        Integer, nullable=True
    )  # → CandidateProfile.salary_expectation_max

    # ── DEPRECATED: use RecruiterProfile ──────────────────────────────
    company_name = Column(String(255))  # → RecruiterProfile.company_name
    company_description = Column(Text)  # → RecruiterProfile.company_description
    company_logo_url = Column(String(255))  # → RecruiterProfile.company_logo_url

    # ── DEPRECATED: use RecruiterProfile ──────────────────────────────
    smtp_host = Column(String(255))  # → RecruiterProfile.smtp_host
    smtp_port = Column(Integer)  # → RecruiterProfile.smtp_port
    smtp_user = Column(String(255))  # → RecruiterProfile.smtp_user
    smtp_password = Column(EncryptedText(512))  # → RecruiterProfile.smtp_password

    # ── DEPRECATED: use RecruiterProfile ──────────────────────────────
    usage_jobs = Column(Integer, default=0)  # → RecruiterProfile.usage_jobs
    usage_cvs = Column(Integer, default=0)  # → RecruiterProfile.usage_cvs
    usage_ai_interviews = Column(
        Integer, default=0
    )  # → RecruiterProfile.usage_ai_interviews
    usage_reset_date = Column(
        DateTime, nullable=True
    )  # → RecruiterProfile.usage_reset_date

    # ── DEPRECATED: use CandidateProfile ──────────────────────────────
    candidate_cv_uploads_this_month = Column(Integer, default=0)  # → CandidateProfile
    candidate_ai_analyses_this_month = Column(Integer, default=0)  # → CandidateProfile
    candidate_pdf_downloads_this_month = Column(
        Integer, default=0
    )  # → CandidateProfile
    candidate_usage_reset_date = Column(DateTime, nullable=True)  # → CandidateProfile

    # ── DEPRECATED: use CandidateProfile ──────────────────────────────
    profile_views = Column(Integer, default=0)  # → CandidateProfile.profile_views
    profile_views_growth = Column(
        Float, default=12.0
    )  # → CandidateProfile.profile_views_growth

    current_plan_id = Column(
        Integer, ForeignKey("subscription_plans.id"), nullable=True
    )
    current_plan = relationship("SubscriptionPlan", foreign_keys=[current_plan_id])

    created_at = Column(DateTime, default=utcnow)

    # Security Fields
    marketing_consent = Column(Boolean, default=False)  # GDPR Art. 6
    data_processing_consent = Column(Boolean, default=False)  # GDPR Art. 6
    email_verified = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False, index=True)
    lockout_until = Column(DateTime, nullable=True)

    # Soft Delete
    deleted_at = Column(DateTime, nullable=True, index=True)

    # RBAC (Phase 3)
    admin_permissions = Column(
        Text, nullable=True
    )  # CSV: 'manage_users,manage_finance,manage_content'
    # ── DEPRECATED: use AdminProfile.is_super_admin ────────────────────
    is_super_admin = Column(Boolean, default=False, index=True, nullable=False)

    applications = relationship(
        "Application", back_populates="owner", foreign_keys="Application.user_id"
    )
    batch_jobs = relationship(
        "BatchJob", back_populates="recruiter", foreign_keys="BatchJob.recruiter_id"
    )

    # NEW: Relationships for profile visitors
    visits_received = relationship(
        "ProfileVisit",
        foreign_keys="ProfileVisit.candidate_id",
        back_populates="candidate",
    )
    visits_made = relationship(
        "ProfileVisit", foreign_keys="ProfileVisit.visitor_id", back_populates="visitor"
    )
    saved_jobs = relationship("SavedJob", back_populates="user")
    roadmaps = relationship("CareerRoadmap", back_populates="user")
    notification_preferences = relationship(
        "NotificationPreference", back_populates="user"
    )


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True)
    success = Column(Boolean)
    timestamp = Column(DateTime, default=utcnow, index=True)
    ip_address = Column(String(255))

    __table_args__ = (
        Index("idx_login_attempts_email_timestamp", "email", "timestamp"),
        Index("idx_login_attempts_ip_timestamp", "ip_address", "timestamp"),
        {"extend_existing": True},
    )


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (
        Index("idx_email_verifications_user", "user_id"),
        {"extend_existing": True},
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token = Column(String(255), unique=True, index=True)
    code = Column(String(6), nullable=True)  # 6-digit OTP code
    expires_at = Column(DateTime)
    verified = Column(Boolean, default=False)


class PasswordReset(Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        Index("idx_password_resets_user", "user_id"),
        {"extend_existing": True},
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token = Column(String(255), unique=True, index=True)
    expires_at = Column(DateTime)
    used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)  # Added missing field
    ip_address = Column(String(255), nullable=True)  # Added missing field
    created_at = Column(DateTime, default=utcnow)


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    __table_args__ = (
        Index("idx_token_blacklist_invalidated", "invalidated_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    # Nullable: interview-nonce entries (verify_interview_token's DB fallback)
    # are not linked to a real user, so user_id may be NULL.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    reason = Column(String(255), nullable=False)
    invalidated_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_user", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_timestamp", "timestamp"),
        {"extend_existing": True},
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), index=True
    )  # Person performing the action
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    action = Column(
        String(255)
    )  # e.g., 'impersonate', 'delete_user', 'change_settings'
    target_id = Column(String(255), nullable=True)  # ID of target object
    details = deferred(Column(Text, nullable=True))
    ip_address = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=utcnow, index=True)


class ConsentLog(Base):
    """Immutable log of user consent for legal compliance (GDPR Art. 7)"""

    __tablename__ = "consent_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # What did they agree to?
    agreement_type = Column(
        String(50)
    )  # "terms", "privacy", "marketing", "data_processing"
    version = Column(String(50))  # e.g., "v1.0", "2026-02-14"

    # Context
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(String(500))

    # Timestamp
    accepted_at = Column(DateTime, default=utcnow)

    user = relationship("User")


class FeatureFlag(Base, TenantMixin):
    """Feature flags for gradual rollout of new features (S7 extension).

    A row is either global (user_id NULL) or a per-user override (user_id set).
    S7 adds governance/rollout controls: visibility, audiences, kill switches,
    dependencies, plan restrictions and temporary/permanent user unlocks.
    """

    __tablename__ = "feature_flags"
    __table_args__ = (
        Index("idx_feature_flags_key", "flag_key"),
        Index("idx_feature_flags_user", "user_id"),
        Index("idx_feature_flags_key_audiences", "flag_key", "audiences"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    flag_key = Column(
        String(100), nullable=False, index=True
    )  # e.g. "recruiter_enhancements"
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )  # null = global flag

    enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0)  # 0-100 for gradual rollout
    description = Column(String(500), nullable=True)

    # ── S7 governance / rollout controls ──────────────────────────────
    visibility = Column(
        String(20), default="public"
    )  # public|beta|internal|hidden|experimental
    audiences = Column(
        String(100), default="all"
    )  # recruiter|candidate|admin|enterprise|all
    maintenance_mode = Column(Boolean, default=False)  # soft kill switch
    kill_switch = Column(Boolean, default=False)  # hard kill switch
    depends_on = Column(String(100), nullable=True)  # feature dependency key
    plan_restrictions = Column(String(255), nullable=True)  # CSV of allowed plan slugs
    company_override_key = Column(
        String(100), nullable=True
    )  # per-company override key
    temp_unlock_user_id = Column(Integer, nullable=True, index=True)
    temp_unlock_until = Column(DateTime, nullable=True)
    permanent_unlock_user_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", foreign_keys=[user_id])


class Notification(Base, TenantMixin):
    """In-app notifications for users"""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user", "user_id"),
        Index("idx_notifications_read", "is_read"),
        Index("idx_notifications_created", "created_at"),
        Index(
            "idx_notifications_user_read_created", "user_id", "is_read", "created_at"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String(20), default="info")

    related_type = Column(String(50), nullable=True)
    related_id = Column(Integer, nullable=True)
    payload_json = Column(Text, nullable=True)

    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])


class NotificationPreference(Base):
    """Per-user notification type/channel preferences"""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "notification_type", name="uq_user_notification_type"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notification_type = Column(
        String(50), nullable=False
    )  # 'interview_reminder', 'offer_expiration', etc.
    channel = Column(
        String(20), nullable=False, default="email"
    )  # 'email', 'websocket', 'bot'
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="notification_preferences")


# ============================================================================
# RUBRIC ENGINE TABLES (Deterministic Scoring System)
# ============================================================================


class ProfileVisit(Base):
    __tablename__ = "profile_visits"
    __table_args__ = (
        Index("idx_profile_visits_candidate", "candidate_id"),
        Index("idx_profile_visits_visitor", "visitor_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("users.id"), index=True)
    visitor_id = Column(Integer, ForeignKey("users.id"), index=True)

    created_at = Column(DateTime, default=utcnow, index=True)

    candidate = relationship(
        "User", foreign_keys=[candidate_id], back_populates="visits_received"
    )
    visitor = relationship(
        "User", foreign_keys=[visitor_id], back_populates="visits_made"
    )


# ============================================================================
# PROMPT MANAGEMENT MODELS
# ============================================================================


class UndoAction(Base, TenantMixin):
    """Undo buffer for recent recruiter actions"""

    __tablename__ = "undo_actions"
    __table_args__ = (
        Index("idx_undo_user", "user_id"),
        Index("idx_undo_expires", "expires_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    action_type = Column(String(50), nullable=False)  # status_change, delete, invite
    target_type = Column(String(50), nullable=False)  # application, campaign
    target_id = Column(Integer, nullable=False)

    # State before action (JSON) — used to rollback
    previous_state_json = Column(Text, nullable=False)

    # State after action (JSON) — for reference
    new_state_json = Column(Text, nullable=True)

    expires_at = Column(
        DateTime, nullable=False, index=True
    )  # 10 seconds from creation
    is_executed = Column(Boolean, default=False)  # True if undo was performed
    is_expired = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])


# =============================================================================
# ENTERPRISE: Tenant Management
# =============================================================================
