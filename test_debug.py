import json
from backend.database import SessionLocal
from backend.models.evaluation.evaluation import EvaluationSession
from backend.models.ats.application import Application

db = SessionLocal()
app = db.query(Application).filter(Application.id == 121).first()
cv = app.cv_document
if cv and cv.analysis_json:
    aj = json.loads(cv.analysis_json) if isinstance(cv.analysis_json, str) else cv.analysis_json
    es = aj.get('engine_v2_state', {})
    print('covered_skills:', es.get('covered_skills', 'MISSING'))
    print('current_focus:', es.get('current_focus', 'MISSING'))
    print('turn:', es.get('turn', 'MISSING'))
    print('live_skill_metrics:', list(es.get('live_skill_metrics', {}).keys()) or 'EMPTY')
    print('history length:', len(es.get('history', [])))
    for h in es.get('history', []):
        print('  focus=%s score=%s quality=%s' % (h.get('focus'), h.get('score'), h.get('quality')))
    print('score_breakdown:', es.get('score_breakdown', 'MISSING'))
    print('skill_scores:', es.get('skill_scores', 'MISSING'))

es2 = db.query(EvaluationSession).filter(EvaluationSession.application_id == 121).order_by(EvaluationSession.id.desc()).first()
print('\nES turn_seq:', es2.interview_turn_seq)
print('ES interview_state:', es2.interview_state)
print('ES time_left:', es2.interview_time_left)
print('ES interview_log entries:', len(es2.interview_log or []))
db.close()
