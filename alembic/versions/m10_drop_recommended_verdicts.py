"""drop recommended_verdicts table

Migration to drop the recommended_verdicts table which was created
in the initial migration (M001) and is no longer used.

Revision ID: m10_drop_recommended_verdicts
Revises: a3b4c5d6e7f8
Create Date: 2026-06-25 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "m10_drop_recommended_verdicts"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("recommended_verdicts")


def downgrade() -> None:
    # Cannot restore — table was created in M001, no model class exists
    pass
