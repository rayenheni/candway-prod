"""Add builder_data to candidate_profiles

Store CV builder JSON on the user-scoped CandidateProfile so CV builder
persistence works for candidates without a company membership.

Revision ID: m46
Revises: m45
Create Date: 2026-07-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m46"
down_revision: Union[str, None] = "m45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("candidate_profiles")}
    if "builder_data" not in cols:
        op.add_column("candidate_profiles", sa.Column("builder_data", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("candidate_profiles")}
    if "builder_data" in cols:
        op.drop_column("candidate_profiles", "builder_data")
