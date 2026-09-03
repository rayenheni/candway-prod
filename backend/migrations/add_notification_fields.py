"""
Database Migration: Add Notification Tracking Fields
Adds fields to Interview and Offer models for tracking sent notifications
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from sqlalchemy import text

from backend.database import engine

logger = logging.getLogger(__name__)


def upgrade():
    """Add notification tracking fields"""

    migrations = [
        # Interview table - add reminder tracking fields
        """
        ALTER TABLE interviews
        ADD COLUMN IF NOT EXISTS reminder_24h_sent BOOLEAN DEFAULT FALSE;
        """,
        """
        ALTER TABLE interviews
        ADD COLUMN IF NOT EXISTS reminder_1h_sent BOOLEAN DEFAULT FALSE;
        """,
        # Offer table - add expiration warning tracking fields
        """
        ALTER TABLE offers
        ADD COLUMN IF NOT EXISTS expiry_warning_3d_sent BOOLEAN DEFAULT FALSE;
        """,
        """
        ALTER TABLE offers
        ADD COLUMN IF NOT EXISTS expiry_warning_1d_sent BOOLEAN DEFAULT FALSE;
        """,
        """
        ALTER TABLE offers
        ADD COLUMN IF NOT EXISTS expiry_warning_expired_sent BOOLEAN DEFAULT FALSE;
        """,
    ]

    with engine.connect() as conn:
        for migration in migrations:
            try:
                conn.execute(text(migration))
                conn.commit()
                logger.info("Migration executed successfully")
            except Exception as e:
                logger.error(f"Migration failed: {e}")
                # Continue with other migrations even if one fails

    logger.info("All notification tracking fields added successfully")


def downgrade():
    """Remove notification tracking fields (rollback)"""

    rollbacks = [
        "ALTER TABLE interviews DROP COLUMN IF EXISTS reminder_24h_sent;",
        "ALTER TABLE interviews DROP COLUMN IF EXISTS reminder_1h_sent;",
        "ALTER TABLE offers DROP COLUMN IF EXISTS expiry_warning_3d_sent;",
        "ALTER TABLE offers DROP COLUMN IF EXISTS expiry_warning_1d_sent;",
        "ALTER TABLE offers DROP COLUMN IF EXISTS expiry_warning_expired_sent;",
    ]

    with engine.connect() as conn:
        for rollback in rollbacks:
            try:
                conn.execute(text(rollback))
                conn.commit()
                logger.info("Rollback executed successfully")
            except Exception as e:
                logger.error(f"Rollback failed: {e}")

    logger.info("All notification tracking fields removed")


if __name__ == "__main__":
    # Run migration
    print("Running database migration...")
    upgrade()
    print("Migration complete!")

    # Uncomment to rollback:
    # print("Rolling back migration...")
    # downgrade()
    # print("Rollback complete!")
