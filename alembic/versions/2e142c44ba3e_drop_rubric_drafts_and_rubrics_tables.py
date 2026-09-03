"""Drop rubric_drafts and rubrics tables (data migrated to job_rubrics in C2).

Phase C4 of the unified rubric model migration.  After data migration (C2) and
code migration (C3), the old rubric_drafts and rubrics tables are no longer
referenced by any code.

The ``job_rubrics`` table is now the single source of truth for both published
rubrics (status='published', version >= 1) and recruiter drafts
(status='draft', version <= 0).

Revision ID: 2e142c44ba3e
Revises: d0e1f2a3b4c5
Create Date: 2026-06-10 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "2e142c44ba3e"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Drop rubric_drafts — data migrated in C2
    op.execute("DROP TABLE IF EXISTS rubric_drafts")
    # Drop rubrics — never had data in prod; may exist in dev/create_all
    op.execute("DROP TABLE IF EXISTS rubrics")


def downgrade():
    # Recreate rubric_drafts table
    op.execute("""
        CREATE TABLE rubric_drafts (
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
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Recreate rubrics table (from the now-removed Rubric model)
    op.execute("""
        CREATE TABLE rubrics (
            id INTEGER NOT NULL AUTO_INCREMENT,
            job_id INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_current TINYINT(1) NOT NULL DEFAULT 1,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            seniority VARCHAR(20) NOT NULL DEFAULT 'mid',
            name VARCHAR(200) NOT NULL DEFAULT 'Untitled Rubric',
            rubric_json JSON NOT NULL,
            created_by INTEGER,
            created_at DATETIME,
            updated_at DATETIME,
            superseded_at DATETIME,
            PRIMARY KEY (id),
            UNIQUE KEY uq_rubric_version (job_id, version),
            KEY idx_rubric_job_current (job_id, is_current),
            CONSTRAINT fk_r_job FOREIGN KEY (job_id) REFERENCES jobs(id),
            CONSTRAINT fk_r_creator FOREIGN KEY (created_by) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
