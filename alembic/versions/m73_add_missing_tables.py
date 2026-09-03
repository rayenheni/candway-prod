"""Add missing tables that exist in SQLAlchemy models.

Revision ID: m73
Revises: m72
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m73"
down_revision: Union[str, None] = "m72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    # ---------------------------------------------------------------
    # 1. conversations
    # ---------------------------------------------------------------
    if "conversations" not in existing:
        op.create_table(
            "conversations",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("subject", sa.String(255), nullable=True),
            sa.Column("type", sa.String(20), nullable=True, server_default="direct"),
            sa.Column("last_message_at", sa.DateTime(), nullable=True),
            sa.Column("last_message_preview", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_conversations_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("ix_conversations_id", "conversations", ["id"])
        op.create_index(
            "ix_conversations_company_id",
            "conversations",
            ["company_id"],
        )
        op.create_index(
            "ix_conversations_last_message_at",
            "conversations",
            ["last_message_at"],
        )
        op.create_index(
            "idx_conv_updated",
            "conversations",
            ["last_message_at"],
        )

    # ---------------------------------------------------------------
    # 2. conversation_participants
    # ---------------------------------------------------------------
    if "conversation_participants" not in existing:
        op.create_table(
            "conversation_participants",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(20), nullable=True, server_default="member"),
            sa.Column("last_read_at", sa.DateTime(), nullable=True),
            sa.Column("is_muted", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("left_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["conversation_id"], ["conversations.id"],
                name="fk_cp_conversation",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_cp_user",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_cp_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index(
            "ix_conversation_participants_id",
            "conversation_participants",
            ["id"],
        )
        op.create_index(
            "ix_conversation_participants_user_id",
            "conversation_participants",
            ["user_id"],
        )
        op.create_index(
            "ix_conversation_participants_conversation_id",
            "conversation_participants",
            ["conversation_id"],
        )
        op.create_index(
            "ix_conversation_participants_company_id",
            "conversation_participants",
            ["company_id"],
        )
        op.create_index(
            "idx_cp_user_conv",
            "conversation_participants",
            ["user_id", "conversation_id"],
        )

    # ---------------------------------------------------------------
    # 3. messages
    # ---------------------------------------------------------------
    if "messages" not in existing:
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("sender_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_type", sa.String(20), nullable=True, server_default="text"),
            sa.Column("attachments", sa.Text(), nullable=True),
            sa.Column("reply_to_id", sa.Integer(), nullable=True),
            sa.Column("edited_at", sa.DateTime(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["conversation_id"], ["conversations.id"],
                name="fk_messages_conversation",
            ),
            sa.ForeignKeyConstraint(
                ["sender_id"], ["users.id"],
                name="fk_messages_sender",
            ),
            sa.ForeignKeyConstraint(
                ["reply_to_id"], ["messages.id"],
                name="fk_messages_reply_to",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_messages_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("ix_messages_id", "messages", ["id"])
        op.create_index("ix_messages_created_at", "messages", ["created_at"])
        op.create_index("ix_messages_company_id", "messages", ["company_id"])
        op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
        op.create_index(
            "ix_messages_conversation_id",
            "messages",
            ["conversation_id"],
        )
        op.create_index(
            "idx_msg_sender",
            "messages",
            ["sender_id"],
        )
        op.create_index(
            "idx_msg_conv",
            "messages",
            ["conversation_id", "created_at"],
        )

    # ---------------------------------------------------------------
    # 4. background_checks
    # ---------------------------------------------------------------
    if "background_checks" not in existing:
        op.create_table(
            "background_checks",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=True),
            sa.Column("offer_id", sa.Integer(), nullable=True),
            sa.Column("recruiter_id", sa.Integer(), nullable=True),
            sa.Column("provider", sa.String(50), nullable=True, server_default="checkr"),
            sa.Column("provider_candidate_id", sa.String(255), nullable=True),
            sa.Column("provider_report_id", sa.String(255), nullable=True),
            sa.Column("status", sa.String(50), nullable=True, server_default="pending"),
            sa.Column("verdict", sa.String(50), nullable=True),
            sa.Column("findings", sa.Text(), nullable=True),
            sa.Column("report_url", sa.String(500), nullable=True),
            sa.Column("candidate_notified_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["application_id"], ["applications.id"],
                name="fk_background_checks_application",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["offer_id"], ["offers.id"],
                name="fk_background_checks_offer",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["recruiter_id"], ["users.id"],
                name="fk_background_checks_recruiter",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_background_checks_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("idx_bg_app", "background_checks", ["application_id"])
        op.create_index("idx_bg_offer", "background_checks", ["offer_id"])
        op.create_index("idx_bg_recruiter", "background_checks", ["recruiter_id"])
        op.create_index("idx_bg_status", "background_checks", ["status"])
        op.create_index(
            "ix_background_checks_company_id",
            "background_checks",
            ["company_id"],
        )

    # ---------------------------------------------------------------
    # 5. background_check_status_logs
    # ---------------------------------------------------------------
    if "background_check_status_logs" not in existing:
        op.create_table(
            "background_check_status_logs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("background_check_id", sa.Integer(), nullable=False),
            sa.Column("from_status", sa.String(50), nullable=True),
            sa.Column("to_status", sa.String(50), nullable=False),
            sa.Column("changed_by", sa.Integer(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["background_check_id"], ["background_checks.id"],
                name="fk_bg_status_log_check",
            ),
            sa.ForeignKeyConstraint(
                ["changed_by"], ["users.id"],
                name="fk_bg_status_log_changed_by",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_bg_status_log_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index(
            "idx_bg_status_log_check",
            "background_check_status_logs",
            ["background_check_id"],
        )
        op.create_index(
            "ix_background_check_status_logs_company_id",
            "background_check_status_logs",
            ["company_id"],
        )

    # ---------------------------------------------------------------
    # 6. bot_integrations
    # ---------------------------------------------------------------
    if "bot_integrations" not in existing:
        op.create_table(
            "bot_integrations",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("recruiter_id", sa.Integer(), nullable=False),
            sa.Column("platform", sa.String(20), nullable=False),
            sa.Column("platform_user_id", sa.String(255), nullable=False),
            sa.Column("platform_team_id", sa.String(255), nullable=True),
            sa.Column("conversation_ref", sa.Text(), nullable=True),
            sa.Column("access_token", sa.String(500), nullable=True),
            sa.Column("refresh_token", sa.String(500), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["recruiter_id"], ["users.id"],
                name="fk_bot_integrations_recruiter",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_bot_integrations_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("ix_bot_integrations_id", "bot_integrations", ["id"])
        op.create_index(
            "idx_bot_platform",
            "bot_integrations",
            ["platform", "platform_user_id"],
        )
        op.create_index(
            "ix_bot_integrations_recruiter_id",
            "bot_integrations",
            ["recruiter_id"],
        )
        op.create_index(
            "ix_bot_integrations_company_id",
            "bot_integrations",
            ["company_id"],
        )
        op.create_index(
            "idx_bot_recruiter",
            "bot_integrations",
            ["recruiter_id"],
        )

    # ---------------------------------------------------------------
    # 7. eeo_consent
    # ---------------------------------------------------------------
    if "eeo_consent" not in existing:
        op.create_table(
            "eeo_consent",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=True),
            sa.Column("consent_given", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("gender", sa.String(50), nullable=True),
            sa.Column("race_ethnicity", sa.String(100), nullable=True),
            sa.Column("veteran_status", sa.String(50), nullable=True),
            sa.Column("disability_status", sa.String(50), nullable=True),
            sa.Column("age_group", sa.String(20), nullable=True),
            sa.Column("collected_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["application_id"], ["applications.id"],
                name="fk_eeo_consent_application",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_eeo_consent_company",
                ondelete="RESTRICT",
            ),
            sa.UniqueConstraint("application_id", name="uq_eeo_consent_application"),
        )
        op.create_index(
            "ix_eeo_consent_company_id",
            "eeo_consent",
            ["company_id"],
        )

    # ---------------------------------------------------------------
    # 8. email_sequence_logs
    # ---------------------------------------------------------------
    if "email_sequence_logs" not in existing:
        op.create_table(
            "email_sequence_logs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.Integer(), nullable=True),
            sa.Column("step_number", sa.Integer(), nullable=False),
            sa.Column("subject", sa.String(500), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("opened_at", sa.DateTime(), nullable=True),
            sa.Column("clicked_at", sa.DateTime(), nullable=True),
            sa.Column("unsubscribed_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["application_id"], ["applications.id"],
                name="fk_email_seq_application",
            ),
            sa.ForeignKeyConstraint(
                ["batch_id"], ["batch_jobs.id"],
                name="fk_email_seq_batch",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_email_seq_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("idx_email_seq_app", "email_sequence_logs", ["application_id"])
        op.create_index("idx_email_seq_batch", "email_sequence_logs", ["batch_id"])
        op.create_index(
            "ix_email_sequence_logs_company_id",
            "email_sequence_logs",
            ["company_id"],
        )
        op.create_index(
            "ix_email_sequence_logs_application_id",
            "email_sequence_logs",
            ["application_id"],
        )
        op.create_index("ix_email_sequence_logs_id", "email_sequence_logs", ["id"])

    # ---------------------------------------------------------------
    # 9. interview_questions
    # ---------------------------------------------------------------
    if "interview_questions" not in existing:
        op.create_table(
            "interview_questions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("type", sa.String(50), nullable=True, server_default="technical"),
            sa.Column("difficulty", sa.String(20), nullable=True, server_default="medium"),
            sa.Column("skill_focus", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["job_id"], ["jobs.id"],
                name="fk_interview_questions_job",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_interview_questions_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("ix_interview_questions_id", "interview_questions", ["id"])
        op.create_index("ix_interview_questions_job_id", "interview_questions", ["job_id"])
        op.create_index(
            "ix_interview_questions_company_id",
            "interview_questions",
            ["company_id"],
        )
        op.create_index("idx_iq_job", "interview_questions", ["job_id"])

    # ---------------------------------------------------------------
    # 10. notification_preferences
    # ---------------------------------------------------------------
    if "notification_preferences" not in existing:
        op.create_table(
            "notification_preferences",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("notification_type", sa.String(50), nullable=False),
            sa.Column("channel", sa.String(20), nullable=False, server_default="email"),
            sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_notification_preferences_user",
            ),
            sa.UniqueConstraint(
                "user_id",
                "notification_type",
                name="uq_user_notification_type",
            ),
        )
        op.create_index(
            "ix_notification_preferences_id",
            "notification_preferences",
            ["id"],
        )
        op.create_index(
            "ix_notification_preferences_user_id",
            "notification_preferences",
            ["user_id"],
        )

    # ---------------------------------------------------------------
    # 11. notifications
    # ---------------------------------------------------------------
    if "notifications" not in existing:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("level", sa.String(20), nullable=True, server_default="info"),
            sa.Column("related_type", sa.String(50), nullable=True),
            sa.Column("related_id", sa.Integer(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_notifications_user",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_notifications_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("idx_notifications_user", "notifications", ["user_id"])
        op.create_index("idx_notifications_read", "notifications", ["is_read"])
        op.create_index("idx_notifications_created", "notifications", ["created_at"])
        op.create_index(
            "idx_notifications_user_read_created",
            "notifications",
            ["user_id", "is_read", "created_at"],
        )
        op.create_index("ix_notifications_id", "notifications", ["id"])
        op.create_index("ix_notifications_company_id", "notifications", ["company_id"])
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # ---------------------------------------------------------------
    # 12. reengagement_campaigns
    # ---------------------------------------------------------------
    if "reengagement_campaigns" not in existing:
        op.create_table(
            "reengagement_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("recruiter_id", sa.Integer(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("total_candidates", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("matched_candidates", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("invited_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("response_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("avg_match_score", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(50), nullable=True, server_default="analyzing"),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["recruiter_id"], ["users.id"],
                name="fk_re_campaign_recruiter",
            ),
            sa.ForeignKeyConstraint(
                ["job_id"], ["jobs.id"],
                name="fk_re_campaign_job",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_re_campaign_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index(
            "idx_re_campaign_recruiter",
            "reengagement_campaigns",
            ["recruiter_id"],
        )
        op.create_index(
            "idx_re_campaign_job",
            "reengagement_campaigns",
            ["job_id"],
        )
        op.create_index(
            "idx_re_campaign_status",
            "reengagement_campaigns",
            ["status"],
        )
        op.create_index(
            "ix_reengagement_campaigns_company_id",
            "reengagement_campaigns",
            ["company_id"],
        )
        op.create_index(
            "ix_reengagement_campaigns_id",
            "reengagement_campaigns",
            ["id"],
        )

    # ---------------------------------------------------------------
    # 13. reengagement_candidates
    # ---------------------------------------------------------------
    if "reengagement_candidates" not in existing:
        op.create_table(
            "reengagement_candidates",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=True),
            sa.Column("application_id", sa.Integer(), nullable=True),
            sa.Column("match_score", sa.Float(), nullable=True),
            sa.Column("match_reason", sa.Text(), nullable=True),
            sa.Column("invited_at", sa.DateTime(), nullable=True),
            sa.Column("responded_at", sa.DateTime(), nullable=True),
            sa.Column("response_status", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["campaign_id"], ["reengagement_campaigns.id"],
                name="fk_re_candidate_campaign",
            ),
            sa.ForeignKeyConstraint(
                ["application_id"], ["applications.id"],
                name="fk_re_candidate_application",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_re_candidate_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index(
            "idx_re_candidate_campaign",
            "reengagement_candidates",
            ["campaign_id"],
        )
        op.create_index(
            "idx_re_candidate_application",
            "reengagement_candidates",
            ["application_id"],
        )
        op.create_index(
            "idx_re_candidate_response",
            "reengagement_candidates",
            ["response_status"],
        )
        op.create_index(
            "ix_reengagement_candidates_id",
            "reengagement_candidates",
            ["id"],
        )
        op.create_index(
            "ix_reengagement_candidates_company_id",
            "reengagement_candidates",
            ["company_id"],
        )

    # ---------------------------------------------------------------
    # 14. saved_jobs
    # ---------------------------------------------------------------
    if "saved_jobs" not in existing:
        op.create_table(
            "saved_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name="fk_saved_jobs_user",
            ),
            sa.ForeignKeyConstraint(
                ["job_id"], ["jobs.id"],
                name="fk_saved_jobs_job",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_saved_jobs_company",
                ondelete="RESTRICT",
            ),
        )
        op.create_index("ix_saved_jobs_id", "saved_jobs", ["id"])
        op.create_index("ix_saved_jobs_user_id", "saved_jobs", ["user_id"])
        op.create_index("ix_saved_jobs_job_id", "saved_jobs", ["job_id"])
        op.create_index("ix_saved_jobs_company_id", "saved_jobs", ["company_id"])
        op.create_index("idx_saved_jobs_user", "saved_jobs", ["user_id"])

    # ---------------------------------------------------------------
    # 15. skill_definitions
    # ---------------------------------------------------------------
    if "skill_definitions" not in existing:
        op.create_table(
            "skill_definitions",
            sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("id", sa.String(36), primary_key=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "expected_proficiency",
                sa.String(20),
                nullable=True,
                server_default="mid",
            ),
            sa.Column("weight", sa.Float(), nullable=True, server_default="1.0"),
            sa.Column("keywords", sa.JSON(), nullable=True),
            sa.Column("levels", sa.JSON(), nullable=True),
            sa.Column("is_required", sa.Boolean(), nullable=True, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["category_id"], ["categories.id"],
                name="fk_skill_def_category",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["company_id"], ["companies.id"],
                name="fk_skill_def_company",
                ondelete="RESTRICT",
            ),
            sa.UniqueConstraint(
                "company_id",
                "name",
                name="uq_skill_def_company_name",
            ),
        )
        op.create_index(
            "ix_skill_definitions_company_id",
            "skill_definitions",
            ["company_id"],
        )
        op.create_index(
            "idx_skill_def_category",
            "skill_definitions",
            ["category_id"],
        )
        op.create_index(
            "ix_skill_definitions_category_id",
            "skill_definitions",
            ["category_id"],
        )


def downgrade() -> None:
    # Reverse dependency order.
    for table in (
        "skill_definitions",
        "saved_jobs",
        "reengagement_candidates",
        "reengagement_campaigns",
        "notifications",
        "notification_preferences",
        "interview_questions",
        "email_sequence_logs",
        "eeo_consent",
        "bot_integrations",
        "background_check_status_logs",
        "background_checks",
        "messages",
        "conversation_participants",
        "conversations",
    ):
        op.drop_table(table)
