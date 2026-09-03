"""Admin CRUD for Job Categories (company-scoped)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import JobCategory, get_db
from backend.dependencies import get_current_user
from backend.models.foundation.user import User
from backend.routers.admin.common import check_permission
from backend.tenant import get_current_company_id

router = APIRouter(tags=["admin"])


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


@router.get("/job-categories", response_model=List[CategoryResponse])
def list_job_categories(
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "view_users")
    categories = (
        db.query(JobCategory)
        .filter(JobCategory.company_id == company_id)
        .order_by(JobCategory.name)
        .all()
    )
    return categories


@router.post("/job-categories", response_model=CategoryResponse)
def create_job_category(
    req: CategoryCreate,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "edit_users")
    existing = (
        db.query(JobCategory)
        .filter(
            JobCategory.company_id == company_id,
            JobCategory.name == req.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="A category with this name already exists"
        )
    category = JobCategory(
        company_id=company_id,
        name=req.name,
        description=req.description,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/job-categories/{category_id}", response_model=CategoryResponse)
def update_job_category(
    category_id: int,
    req: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "edit_users")
    category = (
        db.query(JobCategory)
        .filter(JobCategory.id == category_id, JobCategory.company_id == company_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if req.name is not None:
        dup = (
            db.query(JobCategory)
            .filter(
                JobCategory.company_id == company_id,
                JobCategory.name == req.name,
                JobCategory.id != category_id,
            )
            .first()
        )
        if dup:
            raise HTTPException(
                status_code=409, detail="A category with this name already exists"
            )
        category.name = req.name
    if req.description is not None:
        category.description = req.description
    db.commit()
    db.refresh(category)
    return category


@router.delete("/job-categories/{category_id}")
def delete_job_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "edit_users")
    category = (
        db.query(JobCategory)
        .filter(JobCategory.id == category_id, JobCategory.company_id == company_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(category)
    db.commit()
    return {"message": "Category deleted"}
