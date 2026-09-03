"""Make company_id nullable on credit tables.

Credit wallets, credit transactions, and usage events are user-scoped —
standalone recruiters and candidates belong to no company (mirrors m43/m53
precedent for user-scoped resources). The NOT NULL enforcement from m22b
broke wallet creation for any standalone user because get_or_create_wallet
falls back to company_id=1 which does not exist for non-company users.

Revision ID: m55
Revises: m54
Create Date: 2026-08-07
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m55"
down_revision: Union[str, None] = "m54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("credit_wallets", "credit_transactions", "usage_events")


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table in _TABLES:
        if not _has_column(bind, table, "company_id"):
            continue
        if dialect == "mysql":
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN company_id INT NULL")
        elif dialect == "postgresql":
            op.alter_column(table, "company_id", nullable=True)
        elif dialect == "sqlite":
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table in _TABLES:
        if not _has_column(bind, table, "company_id"):
            continue
        if dialect == "mysql":
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN company_id INT NOT NULL")
        elif dialect == "postgresql":
            op.alter_column(table, "company_id", nullable=False)
        elif dialect == "sqlite":
            pass
