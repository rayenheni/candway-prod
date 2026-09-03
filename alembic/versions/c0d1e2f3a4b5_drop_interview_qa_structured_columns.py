"""Drop deprecated interview_qa_structured columns

Revision ID: c0d1e2f3a4b5
Revises: b9a8c7d6e5f4
Create Date: 2026-06-09 14:30:00.000000

Drops columns from two tables (Phase 3B of the InterviewTurn migration):

  - ``applications.interview_qa_structured`` — EncryptedText (TEXT)
  - ``ai_interview_sessions.interview_qa_structured`` — JSON

All interview QA data now lives in the ``interview_turns`` table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b9a8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    try:
        op.drop_column("applications", "interview_qa_structured")
    except Exception:
        pass
    op.drop_column("ai_interview_sessions", "interview_qa_structured")


def downgrade():
    op.add_column(
        "applications",
        sa.Column("interview_qa_structured", sa.Text(), nullable=True),
    )
    op.add_column(
        "ai_interview_sessions",
        sa.Column("interview_qa_structured", mysql.JSON(), nullable=True),
    )
