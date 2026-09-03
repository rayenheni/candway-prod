"""Add evaluation_config_snapshots table and FK on evaluation_sessions

Creates the immutable, self-contained config snapshot table that
decouples the AI Interview Engine from live Campaign / Job / Rubric
tables, and adds the FK column to evaluation_sessions.

Revision ID: ac4f530aebb2
Revises: m19_make_rubric_job_id_nullable
Create Date: 2026-06-27 19:23:31.547326
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "ac4f530aebb2"
down_revision: Union[str, Sequence[str], None] = "m19_make_rubric_job_id_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return bind.dialect.has_table(bind, name)


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in {c["name"] for c in inspect(conn).get_columns(table_name)}


def _has_index(conn, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in inspect(conn).get_indexes(table_name))


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create evaluation_config_snapshots table ──────────────
    if not _has_table("evaluation_config_snapshots"):
        op.create_table(
            "evaluation_config_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_type", sa.String(50), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("hash", sa.String(64), nullable=False, unique=True),
            sa.Column("rubric_id", sa.Integer(), nullable=True),
            sa.Column("rubric_version", sa.Integer(), nullable=True),
            sa.Column("total_questions", sa.Integer(), nullable=False, server_default=sa.text("15")),
            sa.Column("time_limit_seconds", sa.Integer(), nullable=True),
            sa.Column("passing_score", sa.Float(), nullable=True),
            sa.Column("max_score", sa.Float(), nullable=False, server_default=sa.text("100.0")),
            sa.Column("interview_instructions", sa.Text(), nullable=True),
            sa.Column("language", sa.String(10), nullable=False, server_default=sa.text("'en'")),
            sa.Column("question_generation_prompt", sa.Text(), nullable=True),
            sa.Column("evaluation_criteria", sa.JSON(), nullable=True),
            sa.Column("scoring_weights", sa.JSON(), nullable=True),
            sa.Column("source_metadata", sa.JSON(), nullable=True),
            sa.Column("resolved_rubric_json", sa.JSON(), nullable=True),
            sa.Column("resolved_skills_json", sa.JSON(), nullable=True),
            sa.Column("interview_config_json", sa.JSON(), nullable=True),
            sa.Column("scoring_rules_json", sa.JSON(), nullable=True),
            sa.Column("config_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if not _has_index(conn, "evaluation_config_snapshots", "idx_ecs_source"):
        op.create_index("idx_ecs_source", "evaluation_config_snapshots", ["source_type", "source_id"])
    if not _has_index(conn, "evaluation_config_snapshots", "idx_ecs_hash"):
        op.create_index("idx_ecs_hash", "evaluation_config_snapshots", ["hash"], unique=True)
    if not _has_index(conn, "evaluation_config_snapshots", "idx_ecs_created"):
        op.create_index("idx_ecs_created", "evaluation_config_snapshots", ["created_at"])

    # ── 1b. Add frozen-data columns to existing snapshots ─────────
    for col_name in ("resolved_rubric_json", "resolved_skills_json",
                     "interview_config_json", "scoring_rules_json"):
        if _has_table("evaluation_config_snapshots") and not _has_column(conn, "evaluation_config_snapshots", col_name):
            op.add_column("evaluation_config_snapshots", sa.Column(col_name, sa.JSON(), nullable=True))

    # ── 2. Add evaluation_config_snapshot_id to evaluation_sessions ──
    if not _has_column(conn, "evaluation_sessions", "evaluation_config_snapshot_id"):
        op.add_column(
            "evaluation_sessions",
            sa.Column(
                "evaluation_config_snapshot_id",
                sa.Integer(),
                sa.ForeignKey("evaluation_config_snapshots.id"),
                nullable=True,
                index=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop FK column from evaluation_sessions
    if _has_column(conn, "evaluation_sessions", "evaluation_config_snapshot_id"):
        op.drop_constraint(
            "evaluation_sessions_ibfk_6", "evaluation_sessions", type_="foreignkey"
        )
        op.drop_column("evaluation_sessions", "evaluation_config_snapshot_id")

    # Drop evaluation_config_snapshots table
    if _has_table("evaluation_config_snapshots"):
        op.drop_table("evaluation_config_snapshots")
