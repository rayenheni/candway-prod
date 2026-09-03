"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class OfferTemplate(Base, TenantMixin):
    """Offer letter templates"""

    __tablename__ = "offer_templates"
    __table_args__ = (
        Index("idx_offer_templates_recruiter", "recruiter_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"))

    # Template Details
    name = Column(String(255), nullable=False)
    subject = Column(String(500))
    body = Column(Text)  # HTML content with placeholders

    # Placeholders: {{candidate_name}}, {{position}}, {{salary}}, {{start_date}}

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, onupdate=utcnow)

    # Relationships
    recruiter = relationship("User")


class Offer(Base, TenantMixin):
    """Job offers sent to candidates"""

    __tablename__ = "offers"
    __table_args__ = (
        Index("idx_offers_created_by", "created_by"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    # Offer Details
    position = Column(String(255))
    salary = Column(String(100))
    start_date = Column(Date, nullable=True)

    # Offer Letter
    subject = Column(String(500))
    body = Column(Text)  # HTML content

    # Status
    status = Column(
        String(50), default="pending", index=True
    )  # pending, accepted, declined, expired

    # E-signature
    signature_request_id = Column(String(255), nullable=True)  # DocuSign/HelloSign ID
    signed_at = Column(DateTime, nullable=True)

    # Expiration
    expires_at = Column(DateTime, nullable=True)

    # Response
    candidate_response = Column(Text, nullable=True)
    responded_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, onupdate=utcnow)

    # Relationships
    application = relationship("Application", back_populates="offers")
    creator = relationship("User", foreign_keys=[created_by])


class BackgroundCheck(Base, TenantMixin):
    __tablename__ = "background_checks"
    __table_args__ = (
        Index("idx_bg_app", "application_id"),
        Index("idx_bg_offer", "offer_id"),
        Index("idx_bg_recruiter", "recruiter_id"),
        Index("idx_bg_status", "status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"))
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="SET NULL"), nullable=True
    )
    recruiter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    provider = Column(String(50), default="checkr")
    provider_candidate_id = Column(String(255), nullable=True)
    provider_report_id = Column(String(255), nullable=True)
    status = Column(String(50), default="pending")
    verdict = Column(String(50), nullable=True)
    findings = Column(Text, nullable=True)
    report_url = Column(String(500), nullable=True)
    candidate_notified_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    application = relationship(
        "Application", foreign_keys=[application_id], back_populates="background_checks"
    )
    offer = relationship("Offer", foreign_keys=[offer_id])
    recruiter = relationship("User", foreign_keys=[recruiter_id])


class BackgroundCheckStatusLog(Base, TenantMixin):
    __tablename__ = "background_check_status_logs"
    __table_args__ = (
        Index("idx_bg_status_log_check", "background_check_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    background_check_id = Column(
        Integer, ForeignKey("background_checks.id"), nullable=False
    )
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    background_check = relationship("BackgroundCheck")
    changer = relationship("User", foreign_keys=[changed_by])


# ============================================================================
# v3.0 — CANONICAL DOMAIN ENTITIES (Single Source of Truth)
# ============================================================================
# These entities replace ad-hoc JSON bags and duplicated columns on Application.
# Migration plan:
#   Phase 1: Create alongside existing columns (dual-write)
#   Phase 2: Cut over reads to new entities
#   Phase 3: Drop legacy columns from Application
# ============================================================================
