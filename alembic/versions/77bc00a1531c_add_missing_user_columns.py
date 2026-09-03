"""add_missing_user_columns

Revision ID: 77bc00a1531c
Revises: 4e4f4b511b0e
Create Date: 2026-05-18 16:17:45.270640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77bc00a1531c'
down_revision: Union[str, Sequence[str], None] = '4e4f4b511b0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('languages', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('availability', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('work_preference', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('salary_expectation_min', sa.Float, nullable=True))
    op.add_column('users', sa.Column('salary_expectation_max', sa.Float, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    try:
        op.drop_column('users', 'salary_expectation_max')
    except Exception:
        pass
    try:
        op.drop_column('users', 'salary_expectation_min')
    except Exception:
        pass
    try:
        op.drop_column('users', 'work_preference')
    except Exception:
        pass
    try:
        op.drop_column('users', 'availability')
    except Exception:
        pass
    try:
        op.drop_column('users', 'languages')
    except Exception:
        pass