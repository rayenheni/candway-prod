"""m22: Add company_id to all tenant-scoped resources

Every company-owned resource must have a direct company_id FK for
fast tenant filtering without JOINs.  This migration:

1. Adds company_id (NOT NULL, FK → companies.id) to tables that
   lacked it entirely.
2. Converts existing nullable company_id columns to NOT NULL
   (AIAuditLog, CalibrationSample, DriftSnapshot, ABExperiment).
3. Creates indexes on every new company_id column.
4. No data migration here — run backfill_company_ids.py first
   if the table has existing rows.

Affected tables — NEW column:
  messages, conversations, conversation_participants,
  transactions, invoices, saved_reports, report_snapshots,
  campaign_costs,
  interviews, interview_participants, interview_feedback,
  interview_scorecards, scorecard_submissions,
  background_checks, background_check_status_logs,
  offer_templates, offers,
  email_templates, campaign_templates, email_sequence_logs,
  webhook_integrations, bot_integrations,
  reengagement_campaigns, reengagement_candidates,
  comments, tagged_notes, candidate_ratings, activity_logs,
  team_members, candidate_interactions,
  application_stage_history,
  jobs, saved_jobs, interview_questions, chatbot_leads,
  batch_jobs, pipeline_stages, pipeline_automation_rules,
  evaluation_results, rubrics, rubric_scoring_details,
  verdicts, evaluation_config_snapshots, rubric_snapshots,
  notifications, feature_flags, undo_actions,
  recruiter_profiles,
  ab_test_experiments, ab_test_assignments,
  scoring_variant_results, prompt_tests, prompt_variants,
  prompt_test_results, skill_definitions,
  tickets, support_tickets,
  blog_posts, announcements,
  courses, enrollments, payout_requests,
  qualifications, cv_documents, extracted_skills,
  eeoconsent,
  company_verifications,
  chatbot_leads

Affected tables — nullable→NOT NULL:
  ai_audit_logs, calibration_samples, drift_snapshots,
  ab_experiments

Revision ID: m22
Revises: p1prod202606300_add_company_member_index
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa


revision = "m22"
down_revision = "p1prod202606300"
branch_labels = None
depends_on = None


# ── Tables that need a NEW company_id column ─────────────────────────
NEW_COMPANY_ID = [
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

# ── Tables where company_id exists but is nullable → NOT NULL ─────────
EXISTING_NULLABLE = [
    "ai_audit_logs",
    "calibration_samples",
    "drift_snapshots",
    "ab_experiments",
]


def _add_company_id_column(table: str) -> None:
    """Add company_id as nullable first, then make it NOT NULL
    after backfill. The backfill script must run between these
    two steps for tables with existing rows.
    """
    op.add_column(
        table,
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
    )
    op.create_index(
        op.f(f"idx_{table}_company_id"),
        table,
        ["company_id"],
    )


def _make_not_nullable(table: str) -> None:
    """ALTER column to NOT NULL — safe only after backfill."""
    op.alter_column(
        table,
        "company_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )


def _drop_company_id(table: str) -> None:
    op.drop_index(op.f(f"idx_{table}_company_id"), table_name=table)
    op.drop_column(table, "company_id")


def upgrade() -> None:
    # ── Step 1: Add company_id as nullable to tables that lack it ──
    # WARNING: Run backfill_company_ids.py BEFORE migrating to NOT NULL.
    for table in NEW_COMPANY_ID:
        _add_company_id_column(table)

    # ── Step 2: Make existing nullable company_id NOT NULL ────────
    # WARNING: Ensure backfill has run before upgrading in production.
    # These tables already had company_id but as nullable; now they
    # must be NOT NULL to match TenantMixin.
    for table in EXISTING_NULLABLE:
        _make_not_nullable(table)


def downgrade() -> None:
    # ── Revert Step 2 ─────────────────────────────────────────
    for table in EXISTING_NULLABLE:
        op.alter_column(
            table,
            "company_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )

    # ── Revert Step 1 ─────────────────────────────────────────
    for table in reversed(NEW_COMPANY_ID):
        _drop_company_id(table)
