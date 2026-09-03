"""Drop unused legacy coach tables.

Revision ID: m75
Revises: m74

The coach_conversations and coach_progress tables are legacy schema
objects with no active SQLAlchemy models, router registration, or
runtime usage. Both tables are empty in the current production DB.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m75"
down_revision: Union[str, None] = "m74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()

    # These are confirmed-dead legacy tables.
    # Both currently contain 0 rows.
    #
    # Their only FK is:
    #   coach_*.user_id -> users.id
    #
    # There are no FKs from users or other active tables pointing
    # back to these tables.
    for table in ("coach_progress", "coach_conversations"):
        if _has_table(bind, table):
            op.drop_table(table)


def downgrade() -> None:
    # Exact schema restored from the original migration
    # 367fd943df54_initial_schema.py.

    op.create_table(
        "coach_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_coach_conversations_id"),
        "coach_conversations",
        ["id"],
        unique=False,
    )

    op.create_table(
        "coach_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("last_practiced", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_coach_progress_id"),
        "coach_progress",
        ["id"],
        unique=False,
    )
