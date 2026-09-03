import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import SessionLocal, Application, User
db = SessionLocal()
u = db.query(User).filter(User.email=="rayenteck@gmail.com").first()
app = db.query(Application).filter(Application.user_id==u.id).order_by(Application.created_at.desc()).first()
print("App ID:", app.id)
print("Analysis JSON:", app.analysis_json)
print("Score:", app.overall_score)
