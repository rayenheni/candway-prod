"""
Migration: Add notifications table
Creates the notifications table for storing in-app notifications
"""

import os
import sys

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from backend.database import Notification, engine
from backend.logger import logger


def upgrade():
    """Create notifications table"""
    inspector = inspect(engine)

    if "notifications" in inspector.get_table_names():
        logger.info("Notifications table already exists. Skipping.")
        return

    logger.info("Creating notifications table...")

    # Create only the Notification table
    Notification.__table__.create(engine, checkfirst=True)

    logger.info("✅ Notifications table created successfully")


def downgrade():
    """Drop notifications table"""
    inspector = inspect(engine)

    if "notifications" not in inspector.get_table_names():
        logger.info("Notifications table does not exist. Skipping.")
        return

    logger.info("Dropping notifications table...")

    Notification.__table__.drop(engine)

    logger.info("✅ Notifications table dropped successfully")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
