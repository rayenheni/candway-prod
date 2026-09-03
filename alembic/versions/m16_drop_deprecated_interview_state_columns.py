"""Drop deprecated interview state columns from applications table

Phase 3: These 8 columns were migrated to EvaluationSession. The
@property accessors on Application already delegate to EvaluationSession;
setters are no-ops since Phase 3.  Data was backfilled by
backend/migrations/phase3_backfill_app_to_eval_session.py.

The 3 columns ``interview_log``, ``interview_questions``, and
``video_file_path`` were already handled by ``m11_drop_deprecated_app_columns``.

Migration ID: m16_drop_deprecated_interview_state_columns
Revises: m15_add_evaluation_session_composite_index
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m16_drop_deprecated_interview_state_columns"
down_revision: Union[str, None] = "m15_add_evaluation_session_composite_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop check constraint on interview_state (safe wrapper for cross-DB compat)
    try:
        op.drop_constraint("ck_application_interview_state", "applications", type_="check")
    except Exception:
        pass

    # 2. Drop index on (interview_state, updated_at)
    try:
        op.drop_index("idx_applications_interview_state", table_name="applications")
    except Exception:
        pass

    # 3. Drop 8 deprecated columns
    for col in (
        "interview_state",
        "interview_progress",
        "interview_time_left",
        "interview_last_saved",
        "interview_turn_seq",
        "interview_reset_count",
        "interview_last_reset_at",
        "calibration_json",
    ):
        try:
            op.drop_column("applications", col)
        except Exception:
            pass


def downgrade() -> None:
    # Restore columns (data is in EvaluationSession, not recoverable)
    op.add_column("applications", sa.Column("interview_state", sa.String(20), default="not_started", index=True))
    op.add_column("applications", sa.Column("interview_progress", sa.Integer, default=0))
    op.add_column("applications", sa.Column("interview_time_left", sa.Integer, default=1800))
    op.add_column("applications", sa.Column("interview_last_saved", sa.DateTime, nullable=True))
    op.add_column("applications", sa.Column("interview_turn_seq", sa.Integer, default=0))
    op.add_column("applications", sa.Column("interview_reset_count", sa.Integer, default=0, nullable=False))
    op.add_column("applications", sa.Column("interview_last_reset_at", sa.DateTime, nullable=True))
    op.add_column("applications", sa.Column("calibration_json", sa.Text, nullable=True))

    op.create_index("idx_applications_interview_state", "applications", ["interview_state", "updated_at"])
    op.create_check_constraint(
        "ck_application_interview_state",
        "applications",
        "interview_state IS NULL OR interview_state IN ('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused')",
    )
