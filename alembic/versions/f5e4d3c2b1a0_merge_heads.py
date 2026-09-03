"""Merge heads

Revision ID: f5e4d3c2b1a0
Revises: 7f6a7b8c9d0e, a0b1c2d3e4f5
Create Date: 2026-06-06 14:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5e4d3c2b1a0'
down_revision: Union[str, Sequence[str], None] = ('7f6a7b8c9d0e', 'a0b1c2d3e4f5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
