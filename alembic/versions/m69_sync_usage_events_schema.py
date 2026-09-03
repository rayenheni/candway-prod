"""
Sync usage_events schema with the current UsageEvent model.

Revision ID: m69
Revises: m68
Create Date: 2026-08-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m69"
down_revision: Union[str, None] = "m68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("usage_events"):
        return

    columns = {c["name"] for c in inspector.get_columns("usage_events")}

    # Legacy -> current model naming.
    if "event_type" in columns and "resource" not in columns:
        op.alter_column(
            "usage_events",
            "event_type",
            new_column_name="resource",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
        columns.remove("event_type")
        columns.add("resource")

    if "cost_credits" in columns and "credits" not in columns:
        op.alter_column(
            "usage_events",
            "cost_credits",
            new_column_name="credits",
            existing_type=sa.Numeric(18, 4),
            existing_nullable=False,
        )
        columns.remove("cost_credits")
        columns.add("credits")

    # Current model fields.
    if "cost_usd" not in columns:
        op.add_column(
            "usage_events",
            sa.Column(
                "cost_usd",
                sa.Numeric(12, 6),
                nullable=True,
            ),
        )

    if "model" not in columns:
        op.add_column(
            "usage_events",
            sa.Column(
                "model",
                sa.String(length=64),
                nullable=True,
            ),
        )

    if "reference_type" not in columns:
        op.add_column(
            "usage_events",
            sa.Column(
                "reference_type",
                sa.String(length=64),
                nullable=True,
            ),
        )

    if "reference_id" not in columns:
        op.add_column(
            "usage_events",
            sa.Column(
                "reference_id",
                sa.Integer(),
                nullable=True,
            ),
        )

    # Current model indexes.
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("usage_events")}

    if "idx_usage_events_resource" not in indexes:
        op.create_index(
            "idx_usage_events_resource",
            "usage_events",
            ["resource"],
        )

    if "idx_usage_events_created" not in indexes:
        op.create_index(
            "idx_usage_events_created",
            "usage_events",
            ["created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("usage_events"):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("usage_events")}

    if "idx_usage_events_created" in indexes:
        op.drop_index(
            "idx_usage_events_created",
            table_name="usage_events",
        )

    if "idx_usage_events_resource" in indexes:
        op.drop_index(
            "idx_usage_events_resource",
            table_name="usage_events",
        )

    columns = {c["name"] for c in inspector.get_columns("usage_events")}

    for column in (
        "reference_id",
        "reference_type",
        "model",
        "cost_usd",
    ):
        if column in columns:
            op.drop_column("usage_events", column)

    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("usage_events")}

    if "credits" in columns and "cost_credits" not in columns:
        op.alter_column(
            "usage_events",
            "credits",
            new_column_name="cost_credits",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("usage_events")}

    if "resource" in columns and "event_type" not in columns:
        op.alter_column(
            "usage_events",
            "resource",
            new_column_name="event_type",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
