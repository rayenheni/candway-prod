"""Add recruiter-chosen campaign config columns to batch_jobs.

The full-campaign wizard collects interview language, duration, difficulty,
candidate source and target location, but none of these (except language)
were persisted on BatchJob. This migration adds the missing columns so the
recruiter's choices become real data instead of being silently dropped.

Revision ID: m57
Revises: m56
Create Date: 2026-08-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "m57"
down_revision: Union[str, None] = "m56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "batch_jobs",
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "batch_jobs",
        sa.Column("difficulty", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "batch_jobs",
        sa.Column("candidate_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "batch_jobs",
        sa.Column("location", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("batch_jobs", "location")
    op.drop_column("batch_jobs", "candidate_source")
    op.drop_column("batch_jobs", "difficulty")
    op.drop_column("batch_jobs", "duration_minutes")
