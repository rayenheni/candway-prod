"""Seed demo data for Recruiter Interview Analysis on application 99.

Creates: EvaluationSession (update), EvaluationResult, RubricScoringDetail,
InterviewTurn, and updates Application status.

Usage: python -m backend.scripts.seed_demo_interview_analysis
"""
import json
import sys
from datetime import datetime, timedelta, timezone

from backend.database import SessionLocal
from backend.models.ats.application import Application
from backend.models.evaluation.evaluation import EvaluationSession, EvaluationResult
from backend.models.evaluation.scoring import Rubric, RubricScoringDetail
from backend.models.evaluation.ai import InterviewTurn

APP_ID = 99
COMPANY_ID = 4
SESSION_ID = 59
RUBRIC_ID = 16
USER_ID = 7  # candidate@test.com


def seed():
    db = SessionLocal()
    try:
        # ── Verify prerequisites ──
        app = db.query(Application).filter(Application.id == APP_ID).first()
        if not app:
            print(f"ERROR: Application {APP_ID} not found")
            sys.exit(1)
        print(f"Application {APP_ID}: status={app.status}, job_id={app.job_id}")

        session = db.query(EvaluationSession).filter(EvaluationSession.id == SESSION_ID).first()
        if not session:
            print(f"ERROR: EvaluationSession {SESSION_ID} not found")
            sys.exit(1)
        print(f"Session {SESSION_ID}: status={session.status}")

        existing_result = db.query(EvaluationResult).filter(
            EvaluationResult.evaluation_session_id == SESSION_ID
        ).first()
        if existing_result:
            print(f"EvaluationResult {existing_result.id} already exists - deleting to re-seed")
            db.delete(existing_result)
            db.flush()

        existing_turns = db.query(InterviewTurn).filter(
            InterviewTurn.evaluation_session_id == SESSION_ID
        ).all()
        if existing_turns:
            print(f"Deleting {len(existing_turns)} existing InterviewTurns")
            for t in existing_turns:
                db.delete(t)
            db.flush()

        # ── Timestamps ──
        now = datetime.now(timezone.utc)
        interview_start = now - timedelta(hours=1, minutes=30)
        interview_end = now - timedelta(hours=1, minutes=15)

        # ── Demo Interview Q&A (5 turns, realistic marketing manager answers) ──
        turns_data = [
            {
                "turn": 1,
                "question": "Can you walk me through your experience with developing a comprehensive digital marketing strategy? How do you align it with business objectives?",
                "answer": "In my previous role at TechCorp, I developed a 12-month digital marketing strategy that aligned with the company's goal of expanding into the MENA market. I started by conducting thorough market research — analyzing competitor positioning, identifying target audience segments through customer data, and mapping the buyer journey. The strategy integrated content marketing, paid social campaigns on LinkedIn and Meta, and an SEO program targeting high-intent keywords. We set quarterly KPIs tied to pipeline generation, and I worked closely with the sales team to ensure MQL-to-SQL conversion targets were met. Within 6 months, we saw a 40% increase in qualified leads and a 25% reduction in cost per acquisition.",
                "score": 82.0,
                "feedback": "Strong strategic thinking with clear business alignment. Demonstrated ability to connect marketing activities to revenue outcomes. Good use of data to inform strategy.",
                "quality": "strong",
                "response_time": 95.0,
                "timestamp": interview_start,
            },
            {
                "turn": 2,
                "question": "Tell me about a time you managed a marketing budget. How did you allocate resources across channels, and how did you measure ROI?",
                "answer": "I managed an annual budget of 500K TND across six channels. I used a zero-based budgeting approach each quarter, requiring justification for every spend. I allocated 35% to paid acquisition (Google Ads, Meta), 25% to content and SEO, 20% to events and partnerships, and 20% to marketing automation tools. For measurement, I built dashboards in Google Data Studio tracking CAC, LTV, ROAS by channel. When I noticed our LinkedIn campaigns had a 3.2x ROAS while Meta was at 1.8x, I reallocated 15% of Meta budget to LinkedIn, which improved overall ROAS to 2.7x. I also negotiated annual contracts with tool vendors to save 20% on SaaS costs.",
                "score": 75.0,
                "feedback": "Good budget management with specific numbers. Demonstrated data-driven reallocation decisions. Could have mentioned more about forecasting and scenario planning.",
                "quality": "medium",
                "response_time": 80.0,
                "timestamp": interview_start + timedelta(minutes=5),
            },
            {
                "turn": 3,
                "question": "How do you approach SEO strategy? Can you give an example of a successful SEO campaign you led?",
                "answer": "I take a holistic approach to SEO — combining technical optimization, content strategy, and link building. At my previous company, I led a project to rebuild our entire content hub. I started with a technical audit using Screaming Frog and Ahrefs, fixing 200+ crawl errors, improving Core Web Vitals, and implementing structured data. Then I developed a content cluster strategy around our core product categories, creating 50+ pieces of pillar and supporting content. I also built relationships with industry publications for backlinks. Over 8 months, organic traffic increased by 180%, and we ranked on page 1 for 35 high-intent keywords. Organic became our #1 lead source, contributing 45% of total pipeline.",
                "score": 91.0,
                "feedback": "Excellent SEO knowledge with impressive, quantifiable results. Demonstrated both technical and content expertise. Strong understanding of the full SEO funnel.",
                "quality": "strong",
                "response_time": 75.0,
                "timestamp": interview_start + timedelta(minutes=10),
            },
            {
                "turn": 4,
                "question": "Describe your experience with marketing analytics and reporting. What KPIs do you track, and how do you present data to leadership?",
                "answer": "I'm very data-driven in my approach. I set up the analytics infrastructure at my last company, implementing GA4, configuring conversion tracking, and building Looker Studio dashboards. The KPIs I track include: traffic and engagement metrics, conversion rates by funnel stage, CAC and LTV by channel, email open/click rates, and campaign-specific ROAS. For leadership reporting, I created a monthly marketing scorecard that tells a story — not just numbers but insights and recommendations. I use the PACE framework: Performance vs targets, Analysis of variances, Corrective actions, and Expected outcomes. When presenting to the board, I focus on marketing's contribution to revenue and pipeline, translating marketing metrics into business language.",
                "score": 78.0,
                "feedback": "Solid analytics experience with good tool knowledge. The PACE framework is a nice touch for executive communication. Could have given more specific examples of data-driven decisions that changed strategy direction.",
                "quality": "medium",
                "response_time": 70.0,
                "timestamp": interview_start + timedelta(minutes=15),
            },
            {
                "turn": 5,
                "question": "How would you handle a situation where a major campaign is underperforming? Walk me through your diagnostic and optimization process.",
                "answer": "I follow a systematic diagnostic approach. First, I establish whether the underperformance is real or a measurement issue — checking tracking implementation and comparing against benchmarks. Assuming it's real, I analyze the funnel to identify where the drop-off occurs: awareness (impressions, reach), consideration (CTR, engagement), or conversion (landing page, offer). For example, we had a product launch campaign where leads were coming in but MQL conversion was 60% below target. I dug into the data and found that our targeting was too broad — we were attracting students and hobbyists instead of professionals. I narrowed the audience by job title and industry, improved the lead magnets to be more relevant, and added a qualification step. Within 3 weeks, MQL conversion improved by 45%. I also believe in transparent communication — I flagged the issue early to stakeholders with a clear recovery plan.",
                "score": 85.0,
                "feedback": "Excellent structured thinking and problem-solving. Strong real example with clear metrics. Good balance of analytical approach and stakeholder management.",
                "quality": "strong",
                "response_time": 90.0,
                "timestamp": interview_start + timedelta(minutes=20),
            },
        ]

        # ── Rubric skill scores (11 skills, realistic demo data matching screenshot style) ──
        skill_scores = {
            "Market Research": {
                "base_score": 85, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 85, "confidence_range": [78, 92],
                "evidence": [
                    "Conducted thorough market research analyzing competitor positioning and audience segments",
                    "Used customer data to map the buyer journey for MENA market expansion"
                ],
                "matched_level": "intermediate level demonstrated with advanced indicators",
                "matched_keywords": ["market research", "competitor", "audience segments", "buyer journey"],
                "missing_competencies": ["formal competitive intelligence framework"],
                "explanation": "Market Research score = 85. Strong evidence of practical research skills including competitor analysis and audience segmentation. Candidate demonstrated ability to use data-driven insights to inform strategy."
            },
            "Campaign Planning": {
                "base_score": 82, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 82, "confidence_range": [74, 90],
                "evidence": [
                    "Developed 12-month digital marketing strategy with quarterly KPIs",
                    "Led product launch campaign with systematic diagnostic approach"
                ],
                "matched_level": "advanced level with strong strategic frameworks",
                "matched_keywords": ["campaign", "strategy", "KPIs", "launch", "diagnostic"],
                "missing_competencies": ["multi-touch attribution modeling"],
                "explanation": "Campaign Planning score = 82. Demonstrated strong strategic thinking with clear framework for campaign planning and optimization. Good use of data-driven approach to campaign diagnostics."
            },
            "Budgeting and Forecasting": {
                "base_score": 78, "quality": "medium", "quality_multiplier": 0.7,
                "final_score": 55, "confidence_range": [45, 65],
                "evidence": [
                    "Managed annual budget of 500K TND with zero-based budgeting approach",
                    "Negotiated vendor contracts saving 20% on SaaS costs"
                ],
                "matched_level": "intermediate level",
                "matched_keywords": ["budget", "zero-based", "ROAS", "cost"],
                "missing_competencies": ["financial forecasting models", "scenario planning"],
                "explanation": "Budgeting and Forecasting score = 55. Solid budget management with specific metrics. However, limited evidence of forecasting methodologies or scenario-based financial planning."
            },
            "Competitor Analysis": {
                "base_score": 72, "quality": "medium", "quality_multiplier": 0.7,
                "final_score": 51, "confidence_range": [41, 61],
                "evidence": [
                    "Analyzed competitor positioning as part of market research",
                    "Identified market gaps through competitive landscape analysis"
                ],
                "matched_level": "intermediate level",
                "matched_keywords": ["competitor", "positioning", "market gaps", "landscape"],
                "missing_competencies": ["formal SWOT analysis", "competitive intelligence tools"],
                "explanation": "Competitor Analysis score = 51. Shows some competitive awareness but evidence is primarily as part of broader research rather than dedicated competitor intelligence work."
            },
            "Social Media Marketing": {
                "base_score": 85, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 85, "confidence_range": [78, 92],
                "evidence": [
                    "Ran paid social campaigns on LinkedIn and Meta as part of MENA expansion",
                    "Achieved 3.2x ROAS on LinkedIn campaigns through budget reallocation",
                    "Developed multi-platform social strategy with audience segmentation"
                ],
                "matched_level": "advanced level",
                "matched_keywords": ["social media", "LinkedIn", "Meta", "paid campaigns", "ROAS", "audience"],
                "missing_competencies": ["community management"],
                "explanation": "Social Media Marketing score = 85. Strong experience with paid social advertising and performance optimization. Demonstrated ability to analyze and improve ROAS across platforms."
            },
            "Search Engine Optimization (SEO)": {
                "base_score": 91, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 91, "confidence_range": [85, 97],
                "evidence": [
                    "Led SEO project increasing organic traffic by 180% over 8 months",
                    "Implemented content cluster strategy with 50+ pieces of pillar and supporting content",
                    "Achieved page 1 rankings for 35 high-intent keywords",
                    "Fixed 200+ crawl errors and improved Core Web Vitals"
                ],
                "matched_level": "advanced level demonstrated",
                "matched_keywords": ["SEO", "organic traffic", "content clusters", "Core Web Vitals", "Screaming Frog", "Ahrefs", "structured data", "backlinks"],
                "missing_competencies": [],
                "explanation": "Search Engine Optimization (SEO) score = 91. Exceptional SEO expertise demonstrated with impressive quantifiable results. Candidate showed both technical SEO knowledge and content strategy skills. This is clearly a core strength."
            },
            "Pay-Per-Click (PPC) Advertising": {
                "base_score": 75, "quality": "medium", "quality_multiplier": 0.7,
                "final_score": 53, "confidence_range": [43, 63],
                "evidence": [
                    "Managed 35% of budget allocation to Google Ads and Meta advertising",
                    "Optimized ROAS from 1.8x to 2.7x through channel reallocation"
                ],
                "matched_level": "intermediate level",
                "matched_keywords": ["Google Ads", "Meta", "PPC", "ROAS", "paid acquisition"],
                "missing_competencies": ["advanced bid management", "programmatic advertising", "A/B testing frameworks"],
                "explanation": "Pay-Per-Click (PPC) Advertising score = 49. Basic PPC experience with good optimization instincts. However, limited evidence of advanced PPC techniques such as programmatic advertising, sophisticated bidding strategies, or structured A/B testing."
            },
            "Email Marketing": {
                "base_score": 65, "quality": "medium", "quality_multiplier": 0.7,
                "final_score": 46, "confidence_range": [36, 56],
                "evidence": [
                    "Integrated email marketing into overall automation stack",
                    "Used email campaigns for lead nurturing as part of funnel strategy"
                ],
                "matched_level": "beginner to intermediate level",
                "matched_keywords": ["email", "automation", "lead nurturing", "funnel"],
                "missing_competencies": ["advanced segmentation", "deliverability optimization", "A/B testing"],
                "explanation": "Email Marketing score = 46. Some practical email marketing experience but evidence is limited. Candidate understands email's role in the marketing funnel but has not demonstrated advanced execution skills."
            },
            "Google Analytics": {
                "base_score": 82, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 82, "confidence_range": [74, 90],
                "evidence": [
                    "Implemented GA4 with full conversion tracking",
                    "Built Looker Studio dashboards for leadership reporting"
                ],
                "matched_level": "intermediate to advanced level",
                "matched_keywords": ["GA4", "analytics", "dashboards", "Looker Studio", "conversion tracking"],
                "missing_competencies": ["custom dimension setup", "event-based tracking architecture"],
                "explanation": "Google Analytics score = 82. Strong practical GA4 experience with good dashboarding skills. Candidate demonstrated ability to set up tracking infrastructure and translate data into actionable insights."
            },
            "Data Analysis and Interpretation": {
                "base_score": 82, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 82, "confidence_range": [74, 90],
                "evidence": [
                    "Built dashboards tracking CAC, LTV, ROAS by channel",
                    "Used data insights to reallocate budget improving overall ROAS",
                    "Created monthly marketing scorecard using PACE framework"
                ],
                "matched_level": "advanced level",
                "matched_keywords": ["data analysis", "dashboards", "CAC", "LTV", "ROAS", "PACE"],
                "missing_competencies": ["predictive modeling", "SQL proficiency"],
                "explanation": "Data Analysis and Interpretation score = 82. Strong analytical skills with practical experience translating data into actionable business insights. Good understanding of marketing metrics and performance frameworks."
            },
            "Reporting and Dashboard Creation": {
                "base_score": 80, "quality": "strong", "quality_multiplier": 1.0,
                "final_score": 80, "confidence_range": [72, 88],
                "evidence": [
                    "Created monthly marketing scorecard using PACE framework",
                    "Built Looker Studio dashboards for real-time performance tracking",
                    "Presented data to board in business language"
                ],
                "matched_level": "advanced level",
                "matched_keywords": ["reporting", "dashboard", "scorecard", "Looker Studio", "PACE framework", "board"],
                "missing_competencies": ["automated reporting pipelines"],
                "explanation": "Reporting and Dashboard Creation score = 80. Excellent reporting skills with structured frameworks. Candidate creates meaningful, executive-ready reports and translates marketing metrics into business outcomes."
            },
        }

        # ── Compute category scores ──
        categories_config = [
            {
                "name": "Strategy and Planning",
                "weight": 30.0,
                "skills": ["Market Research", "Campaign Planning", "Budgeting and Forecasting", "Competitor Analysis"],
                "skill_weights": [20.0, 30.0, 25.0, 25.0],
            },
            {
                "name": "Digital Marketing Channels",
                "weight": 40.0,
                "skills": ["Social Media Marketing", "Search Engine Optimization (SEO)", "Pay-Per-Click (PPC) Advertising", "Email Marketing"],
                "skill_weights": [25.0, 30.0, 20.0, 25.0],
            },
            {
                "name": "Analytics and Reporting",
                "weight": 30.0,
                "skills": ["Google Analytics", "Data Analysis and Interpretation", "Reporting and Dashboard Creation"],
                "skill_weights": [30.0, 40.0, 30.0],
            },
        ]

        category_scores = []
        for cat in categories_config:
            total_weight = sum(cat["skill_weights"])
            weighted_sum = sum(
                skill_scores[s]["final_score"] * w
                for s, w in zip(cat["skills"], cat["skill_weights"])
            )
            cat_score = round(weighted_sum / total_weight, 1)
            assessed = sum(1 for s in cat["skills"] if skill_scores[s]["final_score"] > 0)
            category_scores.append({
                "name": cat["name"],
                "score": cat_score,
                "weight": cat["weight"],
                "confidence_range": [
                    max(0, cat_score - 10),
                    min(100, cat_score + 10)
                ],
                "coverage_pct": round(assessed / len(cat["skills"]) * 100, 1),
                "skills_scored": assessed,
                "skills_total": len(cat["skills"]),
                "children": [{
                    "name": "Skills",
                    "score": cat_score,
                    "weight": 1.0,
                    "confidence_range": [
                        max(0, cat_score - 10),
                        min(100, cat_score + 10)
                    ],
                    "coverage_pct": round(assessed / len(cat["skills"]) * 100, 1),
                    "skills_scored": assessed,
                    "skills_total": len(cat["skills"]),
                    "children": None,
                }],
            })

        # Overall rubric score = weighted average of categories
        rubric_score = round(
            sum(c["score"] * c["weight"] / 100.0 for c in category_scores), 1
        )

        # Gaps: skills scoring below 55
        gaps = []
        for cat in categories_config:
            for sname, sw in zip(cat["skills"], cat["skill_weights"]):
                sdata = skill_scores[sname]
                if sdata["final_score"] < 55:
                    gaps.append({
                        "category": cat["name"],
                        "skill": sname,
                        "score": sdata["final_score"],
                        "expected": 55,
                        "gap_pct": round(55 - sdata["final_score"], 1),
                        "severity": "major" if sdata["final_score"] < 35 else "moderate",
                    })

        # Coverage
        assessed_count = sum(1 for s in skill_scores.values() if s["final_score"] > 0)
        total_skills = len(skill_scores)
        coverage_pct = round(assessed_count / total_skills * 100, 1)

        # CV score
        cv_score = 72.0

        # Final score = cv * 0.25 + rubric * 0.40 + human * 0.10 + coverage_bonus * 0.25
        coverage_bonus = min(coverage_pct * 0.10, 10.0)
        final_score = round(cv_score * 0.25 + rubric_score * 0.40 + 100.0 * 0.10 + coverage_bonus * 0.25, 1)

        # Verdict
        if final_score >= 75:
            verdict = "Strong Hire"
        elif final_score >= 60:
            verdict = "Hire"
        elif final_score >= 45:
            verdict = "Consider"
        else:
            verdict = "Low Priority"

        print(f"\nComputed scores:")
        print(f"  CV Score: {cv_score}")
        print(f"  Rubric Score: {rubric_score}")
        print(f"  Coverage: {coverage_pct}% ({assessed_count}/{total_skills} skills)")
        print(f"  Final Score: {final_score}")
        print(f"  Verdict: {verdict}")
        for c in category_scores:
            print(f"  Category '{c['name']}': {c['score']}%")
        print(f"  Gaps: {len(gaps)}")

        # ── Build score_breakdown JSON ──
        skill_scores_for_json = {}
        for sname, sdata in skill_scores.items():
            skill_scores_for_json[sname.lower()] = {
                "skill_name": sname,
                "skill_id": f"demo-{sname.lower().replace(' ', '-').replace('(', '').replace(')', '')}",
                "base_score": sdata["base_score"],
                "quality": sdata["quality"],
                "quality_multiplier": sdata["quality_multiplier"],
                "final_score": sdata["final_score"],
                "confidence_range": sdata["confidence_range"],
                "evidence": sdata["evidence"],
                "matched_level": sdata["matched_level"],
                "matched_keywords": sdata["matched_keywords"],
                "missing_competencies": sdata["missing_competencies"],
                "explanation": sdata["explanation"],
            }

        score_breakdown = {
            "cv": cv_score,
            "rubric": rubric_score,
            "coverage_pct": coverage_pct,
            "final_score": final_score,
            "has_rubric": True,
            "cv_only": False,
            "application_id": APP_ID,
            "rubric_version": 1,
            "overall_score": rubric_score,
            "confidence_range": [max(0, rubric_score - 12), min(100, rubric_score + 12)],
            "category_scores": category_scores,
            "skill_scores": skill_scores_for_json,
            "gaps": gaps,
            "num_answers_scored": len(turns_data),
            "overall_coverage_pct": coverage_pct,
            "skill_metrics": {
                "Strategic Thinking": 75.0,
                "Digital Expertise": 68.0,
                "Analytical Skills": 72.0,
                "Communication": 80.0,
                "Problem Solving": 83.0,
            },
        }

        # ══════════════════════════════════════════════
        # 1. INSERT EvaluationResult
        # ══════════════════════════════════════════════
        eval_result = EvaluationResult(
            evaluation_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            rubric_id=RUBRIC_ID,
            rubric_version=1,
            cv_score=cv_score,
            rubric_score=rubric_score,
            human_integrity_score=100.0,
            rubric_coverage_pct=coverage_pct,
            scoring_status="SCORED",
            final_score=final_score,
            confidence_lower=max(0, rubric_score - 12),
            confidence_upper=min(100, rubric_score + 12),
            verdict=verdict,
            scoring_model="ai",
            needs_review=False,
            score_breakdown=score_breakdown,
            computed_at=now,
            computed_by="ai",
        )
        db.add(eval_result)
        db.flush()
        print(f"\nCreated EvaluationResult id={eval_result.id}")

        # ══════════════════════════════════════════════
        # 2. INSERT RubricScoringDetail rows (one per skill)
        # ══════════════════════════════════════════════
        # Map skills to the question that best elicited evidence
        skill_to_question_idx = {
            "Market Research": 0,
            "Campaign Planning": 0,
            "Budgeting and Forecasting": 1,
            "Competitor Analysis": 0,
            "Social Media Marketing": 0,
            "Search Engine Optimization (SEO)": 2,
            "Pay-Per-Click (PPC) Advertising": 1,
            "Email Marketing": 1,
            "Google Analytics": 3,
            "Data Analysis and Interpretation": 1,
            "Reporting and Dashboard Creation": 3,
        }

        # Rubric weights from criteria_json
        rubric_skill_weights = {
            "Market Research": 20.0,
            "Campaign Planning": 30.0,
            "Budgeting and Forecasting": 25.0,
            "Competitor Analysis": 25.0,
            "Social Media Marketing": 25.0,
            "Search Engine Optimization (SEO)": 30.0,
            "Pay-Per-Click (PPC) Advertising": 20.0,
            "Email Marketing": 25.0,
            "Google Analytics": 30.0,
            "Data Analysis and Interpretation": 40.0,
            "Reporting and Dashboard Creation": 30.0,
        }

        rsd_count = 0
        for sname, sdata in skill_scores.items():
            q_idx = skill_to_question_idx.get(sname, 0)
            turn = turns_data[q_idx]
            rsd = RubricScoringDetail(
                company_id=COMPANY_ID,
                evaluation_result_id=eval_result.id,
                criterion_name=sname,
                criterion_key=None,
                question=turn["question"],
                answer=turn["answer"],
                score=float(sdata["final_score"]),
                weight=rubric_skill_weights.get(sname, 1.0),
                max_score=100.0,
                feedback=sdata["explanation"],
                source="ai",
            )
            db.add(rsd)
            rsd_count += 1
        db.flush()
        print(f"Created {rsd_count} RubricScoringDetail rows")

        # ══════════════════════════════════════════════
        # 3. INSERT InterviewTurn rows
        # ══════════════════════════════════════════════
        turn_count = 0
        for t in turns_data:
            ts = t["timestamp"]
            turn = InterviewTurn(
                company_id=COMPANY_ID,
                application_id=None,
                evaluation_session_id=SESSION_ID,
                user_id=USER_ID,
                turn_number=t["turn"],
                question=t["question"],
                answer=t["answer"],
                score=t["score"],
                feedback=t["feedback"],
                reasoning=None,
                quality=t["quality"],
                type="behavioral",
                difficulty="medium",
                response_time_seconds=t["response_time"],
                status="answered",
                question_timestamp=ts,
                answer_timestamp=ts + timedelta(seconds=t["response_time"]),
            )
            db.add(turn)
            turn_count += 1
        db.flush()
        print(f"Created {turn_count} InterviewTurn rows")

        # ══════════════════════════════════════════════
        # 4. UPDATE EvaluationSession
        # ══════════════════════════════════════════════
        session.status = "completed"
        session.interview_state = "completed"
        session.started_at = interview_start
        session.completed_at = interview_end
        session.interview_progress = 100
        session.interview_time_left = 1200
        session.interview_turn_seq = 5
        session.interview_log = json.dumps([
            {"role": "system", "content": "Interview started for Marketing Manager position."},
            *[{
                "role": "assistant",
                "content": t["question"],
                "timestamp": t["timestamp"].isoformat(),
            } for t in turns_data],
            *[{
                "role": "user",
                "content": t["answer"],
                "timestamp": (t["timestamp"] + timedelta(seconds=t["response_time"])).isoformat(),
            } for t in turns_data],
        ])
        print(f"Updated EvaluationSession {SESSION_ID} to completed")

        # ══════════════════════════════════════════════
        # 5. UPDATE Application
        # ══════════════════════════════════════════════
        app.status = "analyzed"
        app.evaluation_state = "completed"
        app.evaluation_completed_at = now
        app.final_eval_timestamp = now
        print(f"Updated Application {APP_ID} status to analyzed")

        # ── Commit ──
        db.commit()
        print(f"\n[OK] Demo data seeded successfully for Application {APP_ID}")
        print(f"   Visit http://127.0.0.1:8003/candidates/{APP_ID} as recruiter@candway.dev")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
