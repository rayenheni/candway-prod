"""
Simple SQL Migration: Add Notification Tracking Fields
Run this directly with: python run_migration.py
"""

import os
import sqlite3

# Get database path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "candway.db")


def run_migration():
    """Add notification tracking fields to interviews and offers tables"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    migrations = [
        # Interview table - add reminder tracking fields
        "ALTER TABLE interviews ADD COLUMN reminder_24h_sent INTEGER DEFAULT 0;",
        "ALTER TABLE interviews ADD COLUMN reminder_1h_sent INTEGER DEFAULT 0;",
        # Offer table - add expiration warning tracking fields
        "ALTER TABLE offers ADD COLUMN expiry_warning_3d_sent INTEGER DEFAULT 0;",
        "ALTER TABLE offers ADD COLUMN expiry_warning_1d_sent INTEGER DEFAULT 0;",
        "ALTER TABLE offers ADD COLUMN expiry_warning_expired_sent INTEGER DEFAULT 0;",
    ]

    for migration in migrations:
        try:
            cursor.execute(migration)
            print(f"✅ Executed: {migration[:50]}...")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"⏭️  Skipped (already exists): {migration[:50]}...")
            else:
                print(f"❌ Error: {e}")
                print(f"   Migration: {migration}")

    conn.commit()
    conn.close()
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    print("Running database migration...")
    print(f"Database: {DB_PATH}")
    run_migration()
