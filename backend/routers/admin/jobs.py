from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import Application, AuditLog, Category, Job, User
from backend.dependencies import get_current_user, get_db
from backend.profile_helpers import get_user_name
from backend.routers.admin.common import check_permission, paginate
from backend.tenant import get_admin_company_id

router = APIRouter(tags=["admin"])


@router.get("/jobs")
def get_admin_jobs(
    status: Optional[str] = "all",
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Job)
    if company_id is not None:
        query = query.filter(Job.company_id == company_id)
    if status == "active":
        query = query.filter(Job.is_active)
    elif status == "inactive":
        query = query.filter(~Job.is_active)

    if search:
        query = query.join(Job.recruiter).filter(
            (User.email.ilike(f"%{search}%")) | (User.name.ilike(f"%{search}%"))
        )

    query = query.order_by(Job.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company_name
                or (j.company.name if j.company else "Unknown"),
                "location": j.location,
                "recruiter_id": j.recruiter_id,
                "recruiter_name": get_user_name(j.recruiter)
                if j.recruiter
                else "Unknown",
                "created_at": j.created_at.strftime("%Y-%m-%d"),
                "is_active": j.is_active,
                "applicant_count": db.query(Application)
                .filter(Application.job_id == j.id)
                .count(),
            }
            for j in result["items"]
        ],
    }


@router.delete("/jobs/{job_id}")
def delete_job_admin(
    job_id: int,
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Depends(get_admin_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    job = db.query(Job).filter(Job.id == job_id)
    if company_id is not None:
        job = job.filter(Job.company_id == company_id)
    job = job.first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully"}


@router.get("/categories")
def list_categories(
    page: int = 1,
    per_page: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Category)
    if search:
        query = query.filter(Category.name.ilike(f"%{search}%"))
    query = query.order_by(Category.name.asc())
    result = paginate(query, page, per_page)
    items = []
    for cat in result["items"]:
        items.append(
            {
                "id": cat.id,
                "name": cat.name,
                "type": cat.type,
                "slug": cat.slug,
                "parent_id": cat.parent_id,
                "is_active": True,
                "jobs_count": (
                    db.query(Job).filter(Job.category_id == cat.id).count()
                    if cat.type == "job"
                    else 0
                ),
            }
        )
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "categories": items,
    }


@router.put("/categories/{category_id}")
async def update_category(
    category_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    data = await request.json()
    if data.get("name"):
        cat.name = data["name"]
    if data.get("type"):
        cat.type = data["type"]
    if "parent_id" in data:
        cat.parent_id = data.get("parent_id")
    cat.slug = cat.name.lower().replace(" ", "-")

    audit = AuditLog(
        user_id=current_user.id,
        action="update_category",
        target_id=str(cat.id),
        details=f"Updated category: {cat.name}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()
    return {"message": "Category updated", "id": cat.id}


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    # Delete children first, then the parent
    def delete_with_children(cat_id: int):
        cat = db.query(Category).filter(Category.id == cat_id).first()
        if not cat:
            return
        for child in cat.subcategories:
            delete_with_children(child.id)
        audit = AuditLog(
            user_id=current_user.id,
            action="delete_category",
            target_id=str(cat.id),
            details=f"Deleted category: {cat.name}",
            ip_address=None,
        )
        db.add(audit)
        db.delete(cat)

    delete_with_children(category_id)
    db.commit()
    return {"message": "Category deleted"}


@router.post("/categories")
async def create_category(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    data = await request.json()

    if not data.get("name") or not data.get("type"):
        raise HTTPException(status_code=400, detail="Name and Type are required")

    existing = db.query(Category).filter(Category.name == data["name"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")

    slug = data["name"].lower().replace(" ", "-")

    new_cat = Category(
        name=data["name"], type=data["type"], parent_id=data.get("parent_id"), slug=slug
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)

    audit = AuditLog(
        user_id=current_user.id,
        action="create_category",
        target_id=str(new_cat.id),
        details=f"Created category: {new_cat.name}",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()

    return {"message": "Category created", "id": new_cat.id}
