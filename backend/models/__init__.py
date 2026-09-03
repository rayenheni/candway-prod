"""Models package — all SQLAlchemy model classes.

Import order follows the dependency graph:
1. base — engine, session, metadata
2. foundation — users, companies, categories, system, subscriptions, CMS
3. evaluation — North Star scoring, rubrics, verdicts, profiles, AI audit
4. core — jobs, batch jobs, LMS
5. ats — applications, interviews, offers, campaigns, assessments, messaging
6. finance — transactions, invoices, reports
"""

# ── Achievement ─────────────────────────────────────────────────────
from backend.models.achievement import CATALOG, Achievement, seed_achievements_for_user

# ── ATS ─────────────────────────────────────────────────────────────
from backend.models.ats.application import (
    Application,
    CvDocument,
    EEOConsent,
    ExtractedSkill,
    Qualification,
)
from backend.models.ats.campaign import (
    BotIntegration,
    CampaignTemplate,
    EmailSequenceLog,
    EmailTemplate,
    ReEngagementCampaign,
    ReEngagementCandidate,
    WebhookIntegration,
)
from backend.models.ats.candidate import Candidate
from backend.models.ats.interview import (
    Interview,
    InterviewFeedback,
    InterviewParticipant,
    InterviewScorecard,
    ScorecardSubmission,
)
from backend.models.ats.messaging import Conversation, ConversationParticipant, Message
from backend.models.ats.offer import (
    BackgroundCheck,
    BackgroundCheckStatusLog,
    Offer,
    OfferTemplate,
)
from backend.models.ats.pipeline import (
    ActivityLog,
    ApplicationStageHistory,
    CandidateInteraction,
    CandidateRating,
    Comment,
    TaggedNote,
    TeamMember,
)
from backend.models.ats.talent_pool import TalentPool, TalentPoolCandidate
from backend.models.base import (
    DATABASE_URL,
    Base,
    SessionLocal,
    TenantMixin,
    engine,
    get_db,
    utcnow,
)
from backend.models.core.batch_job import (
    BatchJob,
    PipelineAutomationRule,
    PipelineStage,
)

# ── Core ────────────────────────────────────────────────────────────
from backend.models.core.job import ChatbotLead, InterviewQuestion, Job, SavedJob
from backend.models.core.job_extended import (
    JobAIConfig,
    JobCategory,
    JobEvaluationFramework,
    JobNiceToHave,
    JobPipelineStage,
    JobRoleOverview,
    JobScreeningQuestion,
    JobSkill,
)
from backend.models.core.lms import (
    CareerRoadmap,
    Coupon,
    Course,
    CourseReview,
    Enrollment,
    Lesson,
    LessonProgress,
    PayoutRequest,
    Question,
    Quiz,
    Section,
)
from backend.models.evaluation.ai import (
    ABExperiment,
    ABTestAssignment,
    ABTestExperiment,
    AIAuditLog,
    CalibrationSample,
    DBTestResult,
    DriftSnapshot,
    InterviewTurn,
    PromptTest,
    PromptVariant,
    ScoringVariantResult,
    SkillDefinition,
)

# ── Evaluation (North Star) ────────────────────────────────────────
from backend.models.evaluation.config_snapshot import (
    EntryPoint,
    EvaluationConfigSnapshot,
    ResolvedEvaluationConfig,
)
from backend.models.evaluation.evaluation import EvaluationResult, EvaluationSession
from backend.models.evaluation.profile import (
    AdminProfile,
    CandidateProfile,
    RecruiterProfile,
)
from backend.models.evaluation.rubric_snapshot import RubricSnapshot
from backend.models.evaluation.scoring import Rubric, RubricScoringDetail
from backend.models.evaluation.verdict import Verdict

# ── Finance ─────────────────────────────────────────────────────────
from backend.models.finance.credits import CreditTransaction, CreditWallet, UsageEvent
from backend.models.finance.finance import (
    CampaignCost,
    Invoice,
    ReportSnapshot,
    SavedReport,
    Transaction,
)
from backend.models.finance.subscription import Subscription, SubscriptionHistory
from backend.models.foundation.category import Category
from backend.models.foundation.cms import (
    Announcement,
    BlogPost,
    DailyPlatformReport,
    Opportunity,
    SalesCampaign,
    SalesLead,
)
from backend.models.foundation.company import (
    Company,
    CompanyMember,
    CompanyVerification,
)
from backend.models.foundation.subscription import PlanVersion, SubscriptionPlan
from backend.models.foundation.system import (
    PageSection,
    SupportTicket,
    SystemConfig,
    SystemPrompt,
    Ticket,
    TranslationCache,
)

# ── Foundation ──────────────────────────────────────────────────────
from backend.models.foundation.user import (
    AuditLog,
    ConsentLog,
    EmailVerification,
    FeatureFlag,
    LoginAttempt,
    Notification,
    PasswordReset,
    ProfileVisit,
    TokenBlacklist,
    UndoAction,
    User,
)

# ── User Skill ──────────────────────────────────────────────────────
from backend.models.user_skill import UserSkill

__all__ = [
    # base
    "Base",
    "DATABASE_URL",
    "SessionLocal",
    "TenantMixin",
    "engine",
    "get_db",
    "utcnow",
    # foundation
    "Announcement",
    "AuditLog",
    "BlogPost",
    "Category",
    "Company",
    "CompanyMember",
    "CompanyVerification",
    "ConsentLog",
    "DailyPlatformReport",
    "EmailVerification",
    "FeatureFlag",
    "LoginAttempt",
    "Notification",
    "Opportunity",
    "PageSection",
    "PasswordReset",
    "PlanVersion",
    "ProfileVisit",
    "SalesCampaign",
    "SalesLead",
    "SubscriptionPlan",
    "SupportTicket",
    "SystemConfig",
    "SystemPrompt",
    "Ticket",
    "TokenBlacklist",
    "TranslationCache",
    "UndoAction",
    "User",
    # evaluation
    "ABExperiment",
    "ABTestAssignment",
    "ABTestExperiment",
    "AdminProfile",
    "AIAuditLog",
    "CalibrationSample",
    "CandidateProfile",
    "DBTestResult",
    "DriftSnapshot",
    "EntryPoint",
    "EvaluationConfigSnapshot",
    "EvaluationResult",
    "EvaluationSession",
    "InterviewTurn",
    "PromptTest",
    "PromptVariant",
    "RecruiterProfile",
    "ResolvedEvaluationConfig",
    "Rubric",
    "RubricScoringDetail",
    "RubricSnapshot",
    "ScoringVariantResult",
    "SkillDefinition",
    "Verdict",
    # core
    "BatchJob",
    "CareerRoadmap",
    "ChatbotLead",
    "Coupon",
    "Course",
    "CourseReview",
    "Enrollment",
    "InterviewQuestion",
    "Job",
    "JobAIConfig",
    "JobCategory",
    "JobEvaluationFramework",
    "JobNiceToHave",
    "JobPipelineStage",
    "JobRoleOverview",
    "JobScreeningQuestion",
    "JobSkill",
    "Lesson",
    "LessonProgress",
    "PayoutRequest",
    "PipelineAutomationRule",
    "PipelineStage",
    "Question",
    "Quiz",
    "SavedJob",
    "Section",
    # achievement
    "Achievement",
    "seed_achievements_for_user",
    "CATALOG",
    # user skill
    "UserSkill",
    # ats
    "ActivityLog",
    "Application",
    "ApplicationStageHistory",
    "BackgroundCheck",
    "BackgroundCheckStatusLog",
    "BotIntegration",
    "CampaignTemplate",
    "Candidate",
    "CandidateInteraction",
    "CandidateRating",
    "Comment",
    "Conversation",
    "ConversationParticipant",
    "CvDocument",
    "EEOConsent",
    "EmailSequenceLog",
    "EmailTemplate",
    "ExtractedSkill",
    "Interview",
    "InterviewFeedback",
    "InterviewParticipant",
    "InterviewScorecard",
    "Message",
    "Offer",
    "OfferTemplate",
    "Qualification",
    "ReEngagementCampaign",
    "ReEngagementCandidate",
    "ScorecardSubmission",
    "TaggedNote",
    "TalentPool",
    "TalentPoolCandidate",
    "TeamMember",
    "WebhookIntegration",
    # finance
    "CampaignCost",
    "CreditTransaction",
    "CreditWallet",
    "Invoice",
    "ReportSnapshot",
    "SavedReport",
    "Subscription",
    "SubscriptionHistory",
    "Transaction",
    "UsageEvent",
]
