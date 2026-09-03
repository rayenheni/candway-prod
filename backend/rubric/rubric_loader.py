import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from uuid import uuid4

from sqlalchemy import func

from backend.database import SessionLocal
from backend.rubric.rubric_schema import JobRubric

logger = logging.getLogger(__name__)

_cache: Dict[str, "CachedRubric"] = {}

# Cache control constants for tests and internal use
# Maximum number of cached rubric entries before pruning
_CACHE_MAX_ENTRIES = 100
# Alias used by tests to inspect the cache directly
_CACHE = _cache


def _prune_cache() -> None:
    """Prune expired entries and enforce the maximum cache size limit.

    Entries whose ``expires_at`` is in the past are removed unconditionally,
    then if the cache still exceeds ``_CACHE_MAX_ENTRIES`` the oldest remaining
    entries are evicted.
    """
    now = datetime.utcnow()
    expired_keys = [k for k, v in _CACHE.items() if v.expires_at < now]
    for k in expired_keys:
        del _CACHE[k]
    while len(_CACHE) > _CACHE_MAX_ENTRIES:
        oldest_key = min(_CACHE.items(), key=lambda kv: kv[1].expires_at)[0]
        del _CACHE[oldest_key]


class CachedRubric:
    def __init__(self, rubric: "JobRubric", expires_at: datetime):
        self.rubric = rubric
        self.expires_at = expires_at


def _sync_rubric_to_skill_definitions(
    rubric: "JobRubric", db, company_id: Optional[int] = None
) -> None:
    """Sync rubric skill params to the skill_definitions table on save.

    For each skill in the rubric, upsert the skill_definitions row:
    - If a row exists by name, update keywords/levels/is_required/weight.
    - If missing, create a new row with a UUID.
    Caller owns the commit.
    """
    from backend.database import SkillDefinition as SkillDefinitionDB

    for cat in rubric.categories:
        for sub in cat.subcategories:
            for skill in sub.skills:
                existing = (
                    db.query(SkillDefinitionDB)
                    .filter(func.lower(SkillDefinitionDB.name) == skill.name.lower())
                    .first()
                )

                if existing:
                    existing.keywords = skill.keywords
                    existing.levels = {
                        level_name: [ld.__dict__ for ld in descriptors]
                        for level_name, descriptors in skill.levels.items()
                    }
                    existing.is_required = skill.is_required
                    existing.weight = skill.weight
                    existing.description = skill.description
                else:
                    canonical_id = str(uuid4())
                    new_def = SkillDefinitionDB(
                        id=canonical_id,
                        name=skill.name,
                        description=skill.description,
                        expected_proficiency="mid",
                        weight=skill.weight,
                        keywords=skill.keywords,
                        levels={
                            level_name: [ld.__dict__ for ld in descriptors]
                            for level_name, descriptors in skill.levels.items()
                        },
                        is_required=skill.is_required,
                        company_id=company_id,
                    )
                    db.add(new_def)
                    skill.id = canonical_id
                    logger.info(
                        f"Created canonical skill_def row for '{skill.name}' ({canonical_id})"
                    )


def _resolve_skill_definitions(
    rubric: "JobRubric", db, company_id: Optional[int] = None
) -> "JobRubric":
    """Enrich rubric skills with canonical IDs from the skill_definitions table.

    For each skill in the rubric, look up the skill_definitions table by name.
    If a canonical row exists, update the Pydantic skill's id to match.
    If missing, create a new row and assign its UUID.
    """
    from backend.database import SkillDefinition as SkillDefinitionDB
    from backend.rubric.rubric_schema import LevelDescriptor

    skill_names = set()
    for cat in rubric.categories:
        for sub in cat.subcategories:
            for skill in sub.skills:
                skill_names.add(skill.name.lower())

    if not skill_names:
        return rubric

    canonical = {}
    names_lower = list(skill_names)
    for row in (
        db.query(SkillDefinitionDB)
        .filter(func.lower(SkillDefinitionDB.name).in_(names_lower))
        .all()
    ):
        if row.name:
            canonical[row.name.lower()] = row

    for cat in rubric.categories:
        for sub in cat.subcategories:
            for skill in sub.skills:
                key = skill.name.lower()
                if key in canonical:
                    existing = canonical[key]
                    skill.id = existing.id
                    if existing.keywords is not None:
                        skill.keywords = existing.keywords
                    if existing.levels is not None:
                        skill.levels = {
                            level_name: [LevelDescriptor(**ld) for ld in descriptors]
                            for level_name, descriptors in existing.levels.items()
                        }
                    if existing.is_required is not None:
                        skill.is_required = existing.is_required
                else:
                    canonical_id = str(uuid4())
                    new_def = SkillDefinitionDB(
                        id=canonical_id,
                        name=skill.name,
                        description=skill.description,
                        expected_proficiency="mid",
                        weight=skill.weight,
                        keywords=skill.keywords,
                        levels={
                            level_name: [ld.__dict__ for ld in descriptors]
                            for level_name, descriptors in skill.levels.items()
                        },
                        is_required=skill.is_required,
                        company_id=company_id,
                    )
                    db.add(new_def)
                    skill.id = canonical_id
                    logger.info(
                        f"Created canonical skill_def row for '{skill.name}' ({canonical_id})"
                    )

    db.flush()
    return rubric


def load_rubric(job_id: int, force_refresh: bool = False):
    from backend.rubric.rubric_schema import JobRubric

    cache_key = f"job_{job_id}"

    if not force_refresh and cache_key in _cache:
        cached = _cache[cache_key]
        if cached.expires_at > datetime.utcnow():
            return cached.rubric

    db = SessionLocal()
    try:
        from backend.database import Rubric as RubricDB

        rubric_record = (
            db.query(RubricDB)
            .filter(
                RubricDB.job_id == job_id,
                RubricDB.is_active == 1,
            )
            .order_by(RubricDB.version.desc())
            .first()
        )

        if not rubric_record:
            rubric = _create_default_rubric(job_id, db)
            rubric_company_id = None
        else:
            rubric_dict = json.loads(rubric_record.criteria_json)
            if "job_id" not in rubric_dict:
                rubric_dict["job_id"] = getattr(rubric_record, "job_id", None) or job_id
            rubric = JobRubric(**rubric_dict)
            rubric_company_id = getattr(rubric_record, "company_id", None)

        rubric = _resolve_skill_definitions(rubric, db, company_id=rubric_company_id)
        db.commit()

        _cache[cache_key] = CachedRubric(
            rubric=rubric,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )

        return rubric
    finally:
        db.close()


def load_current_rubric_record(
    job_id: int,
    rubric_id: Optional[int] = None,
    company_id: Optional[int] = None,
) -> Tuple[Optional["JobRubric"], Optional[int]]:
    """Load the current rubric plus its database row id.

    When company_id is available, every rubric lookup is tenant-scoped.
    """
    from backend.rubric.rubric_schema import JobRubric

    db = SessionLocal()
    try:
        from backend.database import Rubric as RubricDB

        rubric_record = None

        # 1. Explicit rubric ID lookup
        if rubric_id:
            query = db.query(RubricDB).filter(RubricDB.id == rubric_id)

            if company_id is not None:
                query = query.filter(RubricDB.company_id == company_id)

            rubric_record = query.first()

        # 2. Current active rubric for the job
        if not rubric_record and job_id:
            query = (
                db.query(RubricDB)
                .filter(
                    RubricDB.job_id == job_id,
                    RubricDB.is_active == 1,
                )
            )

            if company_id is not None:
                query = query.filter(RubricDB.company_id == company_id)

            rubric_record = (
                query
                .order_by(RubricDB.version.desc())
                .first()
            )

        # 3. Create default rubric if none exists
        if not rubric_record:
            rubric = _create_default_rubric(job_id, db)

            query = (
                db.query(RubricDB)
                .filter(
                    RubricDB.job_id == job_id,
                    RubricDB.is_active == 1,
                )
            )

            if company_id is not None:
                query = query.filter(RubricDB.company_id == company_id)

            rubric_record = (
                query
                .order_by(RubricDB.version.desc())
                .first()
            )

            rubric_company_id = (
                getattr(rubric_record, "company_id", None)
                if rubric_record
                else company_id
            )

        else:
            rubric_dict = json.loads(rubric_record.criteria_json)

            if "job_id" not in rubric_dict:
                rubric_dict["job_id"] = (
                    getattr(rubric_record, "job_id", None) or job_id
                )

            rubric = JobRubric(**rubric_dict)
            rubric_company_id = getattr(rubric_record, "company_id", None)

        rubric = _resolve_skill_definitions(
            rubric,
            db,
            company_id=rubric_company_id,
        )

        db.commit()

        return (
            rubric,
            rubric_record.id if rubric_record else None,
        )

    finally:
        db.close()


def load_rubric_by_id(
    rubric_id: int,
    db=None,
    company_id: int | None = None,
):
    from backend.rubric.rubric_schema import JobRubric

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        from backend.database import Rubric as RubricDB

        query = db.query(RubricDB).filter(RubricDB.id == rubric_id)

        # Tenant isolation:
        # When a company scope is available, the rubric MUST belong
        # to that company. Never resolve a cross-tenant rubric by ID.
        if company_id is not None:
            query = query.filter(RubricDB.company_id == company_id)

        rubric_record = query.first()

        if not rubric_record:
            return None

        rubric_dict = json.loads(rubric_record.criteria_json)

        # Older rubric records may not include job_id in criteria_json.
        if "job_id" not in rubric_dict:
            linked_job_id = getattr(rubric_record, "job_id", None) or rubric_id
            rubric_dict["job_id"] = linked_job_id

        rubric = JobRubric(**rubric_dict)

        rubric_company_id = getattr(rubric_record, "company_id", None)
        rubric = _resolve_skill_definitions(
            rubric,
            db,
            company_id=rubric_company_id,
        )

        return rubric

    finally:
        if close_db:
            db.close()

def _create_default_rubric(job_id: int, db):
    from backend.database import Rubric as RubricDB
    from backend.rubric.rubric_schema import JobRubric

    rubric = JobRubric(job_id=job_id, version=1, categories=[])

    if job_id == 0:
        return rubric

    db_record = RubricDB(
        job_id=job_id,
        version=1,
        is_active=1,
        criteria_json=rubric.model_dump_json(),
    )
    db.add(db_record)
    db.flush()
    logger.info(f"Created empty default rubric v1 for job {job_id}")

    return rubric


def invalidate_cache(job_id: int):
    _cache.pop(f"job_{job_id}", None)


def sync_rubric_skill_definitions(
    rubric_json: str, db, company_id: Optional[int] = None
) -> None:
    """Public entrypoint: parse rubric_json and sync skills to skill_definitions.

    Called from rubric CRUD endpoints after a JobRubric row is created/updated.
    """
    from backend.rubric.rubric_schema import JobRubric

    rubric = JobRubric(**json.loads(rubric_json))
    _sync_rubric_to_skill_definitions(rubric, db, company_id=company_id)
