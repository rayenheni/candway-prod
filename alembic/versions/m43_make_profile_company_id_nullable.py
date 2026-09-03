"""Make company_id nullable on profile tables

CandidateProfile, RecruiterProfile, and AdminProfile are user-scoped
(not company-scoped). They should not require a company_id at creation
time. Candidates sign up without a company; recruiters create their
company during onboarding; admins are system-level.

The previous m22b migration enforced NOT NULL on ALL TenantMixin tables,
but profile tables are exceptions to the tenant isolation pattern.

Revision ID: m43
Revises: m42
Create Date: 2026-07-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m43"
down_revision: Union[str, None] = "m42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROFILE_TABLES = ["candidate_profiles", "recruiter_profiles", "admin_profiles"]


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table in PROFILE_TABLES:
        if not _has_column(bind, table, "company_id"):
            continue
        if dialect == "mysql":
            op.execute(
                f"ALTER TABLE {table} MODIFY COLUMN company_id INT NULL"
            )
        elif dialect == "postgresql":
            op.alter_column(table, "company_id", nullable=True)
        elif dialect == "sqlite":
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table in PROFILE_TABLES:
        if not _has_column(bind, table, "company_id"):
            continue
        if dialect == "mysql":
            op.execute(
                f"ALTER TABLE {table} MODIFY COLUMN company_id INT NOT NULL"
            )
        elif dialect == "postgresql":
            op.alter_column(table, "company_id", nullable=False)
