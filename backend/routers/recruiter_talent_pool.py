"""
Talent Pool Management API — /api/v1/recruiter/talent-pools
----------------------------------------------------------
CRUD for curated candidate pools; requires recruiter auth.
"""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.database import User
from backend.dependencies import get_db, require_recruiter
from backend.models.ats.candidate import Candidate
from backend.models.ats.talent_pool import TalentPool, TalentPoolCandidate
from backend.tenant import get_current_company_id

router = APIRouter(prefix="/recruiter/talent-pools", tags=["Recruiter TalentPools"])


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ── Schemas ──────────────────────────────────────────────────────────


class PoolCreate(BaseModel):
    name: str
    description: Optional[str] = None


class PoolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PoolCandidateAdd(BaseModel):
    candidate_id: int
    notes: Optional[str] = None


class PoolCandidateOut(BaseModel):
    id: int
    candidate_id: int
    full_name: Optional[str] = None
    email: str
    headline: Optional[str] = None
    skills: Optional[str] = None
    notes: Optional[str] = None
    added_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PoolOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    candidate_count: int = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("")
async def list_pools(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    q = db.query(TalentPool).filter(
        TalentPool.company_id == company_id,
        TalentPool.deleted_at.is_(None),
    )
    total = q.count()
    pools = (
        q.order_by(TalentPool.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    result = []
    for p in pools:
        cnt = (
            db.query(func.count(TalentPoolCandidate.id))
            .filter(
                TalentPoolCandidate.talent_pool_id == p.id,
                TalentPoolCandidate.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )
        result.append(
            PoolOut(
                id=p.id,
                name=p.name,
                description=p.description,
                candidate_count=cnt,
                created_by=p.created_by,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pools": [r.model_dump() for r in result],
    }


@router.post("", status_code=201)
async def create_pool(
    body: PoolCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)

    existing = (
        db.query(TalentPool)
        .filter(
            TalentPool.company_id == company_id,
            TalentPool.name == body.name,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="A talent pool with this name already exists"
        )

    pool = TalentPool(
        company_id=company_id,
        name=body.name,
        description=body.description,
        created_by=user.id,
    )
    db.add(pool)
    db.commit()
    db.refresh(pool)
    return {
        "success": True,
        "id": pool.id,
        "pool": PoolOut(
            id=pool.id,
            name=pool.name,
            description=pool.description,
            created_by=pool.created_by,
            created_at=pool.created_at,
            updated_at=pool.updated_at,
        ).model_dump(),
    }


@router.get("/{pool_id}")
async def get_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    pool = (
        db.query(TalentPool)
        .filter(
            TalentPool.id == pool_id,
            TalentPool.company_id == company_id,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if not pool:
        raise HTTPException(status_code=404, detail="Talent pool not found")

    cnt = (
        db.query(func.count(TalentPoolCandidate.id))
        .filter(
            TalentPoolCandidate.talent_pool_id == pool.id,
            TalentPoolCandidate.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )

    return PoolOut(
        id=pool.id,
        name=pool.name,
        description=pool.description,
        candidate_count=cnt,
        created_by=pool.created_by,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
    ).model_dump()


@router.put("/{pool_id}")
async def update_pool(
    pool_id: int,
    body: PoolUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    pool = (
        db.query(TalentPool)
        .filter(
            TalentPool.id == pool_id,
            TalentPool.company_id == company_id,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if not pool:
        raise HTTPException(status_code=404, detail="Talent pool not found")

    if body.name is not None:
        dup = (
            db.query(TalentPool)
            .filter(
                TalentPool.company_id == company_id,
                TalentPool.name == body.name,
                TalentPool.id != pool_id,
                TalentPool.deleted_at.is_(None),
            )
            .first()
        )
        if dup:
            raise HTTPException(
                status_code=409, detail="A talent pool with this name already exists"
            )
        pool.name = body.name
    if body.description is not None:
        pool.description = body.description
    pool.updated_at = _utcnow()
    db.commit()
    db.refresh(pool)
    return {
        "success": True,
        "pool": PoolOut(
            id=pool.id,
            name=pool.name,
            description=pool.description,
            created_by=pool.created_by,
            created_at=pool.created_at,
            updated_at=pool.updated_at,
        ).model_dump(),
    }


@router.delete("/{pool_id}")
async def delete_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    pool = (
        db.query(TalentPool)
        .filter(
            TalentPool.id == pool_id,
            TalentPool.company_id == company_id,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if not pool:
        raise HTTPException(status_code=404, detail="Talent pool not found")

    pool.deleted_at = _utcnow()
    db.commit()
    return {"success": True}


@router.get("/{pool_id}/candidates")
async def list_pool_candidates(
    pool_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    pool = (
        db.query(TalentPool)
        .filter(
            TalentPool.id == pool_id,
            TalentPool.company_id == company_id,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if not pool:
        raise HTTPException(status_code=404, detail="Talent pool not found")

    q = (
        db.query(TalentPoolCandidate)
        .options(joinedload(TalentPoolCandidate.candidate))
        .filter(
            TalentPoolCandidate.talent_pool_id == pool_id,
            TalentPoolCandidate.deleted_at.is_(None),
        )
    )
    total = q.count()
    items = (
        q.order_by(TalentPoolCandidate.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    candidates = []
    for tpc in items:
        c = tpc.candidate
        candidates.append(
            PoolCandidateOut(
                id=tpc.id,
                candidate_id=tpc.candidate_id,
                full_name=c.full_name if c else None,
                email=c.email if c else "",
                headline=c.headline if c else None,
                skills=c.skills if c else None,
                notes=tpc.notes,
                added_at=tpc.created_at,
            ).model_dump()
        )

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "candidates": candidates,
    }


@router.post("/{pool_id}/candidates", status_code=201)
async def add_pool_candidate(
    pool_id: int,
    body: PoolCandidateAdd,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    pool = (
        db.query(TalentPool)
        .filter(
            TalentPool.id == pool_id,
            TalentPool.company_id == company_id,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if not pool:
        raise HTTPException(status_code=404, detail="Talent pool not found")

    candidate = (
        db.query(Candidate)
        .filter(
            Candidate.id == body.candidate_id,
            Candidate.company_id == company_id,
        )
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    dup = (
        db.query(TalentPoolCandidate)
        .filter(
            TalentPoolCandidate.talent_pool_id == pool_id,
            TalentPoolCandidate.candidate_id == body.candidate_id,
            TalentPoolCandidate.deleted_at.is_(None),
        )
        .first()
    )
    if dup:
        raise HTTPException(
            status_code=409, detail="Candidate already in this talent pool"
        )

    tpc = TalentPoolCandidate(
        talent_pool_id=pool_id,
        company_id=company_id,
        candidate_id=body.candidate_id,
        notes=body.notes,
        added_by=user.id,
    )
    db.add(tpc)
    db.commit()
    db.refresh(tpc)
    return {"success": True, "id": tpc.id}


@router.delete("/{pool_id}/candidates/{candidate_id}")
async def remove_pool_candidate(
    pool_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_recruiter),
):
    company_id = get_current_company_id(user, db)
    tpc = (
        db.query(TalentPoolCandidate)
        .join(TalentPool)
        .filter(
            TalentPoolCandidate.talent_pool_id == pool_id,
            TalentPoolCandidate.candidate_id == candidate_id,
            TalentPoolCandidate.deleted_at.is_(None),
            TalentPool.company_id == company_id,
            TalentPool.deleted_at.is_(None),
        )
        .first()
    )
    if not tpc:
        raise HTTPException(status_code=404, detail="Pool candidate not found")

    tpc.deleted_at = _utcnow()
    db.commit()
    return {"success": True}
