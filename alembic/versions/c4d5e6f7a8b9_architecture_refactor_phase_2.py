"""Architecture refactor Phase 2.

- Add application_id columns to 3 rubric tables + backfill
- Create CvDocument, AIInterviewSession, EvaluationState tables
- Enforce BatchJob.job_id NOT NULL
- Backfill SkillDefinition from rubric JSON

Revision ID: c4d5e6f7a8b9
Revises: a7b8c9d0e1f2
Create Date: 2026-06-07 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import OperationalError

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table, column):
    """Check if a column exists in MySQL."""
    conn = op.get_bind()
    return conn.execute(
        sa.text(f"SHOW COLUMNS FROM `{table}` LIKE :col"),
        {"col": column},
    ).fetchone() is not None


def _table_exists(table):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl"
    ), {"tbl": table}).fetchone()
    return result is not None


def _fk_exists(table, column, ref_table):
    """Check if a foreign key constraint exists."""
    conn = op.get_bind()
    return conn.execute(sa.text(
        "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl "
        "AND COLUMN_NAME = :col AND REFERENCED_TABLE_NAME = :ref"
    ), {"tbl": table, "col": column, "ref": ref_table}).fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    # ──────────────────────────────────────────────────────
    # 1. Add application_id columns to rubric tables (dual-column phase)
    # ──────────────────────────────────────────────────────
    for tbl in ("extracted_skills", "rubric_scoring_results", "interview_rubric_summaries"):
        if not _col_exists(tbl, "application_id"):
            op.add_column(tbl, sa.Column("application_id", sa.Integer(), nullable=True))
        if not _fk_exists(tbl, "application_id", "applications"):
            fk_name = {"extracted_skills": "fk_extracted_skills_app",
                       "rubric_scoring_results": "fk_rubric_score_app",
                       "interview_rubric_summaries": "fk_rubric_summary_app"}[tbl]
            op.create_foreign_key(fk_name, tbl, "applications", ["application_id"], ["id"])

    # Create indexes (idempotent — wrap duplicate errors)
    for idx_name, tbl_name, is_unique in [
        ("idx_extracted_skills_app", "extracted_skills", False),
        ("idx_rubric_score_app", "rubric_scoring_results", False),
        ("idx_rubric_summary_app", "interview_rubric_summaries", True),
    ]:
        try:
            op.create_index(idx_name, tbl_name, ["application_id"], unique=is_unique)
        except OperationalError as e:
            if e.orig and e.orig.args[0] not in (1061, 1069):
                raise

    # Backfill application_id = interview_id
    for tbl in ("extracted_skills", "rubric_scoring_results", "interview_rubric_summaries"):
        conn.execute(sa.text(f"UPDATE `{tbl}` SET application_id = interview_id WHERE application_id IS NULL"))

    # Make application_id NOT NULL after backfill
    for tbl in ("extracted_skills", "rubric_scoring_results", "interview_rubric_summaries"):
        op.alter_column(tbl, "application_id", existing_type=sa.Integer(), nullable=False)

    # ──────────────────────────────────────────────────────
    # 2. Add + Enforce BatchJob.job_id NOT NULL
    # ──────────────────────────────────────────────────────
    if not _col_exists("batch_jobs", "job_id"):
        op.add_column("batch_jobs", sa.Column("job_id", sa.Integer(), nullable=True))
    if not _fk_exists("batch_jobs", "job_id", "jobs"):
        op.create_foreign_key("fk_batch_job_job", "batch_jobs", "jobs", ["job_id"], ["id"])
    # Backfill NULL job_ids to recruiter's most recent job
    null_batches = conn.execute(
        sa.text("SELECT b.id, b.recruiter_id FROM batch_jobs b WHERE b.job_id IS NULL")
    ).fetchall()
    for batch_id, recruiter_id in null_batches:
        most_recent_job = conn.execute(
            sa.text(
                "SELECT id FROM jobs WHERE recruiter_id = :rid ORDER BY created_at DESC LIMIT 1"
            ),
            {"rid": recruiter_id},
        ).fetchone()
        if most_recent_job:
            conn.execute(
                sa.text("UPDATE batch_jobs SET job_id = :jid WHERE id = :bid"),
                {"jid": most_recent_job[0], "bid": batch_id},
            )
    op.alter_column("batch_jobs", "job_id", existing_type=sa.Integer(), nullable=False)

    # ──────────────────────────────────────────────────────
    # 3. Create CvDocument table
    # ──────────────────────────────────────────────────────
    if not _table_exists("cv_documents"):
        op.create_table(
            "cv_documents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, unique=True),
            sa.Column("cv_text", sa.Text(), nullable=True),
            sa.Column("cv_file_path", sa.String(255), nullable=True),
            sa.Column("cv_text_anonymized", sa.Text(), nullable=True),
            sa.Column("extracted_skills", sa.JSON(), nullable=True),
            sa.Column("cv_embedding", sa.Text(), nullable=True),
            sa.Column("analysis_json", sa.JSON(), nullable=True),
            sa.Column("cv_review_json", sa.JSON(), nullable=True),
            sa.Column("roadmap_json", sa.JSON(), nullable=True),
            sa.Column("detected_role", sa.String(255), nullable=True),
            sa.Column("declared_role", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("idx_cv_doc_app", "cv_documents", ["application_id"], unique=True)

    # ──────────────────────────────────────────────────────
    # 4. Create AIInterviewSession table
    # ──────────────────────────────────────────────────────
    if not _table_exists("ai_interview_sessions"):
        op.create_table(
            "ai_interview_sessions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, unique=True),
            sa.Column("interview_state", sa.String(20), server_default="not_started"),
            sa.Column("interview_progress", sa.Integer(), server_default="0"),
            sa.Column("interview_time_left", sa.Integer(), server_default="1800"),
            sa.Column("interview_last_saved", sa.DateTime(), nullable=True),
            sa.Column("interview_log", sa.JSON(), nullable=True),
            sa.Column("interview_questions", sa.JSON(), nullable=True),
            sa.Column("interview_qa_structured", sa.JSON(), nullable=True),
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
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("idx_ai_session_app", "ai_interview_sessions", ["application_id"], unique=True)
        op.create_index("idx_ai_session_state", "ai_interview_sessions", ["interview_state"])

    # ──────────────────────────────────────────────────────
    # 5. Create EvaluationState table
    # ──────────────────────────────────────────────────────
    if not _table_exists("evaluation_states"):
        op.create_table(
            "evaluation_states",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, unique=True),
            sa.Column("evaluation_state", sa.String(20), server_default="pending"),
            sa.Column("evaluation_source", sa.String(20), nullable=True),
            sa.Column("evaluation_started_at", sa.DateTime(), nullable=True),
            sa.Column("evaluation_completed_at", sa.DateTime(), nullable=True),
            sa.Column("final_eval_done", sa.Boolean(), server_default=sa.text("0")),
            sa.Column("final_eval_timestamp", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("idx_eval_state_app", "evaluation_states", ["application_id"], unique=True)
        op.create_index("idx_eval_state_status", "evaluation_states", ["evaluation_state"])

    # ──────────────────────────────────────────────────────
    # 6. Create application_scores table (if not existing)
    # ──────────────────────────────────────────────────────
    if not _table_exists("application_scores"):
        op.create_table(
            "application_scores",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, unique=True),
            sa.Column("cv_score", sa.Float(), nullable=True),
            sa.Column("rubric_score", sa.Float(), nullable=True),
            sa.Column("human_integrity_score", sa.Float(), server_default="100.0"),
            sa.Column("rubric_coverage_pct", sa.Float(), nullable=True),
            sa.Column("final_score", sa.Float(), nullable=False),
            sa.Column("composite_score", sa.Float(), nullable=True),
            sa.Column("score_breakdown", sa.JSON(), nullable=True),
            sa.Column("verdict", sa.String(255), nullable=True),
            sa.Column("fraud_score", sa.Float(), server_default="0.0"),
            sa.Column("fraud_reported_by", sa.Integer(), nullable=True),
            sa.Column("fraud_reported_at", sa.DateTime(), nullable=True),
            sa.Column("scoring_model", sa.String(20), server_default="rubric"),
            sa.Column("rubric_version", sa.Integer(), nullable=True),
            sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("computed_by", sa.String(50), nullable=True),
        )
        op.create_index("idx_app_score_app", "application_scores", ["application_id"], unique=True)
        op.create_index("idx_app_score_final", "application_scores", ["final_score"])

    # ──────────────────────────────────────────────────────
    # 7. Backfill SkillDefinition from rubric JSON (pure Python)
    # ──────────────────────────────────────────────────────
    from uuid import uuid4
    import json as _json
    seen = set()
    rows = conn.execute(sa.text("SELECT id, rubric_json FROM job_rubrics WHERE rubric_json IS NOT NULL")).fetchall()
    for row in rows:
        try:
            raw = row[1]
            if isinstance(raw, str):
                rubric = _json.loads(raw)
            else:
                rubric = raw
        except (_json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(rubric, dict):
            continue
        for cat in rubric.get("categories", []):
            for sub in cat.get("subcategories", []):
                for skill in sub.get("skills", []):
                    name = skill.get("name", "").strip()
                    if not name or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    skill_id = str(uuid4())
                    desc = skill.get("description", "")
                    exp_prof = skill.get("expected_proficiency", "mid")
                    weight = skill.get("weight", 1.0)
                    conn.execute(
                        sa.text(
                            "INSERT IGNORE INTO skill_definitions (id, name, description, expected_proficiency, weight) "
                            "VALUES (:id, :name, :desc, :exp, :weight)"
                        ),
                        {"id": skill_id, "name": name, "desc": desc, "exp": exp_prof, "weight": weight},
                    )


def downgrade() -> None:
    # Drop extracted entity tables
    op.drop_table("application_scores")
    op.drop_table("evaluation_states")
    op.drop_table("ai_interview_sessions")
    op.drop_table("cv_documents")

    # Revert BatchJob.job_id back to nullable + drop FK
    op.drop_constraint("fk_batch_job_job", "batch_jobs", type_="foreignkey")
    op.alter_column("batch_jobs", "job_id", existing_type=sa.Integer(), nullable=True)

    # Drop application_id columns from rubric tables
    op.drop_column("interview_rubric_summaries", "application_id")
    op.drop_column("rubric_scoring_results", "application_id")
    op.drop_column("extracted_skills", "application_id")
