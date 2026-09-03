"""
Check existing database tables
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "candway.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()

print("📊 Existing tables in database:")
print("=" * 50)
for table in tables:
    print(f"  • {table[0]}")

# Check interviews table structure
print("\n📋 Interviews table columns:")
print("=" * 50)
cursor.execute("PRAGMA table_info(interviews);")
columns = cursor.fetchall()
for col in columns:
    print(f"  • {col[1]} ({col[2]})")

conn.close()
