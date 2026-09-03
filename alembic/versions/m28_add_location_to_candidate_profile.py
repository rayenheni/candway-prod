"""m28: Add location column to candidate_profiles table.

Adds the ``location`` VARCHAR(255) column to ``candidate_profiles``
so that the CandidateProfile model reflects all fields previously
stored only on the User model.

Revision ID: m28
Revises: m27
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m28"
down_revision: Union[str, Sequence[str], None] = "m27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("location", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "location")
