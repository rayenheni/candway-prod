"""M001: Create evaluation + profile + rubric North Star tables.

Revision ID: a1b2c3d4e5f7
Revises: 2e142c44ba3e
Create Date: 2026-06-11

This migration is purely additive — no data is dropped or altered.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "2e142c44ba3e"
branch_labels = None
depends_on = None


def upgrade():
    # ── Profile tables first (referenced by evaluation_sessions) ────
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("headline", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("languages", sa.String(255), nullable=True),
        sa.Column("availability", sa.String(255), nullable=True),
        sa.Column("work_preference", sa.String(255), nullable=True),
        sa.Column("salary_expectation_min", sa.Integer(), nullable=True),
        sa.Column("salary_expectation_max", sa.Integer(), nullable=True),
        sa.Column("linkedin_url", sa.String(255), nullable=True),
        sa.Column("github_url", sa.String(255), nullable=True),
        sa.Column("portfolio_url", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(255), nullable=True),
        sa.Column("profile_views", sa.Integer(), server_default="0"),
        sa.Column("profile_views_growth", sa.Float(), server_default="12.0"),
        sa.Column("candidate_cv_uploads_this_month", sa.Integer(), server_default="0"),
        sa.Column("candidate_ai_analyses_this_month", sa.Integer(), server_default="0"),
        sa.Column("candidate_pdf_downloads_this_month", sa.Integer(), server_default="0"),
        sa.Column("candidate_usage_reset_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_candidate_profiles_user", "candidate_profiles", ["user_id"], unique=True)
    op.create_foreign_key(
        "fk_candidate_profile_user",
        "candidate_profiles", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )

    op.create_table(
        "recruiter_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("company_description", sa.Text(), nullable=True),
        sa.Column("company_logo_url", sa.String(255), nullable=True),
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_user", sa.String(255), nullable=True),
        sa.Column("smtp_password", sa.Text(), nullable=True),
        sa.Column("usage_jobs", sa.Integer(), server_default="0"),
        sa.Column("usage_cvs", sa.Integer(), server_default="0"),
        sa.Column("usage_ai_interviews", sa.Integer(), server_default="0"),
        sa.Column("usage_reset_date", sa.DateTime(), nullable=True),
        sa.Column("email_settings", sa.Text(), nullable=True),
        sa.Column("linkedin_settings", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_recruiter_profiles_user", "recruiter_profiles", ["user_id"], unique=True)
    op.create_foreign_key(
        "fk_recruiter_profile_user",
        "recruiter_profiles", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )

    op.create_table(
        "admin_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("permissions", sa.Text(), nullable=True),
        sa.Column("is_super_admin", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_admin_profiles_user", "admin_profiles", ["user_id"], unique=True)
    op.create_foreign_key(
        "fk_admin_profile_user",
        "admin_profiles", "users",
        ["user_id"], ["id"], ondelete="CASCADE",
    )

    # ── rubrics (referenced by evaluation_sessions FK) ──────────────
    op.create_table(
        "rubrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("passing_score", sa.Float(), server_default="0.0"),
        sa.Column("max_score", sa.Float(), server_default="100.0"),
        sa.Column("weight", sa.Float(), server_default="1.0"),
        sa.Column("criteria_json", sa.Text(), nullable=True),
        sa.Column("skill_weights", sa.Text(), nullable=True),
        sa.Column("complexity", sa.String(50), server_default="intermediate"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rubric_job", "rubrics", ["job_id"])
    op.create_index("idx_rubric_version", "rubrics", ["job_id", "version"])
    op.create_foreign_key("fk_rubric_job", "rubrics", "jobs", ["job_id"], ["id"])
    op.create_foreign_key("fk_rubric_creator", "rubrics", "users", ["created_by"], ["id"])

    # ── evaluation_sessions (refs candidate_profiles + rubrics) ─────
    op.create_table(
        "evaluation_sessions",
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("context_type", sa.String(50), nullable=False, server_default="job"),
        sa.Column("context_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("language", sa.String(50), server_default="English"),
        sa.Column("source", sa.String(50), nullable=True),
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
        mysql_engine="InnoDB",
    )
    op.create_index("idx_es_app", "evaluation_sessions", ["application_id"])
    op.create_index("idx_es_candidate", "evaluation_sessions", ["candidate_id"])
    op.create_index("idx_es_context", "evaluation_sessions", ["context_type", "context_id"])
    op.create_index("idx_es_status", "evaluation_sessions", ["status"])
    op.create_foreign_key(
        "fk_es_application",
        "evaluation_sessions", "applications",
        ["application_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_es_candidate",
        "evaluation_sessions", "candidate_profiles",
        ["candidate_id"], ["id"],
    )

    # ── evaluation_results (refs evaluation_sessions + rubrics) ────
    op.create_table(
        "evaluation_results",
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_session_id", sa.Integer(), nullable=False),
        sa.Column("rubric_id", sa.Integer(), nullable=False),
        sa.Column("rubric_version", sa.Integer(), nullable=False),
        sa.Column("cv_score", sa.Float(), nullable=True),
        sa.Column("rubric_score", sa.Float(), nullable=True),
        sa.Column("human_integrity_score", sa.Float(), server_default="100.0"),
        sa.Column("rubric_coverage_pct", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("confidence_lower", sa.Float(), nullable=True),
        sa.Column("confidence_upper", sa.Float(), nullable=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("fraud_score", sa.Float(), server_default="0.0"),
        sa.Column("fraud_reported_by", sa.Integer(), nullable=True),
        sa.Column("fraud_reported_at", sa.DateTime(), nullable=True),
        sa.Column("scoring_model", sa.String(50), server_default="rubric"),
        sa.Column("needs_review", sa.Boolean(), server_default="0"),
        sa.Column("needs_review_reason", sa.String(500), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("computed_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_session_id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_er_final_score", "evaluation_results", ["final_score"])
    op.create_index("idx_er_needs_review", "evaluation_results", ["needs_review"])
    op.create_foreign_key(
        "fk_er_session",
        "evaluation_results", "evaluation_sessions",
        ["evaluation_session_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_er_rubric",
        "evaluation_results", "rubrics",
        ["rubric_id"], ["id"],
    )

    # ── rubric_scoring_details (refs evaluation_results) ───────────
    op.create_table(
        "rubric_scoring_details",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_result_id", sa.Integer(), nullable=False),
        sa.Column("criterion_name", sa.String(255), nullable=False),
        sa.Column("criterion_key", sa.String(100), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1.0"),
        sa.Column("max_score", sa.Float(), server_default="100.0"),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_rsd_result", "rubric_scoring_details", ["evaluation_result_id"])
    op.create_foreign_key(
        "fk_rsd_result",
        "rubric_scoring_details", "evaluation_results",
        ["evaluation_result_id"], ["id"],
    )

    # ── recommended_verdicts (refs evaluation_sessions) ─────────────
    op.create_table(
        "recommended_verdicts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_session_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_session_id"),
        mysql_engine="InnoDB",
    )
    op.create_foreign_key(
        "fk_rv_session",
        "recommended_verdicts", "evaluation_sessions",
        ["evaluation_session_id"], ["id"],
    )

    # ── verdicts (refs applications + evaluation_sessions + self) ──
    op.create_table(
        "verdicts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(255), nullable=False),
        sa.Column("decided_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("evaluation_session_id", sa.Integer(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.Column("adverse_action_sent", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
    )
    op.create_index("idx_verdict_application", "verdicts", ["application_id"])
    op.create_index("idx_verdict_decision", "verdicts", ["decision"])
    op.create_index("idx_verdict_source", "verdicts", ["source"])
    op.create_foreign_key(
        "fk_verdict_application",
        "verdicts", "applications",
        ["application_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_verdict_eval_session",
        "verdicts", "evaluation_sessions",
        ["evaluation_session_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_verdict_superseded_by",
        "verdicts", "verdicts",
        ["superseded_by"], ["id"],
    )

    # ── Add evaluation_session_id to cv_documents ───────────────────
    op.add_column(
        "cv_documents",
        sa.Column("evaluation_session_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_cv_doc_eval_session", "cv_documents", ["evaluation_session_id"])
    op.create_foreign_key(
        "fk_cv_doc_eval_session",
        "cv_documents", "evaluation_sessions",
        ["evaluation_session_id"], ["id"],
    )

    # ── Add evaluation_session_id to interview_turns ────────────────
    op.add_column(
        "interview_turns",
        sa.Column("evaluation_session_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_turns_eval_session", "interview_turns", ["evaluation_session_id"])
    op.create_foreign_key(
        "fk_turn_eval_session",
        "interview_turns", "evaluation_sessions",
        ["evaluation_session_id"], ["id"],
    )


def downgrade():
    op.drop_constraint("fk_turn_eval_session", "interview_turns", type_="foreignkey")
    op.drop_index("idx_turns_eval_session", table_name="interview_turns")
    op.drop_column("interview_turns", "evaluation_session_id")

    op.drop_constraint("fk_cv_doc_eval_session", "cv_documents", type_="foreignkey")
    op.drop_index("idx_cv_doc_eval_session", table_name="cv_documents")
    op.drop_column("cv_documents", "evaluation_session_id")

    op.drop_table("rubric_scoring_details")
    op.drop_table("rubrics")
    op.drop_table("recommended_verdicts")
    op.drop_table("evaluation_results")
    op.drop_table("verdicts")
    op.drop_table("recruiter_profiles")
    op.drop_table("candidate_profiles")
    op.drop_table("admin_profiles")
    op.drop_table("evaluation_sessions")
