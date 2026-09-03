"""Add company-level billing columns to companies

Adds plan_id (FK to subscription_plans), billing_email, billing_address and
tax_id so the organization portal can hold a company-scoped subscription,
invoice billing details and the company's Matricule Fiscale (KYB) at the
company level instead of per recruiter.

Revision ID: m51
Revises: m50
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m51"
down_revision: Union[str, None] = "m50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "companies", "plan_id"):
        op.add_column(
            "companies",
            sa.Column(
                "plan_id",
                sa.Integer(),
                sa.ForeignKey("subscription_plans.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if not _has_column(bind, "companies", "billing_email"):
        op.add_column(
            "companies",
            sa.Column("billing_email", sa.String(length=255), nullable=True),
        )
    if not _has_column(bind, "companies", "billing_address"):
        op.add_column(
            "companies",
            sa.Column("billing_address", sa.String(length=255), nullable=True),
        )
    if not _has_column(bind, "companies", "tax_id"):
        op.add_column(
            "companies",
            sa.Column("tax_id", sa.String(length=50), nullable=True),
        )
    if not _has_column(bind, "companies", "kyb_status"):
        op.add_column(
            "companies",
            sa.Column("kyb_status", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for col in ["plan_id", "billing_email", "billing_address", "tax_id", "kyb_status"]:
        if _has_column(bind, "companies", col):
            op.drop_column("companies", col)
