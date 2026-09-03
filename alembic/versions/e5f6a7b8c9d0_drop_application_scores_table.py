"""M005: Drop application_scores table — fully replaced by evaluation_results.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c0
Create Date: 2026-06-11

The application_scores table was deprecated in Phase 2 of the architecture
migration.  All reads and writes have been migrated to the new evaluation_results
table, backed by the EvaluationResult model.

Data was backfilled in M002.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_table("application_scores")


def downgrade():
    op.create_table(
        "application_scores",
        op.Column("id", op.INTEGER(), autoincrement=True, nullable=False),
        op.Column("application_id", op.INTEGER(), nullable=False, unique=True),
        op.Column("cv_score", op.FLOAT(), nullable=True),
        op.Column("rubric_score", op.FLOAT(), nullable=True),
        op.Column("human_integrity_score", op.FLOAT(), server_default="100.0"),
        op.Column("rubric_coverage_pct", op.FLOAT(), nullable=True),
        op.Column("final_score", op.FLOAT(), nullable=False),
        op.Column("composite_score", op.FLOAT(), nullable=True),
        op.Column("score_breakdown", op.JSON(), nullable=True),
        op.Column("verdict", op.VARCHAR(255), nullable=True),
        op.Column("fraud_score", op.FLOAT(), server_default="0.0"),
        op.Column("fraud_reported_by", op.INTEGER(), nullable=True),
        op.Column("fraud_reported_at", op.DATETIME(), nullable=True),
        op.Column("scoring_model", op.VARCHAR(20), server_default="rubric"),
        op.Column("rubric_version", op.INTEGER(), nullable=True),
        op.Column("rubric_seniority", op.VARCHAR(20), server_default="mid"),
        op.Column("needs_review", op.BOOLEAN(), server_default="0"),
        op.Column("needs_review_reason", op.VARCHAR(500), nullable=True),
        op.Column("computed_at", op.DATETIME(), nullable=True),
        op.Column("computed_by", op.VARCHAR(50), nullable=True),
        op.PrimaryKeyConstraint("id"),
        op.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_app_score_app"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_app_score_app", "application_scores", ["application_id"], unique=True)
    op.create_index("idx_app_score_final", "application_scores", ["final_score"])
