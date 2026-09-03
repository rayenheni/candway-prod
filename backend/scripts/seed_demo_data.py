"""
Seed comprehensive demo data for the recruiter account (user_id=13, company_id=4).
Run: python -m backend.scripts.seed_demo_data
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
from datetime import datetime, timedelta

from backend.database import SessionLocal
from backend.models import (
    Application,
    Candidate,
    Company,
    CompanyMember,
    Job,
    JobCategory,
    RecruiterProfile,
    Rubric,
    User,
)

DEMO_USER_ID = 13
DEMO_COMPANY_ID = 4


def seed():
    db = SessionLocal()
    try:
        # Verify user + company exist
        user = db.query(User).filter(User.id == DEMO_USER_ID).first()
        if not user:
            print(f"User {DEMO_USER_ID} not found")
            return
        company = db.query(Company).filter(Company.id == DEMO_COMPANY_ID).first()
        if not company:
            print(f"Company {DEMO_COMPANY_ID} not found")
            return

        # Ensure company membership
        member = (
            db.query(CompanyMember)
            .filter(
                CompanyMember.user_id == DEMO_USER_ID,
                CompanyMember.company_id == DEMO_COMPANY_ID,
            )
            .first()
        )
        if not member:
            db.add(
                CompanyMember(
                    user_id=DEMO_USER_ID, company_id=DEMO_COMPANY_ID, role="admin"
                )
            )
            db.flush()

        # Ensure recruiter profile
        profile = (
            db.query(RecruiterProfile)
            .filter(RecruiterProfile.user_id == DEMO_USER_ID)
            .first()
        )
        if not profile:
            db.add(
                RecruiterProfile(
                    user_id=DEMO_USER_ID, company_name="Candway Demo", tier="enterprise"
                )
            )
            db.flush()

        # 1. Job Categories
        categories = []
        for name in ["Engineering", "Data Science", "Product", "Design", "Marketing"]:
            existing = (
                db.query(JobCategory)
                .filter(
                    JobCategory.name == name,
                    JobCategory.company_id == DEMO_COMPANY_ID,
                )
                .first()
            )
            if not existing:
                cat = JobCategory(name=name, company_id=DEMO_COMPANY_ID)
                db.add(cat)
                db.flush()
                categories.append(cat)
            else:
                categories.append(existing)
        db.flush()
        print(f"Categories: {[c.name for c in categories]}")

        # 2. Jobs
        jobs_data = [
            {
                "title": "Senior React Engineer",
                "location": "Tunis, Tunisia",
                "type": "full-time",
                "description": "Build and maintain our React-based SaaS platform. 5+ years experience required.",
                "salary": "45,000 - 65,000 TND",
            },
            {
                "title": "Python Backend Developer",
                "location": "Remote (Tunisia)",
                "type": "full-time",
                "description": "Develop REST APIs with FastAPI. PostgreSQL and Redis experience required.",
                "salary": "35,000 - 55,000 TND",
            },
            {
                "title": "Data Scientist",
                "location": "Tunis, Tunisia",
                "type": "full-time",
                "description": "Build ML models for candidate matching and bias detection. Python, scikit-learn.",
                "salary": "50,000 - 75,000 TND",
            },
            {
                "title": "Product Designer",
                "location": "Sousse, Tunisia",
                "type": "full-time",
                "description": "Design intuitive user experiences for our ATS platform. Figma expertise required.",
                "salary": "30,000 - 48,000 TND",
            },
            {
                "title": "Marketing Lead",
                "location": "Tunis, Tunisia",
                "type": "full-time",
                "description": "Lead B2B marketing for HR tech platform. Content marketing and SEO focus.",
                "salary": "40,000 - 60,000 TND",
            },
        ]
        jobs = []
        for jd in jobs_data:
            existing = (
                db.query(Job)
                .filter(
                    Job.title == jd["title"],
                    Job.company_id == DEMO_COMPANY_ID,
                )
                .first()
            )
            if existing:
                jobs.append(existing)
                continue
            job = Job(
                title=jd["title"],
                location=jd["location"],
                type=jd["type"],
                description=jd["description"],
                salary_range=jd["salary"],
                company_name="Candway",
                company_id=DEMO_COMPANY_ID,
                recruiter_id=DEMO_USER_ID,
                is_active=True,
                version_id=1,
                created_at=datetime.utcnow() - timedelta(days=random.randint(5, 60)),
            )
            db.add(job)
            db.flush()
            jobs.append(job)
        db.flush()
        print(f"Jobs: {[j.title for j in jobs]}")

        # 3. Candidates
        candidates_data = [
            {
                "full_name": "Yasmine Gharbi",
                "email": "yasmine.gharbi@example.com",
                "phone": "+216 50 123 456",
                "headline": "Senior React Engineer",
                "bio": "5+ years building React apps. Previously at Instadeep and Expensya.",
                "skills": "React, TypeScript, Redux, GraphQL, Node.js, Docker",
                "location": "Tunis",
            },
            {
                "full_name": "Mohamed Ben Ali",
                "email": "mohamed.benali@example.com",
                "phone": "+216 52 654 321",
                "headline": "Python Backend Developer",
                "bio": "FastAPI specialist. Built APIs serving 100k+ requests/day.",
                "skills": "Python, FastAPI, PostgreSQL, Redis, Docker, AWS",
                "location": "Sousse",
            },
            {
                "full_name": "Amira Kallel",
                "email": "amira.kallel@example.com",
                "phone": "+216 55 789 012",
                "headline": "Full Stack Developer",
                "bio": "MERN stack developer with startup experience.",
                "skills": "React, Node.js, MongoDB, Express, TypeScript",
                "location": "Sfax",
            },
            {
                "full_name": "Ahmed Mejri",
                "email": "ahmed.mejri@example.com",
                "phone": "+216 58 345 678",
                "headline": "Data Scientist",
                "bio": "PhD in ML from ENIT. Published in top conferences.",
                "skills": "Python, TensorFlow, PyTorch, scikit-learn, SQL",
                "location": "Tunis",
            },
            {
                "full_name": "Sarra Ben Salah",
                "email": "sarra.bensalah@example.com",
                "phone": "+216 50 987 654",
                "headline": "Product Designer",
                "bio": "UX designer with 4 years in B2B SaaS products.",
                "skills": "Figma, Sketch, Prototyping, User Research",
                "location": "Tunis",
            },
            {
                "full_name": "Oussema Trabelsi",
                "email": "oussema.trabelsi@example.com",
                "phone": "+216 20 111 222",
                "headline": "Senior DevOps Engineer",
                "bio": "Kubernetes, CI/CD, and cloud infrastructure expert.",
                "skills": "Kubernetes, Docker, Terraform, AWS, CI/CD",
                "location": "Ariana",
            },
            {
                "full_name": "Nour Jlassi",
                "email": "nour.jlassi@example.com",
                "phone": "+216 22 333 444",
                "headline": "Marketing Specialist",
                "bio": "B2B content marketing for SaaS platforms.",
                "skills": "Content Marketing, SEO, SEM, Social Media",
                "location": "Tunis",
            },
            {
                "full_name": "Khalil Bouaziz",
                "email": "khalil.bouaziz@example.com",
                "phone": "+216 27 555 666",
                "headline": "Junior React Developer",
                "bio": "Fresh graduate from SUP'COM. Internship experience.",
                "skills": "React, JavaScript, HTML, CSS, Git",
                "location": "Tunis",
            },
            {
                "full_name": "Mariem Akkari",
                "email": "mariem.akkari@example.com",
                "phone": "+216 54 777 888",
                "headline": "Backend Developer",
                "bio": "Node.js and Express specialist.",
                "skills": "Node.js, Express, MongoDB, Redis, Docker",
                "location": "Nabeul",
            },
            {
                "full_name": "Fares Mami",
                "email": "fares.mami@example.com",
                "phone": "+216 28 999 000",
                "headline": "AI Engineer",
                "bio": "NLP and computer vision specialist.",
                "skills": "Python, NLP, Computer Vision, PyTorch, FastAPI",
                "location": "Tunis",
            },
        ]
        candidates = []
        for cd in candidates_data:
            existing = (
                db.query(Candidate)
                .filter(
                    Candidate.email == cd["email"],
                    Candidate.company_id == DEMO_COMPANY_ID,
                )
                .first()
            )
            if existing:
                candidates.append(existing)
                continue
            cand = Candidate(
                full_name=cd["full_name"],
                email=cd["email"],
                phone=cd.get("phone", ""),
                headline=cd.get("headline", ""),
                bio=cd.get("bio", ""),
                skills=cd.get("skills", ""),
                location=cd.get("location", ""),
                company_id=DEMO_COMPANY_ID,
            )
            db.add(cand)
            db.flush()
            candidates.append(cand)
        db.flush()
        print(f"Candidates: {[c.full_name for c in candidates]}")

        # 4. Applications (link candidates to jobs)
        statuses = [
            "new",
            "screened",
            "interview",
            "shortlisted",
            "offer",
            "hired",
            "rejected",
        ]
        applications = []
        for i, cand in enumerate(candidates):
            job = jobs[i % len(jobs)]
            existing = (
                db.query(Application)
                .filter(
                    Application.candidate_id == cand.id,
                    Application.job_id == job.id,
                    Application.company_id == DEMO_COMPANY_ID,
                )
                .first()
            )
            if existing:
                applications.append(existing)
                continue
            created = datetime.utcnow() - timedelta(days=random.randint(1, 30))
            status = statuses[i % len(statuses)]
            app = Application(
                candidate_id=cand.id,
                job_id=job.id,
                company_id=DEMO_COMPANY_ID,
                full_name=cand.full_name,
                email=cand.email,
                status=status,
                analysis_score=random.randint(50, 98),
                created_at=created,
                updated_at=created + timedelta(days=random.randint(0, 5)),
            )
            db.add(app)
            db.flush()
            applications.append(app)
        db.flush()
        print(f"Applications: {len(applications)} created")

        # 5. Create a simple rubric for one job
        rubric_job = jobs[0]
        existing_rubric = (
            db.query(Rubric)
            .filter(
                Rubric.job_id == rubric_job.id,
                Rubric.is_active == 1,
            )
            .first()
        )
        if not existing_rubric:
            rubric_json = {
                "job_id": rubric_job.id,
                "version": 1,
                "seniority": "senior",
                "categories": [
                    {
                        "name": "Technical Skills",
                        "weight": 40,
                        "description": "Core technical abilities",
                        "evaluation_criteria": [
                            "Code quality",
                            "Architecture",
                            "Best practices",
                        ],
                        "interview_methods": ["Coding challenge", "System design"],
                        "target_roles": ["Senior Engineer"],
                        "subcategories": [
                            {
                                "name": "Frontend",
                                "description": "React and frontend expertise",
                                "weight": 60,
                                "skills": [
                                    {
                                        "name": "React",
                                        "weight": 30,
                                        "is_required": True,
                                        "keywords": [
                                            "react",
                                            "jsx",
                                            "components",
                                            "hooks",
                                        ],
                                    },
                                    {
                                        "name": "TypeScript",
                                        "weight": 20,
                                        "is_required": True,
                                        "keywords": [
                                            "typescript",
                                            "types",
                                            "interfaces",
                                        ],
                                    },
                                    {
                                        "name": "CSS/Design",
                                        "weight": 10,
                                        "is_required": False,
                                        "keywords": ["css", "responsive", "tailwind"],
                                    },
                                ],
                            },
                            {
                                "name": "Backend",
                                "description": "API and server-side skills",
                                "weight": 40,
                                "skills": [
                                    {
                                        "name": "Node.js",
                                        "weight": 20,
                                        "is_required": True,
                                        "keywords": ["node", "express", "api"],
                                    },
                                    {
                                        "name": "GraphQL",
                                        "weight": 20,
                                        "is_required": False,
                                        "keywords": ["graphql", "apollo", "queries"],
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Soft Skills",
                        "weight": 25,
                        "description": "Interpersonal and communication skills",
                        "evaluation_criteria": [
                            "Communication",
                            "Teamwork",
                            "Leadership",
                        ],
                        "interview_methods": ["Behavioral interview"],
                        "target_roles": ["Senior Engineer", "Tech Lead"],
                        "subcategories": [
                            {
                                "name": "Communication",
                                "description": "Verbal and written communication",
                                "weight": 50,
                                "skills": [
                                    {
                                        "name": "Technical Communication",
                                        "weight": 30,
                                        "is_required": True,
                                        "keywords": ["explain", "document", "present"],
                                    },
                                    {
                                        "name": "Collaboration",
                                        "weight": 20,
                                        "is_required": True,
                                        "keywords": ["team", "collaborate", "pair"],
                                    },
                                ],
                            },
                            {
                                "name": "Leadership",
                                "description": "Mentoring and technical leadership",
                                "weight": 50,
                                "skills": [
                                    {
                                        "name": "Mentoring",
                                        "weight": 25,
                                        "is_required": False,
                                        "keywords": ["mentor", "guide", "review"],
                                    },
                                    {
                                        "name": "Decision Making",
                                        "weight": 25,
                                        "is_required": True,
                                        "keywords": [
                                            "decide",
                                            "prioritize",
                                            "tradeoff",
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Experience & Domain",
                        "weight": 35,
                        "description": "Relevant experience and domain knowledge",
                        "evaluation_criteria": [
                            "Years of experience",
                            "Domain expertise",
                            "Project complexity",
                        ],
                        "interview_methods": ["Experience review", "Portfolio review"],
                        "target_roles": ["Senior Engineer"],
                        "subcategories": [
                            {
                                "name": "Experience",
                                "description": "Professional experience",
                                "weight": 60,
                                "skills": [
                                    {
                                        "name": "SaaS Experience",
                                        "weight": 30,
                                        "is_required": True,
                                        "keywords": ["saas", "b2b", "platform"],
                                    },
                                    {
                                        "name": "System Design",
                                        "weight": 30,
                                        "is_required": True,
                                        "keywords": [
                                            "architecture",
                                            "scalable",
                                            "distributed",
                                        ],
                                    },
                                ],
                            },
                            {
                                "name": "Domain Knowledge",
                                "description": "Industry-specific knowledge",
                                "weight": 40,
                                "skills": [
                                    {
                                        "name": "HR Tech",
                                        "weight": 20,
                                        "is_required": False,
                                        "keywords": ["hr", "ats", "recruiting"],
                                    },
                                    {
                                        "name": "Agile",
                                        "weight": 20,
                                        "is_required": True,
                                        "keywords": ["agile", "scrum", "sprint"],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            }
            rubric = Rubric(
                job_id=rubric_job.id,
                version=1,
                is_active=1,
                company_id=DEMO_COMPANY_ID,
                title="Senior React Engineer - Evaluation Rubric",
                criteria_json=json.dumps(rubric_json),
                created_by=DEMO_USER_ID,
                created_at=datetime.utcnow(),
            )
            db.add(rubric)
            db.flush()
            rubric_job.rubric_id = rubric.id
            print(f"Rubric created for job: {rubric_job.title}")

        db.commit()
        print("\n[DONE] Demo data seeded successfully!")
        print(f"   - {len(jobs)} jobs")
        print(f"   - {len(candidates)} candidates")
        print(f"   - {len(applications)} applications")
        print(f"   - 1 rubric (for '{rubric_job.title}')")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
