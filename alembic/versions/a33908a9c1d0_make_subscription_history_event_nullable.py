from alembic import op
import sqlalchemy as sa


revision = "a33908a9c1d0"
down_revision = "m71"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "subscription_history",
        "event",
        existing_type=sa.String(length=50),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "subscription_history",
        "event",
        existing_type=sa.String(length=50),
        nullable=False,
    )
