
import sqlite3
import os

DB_PATH = "candway.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE career_roadmaps ADD COLUMN progress_json TEXT DEFAULT '{}'")
        conn.commit()
        print("Migration successful: Added progress_json column.")
    except sqlite3.OperationalError as e:
        print(f"Migration skipped or failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        migrate()
    else:
        print("Database not found.")
