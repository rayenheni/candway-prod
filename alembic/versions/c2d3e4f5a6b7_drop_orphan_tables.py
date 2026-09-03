"""Drop 10 orphan tables with zero production query references.

Confirmed dead via codebase audit — no production router, service,
or background worker queries any of these tables.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-08 03:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORPHAN_TABLES = [
    "message_read_receipts",
    "discussions",
    "learning_paths",
    "student_notes",
    "quiz_results",
    "certificates",
    "simulation_actions",
    "simulation_attempts",
    "simulation_scenarios",
    "system_settings",
]


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = 0"))
    for table in ORPHAN_TABLES:
        exists = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :t"
            ).bindparams(t=table)
        ).scalar()
        if exists:
            op.drop_table(table)
    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = 1"))


def downgrade():
    pass
