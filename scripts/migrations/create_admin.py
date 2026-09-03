import os
from backend.database import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_bootstrap_password() -> str:
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not password:
        raise ValueError("ADMIN_BOOTSTRAP_PASSWORD is required to create/update admin user.")
    return password

def create_admin():
    db = SessionLocal()
    email = "admin@candway.io"
    password = get_bootstrap_password()
    
    try:
        # Check if exists
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User {email} already exists. Updating role to admin.")
            user.role = "admin"
            user.hashed_password = pwd_context.hash(password)
            db.commit()
        else:
            print(f"Creating new admin user: {email}")
            new_user = User(
                email=email,
                hashed_password=pwd_context.hash(password),
                role="admin",
                name="System Administrator",
                headline="Platform Superuser"
            )
            db.add(new_user)
            db.commit()
            
        print("--------------------------------------------------")
        print(f"Admin Access Ready!")
        print(f"Email:    {email}")
        print("Password: [from ADMIN_BOOTSTRAP_PASSWORD]")
        print("--------------------------------------------------")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
