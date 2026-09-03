"""m26: Add application_type to applications table.

Adds ``application_type`` ENUM column to ``applications`` with
default ``manual``.  Backfills existing rows based on:
  - batch_id IS NOT NULL         → CAMPAIGN
  - job_id IS NOT NULL           → JOB
  - AI interview session exists  → AI_INTERVIEW
  - everything else              → MANUAL

Revision ID: m26
Revises: m_merge_m25_m_merge
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa


revision = "m26"
down_revision = "m_merge_m25_m_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Create the ENUM type (safe checkfirst)
    application_type_enum = sa.Enum(
        "job", "campaign", "ai_interview", "referral", "import", "manual",
        name="applicationtype",
    )
    try:
        application_type_enum.create(bind, checkfirst=True)
    except Exception:
        pass

    app_cols = {c["name"] for c in inspector.get_columns("applications")}

    # 2. Add column (nullable temporarily for backfill)
    if "application_type" not in app_cols:
        op.add_column(
            "applications",
            sa.Column(
                "application_type",
                application_type_enum,
                nullable=True,
                server_default=None,
            ),
        )

    # 3. Backfill based on existing data
    # Campaign imports
    bind.execute(
        sa.text(
            "UPDATE applications SET application_type = 'campaign' "
            "WHERE batch_id IS NOT NULL AND application_type IS NULL"
        )
    )

    # Job applications
    bind.execute(
        sa.text(
            "UPDATE applications SET application_type = 'job' "
            "WHERE job_id IS NOT NULL AND batch_id IS NULL "
            "AND application_type IS NULL"
        )
    )

    # AI interview — has evaluation_sessions with interview_state
    bind.execute(
        sa.text(
            "UPDATE applications SET application_type = 'ai_interview' "
            "WHERE id IN ("
            "  SELECT DISTINCT es.application_id FROM evaluation_sessions es "
            "  WHERE es.application_id IS NOT NULL"
            ") AND application_type IS NULL"
        )
    )

    # Everything else → manual
    bind.execute(
        sa.text(
            "UPDATE applications SET application_type = 'manual' "
            "WHERE application_type IS NULL"
        )
    )

    # 4. Make NOT NULL with server default (existing_type is REQUIRED by MySQL for MODIFY COLUMN)
    op.alter_column(
        "applications",
        "application_type",
        existing_type=application_type_enum,
        nullable=False,
        server_default=sa.text("'manual'"),
    )

    # 5. Index
    app_indexes = {idx["name"] for idx in inspector.get_indexes("applications")}
    if "idx_applications_type" not in app_indexes:
        op.create_index("idx_applications_type", "applications", ["application_type"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    app_indexes = {idx["name"] for idx in inspector.get_indexes("applications")}
    if "idx_applications_type" in app_indexes:
        op.drop_index("idx_applications_type", table_name="applications")

    app_cols = {c["name"] for c in inspector.get_columns("applications")}
    if "application_type" in app_cols:
        op.drop_column("applications", "application_type")

    try:
        sa.Enum(name="applicationtype").drop(bind, checkfirst=True)
    except Exception:
        pass
