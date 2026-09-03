"""add all rubric engine tables (Phase 1 + Phase 2)

Uses IF NOT EXISTS to safely handle already-created tables.

Phase 1: job_rubrics, extracted_skills, rubric_scoring_results, interview_rubric_summaries
Plus: rubric_id/rubric_version/scoring_model/rubric_seniority on applications
Phase 2: rubric_drafts, rubric_nodes, ab_test_experiments, ab_test_assignments, scoring_variant_results

Revision ID: 0ce7416aa096
Revises: 5f6a7b8c9d0e
Create Date: 2026-06-04 15:06:27.106576
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = '0ce7416aa096'
down_revision: Union[str, Sequence[str], None] = '5f6a7b8c9d0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _if_not_exists(create_sql: str, table: str) -> str:
    return f"CREATE TABLE IF NOT EXISTS `{table}` (\n{create_sql}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"


def upgrade() -> None:
    # ---- PHASE 1: Core rubric engine tables ----

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        job_id INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        is_current TINYINT(1) NOT NULL DEFAULT 1,
        seniority VARCHAR(20) NOT NULL DEFAULT 'mid',
        rubric_json JSON NOT NULL,
        created_by INTEGER,
        created_at DATETIME,
        superseded_at DATETIME,
        PRIMARY KEY (id),
        UNIQUE KEY uq_job_rubric_version (job_id, version),
        KEY idx_job_rubrics_current (job_id, is_current),
        CONSTRAINT fk_jr_job FOREIGN KEY (job_id) REFERENCES jobs(id),
        CONSTRAINT fk_jr_creator FOREIGN KEY (created_by) REFERENCES users(id)
    """, 'job_rubrics'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        interview_id INTEGER NOT NULL,
        answer_id INTEGER NOT NULL,
        skill_name VARCHAR(100) NOT NULL,
        skill_id VARCHAR(64),
        evidence_sentences JSON,
        evidence_quality VARCHAR(10) NOT NULL DEFAULT 'weak',
        quality_reason TEXT,
        extraction_version VARCHAR(20) NOT NULL DEFAULT 'rubric-v1',
        created_at DATETIME,
        PRIMARY KEY (id),
        KEY idx_extracted_skills_answer (answer_id),
        KEY idx_extracted_skills_interview (interview_id),
        CONSTRAINT fk_es_app FOREIGN KEY (interview_id) REFERENCES applications(id)
    """, 'extracted_skills'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        interview_id INTEGER NOT NULL,
        answer_id INTEGER NOT NULL,
        rubric_id INTEGER NOT NULL,
        skill_name VARCHAR(100) NOT NULL,
        skill_id VARCHAR(64),
        base_score INTEGER NOT NULL,
        quality_multiplier FLOAT NOT NULL,
        final_score INTEGER NOT NULL,
        confidence_lower INTEGER NOT NULL,
        confidence_upper INTEGER NOT NULL,
        evidence_sentences JSON,
        matched_keywords JSON,
        matched_level_description TEXT,
        missing_competencies JSON,
        explanation TEXT NOT NULL,
        computed_at DATETIME,
        PRIMARY KEY (id),
        KEY idx_rubric_score_answer (answer_id),
        KEY idx_rubric_score_interview (interview_id),
        CONSTRAINT fk_rs_app FOREIGN KEY (interview_id) REFERENCES applications(id),
        CONSTRAINT fk_rs_rubric FOREIGN KEY (rubric_id) REFERENCES job_rubrics(id)
    """, 'rubric_scoring_results'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        interview_id INTEGER NOT NULL,
        rubric_id INTEGER NOT NULL,
        rubric_version INTEGER NOT NULL,
        overall_score INTEGER NOT NULL,
        confidence_lower INTEGER NOT NULL,
        confidence_upper INTEGER NOT NULL,
        category_scores JSON,
        skill_scores JSON,
        gaps JSON,
        computed_at DATETIME,
        num_answers_scored INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (id),
        UNIQUE KEY idx_rubric_summary_interview (interview_id),
        CONSTRAINT fk_irs_app FOREIGN KEY (interview_id) REFERENCES applications(id),
        CONSTRAINT fk_irs_rubric FOREIGN KEY (rubric_id) REFERENCES job_rubrics(id)
    """, 'interview_rubric_summaries'))

    # Add rubric columns to applications table (safely)
    for col_sql in [
        "ALTER TABLE applications ADD COLUMN rubric_id INTEGER AFTER evaluation_state",
        "ALTER TABLE applications ADD COLUMN rubric_version INTEGER DEFAULT 0 AFTER rubric_id",
        "ALTER TABLE applications ADD COLUMN scoring_model VARCHAR(20) DEFAULT 'legacy' AFTER rubric_version",
        "ALTER TABLE applications ADD COLUMN rubric_seniority VARCHAR(20) DEFAULT 'mid' AFTER scoring_model",
        "ALTER TABLE applications ADD CONSTRAINT fk_app_rubric FOREIGN KEY (rubric_id) REFERENCES job_rubrics(id)",
    ]:
        try:
            op.execute(col_sql)
        except Exception:
            pass  # Column may already exist

    # ---- PHASE 2: Product interface tables ----

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name VARCHAR(200) NOT NULL DEFAULT 'Untitled Draft',
        rubric_json JSON NOT NULL,
        base_version INTEGER,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        created_at DATETIME,
        updated_at DATETIME,
        PRIMARY KEY (id),
        KEY idx_rubric_draft_user (user_id),
        KEY idx_rubric_draft_job (job_id),
        CONSTRAINT fk_rd_job FOREIGN KEY (job_id) REFERENCES jobs(id),
        CONSTRAINT fk_rd_user FOREIGN KEY (user_id) REFERENCES users(id)
    """, 'rubric_drafts'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        job_id INTEGER NOT NULL,
        rubric_version_id INTEGER,
        node_type VARCHAR(20) NOT NULL,
        parent_id INTEGER,
        sort_order INTEGER NOT NULL DEFAULT 0,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        weight FLOAT NOT NULL DEFAULT 1.0,
        skill_levels JSON,
        keywords JSON,
        is_required TINYINT(1) NOT NULL DEFAULT 0,
        created_at DATETIME,
        PRIMARY KEY (id),
        KEY idx_rubric_node_job (job_id),
        KEY idx_rubric_node_version (rubric_version_id),
        KEY idx_rubric_node_parent (parent_id),
        CONSTRAINT fk_rn_job FOREIGN KEY (job_id) REFERENCES jobs(id),
        CONSTRAINT fk_rn_version FOREIGN KEY (rubric_version_id) REFERENCES job_rubrics(id),
        CONSTRAINT fk_rn_parent FOREIGN KEY (parent_id) REFERENCES rubric_nodes(id)
    """, 'rubric_nodes'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        job_id INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        variant_a_json JSON NOT NULL,
        variant_b_json JSON NOT NULL,
        traffic_split INTEGER NOT NULL DEFAULT 50,
        status VARCHAR(20) NOT NULL DEFAULT 'draft',
        min_sample_size INTEGER NOT NULL DEFAULT 50,
        current_sample_size INTEGER NOT NULL DEFAULT 0,
        started_at DATETIME,
        ended_at DATETIME,
        created_at DATETIME,
        PRIMARY KEY (id),
        KEY idx_ab_test_job (job_id),
        CONSTRAINT fk_abt_job FOREIGN KEY (job_id) REFERENCES jobs(id),
        CONSTRAINT fk_abt_creator FOREIGN KEY (created_by) REFERENCES users(id)
    """, 'ab_test_experiments'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        experiment_id INTEGER NOT NULL,
        user_id INTEGER,
        candidate_id INTEGER,
        variant VARCHAR(10) NOT NULL,
        assigned_at DATETIME,
        PRIMARY KEY (id),
        UNIQUE KEY idx_ab_assign_exp_user (experiment_id, user_id),
        UNIQUE KEY idx_ab_assign_exp_candidate (experiment_id, candidate_id),
        CONSTRAINT fk_aba_exp FOREIGN KEY (experiment_id) REFERENCES ab_test_experiments(id),
        CONSTRAINT fk_aba_user FOREIGN KEY (user_id) REFERENCES users(id),
        CONSTRAINT fk_aba_cand FOREIGN KEY (candidate_id) REFERENCES applications(id)
    """, 'ab_test_assignments'))

    op.execute(_if_not_exists("""
        id INTEGER NOT NULL AUTO_INCREMENT,
        experiment_id INTEGER NOT NULL,
        candidate_id INTEGER NOT NULL,
        variant_a_score INTEGER NOT NULL,
        variant_b_score INTEGER NOT NULL,
        variant_a_json JSON,
        variant_b_json JSON,
        score_delta INTEGER,
        recruiter_preference VARCHAR(10),
        hiring_outcome VARCHAR(20),
        created_at DATETIME,
        PRIMARY KEY (id),
        KEY idx_svr_experiment (experiment_id),
        KEY idx_svr_candidate (candidate_id),
        CONSTRAINT fk_svr_exp FOREIGN KEY (experiment_id) REFERENCES ab_test_experiments(id),
        CONSTRAINT fk_svr_cand FOREIGN KEY (candidate_id) REFERENCES applications(id)
    """, 'scoring_variant_results'))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scoring_variant_results")
    op.execute("DROP TABLE IF EXISTS ab_test_assignments")
    op.execute("DROP TABLE IF EXISTS ab_test_experiments")
    op.execute("DROP TABLE IF EXISTS rubric_nodes")
    op.execute("DROP TABLE IF EXISTS rubric_drafts")
    op.execute("DROP TABLE IF EXISTS interview_rubric_summaries")
    op.execute("DROP TABLE IF EXISTS rubric_scoring_results")
    op.execute("DROP TABLE IF EXISTS extracted_skills")
    op.execute("DROP TABLE IF EXISTS job_rubrics")
