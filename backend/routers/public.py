import json
import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from backend.database import (
    Application,
    BlogPost,
    Category,
    Course,
    Job,
    JobNiceToHave,
    JobRoleOverview,
    Opportunity,
    Rubric,
    SalesLead,
    User,
)
from backend.dependencies import get_db
from backend.security import sanitize_rich_text
from sqlalchemy import func

router = APIRouter(tags=["public"])


def _job_logo_placeholder(name: str) -> str:
    safe = name or "Company"
    return f"https://ui-avatars.com/api/?name={safe}&background=random&color=fff"


def _job_company_name(job, recruiter) -> str:
    """Resolve a display company name for a job.

    Order: job free-text company_name → recruiter profile company name →
    neutral placeholder. Never returns blank so orphan jobs (no tenant
    Company row, no free-text name) still display a readable company.
    """
    if getattr(job, "company_name", None):
        return job.company_name
    if recruiter is not None:
        try:
            from backend.profile_helpers import get_user_company_name

            name = get_user_company_name(recruiter)
            if name:
                return name
        except Exception:
            pass
    return "Company"


def _resolve_job_company(job):
    """Resolve the real posting company (tenant record) for a Job.

    Returns authoritative company name / logo / domain when the Job is
    company-scoped, falling back to the job's free-text company_name, then
    the recruiter profile company name, then a placeholder avatar.
    """
    company = getattr(job, "company", None)
    recruiter = getattr(job, "recruiter", None)
    if company is not None:
        name = company.name or _job_company_name(job, recruiter)
        logo = company.logo_url
        if not logo:
            # Legacy logos were stored on the recruiter profile before the
            # company-level column existed; mirror them here.
            if recruiter is not None:
                logo = _get_recruiter_company_logo(recruiter)
        return {
            "company_id": company.id,
            "company": name,
            "logo_url": logo or _job_logo_placeholder(name),
            "company_website": company.domain,
            "company_verified": company.kyb_status == "approved",
        }
    name = _job_company_name(job, recruiter)
    logo = _get_recruiter_company_logo(recruiter) if recruiter is not None else None
    return {
        "company_id": None,
        "company": name,
        "logo_url": logo or _job_logo_placeholder(name),
        "company_website": None,
        "company_verified": False,
    }


def _strip_html(text) -> str:
    import re as _re

    if not text:
        return ""
    return _re.sub(r"<[^>]+>", " ", text).strip()


def _paragraphs(text) -> list:
    """Split sanitized rich text into readable paragraphs."""
    import re as _re

    if not text:
        return []
    normalized = _re.sub(r"</(p|h1|h2|h3|h4)>", "\n\n", text, flags=_re.IGNORECASE)
    normalized = _re.sub(r"<(li|br)>", "\n", normalized, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"<[^>]+>", " ", normalized)
    blocks = [_re.sub(r"\s+", " ", b).strip() for b in cleaned.split("\n\n")]
    return [b for b in blocks if b]


def _split_lines(text) -> list:
    if not text:
        return []
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _rubric_criteria(db, job) -> list:
    """Return rubric categories as [{name, weight}] from a linked rubric."""
    rubric = None
    if getattr(job, "rubric_id", None):
        query = db.query(Rubric).filter(
            Rubric.id == job.rubric_id,
        )

        # Public job data must only resolve the rubric linked to the
        # same tenant as the published job. This prevents a stale or
        # manipulated rubric_id from exposing another company's rubric.
        if getattr(job, "company_id", None) is not None:
            query = query.filter(Rubric.company_id == job.company_id)

        rubric = query.first()
    if rubric is None or not getattr(rubric, "criteria_json", None):
        return []
    raw = rubric.criteria_json
    try:
        cats = (
            json.loads(raw).get("categories", [])
            if isinstance(raw, str)
            else (raw.get("categories", []) if isinstance(raw, dict) else raw)
        )
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []
    result = []
    for cat in cats or []:
        if not isinstance(cat, dict):
            continue
        name = cat.get("name")
        weight = cat.get("weight")
        if not name:
            continue
        try:
            weight = float(weight) if weight is not None else 0.0
        except (TypeError, ValueError):
            weight = 0.0
        result.append({"name": name, "weight": weight})
    return result


def _get_recruiter_company_logo(recruiter):
    try:
        from backend.profile_helpers import get_user_company_logo_url

        return get_user_company_logo_url(recruiter)
    except Exception:
        return None


# --- PUBLIC STATS ENDPOINT ---
@router.get("/stats/public")
def get_public_stats(db: Session = Depends(get_db)):
    user_count = db.query(User).count()
    job_count = db.query(Job).filter(Job.is_active).count()
    # Real Stats
    # Count applications active today (approximate 'Interviews Today' as active applications)
    interviews_today = (
        db.query(Application)
        .filter(Application.status.in_(["interviewing", "invited", "screening"]))
        .count()
    )

    # Real Hiring Companies count
    hiring_companies = db.query(Job.company_name).distinct().count()

    return {
        "verified_talent": user_count,
        "active_jobs": job_count,
        "interviews_today": interviews_today,
        "hiring_companies": hiring_companies,
    }


# --- PUBLIC LISTINGS ENDPOINTS ---


@router.get("/jobs/")
def get_all_jobs(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    type: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns all active job listings with optional filters.
    Used by candidate job board.
    """
    query = db.query(Job).filter(Job.is_active, Job.deleted_at.is_(None))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Job.title.ilike(search_term))
            | (Job.company_name.ilike(search_term))
            | (Job.description.ilike(search_term))
            | (Job.required_skills.ilike(search_term))
        )

    if type:
        query = query.filter(Job.type == type)

    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))

    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company_name,
            "location": j.location,
            "salary_range": j.salary_range,
            "type": j.type,
            "description": j.description,
            "required_skills": j.required_skills,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "logo_url": f"https://ui-avatars.com/api/?name={j.company_name}&background=random&color=fff",
        }
        for j in jobs
    ]


@router.get("/jobs/public")
def get_public_jobs(
    category_id: int = None, search: str = None, db: Session = Depends(get_db)
):
    """Returns listings, optionally filtered by category and search text"""
    query = (
        db.query(Job)
        .filter(Job.is_active, Job.deleted_at.is_(None))
        .options(
            joinedload(Job.company),
            joinedload(Job.recruiter),
        )
    )
    if category_id:
        query = query.filter(Job.category_id == category_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Job.title.ilike(search_term))
            | (Job.company_name.ilike(search_term))
            | (Job.required_skills.ilike(search_term))
        )

    jobs = query.order_by(Job.created_at.desc()).limit(50).all()

    job_ids = [j.id for j in jobs]
    app_counts = {}
    if job_ids:
        rows = (
            db.query(Application.job_id, func.count(Application.id))
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        app_counts = {row[0]: row[1] for row in rows}

    results = []
    for j in jobs:
        company = _resolve_job_company(j)
        about = _paragraphs(j.description)
        results.append(
            {
                "id": j.id,
                "title": j.title,
                "company": company["company"],
                "company_id": company["company_id"],
                "company_website": company["company_website"],
                "company_verified": company["company_verified"],
                "location": j.location,
                "salary_range": j.salary_range,
                "type": j.type,
                "category": j.category_rel.name if j.category_rel else "General",
                "required_skills": j.required_skills,
                "summary": about[0][:180] if about else "",
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "logo_url": company["logo_url"],
                "applicants": app_counts.get(j.id, 0),
            }
        )
    return results


@router.get("/jobs/public/{job_id}")
def get_public_job(job_id: int, db: Session = Depends(get_db)):
    """Returns a single public job listing details"""
    job = db.query(Job).filter(Job.id == job_id, Job.is_active).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Increment View Count
    if job.views is None:
        job.views = 0
    job.views += 1
    db.commit()

    salary_min = None
    salary_max = None
    if job.salary_range:
        import re as _re

        nums = _re.findall(r"\d[\d,]*", job.salary_range.replace(",", ""))
        if len(nums) >= 2:
            salary_min = int(nums[0].replace(",", ""))
            salary_max = int(nums[1].replace(",", ""))
        elif len(nums) == 1:
            salary_min = int(nums[0].replace(",", ""))

    valid_through = job.valid_through
    if not valid_through and job.created_at:
        valid_through = job.created_at + timedelta(days=30)

    company = _resolve_job_company(job)

    skills = (
        [s.strip() for s in str(job.required_skills).split(",") if s.strip()]
        if job.required_skills
        else []
    )

    # Fallback: extract skills from linked rubric if empty
    if not skills:
        skills = [c["name"] for c in _rubric_criteria(db, job)]

    # Role & Outcomes Q&A + nice-to-haves (real structured data)
    overviews = (
        db.query(JobRoleOverview)
        .filter(JobRoleOverview.job_id == job.id)
        .order_by(JobRoleOverview.question_key)
        .all()
    )
    overview_map = {
        o.question_key: o.answer for o in overviews if o.answer and o.answer.strip()
    }
    nice_to_have = [
        n.label
        for n in db.query(JobNiceToHave)
        .filter(JobNiceToHave.job_id == job.id)
        .order_by(JobNiceToHave.sort_order)
        .all()
    ]

    # Fallback: build description from Role & Outcomes if missing
    description = job.description
    if not description:
        if overviews:
            sections = []
            for rv in overviews:
                if rv.answer and rv.answer.strip():
                    sections.append(f"<h3>{rv.question}</h3>\n<p>{rv.answer}</p>")
            if sections:
                description = "\n\n".join(sections)

    about = _paragraphs(description)
    summary = about[0][:200] if about else ""
    responsibilities = _split_lines(overview_map.get("responsibilities"))

    recruiter_name = None
    if job.recruiter is not None:
        try:
            from backend.profile_helpers import get_user_name

            recruiter_name = get_user_name(job.recruiter)
        except Exception:
            recruiter_name = getattr(job.recruiter, "name", None)

    json_ld = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": job.description,
        "datePosted": job.created_at.isoformat() if job.created_at else None,
        "validThrough": valid_through.isoformat() if valid_through else None,
        "employmentType": job.type if job.type else "FULL_TIME",
        "hiringOrganization": {
            "@type": "Organization",
            "name": company["company"],
            "logo": company["logo_url"],
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": job.location if job.location else "Remote",
            },
        },
        "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "TND",
            "value": {
                "@type": "QuantitativeValue",
                "value": salary_max
                if salary_max is not None
                else (salary_min if salary_min is not None else ""),
                "unitText": "MONTH",
            },
        }
        if salary_min is not None or salary_max is not None
        else None,
        "skills": job.required_skills if job.required_skills else "",
        "applicantLocationRequirements": {
            "@type": "Country",
            "name": "TN",
        },
    }

    return {
        "id": job.id,
        "title": job.title,
        "company": company["company"],
        "company_id": company["company_id"],
        "company_website": company["company_website"],
        "company_verified": company["company_verified"],
        "location": job.location,
        "salary_range": job.salary_range,
        "type": job.type,
        "description": sanitize_rich_text(description)
        if description
        else description,
        "summary": summary,
        "about": about,
        "responsibilities": responsibilities,
        "requirements": "\n".join(skills) if skills else None,
        "benefits": None,
        "nice_to_have": nice_to_have,
        "perks": [],
        "rubric": _rubric_criteria(db, job),
        "category": job.category_rel.name if job.category_rel else "General",
        "category_id": job.category_id,
        "required_skills": ", ".join(skills) if skills else None,
        "recruiter_name": recruiter_name,
        "recruiter_role": "Hiring Manager" if recruiter_name else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "valid_through": valid_through.isoformat() if valid_through else None,
        "logo_url": company["logo_url"],
        "json_ld": json_ld,
        "applicants": db.query(Application).filter(Application.job_id == job.id).count(),
    }


@router.get("/courses/public")
def get_public_courses(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Course).filter(Course.status == "published")
    if category_id:
        query = query.filter(Course.category_id == category_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Course.title.ilike(like), Course.description.ilike(like))
        )

    courses = (
        query.order_by(Course.is_featured.desc(), Course.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": c.id,
            "title": c.title,
            "mentor_name": c.mentor.name if c.mentor else "Candway Mentor",
            "category": c.category_rel.name if c.category_rel else c.category,
            "price": c.price,
            "rating": 4.8,
            "thumbnail_url": c.thumbnail_url
            or f"https://ui-avatars.com/api/?name={c.title}&background=random&color=fff",
        }
        for c in courses
    ]


@router.get("/blogs")
def get_public_blogs(limit: int = 10, db: Session = Depends(get_db)):
    posts = (
        db.query(BlogPost)
        .filter(BlogPost.is_published)
        .order_by(BlogPost.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for p in posts:
        text = re.sub(r"<[^>]+>", " ", p.content or "")
        text = re.sub(r"\s+", " ", text).strip()
        results.append(
            {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "summary": text[:200] + ("..." if len(text) > 200 else ""),
                "image_url": p.image_url,
                "tags": p.tags,
                "date": p.created_at.strftime("%b %d, %Y"),
                "author_name": p.author.name if p.author else "Candway Team",
            }
        )
    return results


@router.get("/blogs/{slug}")
def get_public_blog_detail(slug: str, db: Session = Depends(get_db)):
    post = (
        db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.is_published).first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "image_url": post.image_url,
        "tags": post.tags,
        "date": post.created_at.strftime("%b %d, %Y"),
        "author_name": post.author.name if post.author else "Candway Team",
    }


@router.get("/opportunities")
def get_public_opportunities(db: Session = Depends(get_db)):
    # Fetch active opportunities
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.is_active)
        .order_by(Opportunity.created_at.desc())
        .all()
    )
    return [
        {
            "id": o.id,
            "title": o.title,
            "type": o.type,
            "description": o.description,
            "link": o.link,
            "image_url": o.image_url,
            "date": o.created_at.strftime("%b %d, %Y"),
        }
        for o in opps
    ]


# --- CATEGORY API ---
@router.get("/categories/{type}")
def get_categories(type: str, db: Session = Depends(get_db)):
    """Fetch category tree (parents with children)"""
    parents = (
        db.query(Category)
        .filter(Category.type == type, Category.parent_id is None)
        .all()
    )

    def serialize_cat(cat):
        return {
            "id": cat.id,
            "name": cat.name,
            "children": [serialize_cat(child) for child in cat.subcategories],
        }

    return [serialize_cat(p) for p in parents]


# --- LEAD CAPTURE ENDPOINTS ---


class WaitlistRequest(BaseModel):
    email: str


@router.post("/waitlist")
async def join_waitlist(payload: WaitlistRequest, db: Session = Depends(get_db)):
    # Check if already exists
    existing = (
        db.query(SalesLead)
        .filter(SalesLead.email == payload.email, SalesLead.source == "waitlist")
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already on waitlist")

    new_lead = SalesLead(
        email=payload.email,
        source="waitlist",
        status="new",
        name=payload.email.split("@")[0],  # Placeholder name
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    return {"message": "Success", "id": new_lead.id}


class DemoRequest(BaseModel):
    name: str
    company: str
    email: str
    pack: str
    context: str


@router.post("/demo-request")
async def request_demo(payload: DemoRequest, db: Session = Depends(get_db)):
    # Prevent duplicate demo requests from the same email.
    existing = (
        db.query(SalesLead)
        .filter(
            SalesLead.email == payload.email,
            SalesLead.source == "demo_request",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Request already received",
        )

    # Persist beta-specific qualification data in the existing ai_notes field.
    # This avoids a DB migration while keeping the complete demo request.
    ai_notes = (
        f"Beta pack: {payload.pack}\n"
        f"Hiring context: {payload.context}"
    )

    new_lead = SalesLead(
        email=payload.email,
        company=payload.company,
        source="demo_request",
        status="new",
        name=payload.name,
        ai_notes=ai_notes,
    )

    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    return {
        "message": "Success",
        "id": new_lead.id,
    }


# --- PUBLIC CONFIG ENDPOINT ---
@router.get("/config/public")
def get_public_config(db: Session = Depends(get_db)):
    from backend.database import SystemConfig

    configs = db.query(SystemConfig).all()
    settings_dict = {c.key: c.value for c in configs}

    return {
        "default_language": settings_dict.get("default_language", "en"),
        "maintenance_mode": settings_dict.get("maintenance_mode") == "true",
        "brand_name": "Candway",
    }
