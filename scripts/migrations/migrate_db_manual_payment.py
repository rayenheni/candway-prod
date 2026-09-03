
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "candway.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

def add_column(table, column, type_def):
    try:
        print(f"Adding {column} to {table}...")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
        print("Done.")
    except sqlite3.OperationalError as e:
        print(f"Skipped (probably exists): {e}")

add_column("enrollments", "proof_url", "TEXT")
add_column("enrollments", "admin_notes", "TEXT")

conn.commit()
conn.close()
print("Migration complete.")
