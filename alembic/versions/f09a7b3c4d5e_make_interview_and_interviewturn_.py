"""Make Interview and InterviewTurn application_id NOT NULL.

Revision ID: f09a7b3c4d5e
Revises: e98fa5102d68
Create Date: 2026-06-08 12:45:00.000000

Changes Interview.application_id and InterviewTurn.application_id
from nullable to NOT NULL. Both columns already have 0 NULL rows
in production so no data migration is needed.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f09a7b3c4d5e"
down_revision: Union[str, Sequence[str], None] = "e98fa5102d68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column("interviews", "application_id", nullable=False, existing_type=sa.Integer())
    op.alter_column("interview_turns", "application_id", nullable=False, existing_type=sa.Integer())


def downgrade():
    op.alter_column("interviews", "application_id", nullable=True, existing_type=sa.Integer())
    op.alter_column("interview_turns", "application_id", nullable=True, existing_type=sa.Integer())
