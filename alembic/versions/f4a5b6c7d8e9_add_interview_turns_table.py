"""Add interview_turns table.

Replaces the ``interview_qa_structured`` JSON bag on
``Application`` (Bug B-32 in the Candidate Experience Audit).

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-06-02 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id"),
            nullable=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("quality", sa.String(length=32), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("response_time_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("question_timestamp", sa.DateTime(), nullable=True),
        sa.Column("answer_timestamp", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("application_id", "turn_number", name="uq_turns_app_number"),
    )
    op.create_index("idx_turns_app", "interview_turns", ["application_id"])
    op.create_index("idx_turns_user", "interview_turns", ["user_id"])
    op.create_index("idx_turns_score", "interview_turns", ["score"])


def downgrade() -> None:
    op.drop_index("idx_turns_score", table_name="interview_turns")
    op.drop_index("idx_turns_user", table_name="interview_turns")
    op.drop_index("idx_turns_app", table_name="interview_turns")
    op.drop_table("interview_turns")
