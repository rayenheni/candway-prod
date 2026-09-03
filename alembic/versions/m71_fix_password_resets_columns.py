"""
Add missing PasswordReset columns.

Revision ID: m71
Revises: m70
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m71"
down_revision: Union[str, None] = "m70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("password_resets"):
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("password_resets")
    }

    if "used_at" not in columns:
        op.add_column(
            "password_resets",
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )

    if "ip_address" not in columns:
        op.add_column(
            "password_resets",
            sa.Column("ip_address", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("password_resets"):
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("password_resets")
    }

    if "ip_address" in columns:
        op.drop_column("password_resets", "ip_address")

    if "used_at" in columns:
        op.drop_column("password_resets", "used_at")
