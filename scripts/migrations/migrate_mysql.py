
from sqlalchemy import text
from backend.database import engine

def migrate_mysql():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE career_roadmaps ADD COLUMN progress_json TEXT"))
            conn.commit()
            print("Migration successful: Added progress_json column to MySQL.")
        except Exception as e:
            print(f"Migration failed (maybe dirty?): {e}")

if __name__ == "__main__":
    migrate_mysql()
