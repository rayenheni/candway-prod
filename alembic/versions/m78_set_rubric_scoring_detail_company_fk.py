"""Set rubric scoring detail company FK to SET NULL.

Revision ID: m78
Revises: m77
"""

from alembic import op


revision = "m78"
down_revision = "m77"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "rubric_scoring_details_ibfk_1",
        "rubric_scoring_details",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_rsd_company",
        "rubric_scoring_details",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_rsd_company",
        "rubric_scoring_details",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "rubric_scoring_details_ibfk_1",
        "rubric_scoring_details",
        "companies",
        ["company_id"],
        ["id"],
    )
