"""Verdict domain model — business decision for an Application."""

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
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Verdict(Base, TenantMixin):
    """Business decision about an Application.

    One active verdict per Application. Superseding creates a
    new row linked to the previous one for auditable appeal trail.
    """

    __tablename__ = "verdicts"
    __table_args__ = (
        Index("idx_verdict_application", "application_id"),
        Index("idx_verdict_decision", "decision"),
        Index("idx_verdict_source", "source"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    decision = Column(String(20), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    decided_by = Column(String(255), nullable=False)
    decided_at = Column(DateTime, default=utcnow)
    source = Column(String(20), nullable=False)
    evaluation_session_id = Column(
        Integer, ForeignKey("evaluation_sessions.id"), nullable=True
    )

    # Supersession chain (for appeal / overturn)
    superseded_at = Column(DateTime, nullable=True)
    superseded_by = Column(Integer, ForeignKey("verdicts.id"), nullable=True)

    # Compliance
    adverse_action_sent = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utcnow)

    # Relationships
    application = relationship(
        "Application",
        foreign_keys=[application_id],
        back_populates="verdicts",
    )
    evaluation_session = relationship(
        "EvaluationSession",
        foreign_keys=[evaluation_session_id],
    )
    superseding_verdict = relationship(
        "Verdict",
        foreign_keys=[superseded_by],
        remote_side=[id],
        uselist=False,
    )
