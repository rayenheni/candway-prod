"""Private query builders — shared filter/join logic for metrics_repository.

No metric computation here — only query scaffolding.
"""

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query, Session

from backend.database import (
    Application,
    BatchJob,
    CompanyMember,
    EvaluationResult,
    EvaluationSession,
    Interview,
    Job,
)


def recruiter_owned_job_ids(db: Session, recruiter_id: int) -> list[int]:
    return [
        r[0]
        for r in db.query(Job.id)
        .join(CompanyMember, CompanyMember.user_id == Job.recruiter_id)
        .filter(
            CompanyMember.user_id == recruiter_id,
            CompanyMember.is_active,
            Job.deleted_at.is_(None),
        )
        .all()
    ]


def recruiter_owned_batch_ids(db: Session, recruiter_id: int) -> list[int]:
    return [
        r[0]
        for r in db.query(BatchJob.id)
        .join(CompanyMember, CompanyMember.user_id == BatchJob.recruiter_id)
        .filter(
            CompanyMember.user_id == recruiter_id,
            CompanyMember.is_active,
        )
        .all()
    ]


def base_application_query(
    db: Session,
    company_id: int,
    recruiter_id: int = None,
    exclude_orphans: bool = True,
) -> Query:
    """Canonical Application query with tenant isolation.

    Company-wide scope (recruiter_id=None):
        Application.company_id == company_id

    Recruiter scope (recruiter_id given):
        assigned_to == recruiter_id
        OR job_id IN (jobs owned via CompanyMember)
        OR batch_id IN (batches owned via CompanyMember)

    Always excludes deleted applications.
    """
    q = db.query(Application).filter(Application.company_id == company_id)

    if recruiter_id is not None:
        owned_jobs = recruiter_owned_job_ids(db, recruiter_id)
        owned_batches = recruiter_owned_batch_ids(db, recruiter_id)
        conditions = [Application.assigned_to == recruiter_id]
        if owned_jobs:
            conditions.append(Application.job_id.in_(owned_jobs))
        if owned_batches:
            conditions.append(Application.batch_id.in_(owned_batches))
        q = q.filter(or_(*conditions))

    if exclude_orphans:
        q = q.filter(
            ~and_(
                Application.job_id.is_(None),
                Application.batch_id.is_(None),
                Application.status.in_(["active", "pending"]),
            )
        )

    return q


def base_job_query(db: Session, company_id: int) -> Query:
    return db.query(Job).filter(Job.company_id == company_id)


def base_interview_query(
    db: Session, company_id: int, recruiter_id: int = None
) -> Query:
    q = (
        db.query(Interview)
        .join(Application, Interview.application_id == Application.id)
        .filter(Application.company_id == company_id)
    )
    if recruiter_id is not None:
        owned_jobs = recruiter_owned_job_ids(db, recruiter_id)
        owned_batches = recruiter_owned_batch_ids(db, recruiter_id)
        conditions = [Application.assigned_to == recruiter_id]
        if owned_jobs:
            conditions.append(Application.job_id.in_(owned_jobs))
        if owned_batches:
            conditions.append(Application.batch_id.in_(owned_batches))
        q = q.filter(or_(*conditions))
    return q


def evaluation_join(q: Query) -> Query:
    """Join EvaluationSession → EvaluationResult onto an Application query."""
    return q.outerjoin(
        EvaluationSession, EvaluationSession.application_id == Application.id
    ).outerjoin(
        EvaluationResult, EvaluationResult.evaluation_session_id == EvaluationSession.id
    )
