
import sys
import os

# Create a valid module path
sys.path.append(os.getcwd())

from backend.database import SessionLocal, Enrollment, User

def reset_enrollment():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "candidate@candway.io").first()
        if not user:
            print("User not found")
            return
        
        enrollment = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.course_id == 1).first()
        if enrollment:
            db.delete(enrollment)
            db.commit()
            print("Enrollment deleted.")
        else:
            print("No enrollment to delete.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_enrollment()
