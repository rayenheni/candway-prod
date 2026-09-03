import json
from datetime import UTC, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import Course, Enrollment, Lesson, Question, Quiz, Section, User
from backend.dependencies import get_current_user, get_db
from backend.schemas import (
    CourseCreate,
    CourseCurriculum,
    CourseOut,
    LessonCreate,
    LessonOut,
    SectionCreate,
    SectionOut,
)

router = APIRouter(prefix="/mentor", tags=["Mentor"])


# --- DEPENDENCY ---
def get_current_mentor(current_user: User = Depends(get_current_user)):
    if (
        current_user.role != "mentor" and current_user.role != "admin"
    ):  # Admins can also act as mentors
        raise HTTPException(status_code=403, detail="Mentor privileges required")
    return current_user


# --- COURSES ---


@router.post("/courses", response_model=CourseOut)
def create_course(
    course: CourseCreate,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Create a new course draft"""
    new_course = Course(
        mentor_id=current_user.id,
        title=course.title,
        subtitle=course.subtitle,
        description=course.description,
        category=course.category,
        difficulty=course.difficulty,
        duration=course.duration,
        thumbnail_url=course.thumbnail_url,
        promo_video_url=course.promo_video_url,
        price=course.price,
        original_price=course.original_price,
        language=course.language,
        what_you_learn=course.what_you_learn,  # JSON string
        requirements=course.requirements,  # JSON string
        target_audience=course.target_audience,  # JSON string
        status="draft",
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    return new_course


@router.get("/courses", response_model=List[CourseOut])
def get_my_courses(
    current_user: User = Depends(get_current_mentor), db: Session = Depends(get_db)
):
    """List all courses created by the mentor"""
    return db.query(Course).filter(Course.mentor_id == current_user.id).all()


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course_details(
    course_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Get single course details"""
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.put("/courses/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    course_update: CourseCreate,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Update course details"""
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Update fields
    course.title = course_update.title
    course.subtitle = course_update.subtitle
    course.description = course_update.description
    course.category = course_update.category
    course.difficulty = course_update.difficulty
    course.duration = course_update.duration
    course.price = course_update.price
    course.thumbnail_url = course_update.thumbnail_url
    course.promo_video_url = course_update.promo_video_url
    course.what_you_learn = course_update.what_you_learn
    course.requirements = course_update.requirements
    course.target_audience = course_update.target_audience
    course.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Delete a course"""
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully"}


@router.post("/courses/{course_id}/publish")
def publish_course(
    course_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Publish a course (make it visible to students)"""
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Simple validation: Must have at least one section and lesson
    if not course.sections:
        raise HTTPException(
            status_code=400, detail="Cannot publish empty course. Add sections first."
        )

    course.status = "pending_review"
    # Note: We omit setting published_at until actual publication
    db.commit()
    return {
        "message": "Course submitted for review by an admin.",
        "status": "pending_review",
    }


# --- CURRICULUM (SECTIONS & LESSONS) ---


@router.get("/courses/{course_id}/curriculum", response_model=CourseCurriculum)
def get_curriculum(
    course_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Get full curriculum (sections + lessons)"""
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course  # SQLA relationships will handle nested serialization via Pydantic


@router.post("/courses/{course_id}/sections", response_model=SectionOut)
def add_section(
    course_id: int,
    section: SectionCreate,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Add a new section (module)"""
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    new_section = Section(
        course_id=course.id,
        title=section.title,
        description=section.description,
        order=section.order,
    )
    db.add(new_section)
    db.commit()
    db.refresh(new_section)
    return new_section


@router.post("/sections/{section_id}/lessons", response_model=LessonOut)
def add_lesson(
    section_id: int,
    lesson: LessonCreate,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Add a lesson to a section"""
    # Verify ownership via join
    section = (
        db.query(Section)
        .join(Course)
        .filter(Section.id == section_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not section:
        raise HTTPException(
            status_code=404, detail="Section not found or access denied"
        )

    new_lesson = Lesson(
        section_id=section_id,
        title=lesson.title,
        content_type=lesson.content_type,
        content_url=lesson.content_url,
        duration=lesson.duration,
        order=lesson.order,
        is_free_preview=lesson.is_free_preview,
    )
    db.add(new_lesson)

    # Update total lessons count
    section.course.total_lessons += 1

    db.commit()
    db.refresh(new_lesson)
    return new_lesson


@router.delete("/sections/{section_id}")
def delete_section(
    section_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    section = (
        db.query(Section)
        .join(Course)
        .filter(Section.id == section_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    db.delete(section)
    db.commit()
    return {"message": "Section deleted"}


@router.delete("/lessons/{lesson_id}")
def delete_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    lesson = (
        db.query(Lesson)
        .join(Section)
        .join(Course)
        .filter(Lesson.id == lesson_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    db.delete(lesson)
    db.commit()
    return {"message": "Lesson deleted"}


# --- AI GENERATION ---


@router.post("/courses/{course_id}/generate-syllabus")
async def ai_generate_syllabus(
    course_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Generate a full course syllabus using AI"""
    from backend.ai.roadmap import generate_course_syllabus

    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.mentor_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    result = await generate_course_syllabus(
        course.title, course.description, course.difficulty
    )

    if not result.get("sections"):
        raise HTTPException(status_code=500, detail="AI failed to generate syllabus")

    # Bulk create sections and lessons
    for s_data in result["sections"]:
        new_section = Section(
            course_id=course.id,
            title=s_data["title"],
            description=s_data["description"],
            order=s_data["order"],
        )
        db.add(new_section)
        db.flush()  # Get section ID

        for l_data in s_data.get("lessons", []):
            new_lesson = Lesson(
                section_id=new_section.id,
                title=l_data["title"],
                content_type="video",
                content_url="",  # Mentor will fill this
                duration=l_data.get("duration", 10),
                order=l_data["order"],
                is_free_preview=l_data.get("is_free_preview", False),
            )
            db.add(new_lesson)

    db.commit()
    return {
        "message": "Syllabus generated successfully",
        "sections_count": len(result["sections"]),
    }


@router.post("/sections/{section_id}/generate-quiz")
async def ai_generate_quiz(
    section_id: int,
    current_user: User = Depends(get_current_mentor),
    db: Session = Depends(get_db),
):
    """Generate a quiz for a module using AI"""
    from backend.ai.roadmap import generate_quiz_questions

    section = (
        db.query(Section)
        .join(Course)
        .filter(Section.id == section_id, Course.mentor_id == current_user.id)
        .first()
    )

    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    result = await generate_quiz_questions(section.title, section.description)

    if not result.get("questions"):
        raise HTTPException(status_code=500, detail="AI failed to generate questions")

    # Create Quiz
    new_quiz = Quiz(
        section_id=section.id,
        title=result.get("quiz_title", f"{section.title} Assessment"),
        passing_score=70,
    )
    db.add(new_quiz)
    db.flush()

    # Create Questions
    for q_data in result["questions"]:
        new_q = Question(
            quiz_id=new_quiz.id,
            text=q_data["text"],
            options=json.dumps(q_data["options"]),
            correct_option_index=q_data["correct_option_index"],
            explanation=q_data.get("explanation", ""),
        )
        db.add(new_q)

    db.commit()
    return {
        "message": "Quiz generated successfully",
        "questions_count": len(result["questions"]),
    }


# --- STATS & ANALYTICS ---


@router.get("/stats")
def get_mentor_stats(
    current_user: User = Depends(get_current_mentor), db: Session = Depends(get_db)
):
    """Get mentor dashboard statistics"""
    # 1. Total Courses
    total_courses = db.query(Course).filter(Course.mentor_id == current_user.id).count()

    # 2. Total Students (Unique enrollments in my courses)
    # Join Enrollment -> Course -> filter by mentor_id
    total_students = (
        db.query(Enrollment.user_id)
        .join(Course)
        .filter(Course.mentor_id == current_user.id)
        .distinct()
        .count()
    )

    # 3. Total Revenue
    # Sum of amount_paid in enrollments for my courses
    # Note: This assumes 'amount_paid' is populated correctly on purchase.
    # If not, we might need to fallback to course.price * count, but amount_paid is safer if discounts exist.
    from sqlalchemy import func

    revenue = (
        db.query(func.sum(Enrollment.amount_paid))
        .join(Course)
        .filter(Course.mentor_id == current_user.id)
        .scalar()
        or 0.0
    )

    # 4. Rating (Average of reviews on my courses)
    # Join CourseReview -> Course -> filter by mentor_id
    from backend.database import CourseReview

    avg_rating = (
        db.query(func.avg(CourseReview.rating))
        .join(Course)
        .filter(Course.mentor_id == current_user.id)
        .scalar()
        or 0.0
    )

    return {
        "total_courses": total_courses,
        "total_students": total_students,
        "revenue": revenue,
        "average_rating": round(avg_rating, 1),
    }


@router.get("/earnings-chart")
def get_earnings_chart(
    current_user: User = Depends(get_current_mentor), db: Session = Depends(get_db)
):
    """Get earnings aggregated by month for the last 6 months"""
    from datetime import timedelta

    from sqlalchemy import extract, func

    today = datetime.now(UTC)
    # Generate labels for last 6 months
    labels = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=i * 30)
        labels.append(d.strftime("%b"))

    # SQL Aggregation
    results = (
        db.query(
            extract("month", Enrollment.enrolled_at).label("month"),
            func.sum(Enrollment.amount_paid).label("total"),
        )
        .join(Course)
        .filter(
            Course.mentor_id == current_user.id,
            Enrollment.enrolled_at >= today - timedelta(days=180),
        )
        .group_by("month")
        .all()
    )

    # Map results (month_int -> total)
    # Note: Extract month returns 1-12.
    data_map = {r.month: float(r.total or 0) for r in results}

    # Build data array matching labels order
    final_data = []

    # We need to match "Jan", "Feb" to month numbers derived from the label generation loop
    # or smarter way: just calculate month number for each label

    for i in range(5, -1, -1):
        d = today - timedelta(days=i * 30)
        m_num = d.month
        final_data.append(data_map.get(m_num, 0.0))

    return {"labels": labels, "data": final_data}


@router.get("/students")
def get_mentor_students(
    current_user: User = Depends(get_current_mentor), db: Session = Depends(get_db)
):
    """List students enrolled in the mentor's courses with progress."""
    rows = (
        db.query(Enrollment, User, Course)
        .join(Course, Course.id == Enrollment.course_id)
        .join(User, User.id == Enrollment.user_id)
        .filter(Course.mentor_id == current_user.id)
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )

    results = []
    for enr, student, course in rows:
        results.append(
            {
                "student_id": student.id,
                "name": student.name or student.email,
                "email": student.email,
                "course_id": course.id,
                "course_title": course.title,
                "progress": enr.progress,
                "status": enr.status,
                "enrolled_at": enr.enrolled_at.isoformat() if enr.enrolled_at else None,
            }
        )
    return {"students": results, "total": len(results)}
