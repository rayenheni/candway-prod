"""M002: Backfill new tables from old deprecated tables.

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-06-11

One-time data migration — populates evaluation_sessions, evaluation_results,
recommended_verdicts, rubrics, rubric_scoring_details, and profile tables
from the old deprecated tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 0. Make rubric_id + rubric_version nullable in evaluation_results
    op.alter_column("evaluation_results", "rubric_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("evaluation_results", "rubric_version", existing_type=sa.Integer(), nullable=True)

    # 1. Profile tables from users
    conn.execute(text("""
        INSERT INTO candidate_profiles (user_id, headline, bio, skills,
            languages, availability, work_preference, salary_expectation_min,
            salary_expectation_max, linkedin_url, github_url, portfolio_url,
            avatar_url, profile_views, profile_views_growth,
            candidate_cv_uploads_this_month, candidate_ai_analyses_this_month,
            candidate_pdf_downloads_this_month, candidate_usage_reset_date)
        SELECT id, headline, bio, skills, languages, availability,
            work_preference, salary_expectation_min, salary_expectation_max,
            linkedin_url, github_url, portfolio_url, avatar_url,
            COALESCE(profile_views, 0), COALESCE(profile_views_growth, 12.0),
            COALESCE(candidate_cv_uploads_this_month, 0),
            COALESCE(candidate_ai_analyses_this_month, 0),
            COALESCE(candidate_pdf_downloads_this_month, 0),
            candidate_usage_reset_date
        FROM users WHERE role = 'candidate' AND deleted_at IS NULL
    """))

    conn.execute(text("""
        INSERT INTO recruiter_profiles (user_id, company_name,
            company_description, company_logo_url, smtp_host, smtp_port,
            smtp_user, smtp_password, usage_jobs, usage_cvs,
            usage_ai_interviews, usage_reset_date, email_settings,
            linkedin_settings)
        SELECT id, company_name, company_description, company_logo_url,
            smtp_host, smtp_port, smtp_user, COALESCE(smtp_password, ''),
            COALESCE(usage_jobs, 0), COALESCE(usage_cvs, 0),
            COALESCE(usage_ai_interviews, 0), usage_reset_date,
            email_settings, linkedin_settings
        FROM users WHERE role = 'recruiter' AND deleted_at IS NULL
    """))

    conn.execute(text("""
        INSERT INTO admin_profiles (user_id, permissions, is_super_admin)
        SELECT id, admin_permissions, COALESCE(is_super_admin, FALSE)
        FROM users WHERE role = 'admin' AND deleted_at IS NULL
    """))

    # 2. Rubrics from job_rubrics
    conn.execute(text("""
        INSERT INTO rubrics (id, job_id, version, title, description,
            passing_score, max_score, weight, criteria_json, skill_weights,
            complexity, created_by, is_active, created_at, updated_at)
        SELECT id, job_id, COALESCE(version, 1),
            COALESCE(name, ''), COALESCE(rubric_json, '{}'),
            0.0, 100.0, 1.0,
            rubric_json, NULL,
            COALESCE(seniority, 'intermediate'),
            created_by,
            CASE WHEN is_current = 1 THEN 1 ELSE 0 END,
            created_at, created_at
        FROM job_rubrics
    """))

    # 3. Evaluation sessions from AIInterviewSession
    conn.execute(text("""
        INSERT INTO evaluation_sessions (
            version_id, application_id, candidate_id, context_type,
            context_id, status, language, source,
            interview_state, interview_progress, interview_time_left,
            interview_last_saved, interview_log, interview_questions,
            generated_questions, proctoring_violations, video_file_path,
            video_transcript, video_analysis_json, interview_reset_count,
            interview_last_reset_at, interview_turn_seq,
            calibration_json, calibration_score, calibration_verified_skills,
            rubric_id, rubric_version,
            started_at, completed_at, created_at, updated_at)
        SELECT 1, application_id, NULL, 'job',
            NULL, 'created', 'English', NULL,
            interview_state, interview_progress, interview_time_left,
            interview_last_saved, interview_log, interview_questions,
            generated_questions, proctoring_violations, video_file_path,
            video_transcript, video_analysis_json, interview_reset_count,
            interview_last_reset_at, interview_turn_seq,
            calibration_json, calibration_score, calibration_verified_skills,
            rubric_id, rubric_version,
            started_at, completed_at, created_at, updated_at
        FROM ai_interview_sessions
    """))

    # 4. Evaluation sessions from EvaluationState (no AIInterviewSession)
    conn.execute(text("""
        INSERT INTO evaluation_sessions (
            version_id, application_id, candidate_id, context_type,
            context_id, status, language, source,
            started_at, completed_at, created_at, updated_at)
        SELECT 1, e.application_id, NULL, 'job', NULL,
            COALESCE(e.evaluation_state, 'pending'), 'English',
            e.evaluation_source,
            COALESCE(e.evaluation_started_at, e.created_at),
            e.evaluation_completed_at,
            e.created_at, e.updated_at
        FROM evaluation_states e
        WHERE NOT EXISTS (
            SELECT 1 FROM evaluation_sessions es
            WHERE es.application_id = e.application_id
        )
    """))

    # 5. Evaluation sessions for apps with scores but no session
    conn.execute(text("""
        INSERT INTO evaluation_sessions (
            version_id, application_id, candidate_id, context_type,
            context_id, status, language, source,
            created_at, updated_at)
        SELECT 1, a.application_id, NULL, 'job', NULL,
            'completed', 'English', NULL,
            COALESCE(a.computed_at, NOW()), COALESCE(a.computed_at, NOW())
        FROM application_scores a
        WHERE NOT EXISTS (
            SELECT 1 FROM evaluation_sessions es
            WHERE es.application_id = a.application_id
        )
    """))

    # 6. Evaluation results — use NULL for unknown rubric_id
    conn.execute(text("""
        INSERT INTO evaluation_results (
            version_id, evaluation_session_id, rubric_id, rubric_version,
            cv_score, rubric_score, human_integrity_score,
            rubric_coverage_pct, final_score, composite_score,
            confidence_lower, confidence_upper, score_breakdown,
            fraud_score, fraud_reported_by, fraud_reported_at,
            scoring_model, needs_review, needs_review_reason,
            computed_at, computed_by, created_at, updated_at)
        SELECT
            1, es.id,
            NULLIF(app.rubric_id, 0),
            sc.rubric_version,
            sc.cv_score, sc.rubric_score,
            COALESCE(sc.human_integrity_score, 100.0),
            sc.rubric_coverage_pct,
            COALESCE(irs.overall_score, sc.final_score),
            sc.composite_score,
            irs.confidence_lower, irs.confidence_upper,
            sc.score_breakdown,
            COALESCE(sc.fraud_score, 0.0),
            sc.fraud_reported_by, sc.fraud_reported_at,
            COALESCE(sc.scoring_model, 'rubric'),
            COALESCE(sc.needs_review, FALSE), sc.needs_review_reason,
            sc.computed_at, sc.computed_by,
            sc.computed_at, sc.computed_at
        FROM application_scores sc
        INNER JOIN evaluation_sessions es ON es.application_id = sc.application_id
        LEFT JOIN applications app ON app.id = sc.application_id
        LEFT JOIN interview_rubric_summaries irs
            ON irs.application_id = sc.application_id
    """))

    # 7. Recommended verdicts from ApplicationScore.verdict
    conn.execute(text("""
        INSERT INTO recommended_verdicts (
            evaluation_session_id, decision, confidence, reasoning, computed_at)
        SELECT es.id, sc.verdict, NULL, NULL, sc.computed_at
        FROM application_scores sc
        INNER JOIN evaluation_sessions es ON es.application_id = sc.application_id
        WHERE sc.verdict IS NOT NULL AND sc.verdict != ''
    """))

    # 8. Rubric scoring details (0 rows in source, no-op)
    conn.execute(text("""
        INSERT INTO rubric_scoring_details (
            evaluation_result_id, criterion_name, criterion_key,
            question, answer, score, weight, max_score, feedback, source)
        SELECT er.id,
            COALESCE(rsr.skill_name, 'unknown'), rsr.skill_id,
            NULL, NULL,
            rsr.base_score, COALESCE(rsr.quality_multiplier, 1.0),
            100.0, rsr.explanation, 'rubric'
        FROM rubric_scoring_results rsr
        INNER JOIN evaluation_sessions es ON es.application_id = rsr.application_id
        INNER JOIN evaluation_results er ON er.evaluation_session_id = es.id
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("DELETE FROM rubric_scoring_details"))
    conn.execute(text("DELETE FROM recommended_verdicts"))
    conn.execute(text("DELETE FROM evaluation_results"))
    conn.execute(text("DELETE FROM evaluation_sessions"))
    conn.execute(text("DELETE FROM rubrics"))
    conn.execute(text("DELETE FROM candidate_profiles"))
    conn.execute(text("DELETE FROM recruiter_profiles"))
    conn.execute(text("DELETE FROM admin_profiles"))
    op.alter_column("evaluation_results", "rubric_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("evaluation_results", "rubric_version", existing_type=sa.Integer(), nullable=False)
