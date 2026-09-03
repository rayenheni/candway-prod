from backend.database import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def reset_password():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "rayen@demo.com").first()
        if not user:
            print("User rayen@demo.com not found. Trying admin@candway.io")
            user = db.query(User).filter(User.email == "admin@candway.io").first()
            
        if not user:
            print("No suitable user found.")
            return

        print(f"Resetting password for {user.email}")
        user.hashed_password = pwd_context.hash("password123")
        db.commit()
        print("Password reset to 'password123'")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_password()
