
import os
import shutil
import datetime
import subprocess
import warnings
from dotenv import load_dotenv

def backup_database():
    # Load .env from backend directory
    backend_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', '.env')
    load_dotenv(backend_env)
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    print(f"Starting backup for: {db_url}")

    if db_url.startswith("sqlite"):
        # Handle SQLite
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        # If relative path, resolve it relative to backend or root
        if not os.path.isabs(db_path):
             # Try root first (common for candway.db)
             root_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
             if os.path.exists(root_path):
                 db_path = root_path
             else:
                 # Try backend
                 backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', db_path)
                 db_path = backend_path

        if os.path.exists(db_path):
            dest = os.path.join(backup_dir, f"backup_sqlite_{timestamp}.db")
            shutil.copy2(db_path, dest)
            print(f"SQLite backup successful: {dest}")
        else:
            print(f"SQLite DB file not found: {db_path}")

    elif db_url.startswith("mysql"):
        # Handle MySQL (mysql+pymysql://user:pass@host/db)
        try:
            # Simple parsing
            # mysql+pymysql://root:@localhost/candway_app
            parts = db_url.split("://")[1].split("@")
            user_pass = parts[0].split(":")
            user = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ""
            
            host_db = parts[1].split("/")
            host = host_db[0]
            database = host_db[1]

            dest = os.path.join(backup_dir, f"backup_mysql_{database}_{timestamp}.sql")

            # Prefer ~/.my.cnf or environment variable over command-line -p
            mysql_pwd = os.environ.get("MYSQL_PWD") or os.environ.get("DB_PASSWORD")
            if not mysql_pwd:
                mysql_pwd = password
            if password:
                warnings.warn("Password passed via command line — visible in process list")

            # Construct mysqldump command (no -p flag)
            cmd = ["mysqldump", "-h", host, "-u", user]
            cmd.extend([database, "--result-file=" + dest])

            env = os.environ.copy()
            if mysql_pwd:
                env["MYSQL_PWD"] = mysql_pwd

            print("Running: mysqldump -h %s -u %s [database] --result-file=%s" % (host, user, dest))
            subprocess.run(cmd, check=True, env=env)
            print(f"MySQL backup successful: {dest}")
        except Exception as e:
            print(f"MySQL backup failed: {e}")
            print("Ensure 'mysqldump' is installed and in PATH.")

if __name__ == "__main__":
    backup_database()
