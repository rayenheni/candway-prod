"""SQLAlchemy model definitions."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import deferred, relationship

from backend.models.base import Base, TenantMixin, utcnow

# Late-bound relationships added to User model
from backend.models.foundation.user import User


class Course(Base, TenantMixin):
    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_mentor_id", "mentor_id"),
        Index("ix_courses_category_id", "category_id"),
        Index("ix_courses_status", "status"),
        Index("ix_courses_status_created_at", "status", "created_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Basic Info
    title = Column(String(255))
    subtitle = Column(String(255), nullable=True)
    description = deferred(Column(Text))
    category = Column(String(255))
    difficulty = Column(String(255))  # Beginner, Intermediate, Advanced
    language = Column(String(255), default="English")

    # Media
    thumbnail_url = Column(String(255), nullable=True)
    promo_video_url = Column(String(255), nullable=True)

    # Learning Objectives (JSON arrays)
    what_you_learn = deferred(Column(Text, nullable=True))  # JSON list
    requirements = deferred(Column(Text, nullable=True))  # JSON list
    target_audience = deferred(Column(Text, nullable=True))  # JSON list

    # Duration & Stats
    duration = Column(String(255))
    total_lessons = Column(Integer, default=0)
    total_quizzes = Column(Integer, default=0)

    # Monetization
    price = Column(Float, default=0.0)
    original_price = Column(Float, nullable=True)  # For showing discounts
    currency = Column(String(255), default="TND")

    # External / Affiliate Support
    is_external = Column(Boolean, default=False)
    external_url = Column(String(500), nullable=True)
    affiliate_tag = Column(String(255), nullable=True)

    # Status
    status = Column(String(255), default="draft")  # draft, published, archived
    is_featured = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=utcnow, index=True)
    # FIX-9: added onupdate=utcnow so the field reflects the last actual modification
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True)

    # Relationships
    mentor = relationship("User", back_populates="courses")
    sections = relationship(
        "Section",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Section.order",
    )
    enrollments = relationship("Enrollment", back_populates="course")
    reviews = relationship(
        "CourseReview", back_populates="course", cascade="all, delete-orphan"
    )
    category_rel = relationship("Category")


class Section(Base, TenantMixin):
    __tablename__ = "sections"
    __table_args__ = (
        Index("ix_sections_course_id", "course_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))

    title = Column(String(255))
    description = Column(Text, nullable=True)
    order = Column(Integer)

    # Drip Content
    unlock_after_days = Column(Integer, default=0)  # 0 = immediate access

    # Relationships
    course = relationship("Course", back_populates="sections")
    lessons = relationship(
        "Lesson",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="Lesson.order",
    )
    quizzes = relationship(
        "Quiz",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="Quiz.order",
    )


class Lesson(Base, TenantMixin):
    __tablename__ = "lessons"
    __table_args__ = (
        Index("ix_lessons_section_id", "section_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"))

    title = Column(String(255))
    description = Column(Text, nullable=True)
    content_type = Column(String(255))  # video, text, article
    content_url = Column(String(255))  # Video URL or Article body

    # Video specific
    duration = Column(Integer, default=0)  # Seconds
    video_provider = Column(String(255), nullable=True)  # youtube, vimeo, custom

    # Resources (JSON array of {name, url, type})
    resources = deferred(Column(Text, nullable=True))
    transcript = deferred(Column(Text, nullable=True))

    # Settings
    order = Column(Integer)
    is_free_preview = Column(Boolean, default=False)

    # Relationships
    section = relationship("Section", back_populates="lessons")
    progress = relationship(
        "LessonProgress", back_populates="lesson", cascade="all, delete-orphan"
    )
    # notes = relationship("StudentNote", ...)  # DEPRECATED — table dropped


class Quiz(Base, TenantMixin):
    __tablename__ = "quizzes"
    __table_args__ = (
        Index("ix_quizzes_section_id", "section_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"))

    title = Column(String(255))
    description = Column(Text, nullable=True)
    order = Column(Integer)
    passing_score = Column(Integer, default=70)  # Percentage

    section = relationship("Section", back_populates="quizzes")
    questions = relationship(
        "Question", back_populates="quiz", cascade="all, delete-orphan"
    )
    # results = relationship("QuizResult", ...)  # DEPRECATED — table dropped


class Question(Base, TenantMixin):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_quiz_id", "quiz_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))

    text = Column(Text)
    options = deferred(Column(Text))  # JSON list of options
    correct_option_index = Column(Integer)
    explanation = Column(Text, nullable=True)

    quiz = relationship("Quiz", back_populates="questions")


class Enrollment(Base, TenantMixin):
    __tablename__ = "enrollments"
    __table_args__ = (
        Index("ix_enrollments_user_id", "user_id"),
        Index("ix_enrollments_course_id", "course_id"),
        Index("ix_enrollments_approved_by", "approved_by"),
        Index("ix_enrollments_rejected_by", "rejected_by"),
        UniqueConstraint("user_id", "course_id", name="uq_enrollments_user_course"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))

    # Progress
    progress = Column(Integer, default=0)  # 0-100
    completed_lessons = Column(Integer, default=0)
    total_watch_time = Column(Integer, default=0)  # Seconds

    # Status
    status = Column(String(255), default="active")  # active, completed, expired

    # P0-05 FIX: Approval idempotency on course enrollments.
    # Mirrors the Transaction columns so the manual-payment path
    # can be made safe against double-approval.
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Payment
    amount_paid = Column(Float, default=0.0)
    coupon_used = Column(String(255), nullable=True)
    proof_url = Column(String(255), nullable=True)  # Manual payment proof
    admin_notes = Column(Text, nullable=True)  # Admin rejection reason/notes

    enrolled_at = Column(DateTime, default=utcnow)
    last_accessed_at = Column(DateTime, nullable=True)

    user = relationship(
        "User",
        back_populates="enrollments",
        foreign_keys="Enrollment.user_id",
    )
    course = relationship("Course", back_populates="enrollments")


class LessonProgress(Base, TenantMixin):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        Index("ix_lesson_progress_user_id", "user_id"),
        Index("ix_lesson_progress_lesson_id", "lesson_id"),
        UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    lesson_id = Column(Integer, ForeignKey("lessons.id"))

    completed = Column(Boolean, default=False)
    watch_time = Column(Integer, default=0)  # Seconds watched
    last_position = Column(Integer, default=0)  # Video timestamp

    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)  # FIX-9

    lesson = relationship("Lesson", back_populates="progress")


# ============================================
# NEW PREMIUM FEATURES
# ============================================


class CourseReview(Base, TenantMixin):
    __tablename__ = "course_reviews"
    __table_args__ = (
        Index("ix_course_reviews_user_id", "user_id"),
        Index("ix_course_reviews_course_id", "course_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_course_review_rating"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))

    rating = Column(Integer)  # 1-5 stars
    title = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)

    is_featured = Column(Boolean, default=False)
    helpful_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=utcnow)  # FIX-9

    user = relationship("User")
    course = relationship("Course", back_populates="reviews")


class Coupon(Base, TenantMixin):
    __tablename__ = "coupons"
    __table_args__ = (
        Index("ix_coupons_mentor_id", "mentor_id"),
        Index("ix_coupons_course_id", "course_id"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_coupon_discount",
        ),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # null = admin coupon
    course_id = Column(
        Integer, ForeignKey("courses.id"), nullable=True
    )  # null = site-wide

    code = Column(String(255), unique=True, index=True)
    discount_percent = Column(Integer)  # 0-100

    max_uses = Column(Integer, nullable=True)  # null = unlimited
    current_uses = Column(Integer, default=0)

    valid_from = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utcnow)


class CareerRoadmap(Base, TenantMixin):
    __tablename__ = "career_roadmaps"
    __table_args__ = (
        Index("ix_career_roadmaps_user_id", "user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    target_role = Column(String(255))
    current_skills = Column(Text)  # JSON list
    roadmap_json = deferred(Column(Text))  # JSON: Calendar, Milestones, Todo

    status = Column(String(255), default="active")  # active, completed, archived
    progress = Column(Integer, default=0)  # 0-100
    progress_json = deferred(
        Column(Text, default="{}")
    )  # JSON: Checkbox states {id: true}

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="roadmaps")


# ============================================
# RELATIONSHIPS
# ============================================

User.courses = relationship("Course", back_populates="mentor")
User.enrollments = relationship(
    "Enrollment", back_populates="user", foreign_keys="Enrollment.user_id"
)


# ============================================
# SIMULATION ENGINE MODELS
# ============================================


class PayoutRequest(Base, TenantMixin):
    __tablename__ = "payout_requests"
    __table_args__ = (
        Index("ix_payout_requests_mentor_id", "mentor_id"),
        Index("ix_payout_requests_status", "status"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("users.id"))

    amount = Column(Float)
    currency = Column(String(255), default="TND")
    status = Column(String(255), default="pending")  # pending, paid, rejected

    created_at = Column(DateTime, default=utcnow)
    processed_at = Column(DateTime, nullable=True)

    mentor = relationship("User", back_populates="payouts")


# ============================================
# CONTENT MANAGEMENT MODELS (BLOGS & OPPORTUNITIES)
# ============================================
