"""m22b: Enforce company_id NOT NULL after data backfill

Run AFTER backfill_company_ids.py has populated all NULL company_id rows.

1. Makes all company_id columns NOT NULL.
2. Drops any remaining rows with NULL company_id (safety net).

Revision ID: m22b
Revises: m22
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa


revision = "m22b"
down_revision = "m22"
branch_labels = None
depends_on = None


# Same table list as m22
TABLES = [
    # ATS — Messaging
    "messages",
    "conversations",
    "conversation_participants",

    # ATS — Interview
    "interviews",
    "interview_participants",
    "interview_feedback",
    "interview_scorecards",
    "scorecard_submissions",

    # ATS — Offer
    "offer_templates",
    "offers",
    "background_checks",
    "background_check_status_logs",

    # ATS — Pipeline
    "comments",
    "tagged_notes",
    "candidate_ratings",
    "activity_logs",
    "team_members",
    "candidate_interactions",
    "application_stage_history",

    # ATS — Campaign
    "webhook_integrations",
    "bot_integrations",
    "campaign_templates",
    "email_templates",
    "email_sequence_logs",
    "reengagement_campaigns",
    "reengagement_candidates",

    # ATS — Application
    "qualifications",
    "cv_documents",
    "extracted_skills",
    "eeo_consent",

    # Core — Job
    "jobs",
    "saved_jobs",
    "interview_questions",
    "chatbot_leads",

    # Core — Batch
    "batch_jobs",
    "pipeline_stages",
    "pipeline_automation_rules",

    # Evaluation
    "evaluation_results",
    "rubrics",
    "rubric_scoring_details",
    "verdicts",
    "evaluation_config_snapshots",
    "rubric_snapshots",
    "ab_test_experiments",
    "ab_test_assignments",
    "scoring_variant_results",
    "prompt_tests",
    "prompt_variants",
    "prompt_test_results",
    "skill_definitions",

    # Finance
    "transactions",
    "invoices",
    "saved_reports",
    "report_snapshots",
    "campaign_costs",

    # Foundation — User
    "notifications",
    "feature_flags",
    "undo_actions",

    # Foundation — System
    "tickets",
    "support_tickets",

    # Foundation — CMS
    "blog_posts",
    "announcements",

    # Foundation — Company
    "company_verifications",

    # Foundation — Profile
    "recruiter_profiles",

    # LMS
    "courses",
    "enrollments",
    "payout_requests",
]


def upgrade() -> None:
    # Delete rows that still have NULL company_id (safety net)
    for table in TABLES:
        op.execute(
            f"DELETE FROM {table} WHERE company_id IS NULL"
        )

    # Make every company_id NOT NULL
    for table in TABLES:
        op.alter_column(
            table,
            "company_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(
            table,
            "company_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )
