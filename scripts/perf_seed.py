"""Prepare a throwaway SQLite database for the CI load test.

The performance job boots the real app and drives it with locust
(backend/tests/load_test.py). Without a schema every DB-backed endpoint
returned 500, and without accounts every authenticated scenario got 401, so
the job could only fail. This script creates the schema and the fixed
accounts the locust scenarios log in with.

Refuses to run against anything but SQLite: it must never touch a real DB.

Usage (same DATABASE_URL as the app):
    DATABASE_URL=sqlite:///./perf_test.db python scripts/perf_seed.py
"""

from __future__ import annotations

import os
import sys

CANDIDATE = ("candidate@test.com", "testpass123")
RECRUITER = ("recruiter@techcorp.com", "recruiter123")
# Fixed id so load_test.py can address the candidate's interview directly.
INTERVIEW_APP_ID = 900001


def main() -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("sqlite"):
        print(f"perf_seed: refusing non-SQLite DATABASE_URL ({url.split(':', 1)[0]})")
        return 2

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.database import (
        Application,
        Base,
        Company,
        CompanyMember,
        Job,
        SessionLocal,
        User,
        engine,
    )
    from backend.dependencies import pwd_context

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == "perf-co").first()
        if company is None:
            company = Company(name="Perf Co", slug="perf-co")
            db.add(company)
            db.flush()

        def user(email: str, password: str, role: str) -> User:
            existing = db.query(User).filter(User.email == email).first()
            if existing is not None:
                return existing
            u = User(
                email=email,
                name=f"Load Test {role.title()}",
                hashed_password=pwd_context.hash(password),
                role=role,
                email_verified=True,
            )
            db.add(u)
            db.flush()
            return u

        candidate = user(*CANDIDATE, "candidate")
        recruiter = user(*RECRUITER, "recruiter")
        if (
            db.query(CompanyMember)
            .filter(CompanyMember.user_id == recruiter.id)
            .first()
            is None
        ):
            db.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=recruiter.id,
                    role="admin",
                    is_active=True,
                )
            )
        job = db.query(Job).filter(Job.company_id == company.id).first()
        if job is None:
            job = Job(
                title="Load Test Engineer",
                recruiter_id=recruiter.id,
                company_id=company.id,
            )
            db.add(job)
            db.flush()
        if db.get(Application, INTERVIEW_APP_ID) is None:
            db.add(
                Application(
                    id=INTERVIEW_APP_ID,
                    full_name="Load Test Candidate",
                    email=CANDIDATE[0],
                    declared_role="Engineer",
                    status="interviewing",
                    job_id=job.id,
                    company_id=company.id,
                    user_id=candidate.id,
                )
            )
        db.commit()
    finally:
        db.close()

    print("perf_seed: schema created, load-test accounts ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
