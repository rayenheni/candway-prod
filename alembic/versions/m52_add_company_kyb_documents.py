"""Add company KYB document storage

Adds kyb_documents (JSON array of uploaded proof document paths) to the
companies table so companies can attach matricule fiscale / registre de
commerce proofs for admin KYB verification.

Revision ID: m52
Revises: m51
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m52"
down_revision: Union[str, None] = "m51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "companies", "kyb_documents"):
        op.add_column(
            "companies",
            sa.Column("kyb_documents", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "companies", "kyb_documents"):
        op.drop_column("companies", "kyb_documents")
