"""fix tenant isolation constraint collisions

C7: ChatbotLead had duplicate company_id (TenantMixin + explicit column).
    Drop the explicit column; TenantMixin provides it.

C8: SkillDefinition unique constraint was on `name` only, allowing
    cross-tenant collision. Change to (company_id, name).

Revision ID: m40
Revises: m39
Create Date: 2026-07-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m40"
down_revision: Union[str, Sequence[str], None] = "m39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # C7: Drop duplicate company_id column from chatbot_leads
    # (TenantMixin already provides it)
    try:
        op.drop_index("idx_chatbot_lead_company", table_name="chatbot_leads")
    except Exception:
        pass
    try:
        op.drop_constraint("chatbot_leads_ibfk_1", "chatbot_leads", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_column("chatbot_leads", "company_id")
    except Exception:
        pass

    # C8: Replace global unique constraint on skill_definitions.name
    # with tenant-scoped unique constraint on (company_id, name)
    try:
        op.drop_constraint("uq_skill_def_name", "skill_definitions", type_="unique")
    except Exception:
        pass
    try:
        op.create_unique_constraint(
            "uq_skill_def_company_name", "skill_definitions", ["company_id", "name"]
        )
    except Exception:
        pass


def downgrade() -> None:
    # C8 rollback
    op.drop_constraint("uq_skill_def_company_name", "skill_definitions", type_="unique")
    op.create_unique_constraint("uq_skill_def_name", "skill_definitions", ["name"])

    # C7 rollback: re-add explicit company_id column
    op.add_column(
        "chatbot_leads",
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
    )
    op.create_index("idx_chatbot_lead_company", "chatbot_leads", ["company_id"])
