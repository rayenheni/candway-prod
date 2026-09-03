import json
from datetime import datetime, UTC
from backend.database import (
    SessionLocal,
    Application,
    EvaluationSession,
    EvaluationResult,
    RubricScoringDetail,
)

def seed_app99():
    db = SessionLocal()
    try:
        app = db.query(Application).filter(Application.id == 99).first()
        if not app:
            print("Application 99 not found.")
            return

        app.status = "screening"
        app.interview_state = "completed"
        app.evaluation_state = "completed"
        app.overall_score = 73.1
        app.declared_role = "Senior Growth & Digital Marketing Manager"
        app.recruiter_notes = "AI Evaluation: Candidate demonstrated excellent SEO and Analytics skills with strong overall strategic thinking. Minor gaps in PPC bid optimization and cold email automation."

        # Structured QA
        qa_pairs = [
            {
                "question": "Can you explain your experience leading SEO and content strategy for digital growth?",
                "answer": "I led a full SEO audit and content cluster strategy over 8 months. We targeted 35 high-intent keywords, fixed 200+ technical crawl errors, and boosted organic search traffic by 180%. We also integrated Screaming Frog and Ahrefs to build authoritative backlinks.",
                "score": 91,
                "type": "Technical",
                "difficulty": "Hard",
                "feedback": "Outstanding technical SEO answer with clear metrics and tools.",
                "reasoning": "Candidate articulated clear methodology and concrete ROI metrics (180% organic growth).",
                "response_time_seconds": 145
            },
            {
                "question": "How do you manage paid marketing channels (Google Ads, Meta) and optimize ROAS?",
                "answer": "I allocated 35% of overall budget to Google Search and Meta retargeting. On LinkedIn paid social, we achieved a 3.2x ROAS by dynamic audience segmenting and testing creative angles. For Google Ads, we improved ROAS from 1.8x to 2.7x.",
                "score": 75,
                "type": "Technical",
                "difficulty": "Medium",
                "feedback": "Strong performance marketing experience; room for growth in automated bidding.",
                "reasoning": "Solid grasp of ROAS optimization and channel budget split, though missing programmatic advertising experience.",
                "response_time_seconds": 120
            },
            {
                "question": "How do you use Google Analytics and Looker Studio for data-driven decisions?",
                "answer": "I set up GA4 custom event tracking across the entire funnel. Built real-time executive dashboards in Looker Studio tracking CAC, LTV, and ROAS by cohort, which allowed us to reallocate budget weekly to top-performing channels.",
                "score": 82,
                "type": "Analytics",
                "difficulty": "Medium",
                "feedback": "Excellent data visualization and analytics implementation.",
                "reasoning": "Demonstrates strong operational analytics and ability to translate metrics into executive scorecards.",
                "response_time_seconds": 110
            },
            {
                "question": "Describe your approach to market positioning and competitor analysis.",
                "answer": "I regularly conduct competitive landscape analysis by tracking positioning changes, ad copy variations, and pricing tiers of direct competitors. This informed our market entry strategy in the MENA region.",
                "score": 65,
                "type": "Strategy",
                "difficulty": "Medium",
                "feedback": "Good competitive awareness; could benefit from formal SWOT & CI frameworks.",
                "reasoning": "Practical awareness shown, but lacks formal structured competitive intelligence tooling.",
                "response_time_seconds": 95
            },
            {
                "question": "How do you approach marketing budget allocation and financial forecasting?",
                "answer": "I managed an annual marketing budget of 500k TND utilizing zero-based budgeting. We negotiated vendor contracts to save 20% on SaaS subscriptions while maintaining clear ROI benchmarks for all performance spend.",
                "score": 70,
                "type": "Management",
                "difficulty": "Hard",
                "feedback": "Solid budget discipline and vendor negotiation.",
                "reasoning": "Good budget management and cost control, limited exposure to complex scenario planning.",
                "response_time_seconds": 130
            }
        ]

        app.interview_qa_structured = json.dumps(qa_pairs)
        
        # Format interview log
        interview_log = []
        for q in qa_pairs:
            interview_log.append({"role": "assistant", "content": q["question"]})
            interview_log.append({"role": "user", "content": q["answer"]})
        app.interview_log = json.dumps(interview_log)

        # Get or create EvaluationSession
        session = db.query(EvaluationSession).filter(EvaluationSession.application_id == 99).first()
        if not session:
            session = EvaluationSession(
                application_id=99,
                company_id=app.company_id,
                status="completed",
                interview_state="completed",
                language="English"
            )
            db.add(session)
            db.flush()
        else:
            session.status = "completed"
            session.interview_state = "completed"
            session.language = "English"

        session.interview_log = interview_log

        # Score breakdown payload
        score_breakdown = {
            "overall_score": 73.1,
            "rubric_version": 1,
            "overall_coverage_pct": 100.0,
            "num_answers_scored": 5,
            "category_scores": [
                {
                    "name": "Strategy and Planning",
                    "score": 68.1,
                    "weight": 30.0,
                    "coverage_pct": 100.0,
                    "skills_scored": 4,
                    "skills_total": 4
                },
                {
                    "name": "Digital Marketing Channels",
                    "score": 70.7,
                    "weight": 40.0,
                    "coverage_pct": 100.0,
                    "skills_scored": 4,
                    "skills_total": 4
                },
                {
                    "name": "Analytics and Reporting",
                    "score": 81.4,
                    "weight": 30.0,
                    "coverage_pct": 100.0,
                    "skills_scored": 3,
                    "skills_total": 3
                }
            ],
            "skill_scores": {
                "Search Engine Optimization (SEO)": {
                    "final_score": 91,
                    "category": "Digital Marketing Channels",
                    "is_required": True,
                    "explanation": "Exceptional SEO expertise demonstrated with 180% organic traffic growth and 35 page 1 keyword rankings."
                },
                "Social Media Marketing": {
                    "final_score": 85,
                    "category": "Digital Marketing Channels",
                    "is_required": True,
                    "explanation": "Strong experience with paid social advertising on LinkedIn and Meta, achieving 3.2x ROAS."
                },
                "Google Analytics": {
                    "final_score": 82,
                    "category": "Analytics and Reporting",
                    "is_required": True,
                    "explanation": "Strong GA4 setup and tracking infrastructure experience."
                },
                "Data Analysis and Interpretation": {
                    "final_score": 82,
                    "category": "Analytics and Reporting",
                    "is_required": True,
                    "explanation": "Translates marketing metrics (CAC, LTV, ROAS) into executive-level decision dashboards."
                },
                "Reporting and Dashboard Creation": {
                    "final_score": 80,
                    "category": "Analytics and Reporting",
                    "is_required": False,
                    "explanation": "Excellent Looker Studio dashboard creation and monthly scorecard reporting."
                },
                "Market Strategy": {
                    "final_score": 75,
                    "category": "Strategy and Planning",
                    "is_required": True,
                    "explanation": "Clear understanding of MENA market growth and audience expansion tactics."
                },
                "Budgeting and Forecasting": {
                    "final_score": 70,
                    "category": "Strategy and Planning",
                    "is_required": False,
                    "explanation": "Solid 500k TND zero-based budget management and vendor contract savings."
                },
                "Campaign Optimization": {
                    "final_score": 68,
                    "category": "Digital Marketing Channels",
                    "is_required": False,
                    "explanation": "Good continuous improvement instincts across campaign channels."
                },
                "Competitor Analysis": {
                    "final_score": 65,
                    "category": "Strategy and Planning",
                    "is_required": False,
                    "explanation": "Practical competitive positioning analysis; could adopt formal SWOT/CI frameworks."
                },
                "Pay-Per-Click (PPC) Advertising": {
                    "final_score": 53,
                    "category": "Digital Marketing Channels",
                    "is_required": True,
                    "explanation": "Basic PPC experience; limited exposure to automated bidding strategies or programmatic platforms."
                },
                "Email Marketing": {
                    "final_score": 46,
                    "category": "Digital Marketing Channels",
                    "is_required": False,
                    "explanation": "Basic email lead nurturing experience, lacks advanced deliverability and cold automation setups."
                }
            },
            "gaps": [
                "Email Marketing automation & deliverability",
                "Advanced PPC automated bidding frameworks",
                "Formal Competitor Intelligence (CI) tools"
            ],
            "skill_metrics": {
                "SEO & Content": 91,
                "Paid Media & Social": 75,
                "Analytics & GA4": 82,
                "Strategy & Budget": 70,
                "Email & Automation": 46
            }
        }

        eval_res = db.query(EvaluationResult).filter(EvaluationResult.evaluation_session_id == session.id).first()
        if not eval_res:
            eval_res = EvaluationResult(
                evaluation_session_id=session.id,
                company_id=app.company_id,
                scoring_status="SCORED",
                final_score=73.1,
                rubric_score=73.1,
                rubric_coverage_pct=100.0,
                rubric_version=1,
                scoring_model="rubric",
                score_breakdown=score_breakdown,
                verdict="Recommended for Interview",
                needs_review=False
            )
            db.add(eval_res)
            db.flush()
        else:
            eval_res.scoring_status = "SCORED"
            eval_res.final_score = 73.1
            eval_res.rubric_score = 73.1
            eval_res.rubric_coverage_pct = 100.0
            eval_res.rubric_version = 1
            eval_res.scoring_model = "rubric"
            eval_res.score_breakdown = score_breakdown
            eval_res.verdict = "Recommended for Interview"
            eval_res.needs_review = False

        # Add RubricScoringDetails rows if empty
        db.query(RubricScoringDetail).filter(RubricScoringDetail.evaluation_result_id == eval_res.id).delete()
        
        details = [
            ("Search Engine Optimization (SEO)", 91.0, "Demonstrated exceptional technical SEO audit and 180% organic growth results."),
            ("Social Media Marketing", 85.0, "Solid paid social advertising return with 3.2x ROAS on LinkedIn."),
            ("Google Analytics", 82.0, "Hands-on experience setting up GA4 event tracking and conversion models."),
            ("Data Analysis and Interpretation", 82.0, "Translates marketing metrics into Looker Studio executive dashboards."),
            ("Reporting and Dashboard Creation", 80.0, "Creates clear monthly performance scorecards using structured frameworks."),
            ("Market Strategy", 75.0, "Formulated MENA regional expansion strategy with clear market positioning."),
            ("Budgeting and Forecasting", 70.0, "Managed 500k TND zero-based budget with vendor cost reductions."),
            ("Competitor Analysis", 65.0, "Monitors competitor ad copy and landing pages, but lacks formal CI tools."),
            ("Pay-Per-Click (PPC) Advertising", 53.0, "Basic ad group management, limited automated bid strategy experience."),
            ("Email Marketing", 46.0, "Basic email funnel experience, limited advanced deliverability knowledge.")
        ]

        for criterion_name, score, feedback in details:
            detail_row = RubricScoringDetail(
                evaluation_result_id=eval_res.id,
                company_id=app.company_id,
                criterion_name=criterion_name,
                score=score,
                feedback=feedback
            )
            db.add(detail_row)

        db.commit()
        print(f"Successfully seeded demo data for App 99! (Final Score: 73.1, EvaluationResult ID: {eval_res.id})")
    except Exception as e:
        db.rollback()
        print(f"Error seeding app 99: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_app99()
