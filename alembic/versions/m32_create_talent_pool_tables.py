"""m32: Create TalentPool and TalentPoolCandidate tables.

Adds talent pool functionality for enterprise candidate sourcing.

Revision ID: m32
Revises: m31
Create Date: 2026-07-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m32"
down_revision: Union[str, Sequence[str], None] = "m31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "talent_pools",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, nullable=True, index=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True, index=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],),
        sa.UniqueConstraint("company_id", "name", name="uq_talent_pools_company_name"),
    )
    op.create_index("idx_talent_pools_company", "talent_pools", ["company_id"])

    op.create_table(
        "talent_pool_candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer, nullable=False, index=True),
        sa.Column("talent_pool_id", sa.Integer, nullable=False, index=True),
        sa.Column("candidate_id", sa.Integer, nullable=False, index=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("added_by", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["talent_pool_id"], ["talent_pools.id"],),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"],),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"],),
        sa.UniqueConstraint("talent_pool_id", "candidate_id", name="uq_tpc_pool_candidate"),
    )
    op.create_index("idx_tpc_pool", "talent_pool_candidates", ["talent_pool_id"])
    op.create_index("idx_tpc_candidate", "talent_pool_candidates", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("talent_pool_candidates")
    op.drop_table("talent_pools")
