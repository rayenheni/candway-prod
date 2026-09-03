from backend.database import Base, engine
import backend.main
import traceback
import os

print("Creating all tables in MySQL...")
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_error.log")

try:
    Base.metadata.create_all(bind=engine)
    print("SUCCESS: Tables created.")
except Exception:
    with open(log_path, "w") as f:
        traceback.print_exc(file=f)
    print(f"ERROR: Written to {log_path}")
