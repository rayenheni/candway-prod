"""M020: Add company_id FK to audit_logs and make ip_address nullable.

Revision ID: m20_add_company_id_to_audit_log
Revises: ac4f530aebb2
Create Date: 2026-06-28 14:00:00.000000

- Adds company_id FK -> companies.id (nullable, preserves existing records)
- Makes ip_address nullable (safe default when request.client is None)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "m20_add_company_id_to_audit_log"
down_revision: Union[str, Sequence[str], None] = "ac4f530aebb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    # Add company_id column (nullable, preserves existing records)
    if not _has_column(conn, "audit_logs", "company_id"):
        op.add_column(
            "audit_logs",
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True, index=True),
        )

    # Make ip_address nullable
    try:
        op.alter_column("audit_logs", "ip_address", existing_type=sa.String(255), nullable=True)
    except Exception:
        pass  # May already be nullable in some environments


def downgrade() -> None:
    conn = op.get_bind()

    _drop_constraint_if_exists("audit_logs_ibfk_1", "audit_logs", "foreignkey")
    _drop_constraint_if_exists("fk_audit_logs_company", "audit_logs", "foreignkey")

    try:
        op.drop_column("audit_logs", "company_id")
    except Exception:
        pass

    try:
        op.alter_column("audit_logs", "ip_address", existing_type=sa.String(255), nullable=False)
    except Exception:
        pass


def _drop_constraint_if_exists(name: str, table_name: str, constraint_type: str):
    try:
        op.drop_constraint(name, table_name, type_=constraint_type)
    except Exception:
        pass
