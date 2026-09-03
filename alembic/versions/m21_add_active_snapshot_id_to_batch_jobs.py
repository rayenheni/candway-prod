"""M021: Add active_snapshot_id FK to batch_jobs.

Revision ID: m21_add_active_snapshot_id_to_batch_jobs
Revises: m20_add_company_id_to_audit_log
Create Date: 2026-06-28 14:50:00.000000

- Adds active_snapshot_id FK -> evaluation_config_snapshots.id (nullable)
- Resolves 500 error on /api/v1/recruiter/campaigns, /recruiter/jobs/my,
  /recruiter/applications, and any endpoint querying BatchJob model
  with the active_snapshot_id column.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "m21_add_active_snapshot_id_to_batch_jobs"
down_revision: Union[str, Sequence[str], None] = "m20_add_company_id_to_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_column(conn, "batch_jobs", "active_snapshot_id"):
        op.add_column(
            "batch_jobs",
            sa.Column(
                "active_snapshot_id",
                sa.Integer(),
                sa.ForeignKey("evaluation_config_snapshots.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    try:
        _drop_constraint_if_exists("batch_jobs_ibfk_5", "batch_jobs", "foreignkey")
        _drop_constraint_if_exists("fk_batch_jobs_active_snapshot", "batch_jobs", "foreignkey")
    except Exception:
        pass
    try:
        op.drop_column("batch_jobs", "active_snapshot_id")
    except Exception:
        pass


def _drop_constraint_if_exists(name: str, table_name: str, constraint_type: str):
    try:
        op.drop_constraint(name, table_name, type_=constraint_type)
    except Exception:
        pass
