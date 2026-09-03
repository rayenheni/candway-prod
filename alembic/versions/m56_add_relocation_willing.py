"""Add relocation_willing to candidate_profiles.

Candidates need a first-class "willing to relocate" flag so recruiters can
see real data instead of a hardcoded None. Mirrors the salary/availability
preference columns already on CandidateProfile.

Revision ID: m56
Revises: m55
Create Date: 2026-08-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "m56"
down_revision: Union[str, None] = "m55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("relocation_willing", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "relocation_willing")
