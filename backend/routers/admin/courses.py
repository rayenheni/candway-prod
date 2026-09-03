from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import backend.schemas
from backend.database import AuditLog, Course, User
from backend.dependencies import get_current_user, get_db
from backend.email_service import email_service
from backend.routers.admin.common import check_permission, paginate

router = APIRouter(tags=["admin"])


@router.get("/courses")
def get_courses(
    status: str = "pending_review",
    page: int = 1,
    per_page: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    query = db.query(Course)
    if status != "all":
        query = query.filter(Course.status == status)

    result = paginate(query, page, per_page)
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "mentor_name": c.mentor.name if c.mentor else "Unknown",
                "price": c.price,
                "category": c.category,
                "status": c.status,
                "created_at": c.created_at.strftime("%Y-%m-%d"),
            }
            for c in result["items"]
        ],
    }


@router.post("/courses/{course_id}/approve")
def approve_course(
    course_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course.status = "published"
    course.published_at = datetime.now(UTC)

    audit = AuditLog(
        user_id=current_user.id,
        action="approve_course",
        target_id=str(course_id),
        details=f"Admin {current_user.email} approved course '{course.title}'",
        ip_address=request.client.host,
    )
    db.add(audit)
    db.commit()

    if course.mentor and course.mentor.email:
        email_service.send_course_approval_email(course.mentor.email, course.title)

    return {"message": "Course published successfully"}


@router.post("/courses/{course_id}/reject")
def reject_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    course.status = "rejected"
    db.commit()

    if course.mentor and course.mentor.email:
        email_service.send_course_rejection_email(course.mentor.email, course.title)

    return {"message": "Course rejected"}


@router.post("/courses/external")
def create_external_course(
    course: backend.schemas.CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_permission(current_user, "manage_content")

    new_course = Course(
        mentor_id=current_user.id,
        title=course.title,
        description=course.description,
        category=course.category,
        difficulty=course.difficulty,
        duration=course.duration,
        thumbnail_url=course.thumbnail_url,
        price=course.price,
        status="published",
        is_external=True,
        external_url=course.url,
    )

    db.add(new_course)
    db.commit()
    db.refresh(new_course)

    return {"message": "External course created", "course_id": new_course.id}
