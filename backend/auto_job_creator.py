import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.ai.llm import call_groq_cascade
from backend.database import InterviewQuestion, Job, OfferTemplate, User
from backend.database import Rubric as RubricDB
from backend.profile_helpers import get_user_company_name
from backend.subscription_service import SubscriptionService
from backend.tenant import _resolve_company_id

logger = logging.getLogger(__name__)


class AutoJobCreator:
    def __init__(self, db: Session, recruiter: User):
        self.db = db
        self.recruiter = recruiter

    async def run(
        self,
        title: str,
        skills: List[str],
        seniority: str = "mid",
        company: Optional[str] = None,
        location: Optional[str] = None,
        type_: Optional[str] = "Full-time",
        description_override: Optional[str] = None,
    ) -> dict:
        company_name = company or get_user_company_name(self.recruiter) or "My Company"
        steps = []

        description = description_override
        if not description:
            description = await self._generate_description(title, skills)
            steps.append(
                {
                    "step": "Generating job description",
                    "status": "done",
                    "data": {"description": description},
                }
            )
        else:
            steps.append({"step": "Using provided description", "status": "done"})

        rubric = await self._generate_rubric(title, skills, seniority)
        steps.append(
            {"step": "Creating scoring rubric", "status": "done", "data": rubric}
        )

        questions = await self._generate_questions(title, skills, rubric)
        steps.append(
            {
                "step": "Generating interview questions",
                "status": "done",
                "data": {"count": len(questions)},
            }
        )

        email_template = self._generate_email_template(title, company_name)
        steps.append(
            {
                "step": "Creating email templates",
                "status": "done",
                "data": email_template,
            }
        )

        scorecard = self._generate_scorecard_template(rubric)
        steps.append(
            {"step": "Creating scorecard template", "status": "done", "data": scorecard}
        )

        company_id = _resolve_company_id(self.recruiter, self.db)
        if company_id is None:
            raise ValueError(
                "No active company membership. Contact your admin."
            )

        job = Job(
            recruiter_id=self.recruiter.id,
            company_id=company_id,
            title=title,
            company_name=company_name,
            location=location or "Remote",
            salary_range="Competitive",
            type=type_ or "Full-time",
            description=description,
            required_skills=", ".join(skills),
        )
        self.db.add(job)

        # Consume one job slot atomically with the job creation.
        # If the quota is exhausted, rollback the entire transaction so
        # no partially-created job or related records remain.
        if not SubscriptionService.record_usage(
            self.recruiter, "create_job", self.db, commit=False
        ):
            self.db.rollback()
            raise ValueError("Job slot limit reached for your current plan.")

        self.db.flush()
        self.db.refresh(job)
        steps.append(
            {"step": "Publishing job", "status": "done", "data": {"job_id": job.id}}
        )

        rubric_id = None
        try:
            rubric_record = RubricDB(
                job_id=job.id,
                company_id=job.company_id,
                version=1,
                is_active=1,
                criteria_json=json.dumps(rubric),
                created_by=self.recruiter.id,
            )
            self.db.add(rubric_record)
            self.db.flush()
            rubric_id = rubric_record.id
        except Exception as e:
            logger.warning(f"[AUTO_JOB] Failed to save rubric: {e}")

        questions_saved = []
        try:
            for q in questions[:10]:
                iq = InterviewQuestion(
                    job_id=job.id,
                    question=q.get("question", q.get("text", "")),
                    type=q.get("type", "technical"),
                    difficulty=q.get("difficulty", seniority),
                    skill_focus=q.get("skill_focus", skills[0] if skills else ""),
                )
                self.db.add(iq)
                self.db.flush()
                questions_saved.append(iq.id)
        except Exception as e:
            logger.warning(f"[AUTO_JOB] Failed to save questions: {e}")

        email_template_id = None
        try:
            et = OfferTemplate(
                recruiter_id=self.recruiter.id,
                name=f"{title} - Invitation",
                subject=email_template.get("subject", f"Interview Invitation: {title}"),
                body=email_template.get("body", ""),
            )
            self.db.add(et)
            self.db.flush()
            email_template_id = et.id
        except Exception as e:
            logger.warning(f"[AUTO_JOB] Failed to save email template: {e}")

        self.db.commit()

        return {
            "job_id": job.id,
            "job_title": title,
            "rubric_id": rubric_id,
            "questions_count": len(questions_saved),
            "email_template_id": email_template_id,
            "scorecard_id": None,
            "steps": steps,
        }

    async def _generate_description(self, title: str, skills: List[str]) -> str:
        prompt = f"""
You are an expert HR specialist. Write a compelling job description for:
Role: {title}
Skills: {", ".join(skills)}

Return JSON only: {{"description": "Full job description with sections: About the Role, Key Responsibilities, Requirements, Why Join Us"}}
"""
        try:
            res = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True
            )
            if isinstance(res, dict):
                return res.get("description", "")
            if isinstance(res, str):
                parsed = json.loads(res)
                return parsed.get("description", "")
        except Exception as e:
            logger.error(f"[AUTO_JOB] Description generation failed: {e}")
        return (
            f"We are looking for a skilled {title} proficient in {', '.join(skills)}."
        )

    async def _generate_rubric(
        self, title: str, skills: List[str], seniority: str
    ) -> dict:
        prompt = f"""
Build a skill rubric for: {title}
Skills: {", ".join(skills)}
Seniority: {seniority}

Return JSON:
{{
  "role_title": "{title}",
  "seniority": "{seniority}",
  "categories": [
    {{
      "name": "Category Name",
      "weight": 50,
      "subcategories": [],
      "skills": [{{"name": "Skill", "weight": 25, "is_required": true, "keywords": ["kw1","kw2"]}}]
    }}
  ],
  "suggested_extra_skills": []
}}
"""
        try:
            res = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True
            )
            if isinstance(res, dict) and "categories" in res:
                return res
            if isinstance(res, str):
                return json.loads(res)
        except Exception as e:
            logger.error(f"[AUTO_JOB] Rubric generation failed: {e}")
        return {
            "role_title": title,
            "seniority": seniority,
            "categories": [
                {
                    "name": "Core Skills",
                    "weight": 50,
                    "subcategories": [],
                    "skills": [
                        {
                            "name": s,
                            "weight": 50 // len(skills),
                            "is_required": True,
                            "keywords": [s.lower()],
                        }
                        for s in skills[:4]
                    ],
                },
                {
                    "name": "Domain Knowledge",
                    "weight": 30,
                    "subcategories": [],
                    "skills": [
                        {
                            "name": f"{title} Fundamentals",
                            "weight": 30,
                            "is_required": True,
                            "keywords": [title.lower()],
                        }
                    ],
                },
                {
                    "name": "Tools & Workflow",
                    "weight": 20,
                    "subcategories": [],
                    "skills": [
                        {
                            "name": "Collaboration",
                            "weight": 10,
                            "is_required": False,
                            "keywords": ["git", "agile"],
                        },
                        {
                            "name": "Communication",
                            "weight": 10,
                            "is_required": False,
                            "keywords": ["communication", "team"],
                        },
                    ],
                },
            ],
            "suggested_extra_skills": ["Mentoring", "Code Review", "Documentation"],
        }

    async def _generate_questions(
        self, title: str, skills: List[str], rubric: dict
    ) -> list:
        skill_names = [
            s["name"]
            for cat in rubric.get("categories", [])
            for s in cat.get("skills", [])
        ]
        all_skills = list(set(skills + skill_names))[:8]
        prompt = f"""
Generate 5-8 interview questions for {title}.
Skills to cover: {", ".join(all_skills)}

Return JSON: {{"questions": [
  {{"question": "question text", "type": "technical|behavioral|scenario", "difficulty": "junior|mid|senior", "skill_focus": "skill name"}}
]}}
"""
        try:
            res = await call_groq_cascade(
                [{"role": "user", "content": prompt}], json_mode=True
            )
            if isinstance(res, dict):
                return res.get("questions", [])
            if isinstance(res, str):
                parsed = json.loads(res)
                return parsed.get("questions", [])
        except Exception as e:
            logger.error(f"[AUTO_JOB] Questions generation failed: {e}")
        return [
            {
                "question": f"Describe your experience with {s}.",
                "type": "technical",
                "difficulty": "mid",
                "skill_focus": s,
            }
            for s in skills[:5]
        ]

    def _generate_email_template(self, title: str, company: str) -> dict:
        return {
            "subject": f"Interview Invitation: {title} position at {company}",
            "body": f"""<p>Dear {{candidate_name}},</p>
<p>Thank you for your interest in the {title} position at {company}.</p>
<p>We were impressed by your profile and would like to invite you to complete an AI-powered interview at your convenience.</p>
<p><strong>Position:</strong> {title}</p>
<p><strong>Company:</strong> {company}</p>
<p>The interview takes approximately 20-30 minutes and consists of scenario-based questions tailored to your skills.</p>
<p>Click the link below to start your interview:</p>
<p><a href="{{interview_link}}">Start Your Interview</a></p>
<p>Best regards,<br>The {company} Team</p>""",
        }

    def _generate_scorecard_template(self, rubric: dict) -> dict:
        categories = rubric.get("categories", [])
        return {
            "name": "Standard Scorecard",
            "categories": [
                {
                    "name": c.get("name", "Category"),
                    "weight": c.get("weight", 0),
                    "max_score": 100,
                    "criteria": [s.get("name", "") for s in c.get("skills", [])],
                }
                for c in categories
            ],
        }
