
import sqlalchemy
from sqlalchemy import create_engine
from backend.database import init_db, DATABASE_URL

def recreate_database():
    # Parse DB Name from URL
    db_name = DATABASE_URL.split("/")[-1]
    server_url = DATABASE_URL.rsplit("/", 1)[0]
    
    print(f"Connecting to MySQL Server: {server_url}...")
    
    # Connect to Server (No DB)
    engine = create_engine(server_url)
    
    with engine.connect() as conn:
        print(f"Creating database '{db_name}' if missing...")
        conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))
        print("Database checked/created.")

    print("Initializing Tables...")
    init_db()
    print("Tables created successfully.")

if __name__ == "__main__":
    recreate_database()
