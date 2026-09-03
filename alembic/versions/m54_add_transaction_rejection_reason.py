"""Add rejection_reason to transactions.

S10: payment-proof rejection must carry a human-readable reason so the
requester can understand why their payment was rejected and retry.
Stored alongside the existing rejected_at / rejected_by columns.

Revision ID: m54
Revises: m53
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "m54"
down_revision: Union[str, None] = "m53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute(
            "ALTER TABLE transactions ADD COLUMN rejection_reason VARCHAR(500) NULL"
        )
    elif dialect == "postgresql":
        op.add_column("transactions", op.Column("rejection_reason", op.String(500), nullable=True))
    elif dialect == "sqlite":
        op.add_column("transactions", op.Column("rejection_reason", op.String(500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute("ALTER TABLE transactions DROP COLUMN rejection_reason")
    elif dialect == "postgresql":
        op.drop_column("transactions", "rejection_reason")
    elif dialect == "sqlite":
        op.drop_column("transactions", "rejection_reason")
