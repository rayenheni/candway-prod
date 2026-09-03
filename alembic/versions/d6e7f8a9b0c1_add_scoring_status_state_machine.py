"""M008: Add scoring_status state machine, make final_score nullable.

Adds a `scoring_status` column to `evaluation_results` with values:
  - PENDING       (default) — not yet scored, final_score is NULL
  - SCORED        — successfully scored, final_score is valid
  - FAILED        — scoring failed or fraud detected
  - NEEDS_REVIEW  — flagged for human review

Makes `final_score` nullable (was NOT NULL) so the scoring state
is expressed by the status column, not by sentinel numeric values.

Backfills existing rows:
  - needs_review = True  → NEEDS_REVIEW
  - final_score > 0      → SCORED
  - final_score = 0 AND needs_review = False AND
    (computed_by IS NOT NULL OR score_breakdown IS NOT NULL) → SCORED
  - all others           → PENDING

Revision ID: d6e7f8a9b0c1
Revises: e5f4d3c2b1a0
Create Date: 2026-06-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "e5f4d3c2b1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scoring_status column
    op.add_column(
        "evaluation_results",
        sa.Column("scoring_status", sa.String(20), nullable=False, server_default="PENDING"),
    )
    op.create_index("ix_evaluation_results_scoring_status", "evaluation_results", ["scoring_status"])

    # Backfill scoring_status based on existing data
    op.execute("""
        UPDATE evaluation_results
        SET scoring_status = 'NEEDS_REVIEW'
        WHERE needs_review = TRUE
    """)
    op.execute("""
        UPDATE evaluation_results
        SET scoring_status = 'SCORED'
        WHERE scoring_status = 'PENDING'
          AND (final_score > 0
               OR (computed_by IS NOT NULL AND score_breakdown IS NOT NULL))
    """)

    # Make final_score nullable — remove NOT NULL, update check constraint
    op.alter_column("evaluation_results", "final_score", existing_type=sa.Float(), nullable=True)
    op.drop_constraint("ck_eval_result_final_score_range", "evaluation_results", type_="check")
    op.create_check_constraint(
        "ck_eval_result_final_score_range",
        "evaluation_results",
        sa.text("final_score IS NULL OR (final_score >= 0 AND final_score <= 100)"),
    )

    # Clear final_score for non-SCORED rows to satisfy the state machine
    op.execute("""
        UPDATE evaluation_results
        SET final_score = NULL
        WHERE scoring_status IN ('PENDING', 'FAILED', 'NEEDS_REVIEW')
    """)

    # Add scoring_status check constraint
    op.create_check_constraint(
        "ck_eval_result_scoring_status",
        "evaluation_results",
        sa.text("scoring_status IN ('PENDING', 'SCORED', 'FAILED', 'NEEDS_REVIEW')"),
    )

    # Cross-column CHECK: SCORED requires non-null final_score;
    # all other statuses require null final_score.
    op.create_check_constraint(
        "ck_eval_result_state_machine",
        "evaluation_results",
        sa.text(
            "(scoring_status = 'SCORED' AND final_score IS NOT NULL) "
            "OR (scoring_status IN ('PENDING', 'FAILED', 'NEEDS_REVIEW') AND final_score IS NULL)"
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_eval_result_state_machine", "evaluation_results", type_="check")
    op.drop_constraint("ck_eval_result_scoring_status", "evaluation_results", type_="check")
    op.drop_constraint("ck_eval_result_final_score_range", "evaluation_results", type_="check")
    op.create_check_constraint(
        "ck_eval_result_final_score_range",
        "evaluation_results",
        sa.text("final_score >= 0 AND final_score <= 100"),
    )
    op.alter_column("evaluation_results", "final_score", existing_type=sa.Float(), nullable=False)
    op.drop_index("ix_evaluation_results_scoring_status", table_name="evaluation_results")
    op.drop_column("evaluation_results", "scoring_status")
