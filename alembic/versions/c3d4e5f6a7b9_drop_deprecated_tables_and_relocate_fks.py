"""M003: Drop 6 deprecated tables, relocate FKs from job_rubrics to rubrics.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-06-11

This migration is destructive — data was already backfilled in M002.
Drops tables that are fully replaced by North Star equivalents:
  - rubric_scoring_results  → rubric_scoring_details
  - interview_rubric_summaries  → evaluation_results
  - ai_interview_sessions  → evaluation_sessions
  - evaluation_states  → evaluation_sessions
  - rubric_nodes  (dead table, 0 rows, no model class)
  - job_rubrics  → rubrics

Also relocates FK constraints on applications.rubric_id (and optionally
jobs.rubric_id) from job_rubrics.id to rubrics.id.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b9"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_exists(conn, table: str, column: str, ref_table: str) -> str | None:
    """Return the FK constraint name if it exists, else None."""
    row = conn.execute(
        sa.text(
            "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl "
            "AND COLUMN_NAME = :col AND REFERENCED_TABLE_NAME = :ref"
        ),
        {"tbl": table, "col": column, "ref": ref_table},
    ).fetchone()
    return row[0] if row else None


def _col_exists(conn, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(f"SHOW COLUMNS FROM `{table}` LIKE :col"),
            {"col": column},
        ).fetchone()
        is not None
    )


def upgrade():
    conn = op.get_bind()

    # ── 1. Drop FK from applications.rubric_id → job_rubrics.id ─────────
    fk_name = _fk_exists(conn, "applications", "rubric_id", "job_rubrics")
    if fk_name:
        op.drop_constraint(fk_name, "applications", type_="foreignkey")

    # ── 2. Drop FK from jobs.rubric_id → job_rubrics.id (if column exists) ──
    if _col_exists(conn, "jobs", "rubric_id"):
        fk_name = _fk_exists(conn, "jobs", "rubric_id", "job_rubrics")
        if fk_name:
            op.drop_constraint(fk_name, "jobs", type_="foreignkey")

    # ── 3. Add FK from applications.rubric_id → rubrics.id ───────────────
    op.create_foreign_key(
        "fk_app_rubric_new",
        "applications", "rubrics",
        ["rubric_id"], ["id"],
    )

    # ── 4. Add FK from jobs.rubric_id → rubrics.id (if column exists) ───
    if _col_exists(conn, "jobs", "rubric_id"):
        op.create_foreign_key(
            "fk_job_rubric_new",
            "jobs", "rubrics",
            ["rubric_id"], ["id"],
        )

    # ── 5. Drop 6 deprecated tables ───────────────────────────────────────
    op.drop_table("rubric_scoring_results")
    op.drop_table("interview_rubric_summaries")
    op.drop_table("rubric_nodes")
    op.drop_table("ai_interview_sessions")
    op.drop_table("evaluation_states")
    op.drop_table("job_rubrics")


def downgrade():
    conn = op.get_bind()

    # Re-create job_rubrics table (same schema as migration 0ce7416aa096)
    op.create_table(
        "job_rubrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), server_default="1"),
        sa.Column("seniority", sa.String(20), server_default="mid"),
        sa.Column("status", sa.String(20), server_default="published"),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("base_version", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("rubric_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "version", name="uq_job_rubric_version"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_jr_job"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_jr_creator"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_job_rubrics_current", "job_rubrics", ["job_id", "is_current"])

    # Re-create rubric_nodes (dead table — empty schema)
    op.create_table(
        "rubric_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("rubric_version_id", sa.Integer(), nullable=True),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("skill_levels", sa.JSON(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_rn_job"),
        sa.ForeignKeyConstraint(
            ["rubric_version_id"], ["job_rubrics.id"], name="fk_rn_version"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["rubric_nodes.id"], name="fk_rn_parent"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rubric_node_job", "rubric_nodes", ["job_id"])
    op.create_index("idx_rubric_node_version", "rubric_nodes", ["rubric_version_id"])
    op.create_index("idx_rubric_node_parent", "rubric_nodes", ["parent_id"])

    # Re-create ai_interview_sessions
    op.create_table(
        "ai_interview_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("interview_state", sa.String(20), server_default="not_started"),
        sa.Column("interview_progress", sa.Integer(), server_default="0"),
        sa.Column("interview_time_left", sa.Integer(), server_default="1800"),
        sa.Column("interview_last_saved", sa.DateTime(), nullable=True),
        sa.Column("interview_log", sa.JSON(), nullable=True),
        sa.Column("interview_questions", sa.JSON(), nullable=True),
        sa.Column("generated_questions", sa.JSON(), nullable=True),
        sa.Column("proctoring_violations", sa.JSON(), nullable=True),
        sa.Column("video_file_path", sa.String(512), nullable=True),
        sa.Column("video_transcript", sa.Text(), nullable=True),
        sa.Column("video_analysis_json", sa.JSON(), nullable=True),
        sa.Column("interview_reset_count", sa.Integer(), server_default="0"),
        sa.Column("interview_last_reset_at", sa.DateTime(), nullable=True),
        sa.Column("interview_turn_seq", sa.Integer(), server_default="0"),
        sa.Column("calibration_json", sa.JSON(), nullable=True),
        sa.Column("calibration_score", sa.Float(), nullable=True),
        sa.Column("calibration_verified_skills", sa.JSON(), nullable=True),
        sa.Column("rubric_id", sa.Integer(), nullable=True),
        sa.Column("rubric_version", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_ai_session_app"
        ),
        sa.ForeignKeyConstraint(
            ["rubric_id"], ["job_rubrics.id"], name="fk_ai_session_rubric"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_ai_session_app", "ai_interview_sessions", ["application_id"], unique=True)
    op.create_index("idx_ai_session_state", "ai_interview_sessions", ["interview_state"])

    # Re-create evaluation_states
    op.create_table(
        "evaluation_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("evaluation_state", sa.String(20), server_default="pending"),
        sa.Column("evaluation_source", sa.String(20), nullable=True),
        sa.Column("evaluation_started_at", sa.DateTime(), nullable=True),
        sa.Column("evaluation_completed_at", sa.DateTime(), nullable=True),
        sa.Column("final_eval_done", sa.Boolean(), server_default="0"),
        sa.Column("final_eval_timestamp", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_eval_state_app"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_eval_state_app", "evaluation_states", ["application_id"], unique=True)
    op.create_index("idx_eval_state_status", "evaluation_states", ["evaluation_state"])

    # Re-create interview_rubric_summaries
    op.create_table(
        "interview_rubric_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("rubric_id", sa.Integer(), nullable=False),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("confidence_lower", sa.Integer(), nullable=False),
        sa.Column("confidence_upper", sa.Integer(), nullable=False),
        sa.Column("category_scores", sa.JSON(), nullable=True),
        sa.Column("skill_scores", sa.JSON(), nullable=True),
        sa.Column("gaps", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.Column("num_answers_scored", sa.Integer(), server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_irs_app"
        ),
        sa.ForeignKeyConstraint(
            ["rubric_id"], ["job_rubrics.id"], name="fk_irs_rubric"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rubric_summary_app", "interview_rubric_summaries", ["application_id"], unique=True)

    # Re-create rubric_scoring_results
    op.create_table(
        "rubric_scoring_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("answer_id", sa.Integer(), nullable=False),
        sa.Column("rubric_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("skill_id", sa.String(64), nullable=True),
        sa.Column("base_score", sa.Integer(), nullable=False),
        sa.Column("quality_multiplier", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Integer(), nullable=False),
        sa.Column("confidence_lower", sa.Integer(), nullable=False),
        sa.Column("confidence_upper", sa.Integer(), nullable=False),
        sa.Column("evidence_sentences", sa.JSON(), nullable=True),
        sa.Column("matched_keywords", sa.JSON(), nullable=True),
        sa.Column("matched_level_description", sa.Text(), nullable=True),
        sa.Column("missing_competencies", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], name="fk_rs_app"
        ),
        sa.ForeignKeyConstraint(
            ["rubric_id"], ["job_rubrics.id"], name="fk_rs_rubric"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rubric_score_app", "rubric_scoring_results", ["application_id"])
    op.create_index("idx_rubric_score_answer", "rubric_scoring_results", ["answer_id"])

    # Restore FK on jobs.rubric_id (if column exists)
    if _col_exists(conn, "jobs", "rubric_id"):
        op.drop_constraint("fk_job_rubric_new", "jobs", type_="foreignkey")
        op.create_foreign_key(
            "fk_job_rubric_old",
            "jobs", "job_rubrics",
            ["rubric_id"], ["id"],
        )

    # Restore FK on applications.rubric_id → job_rubrics.id
    op.drop_constraint("fk_app_rubric_new", "applications", type_="foreignkey")
    op.create_foreign_key(
        "fk_app_rubric",
        "applications", "job_rubrics",
        ["rubric_id"], ["id"],
    )
