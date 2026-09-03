"""m23: Enforce ChatbotLead.company_id NOT NULL

ChatbotLead.company_id was previously nullable=True, allowing orphan
records to be created without tenant context. This migration:

1. Deletes any chatbot_leads with NULL company_id (safety net).
2. Makes the column NOT NULL.

Revision ID: m23
Revises: m22b
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa


revision = "m23"
down_revision = "m22b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety net: remove any orphan records
    op.execute("DELETE FROM chatbot_leads WHERE company_id IS NULL")
    # Make company_id NOT NULL
    op.alter_column(
        "chatbot_leads",
        "company_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "chatbot_leads",
        "company_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        nullable=True,
    )
