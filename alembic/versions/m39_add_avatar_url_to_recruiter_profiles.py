"""add avatar_url column to recruiter_profiles

Previously this column existed only on User (deprecated) and
CandidateProfile. Login's get_user_avatar_url reads from the
role-specific profile, but RecruiterProfile was missing the column.

Revision ID: m39
Revises: m_merge_m33_m38
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m39"
down_revision: Union[str, Sequence[str], None] = "m_merge_m33_m38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("recruiter_profiles")}
    if "avatar_url" not in cols:
        op.add_column("recruiter_profiles", sa.Column("avatar_url", sa.String(255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("recruiter_profiles")}
    if "avatar_url" in cols:
        op.drop_column("recruiter_profiles", "avatar_url")
