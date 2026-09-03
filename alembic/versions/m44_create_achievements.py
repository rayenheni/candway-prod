"""Create achievements table

Per-user achievement tracking with predefined catalog of 12 achievements.
Achievements are seeded on first API access via seed_achievements_for_user().

Revision ID: m44
Revises: m43
Create Date: 2026-07-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m44"
down_revision: Union[str, None] = "m43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("achievements"):
        op.create_table(
            "achievements",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), index=True, nullable=False),
            sa.Column("slug", sa.String(100), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("icon_slug", sa.String(100), nullable=False),
            sa.Column("category", sa.String(100), nullable=False),
            sa.Column("progress_max", sa.Integer(), default=1),
            sa.Column("progress_current", sa.Integer(), default=0),
            sa.Column("unlocked", sa.Boolean(), default=False),
            sa.Column("unlocked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("achievements"):
        op.drop_table("achievements")
