
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, User
from backend.dependencies import pwd_context

def create_test_user():
    try:
        db = SessionLocal()
        email = "test_candidate@candway.io"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Creating user {email}...")
            u = User(
                email=email,
                hashed_password=pwd_context.hash("password123"),
                role="candidate",
                name="Test Candidate"
            )
            db.add(u)
            db.commit()
            print("User created successfully.")
        else:
            print("User already exists.")
            # Update password just in case
            user.hashed_password = pwd_context.hash("password123")
            db.commit()
            print("Password updated to 'password123'.")
    except Exception as e:
        print(f"Error creating user: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_test_user()
