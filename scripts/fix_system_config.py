import sys
import os

# Ensure the backend module is accessible
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from backend.database import engine, SystemConfig

def force_migrate_system_config():
    print("🚀 Fixing system_config table...")
    try:
        # Checkfirst ensures it doesn't drop anything or raise an error if it exists
        SystemConfig.__table__.create(engine, checkfirst=True)
        print("✅ system_config table created or verified successfully!")
    except Exception as e:
        print(f"❌ Error creating table: {e}")

if __name__ == "__main__":
    force_migrate_system_config()
