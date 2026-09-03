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
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class Transaction(Base, TenantMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_user_status", "user_id", "status"),
        Index("idx_transactions_idempotency", "idempotency_key"),
        Index("idx_transactions_approved_by", "approved_by"),
        Index("idx_transactions_rejected_by", "rejected_by"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    currency = Column(String(255), default="TND")
    status = Column(String(255))
    description = Column(String(255))
    proof_url = Column(String(255), nullable=True)  # Manual payment proof
    proof_status = Column(String(50), nullable=False, default="uploaded")  # S10 proof workflow
    proof_verified_at = Column(DateTime, nullable=True)
    proof_verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    proof_file_size = Column(Integer, nullable=True)
    proof_file_type = Column(String(100), nullable=True)
    proof_review_notes = Column(Text, nullable=True)

    # Fiscal Compliance
    amount_ht = Column(Float, default=0.0)
    tva_amount = Column(Float, default=0.0)
    stamp_duty = Column(Float, default=1.000)
    amount_ttc = Column(Float, default=0.0)

    # P0-05 FIX: Approval idempotency. ``approved_at``/``approved_by``
    # let the admin endpoint detect a double-approval attempt and
    # refuse to extend the subscription window twice. The
    # ``idempotency_key`` lets a client re-submit the same approval
    # request safely (network retry) without double-applying.
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])


# ============================================
# PREMIUM LMS MODELS
# ============================================


class Invoice(Base, TenantMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("idx_invoices_user", "user_id"),
        Index("idx_invoices_transaction", "transaction_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(
        String(50), unique=True, index=True
    )  # Format: INV-2024-0001
    user_id = Column(Integer, ForeignKey("users.id"))
    transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=True
    )  # Optional link to Stripe/System transaction

    # Financials (TND)
    amount_ht = Column(Float)  # Amount Excluding Tax
    tva_rate = Column(Float, default=19.0)  # 19% Standard
    tva_amount = Column(Float)
    retenue_source = Column(Float, default=0.0)  # For B2B
    stamp_duty = Column(Float, default=1.000)  # Timbre fiscal (1 TND)
    total_ttc = Column(Float)  # Total including all taxes

    # Legal Mentions Snapshot
    client_name = Column(String(255))
    client_mf = Column(String(50), nullable=True)  # Matricule Fiscale
    client_address = Column(String(255), nullable=True)

    status = Column(String(20), default="draft")  # draft, paid, cancelled
    pdf_url = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utcnow)
    due_date = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")
    transaction = relationship("Transaction")


class SavedReport(Base, TenantMixin):
    __tablename__ = "saved_reports"
    __table_args__ = (
        Index("idx_saved_reports_recruiter", "recruiter_id"),
        Index("idx_saved_reports_scheduled", "is_scheduled", "next_scheduled_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(255))
    description = Column(Text, nullable=True)
    config = Column(Text)
    is_scheduled = Column(Boolean, default=False)
    schedule_frequency = Column(String(50), nullable=True)
    schedule_recipients = Column(Text, nullable=True)
    last_generated_at = Column(DateTime, nullable=True)
    next_scheduled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    recruiter = relationship("User")

    snapshots = relationship("ReportSnapshot", back_populates="report")


class ReportSnapshot(Base, TenantMixin):
    __tablename__ = "report_snapshots"
    __table_args__ = (
        Index("idx_snapshots_report", "report_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey("saved_reports.id"))
    report_data = Column(Text)
    generated_at = Column(DateTime, default=utcnow)
    file_path = Column(String(500), nullable=True)

    report = relationship("SavedReport", back_populates="snapshots")


class CampaignCost(Base, TenantMixin):
    """Track costs associated with campaigns for cost-per-hire analytics"""

    __tablename__ = "campaign_costs"
    __table_args__ = (
        Index("idx_campaign_costs_batch", "batch_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batch_jobs.id"), nullable=False, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    cost_type = Column(
        String(50), nullable=False
    )  # job_posting, email_campaign, agency_fee, ad_spend
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="TND")
    description = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=utcnow)

    batch_job = relationship("BatchJob")
    recruiter = relationship("User", foreign_keys=[recruiter_id])
