"""drop obsolete unique constraint on application email

Revision ID: a443829e5d63
Revises: m76
Create Date: 2026-08-26 14:47:45.133121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a443829e5d63'
down_revision: Union[str, Sequence[str], None] = 'm76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
