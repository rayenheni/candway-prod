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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Company(Base):
    """Enterprise tenant — isolates all data per company."""

    __tablename__ = "companies"
    __table_args__ = (
        Index("idx_companies_slug", "slug"),
        Index("idx_companies_active", "is_active"),
        Index("idx_companies_plan", "plan_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=True)

    tier = Column(String(50), default="free")
    subscription_status = Column(String(50), default="active")
    max_users = Column(Integer, default=10)
    max_jobs = Column(Integer, default=50)
    max_ai_interviews = Column(Integer, default=500)

    # Company-level subscription (plan the organization purchased; seats)
    plan_id = Column(
        Integer,
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Company-level billing / KYB
    billing_email = Column(String(255), nullable=True)
    billing_address = Column(String(255), nullable=True)
    tax_id = Column(String(50), nullable=True)
    kyb_status = Column(String(20), nullable=True)  # pending, approved, rejected
    kyb_documents = Column(
        Text, nullable=True
    )  # JSON array of uploaded proof doc paths

    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime, nullable=True)

    members = relationship(
        "CompanyMember", back_populates="company", cascade="all, delete-orphan"
    )
    plan = relationship("SubscriptionPlan", foreign_keys=[plan_id])

    @property
    def seats_available(self) -> int:
        """Number of recruiter seats the company can still create."""
        used = (
            sum(1 for m in self.members if m.is_active and m.role == "recruiter")
            if self.members
            else 0
        )
        return max(0, (self.max_users or 0) - used)


class CompanyMember(Base):
    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_member"),
        Index("idx_company_members_role", "role"),
        Index("idx_company_members_user_active", "user_id", "is_active"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role = Column(String(50), default="member")
    permissions = Column(Text, nullable=True)

    invited_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    company = relationship("Company", back_populates="members")
    user = relationship("User")


# =============================================================================
# ENTERPRISE: AI Calibration (DB-backed)
# =============================================================================


class CompanyVerification(Base, TenantMixin):
    __tablename__ = "company_verifications"
    __table_args__ = (
        Index("idx_company_verifications_user", "user_id"),
        Index("idx_company_verifications_verified_by", "verified_by"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # Recruiter ID

    # KYB Fields
    company_name = Column(String(255))
    matricule_fiscale = Column(String(50))  # Critical for Tunisia
    registre_commerce_id = Column(String(50))
    address = Column(String(255))

    # Document Proof
    document_url = Column(String(255))  # PDF/Image of MF/RC

    # Workflow
    status = Column(
        String(20), default="pending", index=True
    )  # pending, approved, rejected
    admin_notes = Column(Text, nullable=True)

    # Timestamps
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin ID
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    verifier = relationship("User", foreign_keys=[verified_by])
