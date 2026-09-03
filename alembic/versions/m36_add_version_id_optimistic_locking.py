"""add version_id to applications, jobs, offers for optimistic locking

Revision ID: m36
Revises: m35
Create Date: 2026-07-06 09:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m36"
down_revision: Union[str, Sequence[str], None] = "m35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("applications", "jobs", "offers"):
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "version_id" not in cols:
            op.add_column(table, sa.Column("version_id", sa.Integer(), nullable=False, server_default=sa.text("1")))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("offers", "jobs", "applications"):
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "version_id" in cols:
            try:
                op.drop_column(table, "version_id")
            except Exception:
                pass