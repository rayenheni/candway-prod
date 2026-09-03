"""Add composite index (application_id, interview_state) to evaluation_sessions

Phase 2 validation audit — Bug 3: Queries filtering by application_id +
interview_state on EvaluationSession were missing a composite index.
The existing idx_es_app (application_id) is too narrow and idx_es_app_status
(application_id, status) indexes the wrong column.

Migration ID: m15_add_evaluation_session_composite_index
Revises: m14_phase2_interview_session_ownership
"""

from typing import Sequence, Union

from alembic import op

revision: str = "m15_add_evaluation_session_composite_index"
down_revision: Union[str, None] = "m14_phase2_interview_session_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.create_index(
            "idx_es_app_interview_state",
            "evaluation_sessions",
            ["application_id", "interview_state"],
            postgresql_using="btree",
        )
    except Exception:
        pass


def downgrade() -> None:
    op.drop_index("idx_es_app_interview_state", table_name="evaluation_sessions")
