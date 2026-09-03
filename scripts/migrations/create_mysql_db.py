import pymysql

# Default XAMPP Credentials
HOST = "localhost"
USER = "root"
PASSWORD = "" # Empty by default
DB_NAME = "candway_app"

try:
    # Connect to MySQL Server (no DB selected yet)
    connection = pymysql.connect(
        host=HOST,
        user=USER,
        password=PASSWORD
    )
    
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        print(f"SUCCESS: Database '{DB_NAME}' created or already exists.")
        
    connection.close()

except Exception as e:
    print(f"ERROR: Could not connect to MySQL. Is XAMPP running? {e}")
