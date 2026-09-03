"""Add temp_password column to users table

Revision ID: a1b2c3d4e5f6
Revises: 367fd943df54
Create Date: 2026-05-01 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '367fd943df54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    """Add temp_password column for auto-generated candidate passwords."""
    # The sibling branch migration 6e4cadea7e92_sync_legacy_schema also adds
    # temp_password; a fresh deployment therefore must not add it twice.
    if not _column_exists("users", "temp_password"):
        op.add_column('users', sa.Column('temp_password', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove temp_password column."""
    if _column_exists("users", "temp_password"):
        op.drop_column('users', 'temp_password')