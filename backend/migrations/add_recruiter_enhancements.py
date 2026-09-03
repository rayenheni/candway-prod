"""
Migration: Recruiter Platform Enhancements v5.0
Creates new tables for: pipeline stages, automation rules, tagged notes,
scorecards, webhooks, undo actions, campaign costs, stage history
"""

import os
import sys

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)

from backend.database import Base, engine  # noqa: E402
from backend.logger import logger  # noqa: E402

TABLES_TO_CREATE = [
    "pipeline_stages",
    "application_stage_history",
    "pipeline_automation_rules",
    "tagged_notes",
    "interview_scorecards",
    "scorecard_submissions",
    "webhook_integrations",
    "undo_actions",
    "campaign_costs",
]


def run_migration():
    """Create new tables if they don't exist"""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    created = []
    skipped = []

    for table_name in TABLES_TO_CREATE:
        if table_name in existing_tables:
            skipped.append(table_name)
            logger.info(f"Table already exists: {table_name}")
            continue

        table = Base.metadata.tables.get(table_name)
        if table is not None:
            try:
                table.create(bind=engine, checkfirst=True)
                created.append(table_name)
                logger.info(f"Created table: {table_name}")
            except Exception as e:
                logger.error(f"Failed to create table {table_name}: {e}")
        else:
            logger.warning(f"Table definition not found: {table_name}")

    if created:
        logger.info(
            f"Migration complete: Created {len(created)} tables: {', '.join(created)}"
        )
    if skipped:
        logger.info(f"Skipped {len(skipped)} existing tables: {', '.join(skipped)}")

    return {"created": created, "skipped": skipped}


if __name__ == "__main__":
    result = run_migration()
    print(f"Migration result: {result}")
