import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import get_settings as _get_cfg_settings
from backend.database import (
    Course,
    CourseReview,
    Enrollment,
    Lesson,
    LessonProgress,
    Section,
    SystemConfig,
    User,
)
from backend.dependencies import get_current_user, get_db
from backend.konnect_service import konnect_service
from backend.profile_helpers import get_user_name
from backend.schemas import ProgressUpdate
from backend.secret_encryption import decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/my-enrollments")
def get_my_enrollments(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """List all courses the current user is enrolled in"""
    enrollments = (
        db.query(Enrollment).filter(Enrollment.user_id == current_user.id).all()
    )

    # Enrich with course data for the frontend
    results = []
    for enr in enrollments:
        course = db.query(Course).filter(Course.id == enr.course_id).first()
        results.append(
            {
                "id": enr.id,
                "course_id": enr.course_id,
                "course_title": course.title if course else "Unknown Course",
                "progress": enr.progress,
                "status": enr.status,
                "enrolled_at": enr.enrolled_at,
            }
        )
    return results


@router.post("/{course_id}/enroll")
def enroll_in_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll in a course"""
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check existing enrollment
    existing = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == current_user.id, Enrollment.course_id == course_id
        )
        .first()
    )

    if existing:
        return {"message": "Already enrolled", "enrollment_id": existing.id}

    # Create new enrollment
    # Determine initial status based on price
    initial_status = "active"
    payment_url = None

    if course.price and course.price > 0:
        initial_status = "pending_payment"

    new_enrollment = Enrollment(
        user_id=current_user.id, course_id=course_id, status=initial_status, progress=0
    )
    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)

    # Handle Payment Initiation
    if initial_status == "pending_payment":
        payment_response = konnect_service.init_payment(
            amount=course.price,
            enrollment_id=new_enrollment.id,
            user_email=current_user.email,
        )

        if payment_response and "payUrl" in payment_response:
            payment_url = payment_response["payUrl"]
        else:
            # Rollback or Error? For now, we return error but keep enrollment as pending (can retry)
            pass

    return {
        "message": "Enrolled successfully"
        if initial_status == "active"
        else "Payment required",
        "enrollment_id": new_enrollment.id,
        "status": initial_status,
        "payment_url": payment_url,
    }


@router.post("/konnect-webhook")
async def konnect_webhook(request: Request, db: Session = Depends(get_db)):
    """P1-01 FIX: Konnect payment webhook with idempotency.

    The webhook is the source of truth for the ``enrollment.status``
    transition from ``pending_approval`` to ``active`` / ``payment_failed``.
    We lock the row, check the current state, and refuse to
    double-apply on a retry so the candidate's enrollment cannot be
    double-extended or re-priced.
    """
    try:
        raw_body = await request.body()
        signature = request.headers.get("x-konnect-signature", "")

        api_key_obj = (
            db.query(SystemConfig).filter(SystemConfig.key == "konnect_api_key").first()
        )
        api_key = (
            decrypt_value(api_key_obj.value, _get_cfg_settings().secret_key)
            if api_key_obj
            else None
        )

        if api_key and signature:
            expected = hmac.new(api_key.encode(), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                logger.warning("Konnect webhook rejected: invalid signature")
                raise HTTPException(status_code=403, detail="Forbidden")
        elif api_key and not signature:
            logger.warning(
                "Konnect webhook called without signature header — rejecting"
            )
            raise HTTPException(status_code=403, detail="Forbidden")

        data = json.loads(raw_body)
        logger.info(f"Konnect Webhook Received: {data}")

        payment_status = data.get("status")
        payment_ref = data.get("paymentRef")
        enrollment_id = data.get("orderId")

        if not enrollment_id:
            return {"detail": "Ignored", "reason": "no_order_id"}

        # SELECT FOR UPDATE so a duplicate webhook delivery cannot
        # race with itself.
        enrollment = (
            db.query(Enrollment)
            .filter(Enrollment.id == enrollment_id)
            .with_for_update()
            .first()
        )
        if not enrollment:
            return {"detail": "Ignored", "reason": "enrollment_not_found"}

        # Idempotency-Key replay protection: Konnect may retry the
        # same webhook; treat the paymentRef as a natural key.
        if payment_ref and enrollment.proof_url == payment_ref:
            return {
                "status": "processed",
                "idempotent": True,
                "detail": "duplicate webhook with same paymentRef",
            }

        if payment_status in ("completed", "success"):
            if enrollment.status == "active":
                # Already activated by an earlier webhook delivery.
                # Persist the paymentRef so future replays are caught.
                if payment_ref and not enrollment.proof_url:
                    enrollment.proof_url = payment_ref
                    db.commit()
                return {
                    "status": "processed",
                    "idempotent": True,
                    "detail": "enrollment already active",
                }
            enrollment.status = "active"
            enrollment.proof_url = payment_ref or "konnect_auto"
            enrollment.amount_paid = enrollment.course.price
            enrollment.approved_at = datetime.now(UTC)
            db.commit()
            logger.info(f"Enrollment {enrollment_id} activated via Webhook")

        elif payment_status == "failed":
            if enrollment.status == "payment_failed":
                return {
                    "status": "processed",
                    "idempotent": True,
                    "detail": "enrollment already marked payment_failed",
                }
            enrollment.status = "payment_failed"
            enrollment.rejected_at = datetime.now(UTC)
            db.commit()

        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Enrollment callback error: {e}")
        return {"detail": "Error processing enrollment callback"}


@router.get("/{course_id}")
def get_course_public(course_id: int, db: Session = Depends(get_db)):
    """Get public details of a course (Legacy alias)"""
    return get_course_details(course_id, db)


@router.get("/{course_id}/details")
def get_course_details(course_id: int, db: Session = Depends(get_db)):
    """Full course details for the landing page"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Calculate stats
    rating_stats = (
        db.query(func.avg(CourseReview.rating), func.count(CourseReview.id))
        .filter(CourseReview.course_id == course_id)
        .first()
    )

    avg_rating = float(rating_stats[0]) if rating_stats[0] else 0.0
    review_count = int(rating_stats[1]) if rating_stats[1] else 0
    enrollment_count = (
        db.query(Enrollment).filter(Enrollment.course_id == course_id).count()
    )

    # Duration in minutes
    total_duration_sec = (
        db.query(func.sum(Lesson.duration))
        .join(Section)
        .filter(Section.course_id == course_id)
        .scalar()
        or 0
    )

    # Safe JSON parsing
    def safe_json(val):
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
            return []

    return {
        "id": course.id,
        "title": course.title,
        "subtitle": course.subtitle,
        "description": course.description,
        "thumbnail_url": course.thumbnail_url,
        "price": course.price,
        "original_price": course.original_price,
        "average_rating": avg_rating,
        "review_count": review_count,
        "enrollment_count": enrollment_count,
        "total_lessons": course.total_lessons
        or db.query(Lesson)
        .join(Section)
        .filter(Section.course_id == course_id)
        .count(),
        "total_duration_minutes": total_duration_sec // 60,
        "level": course.difficulty,
        "what_you_learn": safe_json(course.what_you_learn),
        "requirements": safe_json(course.requirements),
        "mentor": {
            "name": get_user_name(course.mentor) if course.mentor else "Candway Mentor",
            "headline": getattr(course.mentor, "headline", "Certified Instructor")
            if course.mentor
            else "Certified Instructor",
            "bio": getattr(course.mentor, "bio", "Expert teaching and guidance.")
            if course.mentor
            else "Expert teaching and guidance.",
            "avatar_url": getattr(course.mentor, "avatar_url", None)
            if course.mentor
            else None,
        },
    }


@router.get("/{course_id}/curriculum")
def get_course_curriculum(course_id: int, db: Session = Depends(get_db)):
    """Course curriculum (sections and lessons)"""
    sections = (
        db.query(Section)
        .filter(Section.course_id == course_id)
        .order_by(Section.order)
        .all()
    )

    results = []
    for section in sections:
        lessons = (
            db.query(Lesson)
            .filter(Lesson.section_id == section.id)
            .order_by(Lesson.order)
            .all()
        )
        results.append(
            {
                "id": section.id,
                "title": section.title,
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "duration": lesson.duration,
                        "content_type": lesson.content_type,
                    }
                    for lesson in lessons
                ],
            }
        )

    return {"sections": results}


@router.get("/{course_id}/reviews")
def get_course_reviews(course_id: int, db: Session = Depends(get_db)):
    """User reviews for a course"""
    reviews = (
        db.query(CourseReview)
        .filter(CourseReview.course_id == course_id)
        .order_by(CourseReview.created_at.desc())
        .all()
    )

    # Calculate breakdown
    breakdown = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in reviews:
        if r.rating in breakdown:
            breakdown[r.rating] += 1

    return {
        "total_reviews": len(reviews),
        "breakdown": breakdown,
        "reviews": [
            {
                "user_name": get_user_name(r.user) if r.user else "Anonymous",
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
    }


@router.get("/my-progress")
def get_all_my_progress(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get progress for all enrolled courses"""
    enrollments = (
        db.query(Enrollment).filter(Enrollment.user_id == current_user.id).all()
    )
    return [
        {
            "course_id": e.course_id,
            "progress": e.progress,
            "completed_lessons": e.completed_lessons,
            "status": e.status,
        }
        for e in enrollments
    ]


@router.post("/{course_id}/lessons/{lesson_id}/progress")
def update_lesson_progress(
    course_id: int,
    lesson_id: int,
    update: ProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update progress for a specific lesson and update overall course progress"""
    # 1. Verify enrollment
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == current_user.id, Enrollment.course_id == course_id
        )
        .first()
    )

    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    # 2. Update LessonProgress
    progress = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id == lesson_id,
        )
        .first()
    )

    if not progress:
        progress = LessonProgress(user_id=current_user.id, lesson_id=lesson_id)
        db.add(progress)

    progress.completed = update.completed
    progress.watch_time = update.watch_time
    progress.last_position = update.last_position
    progress.updated_at = datetime.now(UTC)

    # 3. Re-calculate overall course progress
    total_lessons = (
        db.query(Lesson).join(Section).filter(Section.course_id == course_id).count()
    )

    if total_lessons > 0:
        completed_count = (
            db.query(LessonProgress)
            .join(Lesson)
            .join(Section)
            .filter(
                Section.course_id == course_id,
                LessonProgress.user_id == current_user.id,
                LessonProgress.completed,
            )
            .count()
        )

        enrollment.completed_lessons = completed_count
        enrollment.progress = int((completed_count / total_lessons) * 100)

        if enrollment.progress >= 100:
            enrollment.status = "completed"
            enrollment.completed_at = datetime.now(UTC)

    db.commit()

    return {
        "lesson_completed": progress.completed,
        "course_progress": enrollment.progress,
        "status": enrollment.status,
    }
