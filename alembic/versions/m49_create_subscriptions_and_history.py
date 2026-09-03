"""Create subscriptions + subscription_history lifecycle tables

Monetization S3 — the Subscription row becomes the single source of truth
for billing state; profile tier/subscription_* columns become cached
mirrors. subscription_history records every lifecycle event.

Revision ID: m49
Revises: m48
Create Date: 2026-08-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m49"
down_revision: Union[str, None] = "m48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("plan_version_id", sa.Integer(), nullable=True),
            sa.Column("target_audience", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("billing_cycle", sa.String(length=10), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("current_period_start", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("grace_end", sa.DateTime(), nullable=True),
            sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
            sa.Column("canceled_at", sa.DateTime(), nullable=True),
            sa.Column("reason_canceled", sa.String(length=255), nullable=True),
            sa.Column("last_payment_transaction_id", sa.Integer(), nullable=True),
            sa.Column("renewal_reminder_sent", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(
                ["plan_version_id"], ["plan_versions.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["last_payment_transaction_id"], ["transactions.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_subscriptions_user", "subscriptions", ["user_id"])
        op.create_index("idx_subscriptions_plan", "subscriptions", ["plan_id"])
        op.create_index("idx_subscriptions_status", "subscriptions", ["status"])
        op.create_index("idx_subscriptions_company", "subscriptions", ["company_id"])
        op.create_index(op.f("ix_subscriptions_id"), "subscriptions", ["id"])

    if not inspector.has_table("subscription_history"):
        op.create_table(
            "subscription_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("subscription_id", sa.Integer(), nullable=False),
            sa.Column("event", sa.String(length=50), nullable=False),
            sa.Column("from_status", sa.String(length=20), nullable=True),
            sa.Column("to_status", sa.String(length=20), nullable=True),
            sa.Column("from_plan_id", sa.Integer(), nullable=True),
            sa.Column("to_plan_id", sa.Integer(), nullable=True),
            sa.Column("reason", sa.String(length=255), nullable=True),
            sa.Column("actor_type", sa.String(length=20), nullable=True),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["from_plan_id"], ["subscription_plans.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_plan_id"], ["subscription_plans.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_sub_hist_subscription", "subscription_history", ["subscription_id"])
        op.create_index("idx_sub_hist_company", "subscription_history", ["company_id"])
        op.create_index(op.f("ix_subscription_history_id"), "subscription_history", ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in ("subscription_history", "subscriptions"):
        if inspector.has_table(table):
            op.drop_table(table)
