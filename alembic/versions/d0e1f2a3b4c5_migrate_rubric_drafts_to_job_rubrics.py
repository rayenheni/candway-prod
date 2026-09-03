"""Migrate rubric_drafts rows into job_rubrics with version-based ordering.

Phase C2 of the unified rubric model migration.  Drafts are assigned sequential
version numbers (0, -1, -2, …) per job so they never collide with the
``(job_id, version)`` unique constraint or with published rubrics (which use
version >= 1).

Because ``rubric_drafts`` has no unique constraint on ``(job_id, …)``, multiple
drafts may exist for the same job.  The most recently updated draft gets
version=0; older ones get negative versions.

Revision ID: d0e1f2a3b4c5
Revises: f0b1c2d3e4f5
Create Date: 2026-06-10 14:30:00.000000
"""

import logging
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

logger = logging.getLogger("alembic.migration")

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "f0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _migrate_rubrics_table(bind) -> int:
    """Migrate rows from ``rubrics`` table (if it exists) into ``job_rubrics``.

    Returns the number of rows migrated.
    """
    inspector = inspect(bind)
    if "rubrics" not in inspector.get_table_names():
        logger.info("rubrics table does not exist — skipping")
        return 0

    # Determine which jobs already have a draft in job_rubrics
    existing = bind.execute(
        text("SELECT DISTINCT job_id FROM job_rubrics WHERE version = 0 AND status = 'draft'")
    ).fetchall()
    existing_job_ids = {r[0] for r in existing}

    rows = bind.execute(text("SELECT * FROM rubrics")).mappings().fetchall()
    if not rows:
        logger.info("rubrics table is empty — skipping")
        return 0

    migrated = 0
    skipped = 0
    for row in rows:
        if row["job_id"] in existing_job_ids:
            logger.warning(
                "Conflict: draft already exists for job_id=%s (rubrics id=%s) — skipping",
                row["job_id"], row["id"],
            )
            skipped += 1
            continue

        bind.execute(
            text("""
                INSERT INTO job_rubrics
                    (job_id, version, is_current, seniority, status, name,
                     user_id, base_version, rubric_json, created_by,
                     created_at, updated_at, superseded_at)
                VALUES
                    (:job_id, 0, 0, COALESCE(:seniority, 'mid'),
                     COALESCE(:status, 'draft'), :name,
                     :created_by, :base_version, :rubric_json, :created_by,
                     :created_at, :updated_at, :superseded_at)
            """),
            {
                "job_id": row["job_id"],
                "seniority": row.get("seniority"),
                "status": row.get("status", "draft"),
                "name": row.get("name"),
                "created_by": row.get("created_by"),
                "base_version": row.get("base_version"),
                "rubric_json": row.get("rubric_json"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "superseded_at": row.get("superseded_at"),
            },
        )
        migrated += 1

    logger.info("Migrated %d rows from rubrics (skipped %d)", migrated, skipped)
    return migrated


def _migrate_rubric_drafts_table(bind) -> int:
    """Migrate rows from ``rubric_drafts`` into ``job_rubrics``.

    Assigns sequential version numbers (0, -1, -2, …) per job so the
    ``(job_id, version)`` unique constraint is satisfied.  Most recently
    updated draft gets version=0.
    """
    inspector = inspect(bind)
    if "rubric_drafts" not in inspector.get_table_names():
        logger.info("rubric_drafts table does not exist — skipping")
        return 0

    # Determine which jobs already have a draft in job_rubrics
    existing = bind.execute(
        text("SELECT DISTINCT job_id FROM job_rubrics WHERE version = 0 AND status = 'draft'")
    ).fetchall()
    existing_job_ids = {r[0] for r in existing}

    # Use MySQL 8+ ROW_NUMBER to assign sequential version numbers per job
    # Most recently updated = version 0, older = -1, -2, ...
    rows = bind.execute(
        text("""
            SELECT
                rd.id,
                rd.job_id,
                rd.name,
                rd.status,
                rd.user_id,
                rd.base_version,
                rd.rubric_json,
                rd.created_at,
                rd.updated_at,
                -ROW_NUMBER() OVER (
                    PARTITION BY rd.job_id ORDER BY rd.updated_at DESC
                ) + 1 AS draft_seq
            FROM rubric_drafts rd
            ORDER BY rd.job_id, rd.updated_at DESC
        """)
    ).mappings().fetchall()

    if not rows:
        logger.info("rubric_drafts table is empty — skipping")
        return 0

    migrated = 0
    skipped = 0
    for row in rows:
        if row["draft_seq"] == 0 and row["job_id"] in existing_job_ids:
            # Version=0 already taken — skip all drafts for this job
            logger.warning(
                "Conflict: primary draft already exists for job_id=%s "
                "(rubric_drafts id=%s) — skipping all drafts for this job",
                row["job_id"], row["id"],
            )
            # We can't assign version=0 to any other draft for this job
            # because version=0 is the "primary" draft slot.
            # This means ALL drafts for this job are skipped.
            # Reset: count all remaining rows for this job as skipped.
            job_id = row["job_id"]
            remaining_for_job = sum(1 for r in rows if r["job_id"] == job_id)
            skipped += remaining_for_job
            continue

        if row["draft_seq"] != 0 and row["job_id"] in existing_job_ids:
            # Non-primary draft for a job that already has version=0 — still OK
            # because negative versions are always unique.
            pass

        bind.execute(
            text("""
                INSERT INTO job_rubrics
                    (job_id, version, is_current, seniority, status, name,
                     user_id, base_version, rubric_json, created_by,
                     created_at, updated_at)
                VALUES
                    (:job_id, :version, 0, 'mid',
                     COALESCE(:status, 'draft'), :name,
                     :user_id, :base_version, :rubric_json, NULL,
                     :created_at, :updated_at)
            """),
            {
                "job_id": row["job_id"],
                "version": row["draft_seq"],
                "status": row.get("status", "draft"),
                "name": row.get("name", "Untitled Draft"),
                "user_id": row.get("user_id"),
                "base_version": row.get("base_version"),
                "rubric_json": row.get("rubric_json"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            },
        )
        migrated += 1

    logger.info("Migrated %d rows from rubric_drafts (skipped %d)", migrated, skipped)
    return migrated


def upgrade():
    bind = op.get_bind()
    _migrate_rubrics_table(bind)
    _migrate_rubric_drafts_table(bind)


def _reverse_rubrics_migration(bind) -> int:
    """Reverse: delete rows that came from the rubrics table.

    Identifies migrated rows as those with ``version=0 AND status='draft'``
    and ``created_by IS NOT NULL`` (rubrics rows have created_by set;
    rubric_drafts rows have created_by=NULL).
    """
    result = bind.execute(
        text("""
            DELETE FROM job_rubrics
            WHERE version <= 0
              AND status = 'draft'
              AND created_by IS NOT NULL
        """)
    )
    logger.info("Rolled back %d rows from rubrics migration", result.rowcount)
    return result.rowcount


def _reverse_rubric_drafts_migration(bind) -> int:
    """Reverse: delete rows that came from rubric_drafts.

    Identified as ``version <= 0 AND status = 'draft' AND created_by IS NULL``.
    """
    result = bind.execute(
        text("""
            DELETE FROM job_rubrics
            WHERE version <= 0
              AND status = 'draft'
              AND created_by IS NULL
        """)
    )
    logger.info("Rolled back %d rows from rubric_drafts migration", result.rowcount)
    return result.rowcount


def downgrade():
    bind = op.get_bind()
    _reverse_rubrics_migration(bind)
    _reverse_rubric_drafts_migration(bind)
