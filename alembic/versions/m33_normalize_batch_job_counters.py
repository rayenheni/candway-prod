"""m33: Drop deprecated BatchJob counter columns.

Removes 5 denormalized counter columns that are now computed from child tables:
  - emails_sent → COUNT(EmailSequenceLog) WHERE batch_id = X
  - emails_opened → COUNT(Application) WHERE batch_id = X AND opened_at IS NOT NULL
  - emails_clicked → COUNT(Application) WHERE batch_id = X AND clicked_at IS NOT NULL
  - responses_received → always 0, never written
  - application_count → MetricsRepository already computes via COUNT(Application)

Revision ID: m33
Revises: m32
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m33"
down_revision: Union[str, None] = "m32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("batch_jobs")}
    for col in ("emails_sent", "emails_opened", "emails_clicked", "responses_received", "application_count"):
        if col in cols:
            op.drop_column("batch_jobs", col)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("batch_jobs")}
    for col in ("emails_sent", "emails_opened", "emails_clicked", "responses_received", "application_count"):
        if col not in cols:
            op.add_column("batch_jobs", sa.Column(col, sa.Integer(), server_default="0", nullable=True))
