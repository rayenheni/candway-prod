"""Add version_id column to entity tables for optimistic locking.

Revision ID: e98fa5102d68
Revises: d3e4f5a6b7c8
Create Date: 2026-06-08 12:07:00.000000

Adds a version_id column (Integer, NOT NULL, DEFAULT 1) to the
5 entity tables that are most susceptible to concurrent-write
conflicts:

  - application_scores     (ScoringService writes)
  - cv_documents           (CV analysis + background writes)
  - ai_interview_sessions  (concurrent interview proctoring writes)
  - evaluation_states      (evaluation claim + completion)
  - skill_definitions      (CRUD + rubric sync writes)

SQLAlchemy's built-in optimistic locking will increment this
column on every UPDATE and reject stale writes via
StaleDataError.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e98fa5102d68"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "application_scores",
    "cv_documents",
    "ai_interview_sessions",
    "evaluation_states",
    "skill_definitions",
]


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade():
    for t in TABLES:
        # Several of these tables are not created by any migration in the chain
        # (they existed only on the legacy DB); m53_sync_schema_to_model creates
        # them later with version_id already present. Only touch tables that
        # exist now.
        if not _table_exists(t):
            continue
        op.add_column(
            t,
            sa.Column("version_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
        )


def downgrade():
    for t in TABLES:
        try:
            op.drop_column(t, "version_id")
        except Exception:
            pass
