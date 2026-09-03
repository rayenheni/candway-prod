"""add valid_through column to jobs table for Google for Jobs

Revision ID: 7f6a7b8c9d0e
Revises: 0ce7416aa096
Create Date: 2026-06-06 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f6a7b8c9d0e'
down_revision: Union[str, Sequence[str], None] = '0ce7416aa096'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('valid_through', sa.DateTime(), nullable=True))


def downgrade() -> None:
    try:
        op.drop_column('jobs', 'valid_through')
    except Exception:
        pass