"""Create credit_wallets, credit_transactions, usage_events

Monetization S2 — universal AI credit wallet + immutable ledger + usage
metering stream.

Revision ID: m48
Revises: m47
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m48"
down_revision: Union[str, None] = "m47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("credit_wallets"):
        op.create_table(
            "credit_wallets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("balance", sa.Numeric(18, 4), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_credit_wallets_user", "credit_wallets", ["user_id"], unique=True)
        op.create_index("idx_credit_wallets_company", "credit_wallets", ["company_id"])
        op.create_index(op.f("ix_credit_wallets_id"), "credit_wallets", ["id"])

    if not inspector.has_table("credit_transactions"):
        op.create_table(
            "credit_transactions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("wallet_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("resource", sa.String(length=64), nullable=True),
            sa.Column("reference_type", sa.String(length=64), nullable=True),
            sa.Column("reference_id", sa.Integer(), nullable=True),
            sa.Column("actor_type", sa.String(length=16), nullable=True),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("provider", sa.String(length=16), nullable=True),
            sa.Column("provider_ref", sa.String(length=128), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
            sa.Column("meta_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["wallet_id"], ["credit_wallets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )
        op.create_index("idx_credit_tx_company", "credit_transactions", ["company_id"])
        op.create_index(op.f("ix_credit_transactions_id"), "credit_transactions", ["id"])
        op.create_index("idx_credit_tx_wallet", "credit_transactions", ["wallet_id"])

    if not inspector.has_table("usage_events"):
        op.create_table(
            "usage_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("cost_credits", sa.Numeric(18, 4), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_usage_events_company", "usage_events", ["company_id"])
        op.create_index("idx_usage_events_user", "usage_events", ["user_id"])
        op.create_index(op.f("ix_usage_events_id"), "usage_events", ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in ("usage_events", "credit_transactions", "credit_wallets"):
        if inspector.has_table(table):
            op.drop_table(table)
