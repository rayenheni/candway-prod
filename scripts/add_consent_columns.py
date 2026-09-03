
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine
from sqlalchemy import text

def add_columns():
    with engine.connect() as conn:
        try:
            # Add marketing_consent
            print("Adding marketing_consent column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN marketing_consent BOOLEAN DEFAULT FALSE"))
            print("marketing_consent added.")
        except Exception as e:
            print(f"Error adding marketing_consent (might already exist): {e}")

        try:
            # Add data_processing_consent
            print("Adding data_processing_consent column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN data_processing_consent BOOLEAN DEFAULT FALSE"))
            print("data_processing_consent added.")
        except Exception as e:
            print(f"Error adding data_processing_consent (might already exist): {e}")
            
        try:
             # Add skills to User if it doesn't exist (based on database.py update)
            print("Adding skills column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN skills TEXT"))
            print("skills added.")
        except Exception as e:
            print(f"Error adding skills (might be skipped or exists): {e}")

if __name__ == "__main__":
    add_columns()
