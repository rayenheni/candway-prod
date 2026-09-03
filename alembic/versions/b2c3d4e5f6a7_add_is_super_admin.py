"""Add is_super_admin column to users table for RBAC

Revision ID: b2c3d4e5f6a7
Revises: 6e4cadea7e92
Create Date: 2026-05-03 14:53:28.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '6e4cadea7e92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_super_admin column."""
    op.add_column('users', sa.Column('is_super_admin', sa.Boolean(), nullable=False, server_default='0', index=True))


def downgrade() -> None:
    """Remove is_super_admin column."""
    try:
        op.drop_column('users', 'is_super_admin')
    except Exception:
        pass