"""Make company_id nullable on qualifications.

Qualifications are user-scoped documents (a candidate's own degrees,
certificates, transcripts) — not company-scoped resources. Following
the precedent set in m43 for profile tables: candidates belong to no
company until they apply to a specific company's job, so they must be
able to upload supporting documents before any Application row exists.

The previous m22b migration enforced NOT NULL on ALL TenantMixin tables,
but qualifications are an exception: candidates can upload before they
have a company context.

Revision ID: m53
Revises: m52
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m53"
down_revision: Union[str, None] = "m52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _has_column(bind, "qualifications", "company_id"):
        return

    if dialect == "mysql":
        op.execute("ALTER TABLE qualifications MODIFY COLUMN company_id INT NULL")
    elif dialect == "postgresql":
        op.alter_column("qualifications", "company_id", nullable=True)
    elif dialect == "sqlite":
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _has_column(bind, "qualifications", "company_id"):
        return

    if dialect == "mysql":
        op.execute("ALTER TABLE qualifications MODIFY COLUMN company_id INT NOT NULL")
    elif dialect == "postgresql":
        op.alter_column("qualifications", "company_id", nullable=False)
