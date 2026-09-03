"""M007: Add canonical verdict column to evaluation_results.

Adds a dedicated `verdict` column to `evaluation_results` so that
the business decision has a queryable, indexable home instead of
being buried inside the `score_breakdown` JSON blob.

Backfills the new column from existing `score_breakdown["verdict"]`
values to ensure zero data loss.

Revision ID: e5f4d3c2b1a0
Revises: p1prod202606111615
Create Date: 2026-06-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "e5f4d3c2b1a0"
down_revision: Union[str, Sequence[str], None] = "p1prod202606111615"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Add verdict column ─────────────────────────────────────
    if not _has_column(conn, "evaluation_results", "verdict"):
        op.add_column(
            "evaluation_results",
            sa.Column("verdict", sa.String(50), nullable=True, index=True),
        )

    # ── 2. Backfill from score_breakdown JSON ──────────────────────
    conn.execute(
        text("""
            UPDATE evaluation_results
            SET verdict = JSON_UNQUOTE(
                JSON_EXTRACT(score_breakdown, '$.verdict')
            )
            WHERE verdict IS NULL
              AND score_breakdown IS NOT NULL
              AND JSON_EXTRACT(score_breakdown, '$.verdict') IS NOT NULL
        """)
    )

    # ── 3. Also backfill from recommended_verdicts table ────────────
    conn.execute(
        text("""
            UPDATE evaluation_results er
            INNER JOIN evaluation_sessions es ON er.evaluation_session_id = es.id
            INNER JOIN recommended_verdicts rv ON rv.evaluation_session_id = es.id
            SET er.verdict = rv.decision
            WHERE er.verdict IS NULL
              AND rv.decision IS NOT NULL
        """)
    )


def downgrade() -> None:
    if _has_column(op.get_bind(), "evaluation_results", "verdict"):
        op.drop_column("evaluation_results", "verdict")
