"""Create user_skills table

Per-user skill progress tracking with levels, trends, and verification.

Revision ID: m45
Revises: m44
Create Date: 2026-07-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m45"
down_revision: Union[str, None] = "m44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("user_skills"):
        op.create_table(
            "user_skills",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), index=True, nullable=False),
            sa.Column("category", sa.String(100), nullable=False),
            sa.Column("skill_name", sa.String(255), nullable=False),
            sa.Column("level", sa.Integer(), default=0),
            sa.Column("trend", sa.String(10), default="+0"),
            sa.Column("verified", sa.Boolean(), default=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_skills"):
        op.drop_table("user_skills")
