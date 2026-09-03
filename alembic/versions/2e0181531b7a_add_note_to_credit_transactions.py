from alembic import op
import sqlalchemy as sa


revision = "2e0181531b7a"
down_revision = "a33908a9c1d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "credit_transactions",
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column(
        "credit_transactions",
        "note",
    )
