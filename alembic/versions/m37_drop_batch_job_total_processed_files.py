"""drop deprecated batch_jobs.total_files and processed_files columns

These counters are now computed from child tables via batch_counters().

Revision ID: m37
Revises: m36
Create Date: 2026-07-06 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m37"
down_revision: Union[str, Sequence[str], None] = "m36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("batch_jobs")}
    for col in ("total_files", "processed_files"):
        if col in cols:
            op.drop_column("batch_jobs", col)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("batch_jobs")}
    for col in ("total_files", "processed_files"):
        if col not in cols:
            op.add_column("batch_jobs", sa.Column(col, sa.Integer(), server_default="0", nullable=True))
