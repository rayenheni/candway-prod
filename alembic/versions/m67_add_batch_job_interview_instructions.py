"""Add interview_instructions to batch_jobs.

The BatchJob SQLAlchemy model defines interview_instructions, and the
campaign creation/update flow persists it, but production batch_jobs
was missing the column.

Revision ID: m67
Revises: m66
Create Date: 2026-08-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m67"
down_revision: Union[str, None] = "m66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("batch_jobs"):
        raise RuntimeError("batch_jobs table does not exist")

    columns = {column["name"] for column in inspector.get_columns("batch_jobs")}

    if "interview_instructions" not in columns:
        op.add_column(
            "batch_jobs",
            sa.Column("interview_instructions", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("batch_jobs"):
        columns = {
            column["name"]
            for column in inspector.get_columns("batch_jobs")
        }

        if "interview_instructions" in columns:
            op.drop_column("batch_jobs", "interview_instructions")
