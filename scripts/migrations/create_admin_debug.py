import sys
import os

# Ensure backend modules can be imported
sys.path.append(os.getcwd())

from backend.database import SessionLocal, User
from backend.dependencies import pwd_context

def get_bootstrap_password() -> str:
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not password:
        raise ValueError("ADMIN_BOOTSTRAP_PASSWORD is required to create/update admin user.")
    return password

def create_admin():
    db = SessionLocal()
    email = "admin@candway.io"
    password = get_bootstrap_password()
    
    print(f"DEBUG: Attempting to hash password '{password}' with length {len(password)}")
    
    try:
        # Test hash in isolation
        test_hash = pwd_context.hash(password)
        print(f"DEBUG: Hash check successful: {test_hash[:10]}...")

        # Check if exists
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User {email} exists. Deleting to recreate fresh...")
            db.delete(user)
            db.commit()
            
        print(f"Creating new admin user: {email}")
        new_user = User(
            email=email,
            hashed_password=test_hash, # Use the pre-computed hash
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
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
