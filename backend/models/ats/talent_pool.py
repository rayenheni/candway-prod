"""TalentPool models — curated candidate pools for enterprise sourcing.

A TalentPool is a named collection of candidates curated by a recruiter.
Candidates can belong to multiple talent pools across the same company.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class TalentPool(Base, TenantMixin):
    """A named pool of candidates curated for a company."""

    __tablename__ = "talent_pools"
    __table_args__ = (
        Index("idx_talent_pools_company", "company_id"),
        UniqueConstraint("company_id", "name", name="uq_talent_pools_company_name"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)

    creator = relationship("User", foreign_keys=[created_by])
    candidates = relationship(
        "TalentPoolCandidate",
        back_populates="talent_pool",
        cascade="all, delete-orphan",
    )


class TalentPoolCandidate(Base, TenantMixin):
    """Membership linking a Candidate to a TalentPool."""

    __tablename__ = "talent_pool_candidates"
    __table_args__ = (
        Index("idx_tpc_pool", "talent_pool_id"),
        Index("idx_tpc_candidate", "candidate_id"),
        UniqueConstraint(
            "talent_pool_id", "candidate_id", name="uq_tpc_pool_candidate"
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    talent_pool_id = Column(
        Integer, ForeignKey("talent_pools.id"), nullable=False, index=True
    )
    candidate_id = Column(
        Integer, ForeignKey("candidates.id"), nullable=False, index=True
    )
    notes = Column(Text, nullable=True)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    deleted_at = Column(DateTime, nullable=True)

    talent_pool = relationship(
        "TalentPool", back_populates="candidates", foreign_keys=[talent_pool_id]
    )
    candidate = relationship(
        "Candidate",
        back_populates="talent_pool_memberships",
        foreign_keys=[candidate_id],
    )
    added_by_user = relationship("User", foreign_keys=[added_by])
