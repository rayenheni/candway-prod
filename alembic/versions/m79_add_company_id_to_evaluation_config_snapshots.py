"""m79: Add company_id to evaluation_config_snapshots

Repairs production schema drift where evaluation_config_snapshots was created
without company_id and skipped during m22/m22b execution.

1. Adds company_id (NOT NULL, FK -> companies.id) to evaluation_config_snapshots
2. Creates index idx_evaluation_config_snapshots_company_id

Revision ID: m79
Revises: m78
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "m79"
down_revision: Union[str, None] = "m78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _has_index(bind, table_name: str, index_name: str) -> bool:
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return any(
        idx.get("name") == index_name
        for idx in inspector.get_indexes(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    table_name = "evaluation_config_snapshots"
    column_name = "company_id"
    index_name = "idx_evaluation_config_snapshots_company_id"

    # 1. Add company_id if missing (NOT NULL, FK -> companies.id, ON DELETE RESTRICT).
    #    Independent of index repair: do NOT assume the index exists because the
    #    column exists.
    if not _has_column(bind, table_name, column_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column(
                    column_name,
                    sa.Integer(),
                    sa.ForeignKey("companies.id", name="fk_ecs_company", ondelete="RESTRICT"),
                    nullable=False,
                )
            )

    # 2. Independently create the index if missing.
    if not _has_index(bind, table_name, index_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_index(index_name, [column_name])


def downgrade() -> None:
    bind = op.get_bind()
    table_name = "evaluation_config_snapshots"
    column_name = "company_id"
    index_name = "idx_evaluation_config_snapshots_company_id"

    if _has_column(bind, table_name, column_name):
        with op.batch_alter_table(table_name) as batch_op:
            if _has_index(bind, table_name, index_name):
                batch_op.drop_index(index_name)
            batch_op.drop_column(column_name)
