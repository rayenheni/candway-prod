"""M006: Production integrity fixes for tenanting and evaluation aggregates.

Revision ID: p1prod202606111615
Revises: a7b8c9d0e1f2, b2c3d4e5f6a8
Create Date: 2026-06-11 16:15:00.000000

Production-stability only:
- Adds tenant FKs to Application, EvaluationSession, and InterviewTurn.
- Backfills tenant IDs from job/batch recruiter company membership.
- Makes EvaluationSession.application_id and InterviewTurn.evaluation_session_id non-null.
- Makes InterviewTurn ownership unambiguous: evaluation_session_id is the owner.
- Aligns score/status constraints with canonical evaluation tables.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "p1prod202606111615"
down_revision: Union[str, Sequence[str], None] = ("a7b8c9d0e1f2", "b2c3d4e5f6a8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspect(conn).get_columns(table_name)}


def _has_index(conn, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in inspect(conn).get_indexes(table_name))


def _has_unique(conn, table_name: str, constraint_name: str) -> bool:
    return any(uc.get("name") == constraint_name for uc in inspect(conn).get_unique_constraints(table_name))


def _has_fk(conn, table_name: str, constraint_name: str) -> bool:
    return any(fk.get("name") == constraint_name for fk in inspect(conn).get_foreign_keys(table_name))


def _drop_constraint(name: str, table_name: str, constraint_type: str):
    try:
        op.drop_constraint(name, table_name, type_=constraint_type)
    except Exception:
        pass


def _drop_index(name: str, table_name: str):
    try:
        op.drop_index(name, table_name=table_name)
    except Exception:
        pass


def _ensure_fallback_company(conn) -> int:
    conn.execute(
        sa.text(
            """
            INSERT INTO companies (name, slug, is_active, created_at, updated_at)
            SELECT 'Legacy Company', 'legacy-company', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM companies WHERE slug = 'legacy-company'
            )
            """
        )
    )
    return int(conn.scalar(sa.text("SELECT id FROM companies WHERE slug = 'legacy-company' ORDER BY id LIMIT 1")))


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_column(conn, "applications", "company_id"):
        op.add_column(
            "applications",
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        )
    if not _has_column(conn, "evaluation_sessions", "company_id"):
        op.add_column(
            "evaluation_sessions",
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        )
    if not _has_column(conn, "interview_turns", "company_id"):
        op.add_column(
            "interview_turns",
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        )

    fallback_company_id = _ensure_fallback_company(conn)

    # MySQL 8.0 cannot reference the same temporary table more than once in a
    # single statement, so we create three separate copies for the three JOIN
    # positions in the UPDATE below.
    for tmp_name in ("tmp_cby_batch", "tmp_cby_job", "tmp_cby_applicant"):
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {tmp_name}"))
        conn.execute(
            sa.text(
                f"""
                CREATE TEMPORARY TABLE {tmp_name} AS
                SELECT user_id, MIN(company_id) AS company_id
                FROM company_members
                WHERE is_active = 1 OR is_active IS NULL
                GROUP BY user_id
                """
            )
        )
        conn.execute(sa.text(f"CREATE INDEX {tmp_name}_idx ON {tmp_name} (user_id)"))

    conn.execute(
        sa.text(
            """
            UPDATE applications a
            LEFT JOIN batch_jobs b ON b.id = a.batch_id
            LEFT JOIN jobs j ON j.id = a.job_id
            LEFT JOIN tmp_cby_batch cb ON cb.user_id = b.recruiter_id
            LEFT JOIN tmp_cby_job cj ON cj.user_id = j.recruiter_id
            LEFT JOIN tmp_cby_applicant cu ON cu.user_id = a.user_id
            SET a.company_id = COALESCE(cb.company_id, cj.company_id, cu.company_id, :fallback_company_id)
            WHERE a.company_id IS NULL
            """
        ),
        {"fallback_company_id": fallback_company_id},
    )

    conn.execute(sa.text("DROP TABLE IF EXISTS tmp_latest_application_by_user"))
    conn.execute(
        sa.text(
            """
            CREATE TEMPORARY TABLE tmp_latest_application_by_user AS
            SELECT user_id, MAX(id) AS application_id
            FROM applications
            GROUP BY user_id
            """
        )
    )
    conn.execute(sa.text("CREATE INDEX tmp_latest_application_by_user_idx ON tmp_latest_application_by_user (user_id)"))

    conn.execute(
        sa.text(
            """
            UPDATE evaluation_sessions es
            JOIN applications a ON a.id = es.application_id
            SET es.company_id = a.company_id
            WHERE es.company_id IS NULL
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE evaluation_sessions es
            JOIN tmp_latest_application_by_user la ON la.user_id = (
                SELECT cp.user_id FROM candidate_profiles cp WHERE cp.id = es.candidate_id LIMIT 1
            )
            SET es.application_id = la.application_id,
                es.company_id = (SELECT a.company_id FROM applications a WHERE a.id = la.application_id LIMIT 1)
            WHERE es.application_id IS NULL
            """
        )
    )

    remaining_eval_sessions = conn.scalar(sa.text("SELECT COUNT(*) FROM evaluation_sessions WHERE application_id IS NULL"))
    if remaining_eval_sessions:
        raise RuntimeError(f"{remaining_eval_sessions} evaluation_sessions cannot be assigned to an application")

    conn.execute(
        sa.text(
            """
            UPDATE interview_turns it
            LEFT JOIN tmp_latest_application_by_user la ON la.user_id = it.user_id
            SET it.evaluation_session_id = COALESCE(
                it.evaluation_session_id,
                (
                    SELECT es.id
                    FROM evaluation_sessions es
                    WHERE es.application_id = it.application_id
                    ORDER BY es.id DESC
                    LIMIT 1
                ),
                (
                    SELECT es.id
                    FROM evaluation_sessions es
                    WHERE es.application_id = la.application_id
                    ORDER BY es.id DESC
                    LIMIT 1
                )
            )
            WHERE it.evaluation_session_id IS NULL
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE interview_turns it
            LEFT JOIN evaluation_sessions es ON es.id = it.evaluation_session_id
            LEFT JOIN applications a ON a.id = COALESCE(es.application_id, it.application_id)
            LEFT JOIN tmp_cby_applicant cu ON cu.user_id = it.user_id
            SET it.company_id = COALESCE(es.company_id, a.company_id, cu.company_id, :fallback_company_id)
            WHERE it.company_id IS NULL
            """
        ),
        {"fallback_company_id": fallback_company_id},
    )

    remaining_turns = conn.scalar(
        sa.text(
            """
            SELECT COUNT(*)
            FROM interview_turns
            WHERE application_id IS NULL AND evaluation_session_id IS NULL
            """
        )
    )
    if remaining_turns:
        raise RuntimeError(f"{remaining_turns} interview_turns cannot be assigned to an evaluation_session")

    # Make application_id nullable before clearing it for XOR ownership
    op.alter_column("interview_turns", "application_id", existing_type=sa.Integer(), nullable=True)

    conn.execute(sa.text("UPDATE interview_turns SET application_id = NULL WHERE application_id IS NOT NULL AND evaluation_session_id IS NOT NULL"))

    remaining_turns = conn.scalar(
        sa.text(
            """
            SELECT COUNT(*)
            FROM interview_turns
            WHERE application_id IS NULL AND evaluation_session_id IS NULL
            """
        )
    )
    if remaining_turns:
        raise RuntimeError(f"{remaining_turns} interview_turns cannot be assigned to an evaluation_session")

    op.alter_column("applications", "company_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("evaluation_sessions", "application_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("evaluation_sessions", "company_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("interview_turns", "evaluation_session_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("interview_turns", "company_id", existing_type=sa.Integer(), nullable=False)

    if not _has_fk(conn, "applications", "fk_applications_company"):
        op.create_foreign_key("fk_applications_company", "applications", "companies", ["company_id"], ["id"])
    if not _has_fk(conn, "evaluation_sessions", "fk_evaluation_sessions_company"):
        op.create_foreign_key("fk_evaluation_sessions_company", "evaluation_sessions", "companies", ["company_id"], ["id"])
    if not _has_fk(conn, "interview_turns", "fk_interview_turns_company"):
        op.create_foreign_key("fk_interview_turns_company", "interview_turns", "companies", ["company_id"], ["id"])

    _drop_constraint("fk_es_application", "evaluation_sessions", "foreignkey")
    if not _has_fk(conn, "evaluation_sessions", "fk_es_application"):
        op.create_foreign_key(
            "fk_es_application",
            "evaluation_sessions",
            "applications",
            ["application_id"],
            ["id"],
            ondelete="CASCADE",
        )

    _drop_constraint("fk_turn_eval_session", "interview_turns", "foreignkey")
    if not _has_fk(conn, "interview_turns", "fk_turn_eval_session"):
        op.create_foreign_key(
            "fk_turn_eval_session",
            "interview_turns",
            "evaluation_sessions",
            ["evaluation_session_id"],
            ["id"],
            ondelete="CASCADE",
        )

    _drop_constraint("uq_turns_app_number", "interview_turns", "unique")

    if not _has_index(conn, "applications", "idx_applications_company"):
        op.create_index("idx_applications_company", "applications", ["company_id"])
    if not _has_index(conn, "evaluation_sessions", "idx_es_company"):
        op.create_index("idx_es_company", "evaluation_sessions", ["company_id"])
    if not _has_index(conn, "evaluation_sessions", "idx_es_app_status"):
        op.create_index("idx_es_app_status", "evaluation_sessions", ["application_id", "status"])
    if not _has_index(conn, "interview_turns", "idx_it_company"):
        op.create_index("idx_it_company", "interview_turns", ["company_id"])
    if not _has_unique(conn, "interview_turns", "uq_turns_eval_number"):
        op.create_index(
            "uq_turns_eval_number",
            "interview_turns",
            ["evaluation_session_id", "turn_number"],
            unique=True,
        )

    conn.execute(sa.text("UPDATE applications SET analysis_score = 0 WHERE analysis_score < 0"))
    conn.execute(sa.text("UPDATE applications SET analysis_score = 100 WHERE analysis_score > 100"))
    conn.execute(sa.text("UPDATE applications SET interview_state = 'not_started' WHERE interview_state IS NULL OR interview_state NOT IN ('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused')"))
    conn.execute(sa.text("UPDATE applications SET evaluation_state = 'pending' WHERE evaluation_state IS NULL OR evaluation_state NOT IN ('pending', 'running', 'completed', 'failed', 'flagged', 'expired', 'override')"))
    conn.execute(sa.text("UPDATE applications SET status = 'pending' WHERE status IS NULL OR status NOT IN ('pending', 'screening', 'interviewing', 'offer', 'rejected', 'analyzed', 'failed', 'applied', 'invited', 'active', 'analyzing', 'analysis_failed')"))
    conn.execute(sa.text("UPDATE evaluation_sessions SET status = 'created' WHERE status IS NULL OR status NOT IN ('created', 'in_progress', 'paused', 'completed', 'expired', 'failed', 'running', 'pending', 'flagged', 'needs_review')"))
    conn.execute(sa.text("UPDATE evaluation_sessions SET interview_state = 'not_started' WHERE interview_state IS NULL OR interview_state NOT IN ('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused')"))
    conn.execute(sa.text("UPDATE interview_turns SET score = 0 WHERE score < 0"))
    conn.execute(sa.text("UPDATE interview_turns SET score = 100 WHERE score > 100"))
    conn.execute(sa.text("UPDATE interview_turns SET status = 'pending' WHERE status IS NULL OR status NOT IN ('answered', 'pending', 'skipped')"))
    conn.execute(sa.text("UPDATE evaluation_results SET cv_score = 0 WHERE cv_score < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET cv_score = 100 WHERE cv_score > 100"))
    conn.execute(sa.text("UPDATE evaluation_results SET rubric_score = 0 WHERE rubric_score < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET rubric_score = 100 WHERE rubric_score > 100"))
    conn.execute(sa.text("UPDATE evaluation_results SET human_integrity_score = 0 WHERE human_integrity_score < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET human_integrity_score = 100 WHERE human_integrity_score > 100"))
    conn.execute(sa.text("UPDATE evaluation_results SET rubric_coverage_pct = 0 WHERE rubric_coverage_pct < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET rubric_coverage_pct = 100 WHERE rubric_coverage_pct > 100"))
    conn.execute(sa.text("UPDATE evaluation_results SET final_score = 0 WHERE final_score < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET final_score = 100 WHERE final_score > 100"))
    conn.execute(sa.text("UPDATE evaluation_results SET composite_score = 0 WHERE composite_score < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET composite_score = 100 WHERE composite_score > 100"))
    conn.execute(sa.text("UPDATE evaluation_results SET fraud_score = 0 WHERE fraud_score < 0"))
    conn.execute(sa.text("UPDATE evaluation_results SET fraud_score = 100 WHERE fraud_score > 100"))
    conn.execute(sa.text("UPDATE rubric_scoring_details SET score = 0 WHERE score < 0"))
    conn.execute(sa.text("UPDATE rubric_scoring_details SET score = 100 WHERE score > 100"))
    conn.execute(sa.text("UPDATE rubric_scoring_details SET max_score = 0 WHERE max_score IS NOT NULL AND max_score < 0"))
    conn.execute(sa.text("UPDATE rubric_scoring_details SET weight = 1 WHERE weight IS NOT NULL AND weight < 0"))
    conn.execute(sa.text("UPDATE rubrics SET passing_score = 0 WHERE passing_score IS NOT NULL AND passing_score < 0"))
    conn.execute(sa.text("UPDATE rubrics SET max_score = 0 WHERE max_score IS NOT NULL AND max_score < 0"))
    conn.execute(sa.text("UPDATE rubrics SET weight = 1 WHERE weight IS NOT NULL AND weight < 0"))

    op.create_check_constraint(
        "ck_interview_turn_owner_xor",
        "interview_turns",
        "((application_id IS NULL AND evaluation_session_id IS NOT NULL) OR "
        "(application_id IS NOT NULL AND evaluation_session_id IS NULL))",
    )
    op.create_check_constraint(
        "ck_interview_turn_status",
        "interview_turns",
        "status IS NULL OR status IN ('answered', 'pending', 'skipped')",
    )
    op.create_check_constraint(
        "ck_interview_turn_score_range",
        "interview_turns",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_check_constraint(
        "ck_eval_session_status",
        "evaluation_sessions",
        "status IS NULL OR status IN ('created', 'in_progress', 'paused', 'completed', 'expired', 'failed', 'running', 'pending', 'flagged', 'needs_review')",
    )
    op.create_check_constraint(
        "ck_eval_session_interview_state",
        "evaluation_sessions",
        "interview_state IS NULL OR interview_state IN ('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused')",
    )
    op.create_check_constraint(
        "ck_eval_result_score_range",
        "evaluation_results",
        "cv_score IS NULL OR (cv_score >= 0 AND cv_score <= 100)",
    )
    op.create_check_constraint(
        "ck_eval_result_rubric_score_range",
        "evaluation_results",
        "rubric_score IS NULL OR (rubric_score >= 0 AND rubric_score <= 100)",
    )
    op.create_check_constraint(
        "ck_eval_result_human_score_range",
        "evaluation_results",
        "human_integrity_score IS NULL OR (human_integrity_score >= 0 AND human_integrity_score <= 100)",
    )
    op.create_check_constraint(
        "ck_eval_result_coverage_range",
        "evaluation_results",
        "rubric_coverage_pct IS NULL OR (rubric_coverage_pct >= 0 AND rubric_coverage_pct <= 100)",
    )
    op.create_check_constraint(
        "ck_eval_result_final_score_range",
        "evaluation_results",
        "final_score >= 0 AND final_score <= 100",
    )
    op.create_check_constraint(
        "ck_eval_result_composite_score_range",
        "evaluation_results",
        "composite_score IS NULL OR (composite_score >= 0 AND composite_score <= 100)",
    )
    op.create_check_constraint(
        "ck_eval_result_fraud_score_range",
        "evaluation_results",
        "fraud_score IS NULL OR (fraud_score >= 0 AND fraud_score <= 100)",
    )
    op.create_check_constraint(
        "ck_rubric_scoring_detail_score_range",
        "rubric_scoring_details",
        "score >= 0 AND score <= 100",
    )
    op.create_check_constraint(
        "ck_rubric_scoring_detail_max_score_non_negative",
        "rubric_scoring_details",
        "max_score IS NULL OR max_score >= 0",
    )
    op.create_check_constraint(
        "ck_rubric_scoring_detail_weight_non_negative",
        "rubric_scoring_details",
        "weight IS NULL OR weight >= 0",
    )
    op.create_check_constraint(
        "ck_rubric_passing_score_non_negative",
        "rubrics",
        "passing_score IS NULL OR passing_score >= 0",
    )
    op.create_check_constraint(
        "ck_rubric_max_score_non_negative",
        "rubrics",
        "max_score IS NULL OR max_score >= 0",
    )
    op.create_check_constraint(
        "ck_rubric_weight_non_negative",
        "rubrics",
        "weight IS NULL OR weight >= 0",
    )
    op.create_check_constraint(
        "ck_application_analysis_score_range",
        "applications",
        "analysis_score IS NULL OR (analysis_score >= 0 AND analysis_score <= 100)",
    )
    op.create_check_constraint(
        "ck_application_interview_state",
        "applications",
        "interview_state IS NULL OR interview_state IN ('not_started', 'in_progress', 'completed', 'expired', 'flagged', 'paused')",
    )
    op.create_check_constraint(
        "ck_application_evaluation_state",
        "applications",
        "evaluation_state IS NULL OR evaluation_state IN ('pending', 'running', 'completed', 'failed', 'flagged', 'expired', 'override')",
    )
    op.create_check_constraint(
        "ck_application_status",
        "applications",
        "status IS NULL OR status IN ('pending', 'screening', 'interviewing', 'offer', 'rejected', 'analyzed', 'failed', 'applied', 'invited', 'active', 'analyzing', 'analysis_failed')",
    )

    for tmp_name in ("tmp_cby_batch", "tmp_cby_job", "tmp_cby_applicant"):
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {tmp_name}"))
    conn.execute(sa.text("DROP TABLE IF EXISTS tmp_latest_application_by_user"))


def downgrade() -> None:
    conn = op.get_bind()

    _drop_constraint("ck_application_analysis_score_range", "applications", "check")
    _drop_constraint("ck_application_interview_state", "applications", "check")
    _drop_constraint("ck_application_evaluation_state", "applications", "check")
    _drop_constraint("ck_application_status", "applications", "check")
    _drop_constraint("ck_rubric_scoring_detail_weight_non_negative", "rubric_scoring_details", "check")
    _drop_constraint("ck_rubric_scoring_detail_max_score_non_negative", "rubric_scoring_details", "check")
    _drop_constraint("ck_rubric_scoring_detail_score_range", "rubric_scoring_details", "check")
    _drop_constraint("ck_rubric_weight_non_negative", "rubrics", "check")
    _drop_constraint("ck_rubric_max_score_non_negative", "rubrics", "check")
    _drop_constraint("ck_rubric_passing_score_non_negative", "rubrics", "check")
    _drop_constraint("ck_eval_result_fraud_score_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_result_composite_score_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_result_final_score_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_result_coverage_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_result_human_score_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_result_rubric_score_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_result_score_range", "evaluation_results", "check")
    _drop_constraint("ck_eval_session_interview_state", "evaluation_sessions", "check")
    _drop_constraint("ck_eval_session_status", "evaluation_sessions", "check")
    _drop_constraint("ck_interview_turn_score_range", "interview_turns", "check")
    _drop_constraint("ck_interview_turn_status", "interview_turns", "check")
    _drop_constraint("ck_interview_turn_owner_xor", "interview_turns", "check")

    _drop_index("uq_turns_eval_number", "interview_turns")
    _drop_index("idx_it_company", "interview_turns")
    _drop_index("idx_es_app_status", "evaluation_sessions")
    _drop_index("idx_es_company", "evaluation_sessions")
    _drop_index("idx_applications_company", "applications")

    _drop_constraint("fk_turn_eval_session", "interview_turns", "foreignkey")
    _drop_constraint("fk_interview_turns_company", "interview_turns", "foreignkey")
    _drop_constraint("fk_es_application", "evaluation_sessions", "foreignkey")
    _drop_constraint("fk_evaluation_sessions_company", "evaluation_sessions", "foreignkey")
    _drop_constraint("fk_applications_company", "applications", "foreignkey")

    op.alter_column("applications", "company_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("evaluation_sessions", "application_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("evaluation_sessions", "company_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("interview_turns", "evaluation_session_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("interview_turns", "company_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("interview_turns", "application_id", existing_type=sa.Integer(), nullable=False)

    if not _has_unique(conn, "interview_turns", "uq_turns_app_number"):
        op.create_index("uq_turns_app_number", "interview_turns", ["application_id", "turn_number"], unique=True)
