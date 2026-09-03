import os
from passlib.context import CryptContext
from backend.database import SessionLocal, User

# Same context as main.py
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_bootstrap_password() -> str:
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not password:
        raise ValueError("ADMIN_BOOTSTRAP_PASSWORD is required to reset/create admin password.")
    return password

def reset_password():
    db = SessionLocal()
    password = get_bootstrap_password()
    try:
        user = db.query(User).filter(User.email == "admin@candway.io").first()
        if user:
            print(f"Found user {user.email}. Resetting password...")
            user.hashed_password = pwd_context.hash(password)
            db.commit()
            print("Password reset successfully.")
        
        if not user:
            print("User admin@candway.io not found. Creating it...")
            new_user = User(
                email="admin@candway.io",
                hashed_password=pwd_context.hash(password),
                role="admin"
            )
            db.add(new_user)
            db.commit()
            print("Created admin@candway.io with provided bootstrap password.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_password()
