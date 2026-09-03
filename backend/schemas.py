from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class Message(BaseModel):
    message: str


class UserSignup(BaseModel):
    email: EmailStr
    password: str
    role: Literal[
        "candidate", "recruiter"
    ]  # Note: 'mentor' assigned by system, not client
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    company_name: Optional[str] = None
    headline: Optional[str] = None


class OrgSignup(BaseModel):
    """Self-service organization (company) signup.

    Company-first signup: the company registers with its billing/KYB
    details up front (kyb_status is set to 'pending' server-side);
    recruiters join later via org-invite only.
    """

    company_name: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    domain: Optional[str] = None
    slug: Optional[str] = None
    billing_email: Optional[str] = None
    billing_address: Optional[str] = None
    tax_id: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    required_role: Optional[str] = None


class GuestLogin(BaseModel):
    app_id: int
    token: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class GuestLoginResponse(Token):
    name: Optional[str] = None
    email: Optional[str] = None
    redirect: Optional[str] = None
    application_id: Optional[int] = None


class OrgSignupResponse(Token):
    id: int
    name: str
    email_verification_required: bool
    company_id: int


class VerifyOTPRequest(BaseModel):
    email: str
    code: str


class ResendOTPRequest(BaseModel):
    email: str
    name: Optional[str] = None
    email_verification_required: Optional[bool] = False


class CourseCreate(BaseModel):
    title: str
    description: str
    category: str
    difficulty: str
    duration: str
    thumbnail_url: Optional[str] = None
    url: str
    price: float = 0.0
    status: str = "draft"
    subtitle: Optional[str] = None
    promo_video_url: Optional[str] = None
    language: Optional[str] = "English"
    original_price: Optional[float] = None
    what_you_learn: Optional[str] = None
    requirements: Optional[str] = None
    target_audience: Optional[str] = None


class CourseOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    difficulty: str
    duration: str
    thumbnail_url: Optional[str]
    price: float
    status: str
    mentor_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssessmentScore(BaseModel):
    interview_score: float
    interviewer_notes: str


class SectionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order: int


class LessonCreate(BaseModel):
    title: str
    content_type: str  # 'video' or 'text'
    content_url: str
    duration: int
    order: int
    is_free_preview: bool = False


class QuestionCreate(BaseModel):
    text: str
    options: List[str]
    correct_option_index: int


class QuizCreate(BaseModel):
    title: str
    order: int
    questions: List[QuestionCreate]


class QuestionOut(BaseModel):
    id: int
    text: str
    options: List[str]

    model_config = ConfigDict(from_attributes=True)


class QuizOut(BaseModel):
    id: int
    title: str
    order: int
    questions: List[QuestionOut]

    model_config = ConfigDict(from_attributes=True)


class LessonOut(BaseModel):
    id: int
    title: str
    content_type: str
    content_url: str
    duration: int
    order: int
    is_free_preview: bool

    model_config = ConfigDict(from_attributes=True)


class ProgressUpdate(BaseModel):
    completed: bool
    watch_time: Optional[int] = 0
    last_position: Optional[int] = 0


class SectionOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    order: int
    lessons: List[LessonOut]
    quizzes: List[QuizOut]

    model_config = ConfigDict(from_attributes=True)


class CourseCurriculum(BaseModel):
    id: int
    sections: List[SectionOut]

    model_config = ConfigDict(from_attributes=True)


class EnrollmentOut(BaseModel):
    id: int
    course_id: int
    user_id: int
    progress: int
    status: str
    course: CourseOut

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):  # Assuming UserBase is a new base class for UserResponse
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None


class UserResponse(UserBase):
    id: int
    created_at: datetime
    role: str
    tier: str = "free"
    subscription_status: str = "active"
    subscription_end: Optional[datetime] = None

    avatar_url: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    company_name: Optional[str] = None
    company_description: Optional[str] = None
    company_logo_url: Optional[str] = None

    admin_permissions: Optional[str] = None  # RBAC

    model_config = ConfigDict(from_attributes=True)


# Subscription Schemas
class SubscriptionPlanBase(BaseModel):
    name: str
    slug: str
    target_audience: str
    price_monthly: float = 0.0
    price_yearly: float = 0.0
    currency: str = "USD"
    features: Optional[str] = "[]"  # JSON string
    permissions_json: Optional[str] = (
        "{}"  # JSON string: {"ghost_formatter": true, ...}
    )
    is_active: bool = True
    is_featured: bool = False

    # Quotas
    job_limit: int = 5
    cv_limit: int = 50
    ai_interview_limit: int = 10
    team_seat_limit: int = 1

    # Candidate Limits
    candidate_cv_uploads_limit: int = 2
    candidate_ai_analyses_limit: int = 1
    candidate_pdf_downloads_limit: int = 0
    candidate_job_matches_limit: int = 5

    # Billing / credit engine (S1 redesign)
    credits_monthly: int = 0
    plan_group: str = "standard"


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    target_audience: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    currency: Optional[str] = None
    features: Optional[str] = None
    permissions_json: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

    # Quotas
    job_limit: Optional[int] = None
    cv_limit: Optional[int] = None
    ai_interview_limit: Optional[int] = None
    team_seat_limit: Optional[int] = None

    # Candidate Limits
    candidate_cv_uploads_limit: Optional[int] = None
    candidate_ai_analyses_limit: Optional[int] = None
    candidate_pdf_downloads_limit: Optional[int] = None
    candidate_job_matches_limit: Optional[int] = None

    # Billing / credit engine (S1 redesign)
    credits_monthly: Optional[int] = None
    plan_group: Optional[str] = None


class SubscriptionPlan(SubscriptionPlanBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserUsageResponse(BaseModel):
    user_id: int
    name: str
    email: str
    tier: str
    plan_name: Optional[str] = None
    usage_jobs: int
    job_limit: int
    usage_cvs: int
    cv_limit: int
    usage_ai_interviews: int
    ai_interview_limit: int
    subscription_status: str
    subscription_end: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# CMS Schemas
class PageSectionUpdate(BaseModel):
    content_json: str  # JSON string


class PageSectionResponse(BaseModel):
    id: int
    page_slug: str
    section_slug: str
    content_json: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    avatar_url: Optional[str] = None
    password: Optional[str] = None


class RoleRequest(BaseModel):
    role: str


class VerifyRequest(BaseModel):
    role: str
    questions: List[str]
    answers: List[str]


class JobCreate(BaseModel):
    title: str
    company: str
    company_name: str = ""
    location: str
    salary_range: str
    type: str  # 'Remote', 'Onsite', 'Hybrid'
    description: str
    required_skills: List[str]
    interview_instructions: Optional[str] = None  # Recruiter custom interview rules
    total_questions: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    duration_minutes: Optional[int] = None
    category_id: Optional[int] = None
    skill_tree_id: Optional[int] = None

    def __init__(self, **data):
        if "company_name" not in data or not data["company_name"]:
            data["company_name"] = data.get("company", "")
        super().__init__(**data)


class RecruiterSettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


class ApplicationOut(BaseModel):
    id: int
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    role: Optional[str] = None
    score: float
    cv_score: Optional[float] = None
    status: str
    created_at: str
    verdict: Optional[str] = None
    cv_url: Optional[str] = None
    job_title: Optional[str] = None
    analysis_summary: Optional[str] = None


class AIRequest(BaseModel):
    application_id: Optional[int] = None
    candidate_id: Optional[int] = None  # Legacy support
    context: Optional[str] = None


class CheatReport(BaseModel):
    application_id: int
    reason: str
    details: str


class HiringChatRequest(BaseModel):
    question: str
    history: List[Dict[str, str]] = []  # List of {role: user/assistant, content: ...}


class GlobalHiringChatRequest(BaseModel):
    question: str
    history: List[Dict[str, str]] = []


class CandidateCard(BaseModel):
    id: int
    name: str
    role: Optional[str] = "Candidate"
    score: Optional[float] = 0.0
    image_url: Optional[str] = None
    summary: Optional[str] = None


class GlobalHiringResponse(BaseModel):
    reply: str
    candidates: List[CandidateCard] = []


class TTSRequest(BaseModel):
    text: str


class SystemSettings(BaseModel):
    maintenance_mode: bool = False
    free_trial: bool = False
    konnect_wallet_id: Optional[str] = None
    konnect_api_key: Optional[str] = None
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    groq_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ai_provider: Optional[str] = "groq"
    ai_temperature: Optional[float] = 0.5
    ai_model: Optional[str] = "groq/compound"
    platform_fee_percent: Optional[float] = 20.0
    use_local_llm: bool = False
    local_llm_url: Optional[str] = "http://localhost:11434"
    local_llm_model: Optional[str] = "llama3"
    default_language: Optional[str] = "en"
    bank_name: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_iban: Optional[str] = None
    payment_instructions: Optional[str] = None
    automations_enabled: bool = True
    ab_test_enabled: bool = False
    ab_test_bucket_size: int = 10
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_enabled: bool = False


class CouponCreate(BaseModel):
    code: str
    discount_percent: float
    max_uses: Optional[int] = None
    expires_in_days: Optional[int] = None


class MarketingCampaign(BaseModel):
    title: str
    subject: str
    content: str


class SystemPromptUpdate(BaseModel):
    key: str
    content: str
    description: Optional[str] = None


class TicketReply(BaseModel):
    message: str
    close_ticket: bool = False


# ============================================
# TUNISIAN ADMIN SCHEMAS (PHASE 1)
# ============================================


class CompanyVerificationCreate(BaseModel):
    company_name: str
    matricule_fiscale: str
    registre_commerce_id: str
    address: str
    document_url: str


class CompanyVerificationResponse(CompanyVerificationCreate):
    id: int
    user_id: int
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AnnouncementCreate(BaseModel):
    title: str
    message: str
    type: str = "info"  # info, warning, critical
    target_role: str = "all"  # all, recruiter, candidate
    expires_at: Optional[datetime] = None


class AnnouncementResponse(AnnouncementCreate):
    id: int
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================
# TUNISIAN ADMIN FINANCIALS (PHASE 2)
# ============================================


class InvoiceCreate(BaseModel):
    user_id: int
    company_id: Optional[int] = None
    transaction_id: Optional[int] = None
    amount_ht: float
    description: str = "Service Platform fee"


class InvoiceUpdate(BaseModel):
    client_name: Optional[str] = None
    client_mf: Optional[str] = None
    client_address: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    user_id: int
    company_id: Optional[int] = None
    transaction_id: Optional[int]

    amount_ht: float
    tva_rate: float
    tva_amount: float
    stamp_duty: float
    total_ttc: float

    client_name: str
    client_mf: Optional[str] = None
    status: str
    pdf_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CopilotChatRequest(BaseModel):
    question: str
    history: List[Dict[str, str]] = []


class CopilotResponse(BaseModel):
    reply: str
    candidates: List[dict] = []
    intent: str = "general_qa"
    suggested_actions: List[str] = []


class AutoJobCreateRequest(BaseModel):
    title: str
    skills: List[str]
    seniority: str = "mid"
    company: Optional[str] = None
    location: Optional[str] = None
    type: Optional[str] = "Full-time"
    description_override: Optional[str] = None


class QuestionGenerateRequest(BaseModel):
    job_id: int
    count: int = 5


class QuestionOut(BaseModel):
    id: int
    job_id: int
    question: str
    type: str = "technical"
    difficulty: str = "medium"
    skill_focus: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QuestionCreate(BaseModel):
    job_id: int
    question: str
    type: str = "technical"
    difficulty: str = "medium"
    skill_focus: Optional[str] = None


class ScoringWeights(BaseModel):
    weight_cv: float = 0.25
    weight_interview: float = 0.40
    weight_rubric: float = 0.25
    weight_human: float = 0.10
