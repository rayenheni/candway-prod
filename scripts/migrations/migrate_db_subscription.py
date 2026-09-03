import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "candway.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Add proof_url column to transactions table
        print("Adding proof_url column to transactions table...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN proof_url TEXT")
        print("Column proof_url added successfully.")
    except sqlite3.OperationalError as e:
        print(f"Skipping proof_url: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
