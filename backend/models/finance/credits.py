"""Credit wallet, immutable credit ledger, and usage metering models.

Monetization S2 — universal AI credit system replacing scattered per-plan
counters. All credit movements are internal SQL transactions: no payment
provider SDK, no webhooks. idempotency_key prevents double-charge on retries.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.models.base import Base, TenantMixin, utcnow


class CreditWallet(Base, TenantMixin):
    __tablename__ = "credit_wallets"
    __table_args__ = (
        Index("idx_credit_wallets_user", "user_id", unique=True),
        Index("idx_credit_wallets_company", "company_id"),
        {"extend_existing": True},
    )

    # Wallets are user-scoped — standalone users belong to no company.
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    balance = Column(Numeric(18, 4), nullable=False, default=0.0)
    currency = Column(String(10), default="CRED")
    version = Column(Integer, nullable=False, default=0)  # optimistic lock
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User")
    transactions = relationship(
        "CreditTransaction", back_populates="wallet", order_by="CreditTransaction.id"
    )


class CreditTransaction(Base, TenantMixin):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        Index("idx_credit_tx_wallet", "wallet_id"),
        Index("idx_credit_tx_user", "user_id"),
        Index("idx_credit_tx_type", "type"),
        Index("idx_credit_tx_resource", "resource"),
        Index("idx_credit_tx_idempotency", "idempotency_key", unique=True),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("credit_wallets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # User-scoped ledger — company_id is attribution only.
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Signed movement: + grant/purchase/topup/refund, - consume
    amount = Column(Numeric(18, 4), nullable=False)

    # grant|purchase|topup|consume|refund|adjustment|promo|expire|rollback
    type = Column(String(20), nullable=False, default="consume")

    resource = Column(String(64), nullable=True)  # e.g. ai_interview_turn
    reference_type = Column(String(64), nullable=True)
    reference_id = Column(Integer, nullable=True)

    actor_type = Column(String(16), default="system")  # user|system|admin|promo
    actor_id = Column(Integer, nullable=True)

    provider = Column(String(16), default="system")  # manual|promo|admin|system
    provider_ref = Column(String(128), nullable=True)  # invoice number / promo code

    idempotency_key = Column(String(128), nullable=False)

    status = Column(
        String(16), default="succeeded"
    )  # pending|succeeded|failed|reversed
    note = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utcnow)

    wallet = relationship("CreditWallet", back_populates="transactions")


class UsageEvent(Base, TenantMixin):
    """Metering stream for analytics dashboards (Part 7).

    Append-only: written at every AI/paid feature call, never mutated.
    """

    __tablename__ = "usage_events"
    __table_args__ = (
        Index("idx_usage_events_user", "user_id"),
        Index("idx_usage_events_company", "company_id"),
        Index("idx_usage_events_resource", "resource"),
        Index("idx_usage_events_created", "created_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resource = Column(String(64), nullable=False)  # ai_interview_turn, cv_analysis, ...
    credits = Column(Integer, default=0)
    cost_usd = Column(Numeric(12, 6), nullable=True)
    model = Column(String(64), nullable=True)
    reference_type = Column(String(64), nullable=True)
    reference_id = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # User-scoped metering — company_id is attribution only.
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    user = relationship("User")
