"""add company_member user_active index + chatbot_lead FK indexes

Revision ID: p1prod202606300
Revises: p1prod202606111615
Create Date: 2026-06-30 12:00:00.000000

chatbot_leads is created here because no earlier migration creates the
table (it was originally created by ``create_all()`` on dev databases).
The schema matches the ChatbotLead model *without* the TenantMixin
company_id column -- m22 adds that column in a later migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p1prod202606300"
down_revision: Union[str, Sequence[str], None] = "p1prod202606111615"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, index_name: str, table_name: str) -> bool:
    """Check information_schema.statistics for an existing index."""
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() "
            "AND table_name = :tbl AND index_name = :idx "
            "LIMIT 1"
        ),
        {"tbl": table_name, "idx": index_name},
    ).fetchone()
    return row is not None


def _table_exists(conn, table_name: str) -> bool:
    """Check information_schema for an existing table."""
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = DATABASE() "
            "AND table_name = :tbl "
            "LIMIT 1"
        ),
        {"tbl": table_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    if not _index_exists(conn, "idx_company_members_user_active", "company_members"):
        op.create_index(
            "idx_company_members_user_active",
            "company_members",
            ["user_id", "is_active"],
        )

    # ------------------------------------------------------------------
    # chatbot_leads: create the table if it does not yet exist.
    # company_id is intentionally omitted -- m22 will add it as a
    # nullable FK, then m22b/m23 will enforce NOT NULL.
    # ------------------------------------------------------------------
    if not _table_exists(conn, "chatbot_leads"):
        conn.execute(
            sa.text(
                """
                CREATE TABLE chatbot_leads (
                    id              INTEGER AUTO_INCREMENT PRIMARY KEY,
                    conversation_id VARCHAR(64)  NOT NULL,
                    name            VARCHAR(255) NULL,
                    email           VARCHAR(255) NULL,
                    phone           VARCHAR(255) NULL,
                    role_interest   VARCHAR(255) NULL,
                    experience_level VARCHAR(100) NULL,
                    skills          TEXT         NULL,
                    message_history TEXT         NULL,
                    stage           VARCHAR(50)  NOT NULL DEFAULT 'greeting',
                    source_job_id   INTEGER      NULL,
                    assigned_recruiter_id INTEGER NULL,
                    contacted_at    DATETIME     NULL,
                    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_chatbot_leads_conv (conversation_id),
                    CONSTRAINT fk_chatbot_leads_source_job
                        FOREIGN KEY (source_job_id) REFERENCES jobs (id)
                        ON DELETE SET NULL ON UPDATE CASCADE,
                    CONSTRAINT fk_chatbot_leads_recruiter
                        FOREIGN KEY (assigned_recruiter_id) REFERENCES users (id)
                        ON DELETE SET NULL ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        )

    if not _index_exists(conn, "idx_chatbot_lead_conv", "chatbot_leads"):
        op.create_index(
            "idx_chatbot_lead_conv",
            "chatbot_leads",
            ["conversation_id"],
        )

    if not _index_exists(conn, "idx_chatbot_lead_job", "chatbot_leads"):
        op.create_index(
            "idx_chatbot_lead_job",
            "chatbot_leads",
            ["source_job_id"],
        )

    if not _index_exists(conn, "idx_chatbot_lead_recruiter", "chatbot_leads"):
        op.create_index(
            "idx_chatbot_lead_recruiter",
            "chatbot_leads",
            ["assigned_recruiter_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _index_exists(conn, "idx_chatbot_lead_recruiter", "chatbot_leads"):
        op.drop_index("idx_chatbot_lead_recruiter", table_name="chatbot_leads")
    if _index_exists(conn, "idx_chatbot_lead_job", "chatbot_leads"):
        op.drop_index("idx_chatbot_lead_job", table_name="chatbot_leads")
    if _index_exists(conn, "idx_chatbot_lead_conv", "chatbot_leads"):
        op.drop_index("idx_chatbot_lead_conv", table_name="chatbot_leads")
    if _table_exists(conn, "chatbot_leads"):
        op.execute(sa.text("DROP TABLE chatbot_leads"))
    if _index_exists(conn, "idx_company_members_user_active", "company_members"):
        op.drop_index("idx_company_members_user_active", table_name="company_members")
