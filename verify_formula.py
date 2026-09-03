from backend.scoring_service import ScoringService
from backend.database import SessionLocal, Application, Company

db = SessionLocal()
company = db.query(Company).first()
if not company:
    company = Company(name='Test Co3', slug='test-co3')
    db.add(company)
    db.commit()

app = Application(company_id=company.id, user_id=1, status='applied')
db.add(app)
db.commit()
db.refresh(app)

# CV only: override_rubric_score=None triggers cv-only path
er = ScoringService.compute_final_score(
    app, db,
    override_cv_score=72.0,
    override_rubric_score=None,
    override_rubric_coverage_pct=10.0,
)
db.commit()
expected = round(72.0 * 0.75 + 10.0 * 0.25, 1)
print(f'CV only: final={er.final_score}, expected={expected}, match={er.final_score == expected}')
print(f'  cv={er.cv_score}, rubric={er.rubric_score}, coverage={er.rubric_coverage_pct}')
weights = er.score_breakdown.get("weights", {}) if er.score_breakdown else {}
print(f'  weights in breakdown: {weights}')

# With rubric
app2 = Application(company_id=company.id, user_id=1, status='applied')
db.add(app2)
db.commit()
db.refresh(app2)

er2 = ScoringService.compute_final_score(
    app2, db,
    override_cv_score=70.0,
    override_rubric_score=80.0,
    override_rubric_coverage_pct=100.0,
)
db.commit()
expected2 = round(70.0 * 0.25 + 80.0 * 0.50 + 100.0 * 0.25, 1)
print(f'With rubric: final={er2.final_score}, expected={expected2}, match={er2.final_score == expected2}')

# Verify human_integrity_score is untouched by compute_final_score
print(f'human_integrity_score on rubric app: {er2.human_integrity_score}')
print(f'"human" in score_breakdown: {"human" in (er2.score_breakdown or {})}')
print(f'"human" in weights: {"human" in weights}')

# Cleanup
for a in [app, app2]:
    for er in db.query(EvaluationResult).join(EvaluationSession).filter(EvaluationSession.application_id == a.id).all():
        db.delete(er)
    for es in db.query(EvaluationSession).filter(EvaluationSession.application_id == a.id).all():
        db.delete(es)
    db.delete(a)
db.commit()
print('Cleanup done')
