"""Drop deprecated ApplicationScore mirror columns from applications table

Revision ID: a2b3c4d5e6f7
Revises: c0d1e2f3a4b5
Create Date: 2026-06-09 16:00:00.000000

ApplicationScore is now the single source of truth for all scoring
data. The following mirror columns on the ``applications`` table
are no longer written or read by any application code and can be
safely dropped:

  - ``overall_score``          → ApplicationScore.final_score
  - ``cv_score``               → ApplicationScore.cv_score
  - ``verdict``                → ApplicationScore.verdict
  - ``fraud_score``            → ApplicationScore.fraud_score
  - ``human_integrity_score``  → ApplicationScore.human_integrity_score
  - ``rubric_version``         → ApplicationScore.rubric_version
  - ``scoring_model``          → ApplicationScore.scoring_model
  - ``rubric_seniority``       → ApplicationScore.rubric_seniority
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    try:
        op.drop_column("applications", "cv_score")
    except Exception:
        pass
    try:
        op.drop_column("applications", "overall_score")
    except Exception:
        pass
    try:
        op.drop_column("applications", "verdict")
    except Exception:
        pass
    try:
        op.drop_column("applications", "fraud_score")
    except Exception:
        pass
    try:
        op.drop_column("applications", "human_integrity_score")
    except Exception:
        pass
    try:
        op.drop_column("applications", "rubric_version")
    except Exception:
        pass
    try:
        op.drop_column("applications", "scoring_model")
    except Exception:
        pass
    try:
        op.drop_column("applications", "rubric_seniority")
    except Exception:
        pass
def downgrade():
    op.add_column("applications", sa.Column("cv_score", sa.Float(), nullable=True))
    op.add_column("applications", sa.Column("overall_score", sa.Float(), nullable=True))
    op.add_column("applications", sa.Column("verdict", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("fraud_score", sa.Float(), server_default="0.0", nullable=True))
    op.add_column("applications", sa.Column("human_integrity_score", sa.Float(), server_default="100.0", nullable=True))
    op.add_column("applications", sa.Column("rubric_version", sa.Integer(), server_default="0", nullable=True))
    op.add_column("applications", sa.Column("scoring_model", sa.String(20), server_default="rubric", nullable=True))
    op.add_column("applications", sa.Column("rubric_seniority", sa.String(20), server_default="mid", nullable=True))
