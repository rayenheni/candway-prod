"""
Sync subscription_history with the current SubscriptionHistory model.

Revision ID: m70
Revises: m69
Create Date: 2026-08-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m70"
down_revision: Union[str, None] = "m69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("subscription_history"):
        return

    columns = {c["name"] for c in inspector.get_columns("subscription_history")}

    # ------------------------------------------------------------------
    # Add fields required by the current SubscriptionHistory model.
    # Keep legacy m49 columns intact for now; this is intentionally
    # non-destructive.
    # ------------------------------------------------------------------

    if "user_id" not in columns:
        op.add_column(
            "subscription_history",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    if "action" not in columns:
        op.add_column(
            "subscription_history",
            sa.Column("action", sa.String(length=30), nullable=True),
        )

    if "amount_paid" not in columns:
        op.add_column(
            "subscription_history",
            sa.Column("amount_paid", sa.Float(), nullable=True),
        )

    if "transaction_id" not in columns:
        op.add_column(
            "subscription_history",
            sa.Column("transaction_id", sa.Integer(), nullable=True),
        )

    if "admin_user_id" not in columns:
        op.add_column(
            "subscription_history",
            sa.Column("admin_user_id", sa.Integer(), nullable=True),
        )

    if "notes" not in columns:
        op.add_column(
            "subscription_history",
            sa.Column("notes", sa.Text(), nullable=True),
        )

    # Refresh inspector after adding columns.
    inspector = sa.inspect(bind)

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes("subscription_history")
    }

    if "idx_sub_history_user" not in existing_indexes:
        op.create_index(
            "idx_sub_history_user",
            "subscription_history",
            ["user_id"],
        )

    if "idx_sub_history_transaction" not in existing_indexes:
        op.create_index(
            "idx_sub_history_transaction",
            "subscription_history",
            ["transaction_id"],
        )

    # ------------------------------------------------------------------
    # Foreign keys required by the current model.
    # ------------------------------------------------------------------

    existing_fks = {
        tuple(sorted(fk["constrained_columns"]))
        for fk in inspector.get_foreign_keys("subscription_history")
    }

    if ("user_id",) not in existing_fks:
        op.create_foreign_key(
            "fk_sub_history_user",
            "subscription_history",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if ("transaction_id",) not in existing_fks:
        op.create_foreign_key(
            "fk_sub_history_transaction",
            "subscription_history",
            "transactions",
            ["transaction_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if ("admin_user_id",) not in existing_fks:
        op.create_foreign_key(
            "fk_sub_history_admin_user",
            "subscription_history",
            "users",
            ["admin_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # The table is currently empty in production, so we can safely make
    # the new model-required fields non-null where the ORM requires it.
    # Keep this conditional so a partially-applied migration remains safe.
    inspector = sa.inspect(bind)
    columns_info = {
        c["name"]: c
        for c in inspector.get_columns("subscription_history")
    }

    if "user_id" in columns_info and columns_info["user_id"]["nullable"]:
        op.alter_column(
            "subscription_history",
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    if "action" in columns_info and columns_info["action"]["nullable"]:
        op.alter_column(
            "subscription_history",
            "action",
            existing_type=sa.String(length=30),
            nullable=False,
        )
    if "event" in columns:
        op.alter_column(
            "subscription_history",
            "event",
            existing_type=sa.String(length=50),
            nullable=True,
        )
def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("subscription_history"):
        return

    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("subscription_history")
        if fk.get("name")
    }

    for fk_name in (
        "fk_sub_history_admin_user",
        "fk_sub_history_transaction",
        "fk_sub_history_user",
    ):
        if fk_name in existing_fks:
            op.drop_constraint(
                fk_name,
                "subscription_history",
                type_="foreignkey",
            )

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes("subscription_history")
    }

    for index_name in (
        "idx_sub_history_transaction",
        "idx_sub_history_user",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="subscription_history")

    columns = {c["name"] for c in inspector.get_columns("subscription_history")}

    for column_name in (
        "notes",
        "admin_user_id",
        "transaction_id",
        "amount_paid",
        "action",
        "user_id",
    ):
        if column_name in columns:
            op.drop_column("subscription_history", column_name)
