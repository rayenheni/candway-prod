"""Candidate model — one row per unique person across all applications.

Every candidate has at least one Application record.  This table
deduplicates by (company_id, email) so the system can distinguish
"42 applications from 37 unique candidates".

Sprint 3 enrichment added skills, headline, bio, location, and
internal_mobility flag.
"""

from sqlalchemy import (
    Boolean,
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


class Candidate(Base, TenantMixin):
    """Unique candidate (person) within a company."""

    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_candidates_company_email"),
        Index("idx_candidates_email", "email"),
        Index("idx_candidates_company_email", "company_id", "email"),
        # NOTE: idx_candidates_skills on a Text column omitted — MySQL forbids
        # indexing a bare TEXT column (key too long, 3072B). `skills` is full-text
        # searched at the query layer (LIKE/JSON), never prefix-matched, so no
        # index is required for correctness. Kept as a no-op entry only on SQLite.
        {"extend_existing": True},
    )

    # company_id is user-scoped for standalone job seekers: a candidate may
    # exist without any company until they apply to a company's job or are
    # invited by a recruiter/campaign. NULL until they acquire a company
    # context (mirrors m61 migration).
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=False)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    photo_url = Column(String(512), nullable=True)

    # Sprint 3 enrichment — lifted from CandidateProfile
    headline = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    internal_mobility = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)

    applications = relationship(
        "Application",
        back_populates="candidate",
        foreign_keys="Application.candidate_id",
    )
    talent_pool_memberships = relationship(
        "TalentPoolCandidate", back_populates="candidate", cascade="all, delete-orphan"
    )
