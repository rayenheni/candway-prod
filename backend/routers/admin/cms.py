import os
import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import BlogPost, Opportunity, PageSection, User
from backend.dependencies import get_current_user, get_db
from backend.logger import logger
from backend.routers.admin.common import check_permission, paginate
from backend.schemas import PageSectionUpdate

router = APIRouter(tags=["admin"])


class BlogPostCreate(BaseModel):
    title: str
    slug: str
    content: str
    image_url: Optional[str] = None
    tags: Optional[str] = None


class OpportunityCreate(BaseModel):
    title: str
    type: str
    description: str
    link: str
    image_url: Optional[str] = None


@router.post("/blogs")
def create_blog_post(
    post: BlogPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    existing = db.query(BlogPost).filter(BlogPost.slug == post.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists")

    new_post = BlogPost(
        title=post.title,
        slug=post.slug,
        content=post.content,
        author_id=current_user.id,
        image_url=post.image_url,
        tags=post.tags,
        is_published=True,
    )
    db.add(new_post)
    db.commit()
    return {"message": "Blog post created", "id": new_post.id}


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/blogs/upload-image")
async def upload_blog_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    check_permission(current_user, "manage_content")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type: {file.content_type}. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
    secure_name = f"blog_{uuid.uuid4().hex}{ext}"
    rel_dir = "uploads/blog"
    abs_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        rel_dir,
    )
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(abs_dir, secure_name)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )
    with open(abs_path, "wb") as f:
        f.write(contents)

    logger.info(
        "Blog image uploaded by user %s: %s (%d bytes)",
        current_user.id,
        secure_name,
        len(contents),
    )

    return {"url": f"/{rel_dir}/{secure_name}"}


@router.delete("/blogs/{post_id}")
def delete_blog_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if post:
        db.delete(post)
        db.commit()
    return {"message": "Blog post deleted"}


@router.put("/blogs/{post_id}")
def update_blog_post(
    post_id: int,
    payload: BlogPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    slug_conflict = (
        db.query(BlogPost)
        .filter(BlogPost.slug == payload.slug, BlogPost.id != post_id)
        .first()
    )
    if slug_conflict:
        raise HTTPException(
            status_code=400, detail="Slug already in use by another post"
        )

    post.title = payload.title
    post.slug = payload.slug
    post.content = payload.content
    post.image_url = payload.image_url
    post.tags = payload.tags
    db.commit()
    return {"message": "Blog post updated", "id": post.id}


@router.get("/blogs/{post_id}")
def get_blog_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return post


@router.get("/blogs")
def get_admin_blogs(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(BlogPost).order_by(BlogPost.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "blogs": result["items"],
    }


@router.post("/opportunities")
def create_opportunity(
    opp: OpportunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    new_opp = Opportunity(
        title=opp.title,
        type=opp.type,
        description=opp.description,
        link=opp.link,
        image_url=opp.image_url,
        is_active=True,
    )
    db.add(new_opp)
    db.commit()
    return {"message": "Opportunity created", "id": new_opp.id}


@router.delete("/opportunities/{opp_id}")
def delete_opportunity(
    opp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if opp:
        db.delete(opp)
        db.commit()
    return {"message": "Opportunity deleted"}


@router.put("/opportunities/{opp_id}")
def update_opportunity(
    opp_id: int,
    payload: OpportunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opp.title = payload.title
    opp.type = payload.type
    opp.description = payload.description
    opp.link = payload.link
    opp.image_url = payload.image_url
    db.commit()
    return {"message": "Opportunity updated", "id": opp.id}


@router.get("/opportunities/{opp_id}")
def get_opportunity(
    opp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@router.get("/opportunities")
def get_admin_opportunities(
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(Opportunity).order_by(Opportunity.created_at.desc())
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "opportunities": result["items"],
    }


@router.get("/pages/{page_slug}")
def get_page_sections(
    page_slug: str,
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    query = db.query(PageSection).filter(PageSection.page_slug == page_slug)
    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "sections": result["items"],
    }


@router.post("/pages/{page_slug}/{section_slug}")
def update_page_section(
    page_slug: str,
    section_slug: str,
    payload: PageSectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    section = (
        db.query(PageSection)
        .filter(
            PageSection.page_slug == page_slug, PageSection.section_slug == section_slug
        )
        .first()
    )

    if not section:
        section = PageSection(
            page_slug=page_slug, section_slug=section_slug, updated_by=current_user.id
        )
        db.add(section)

    section.content_json = payload.content_json
    section.updated_at = datetime.now(UTC)
    section.updated_by = current_user.id

    db.commit()
    db.refresh(section)
    return section
