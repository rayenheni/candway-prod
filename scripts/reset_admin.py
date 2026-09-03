import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, User
from backend.dependencies import pwd_context

def reset_admin():
    db = SessionLocal()
    admin = db.query(User).filter(User.email == 'rayenheni8@gmail.com').first()
    if admin:
        admin.hashed_password = pwd_context.hash('Admin@123!')
        db.commit()
        print("Admin fully updated. Pwd: Admin@123!")
    else:
        print("Admin not found!")

if __name__ == "__main__":
    reset_admin()
