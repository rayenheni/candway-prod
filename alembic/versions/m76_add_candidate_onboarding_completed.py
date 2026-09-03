"""Add explicit onboarding completion state to candidate profiles.

Revision ID: m76
Revises: m75
"""

from alembic import op
import sqlalchemy as sa


revision = "m76"
down_revision = "m75"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("candidate_profiles")
    }

    if "onboarding_completed" not in columns:
        op.add_column(
            "candidate_profiles",
            sa.Column(
                "onboarding_completed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column["name"]
        for column in inspector.get_columns("candidate_profiles")
    }

    if "onboarding_completed" in columns:
        op.drop_column("candidate_profiles", "onboarding_completed")
