"""Make company_id nullable on candidate-owned resources.

Standalone candidates (individual signups, job seekers) belong to no
company until they apply to a specific company's job or are invited by
a recruiter/campaign. They must be able to upload and analyze their CV
before any company context exists. Following the precedent set in m43
(profile tables) and m53 (qualifications), the candidate-owned chain is
exempt from TenantMixin NOT NULL:

  applications, cv_documents, candidates, evaluation_sessions,
  evaluation_results

The CV upload + analysis pipeline (create_application -> sync_cv_document
-> ScoringService.set_cv_only -> EvaluationSession/EvaluationResult)
propagates app.company_id (possibly NULL) down the chain.

Revision ID: m61
Revises: m60
Create Date: 2026-08-17
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m61"
down_revision: Union[str, None] = "m60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "applications",
    "cv_documents",
    "candidates",
    "evaluation_sessions",
    "evaluation_results",
)


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

    if dialect == "mysql":
        for table in _TABLES:
            op.execute(f"ALTER TABLE {table} MODIFY COLUMN company_id INT NOT NULL")
    elif dialect == "postgresql":
        for table in _TABLES:
            op.alter_column(table, "company_id", nullable=False)
