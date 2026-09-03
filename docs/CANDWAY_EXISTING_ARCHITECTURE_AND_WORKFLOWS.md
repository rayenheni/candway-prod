# Candway — Existing Architecture and Workflows

**Status:** Factual documentation of the current state of the codebase as found.
**Scope:** Verified information only. No recommendations, proposals, or future ideas.
**Date of research:** 2026-08-16

---

## 1. Product Overview

Candway is a recruitment platform implemented as a React single-page application (SPA) backed by a FastAPI REST API. The platform covers the recruiting lifecycle: job posting, candidate application, CV upload and AI analysis, AI-driven interviewing, scoring and evaluation, and recruiter-side campaign management.

Evidence of the core product areas:

| Area | Evidence |
|---|---|
| Job board & application | `backend/routers/public.py` (`/jobs/public`), `backend/routers/candidate/jobs.py` (`/jobs/{job_id}/apply`) |
| AI CV analysis | `backend/ai/cv_analysis.py`, `backend/routers/candidate/cv.py` |
| AI interview | `backend/routers/ai_interview/` (chat, session, evaluation, questions, media) |
| Recruiter campaign manager | `backend/routers/recruiter_campaigns/` |
| Scoring | `backend/scoring_service.py`, `backend/rubric/` |

Users of the platform are organized by role (see Section 2). The platform is multi-tenant: most business entities carry a `company_id` (TenantMixin), and tenant isolation is enforced in queries (`backend/tenant.py`, `backend/authz.py`).

The main implemented workflows are:
- Candidate signup/login, profile building, job discovery, and application.
- Recruiter job creation (via a wizard), candidate/CV management, and campaign management.
- AI CV scoring, AI interviews, and deterministic rubric-weighted scoring.
- Monetization: subscription plans, a credit wallet, manual payment proofs, and admin approval.

---

## 2. User Roles Found

Role values found in `backend/models/foundation/user.py:39` (`role = Column(String(255))` with comment `'candidate', 'recruiter', 'mentor', 'admin'`) and `frontend/src/types/index.ts:6` (`UserRole = 'candidate' | 'recruiter' | 'mentor' | 'admin' | 'company'`). The `company` role (formerly `organization`) is used for the org/company portal; `require_org_admin` accepts both `("company", "organization")` per `backend/dependencies.py`.

| Role | Purpose | Evidence | Main Areas |
|---|---|---|---|
| candidate | Applies to jobs, uploads CV, completes AI interviews, manages profile | `backend/routers/candidate/`, `backend/dependencies.py:839` (`require_candidate`) | `/candidate/*`, dashboard, jobs, applications, CV builder, interviews |
| recruiter | Creates jobs, manages candidates/applications, runs campaigns, reviews scores | `backend/routers/recruiter_*`, `backend/dependencies.py:707` (`require_recruiter`) | `/recruiter/*`, dashboard, pipeline, campaigns, candidates, rubrics |
| admin | Platform administration: users, plans, subscriptions, credits, finance, KYB, content | `backend/routers/admin/`, `backend/dependencies.py:831` (`require_admin`) | `/admin/*`, finance dashboard, payment proofs |
| mentor | Mentorship-oriented areas (student roster, wallet, stats) | `backend/routers/mentor.py`, `backend/dependencies.py:847` (`require_mentor`) | `/mentor/*`, students, wallet |
| company (org) | Company/org portal owner; manages members, billing, KYB, analytics | `backend/routers/org/`, `backend/dependencies.py:738` (`require_company_admin`), `:776` (`require_org_admin`) | `/org/*`, members, billing, analytics |
| guest (unregistered) | Invited candidates with interview-scoped access tokens | `backend/dependencies.py:399` (`get_interview_access`), guest login `backend/routers/auth.py:875` (`/guest-login`) | Interview room, interview analysis |

Frontend route-level guard evidence: `frontend/src/app/router.tsx` (`allowed(roles, children)` helper at lines 178–180), `frontend/src/app/guards/auth-guard.tsx` (`RoleGuard`, `InterviewRoomRoute`, `InterviewAnalysisRoute`).

---

## 3. Frontend Architecture

| Area | Description | Evidence |
|---|---|---|
| Framework | React 19.2.6, TypeScript 5.9.3, Vite 7.3.2 build tool | `frontend/package.json:43-44,58,62` |
| Styling | Tailwind CSS 4.1.17 via `@tailwindcss/vite`; class-based dark mode; Inter + Zain fonts | `frontend/package.json:54`, `frontend/src/index.css` |
| Routing | react-router v7 data router (`createBrowserRouter`); all pages code-split via `React.lazy()` | `frontend/package.json:47`, `frontend/src/app/router.tsx` |
| Layouts | `AuthLayout` (pre-login), `DashboardLayout` (Sidebar + Topbar + Outlet), `MarketingLayout` | `frontend/src/layouts/auth-layout.tsx`, `dashboard-layout.tsx`, `dashboard/{sidebar,topbar}.tsx`, `frontend/src/features/marketing/components/marketing-layout.tsx` |
| Role guards | `ProtectedRoute` (auth gate), `RoleGuard` (role allowlist, redirect to `/dashboard`), `InterviewRoomRoute`/`InterviewAnalysisRoute` (guest cookie `logged_in=true` exception) | `frontend/src/app/guards/auth-guard.tsx:16-68` |
| Feature folders | 28 feature folders, ~123 `.tsx` pages (auth, admin, candidate, recruiter, org, mentor, marketing, interviews, jobs, dashboard, courses, etc.) | `frontend/src/features/**/pages/*.tsx` |
| Services | 29 service modules calling `/api/v1` endpoints through a shared `apiClient` | `frontend/src/services/*.ts` |
| State / context | TanStack React Query v5 (global client in `App.tsx`); React contexts: `AuthProvider`, `ThemeProvider`, `LanguageProvider`, `SidebarProvider` | `frontend/src/App.tsx`, `frontend/src/contexts/` |
| API client | Cookie-based (`credentials: 'include'`), CSRF token handling, 401 auto-refresh, 402 insufficient-credits dispatch, 15s timeout | `frontend/src/lib/api-client.ts` |
| i18n | 4 locales: `en`, `fr`, `ar`, `tn`; RTL auto-set for `ar`/`tn` | `frontend/src/i18n/dictionaries.ts` |
| Shared UI | 18 Radix-based primitives (Button, Card, Dialog, Select, Tabs, Toast, etc.) + `CVEvaluation` component | `frontend/src/shared/components/ui/`, `frontend/src/shared/components/cv-evaluation.tsx` |
| Main pages | Landing, auth (login/register/verify), dashboards per role, job board, candidate profile, recruiter candidates/applications, admin finance, org billing | `frontend/src/app/router.tsx` |
| E2E tests | Playwright suite (landing, auth, recruiter-flow, candidate-flow) | `frontend/playwright.config.ts`, `frontend/e2e/*.spec.ts` |
| Build output | `outDir: ../static/app` (SPA served by FastAPI/nginx) | `frontend/vite.config.ts:23-27` |

---

## 4. Backend Architecture

| Area | Description | Evidence |
|---|---|---|
| Framework | FastAPI; app factory `create_app()` | `backend/app.py:127` |
| API prefix | `/api/v1` (all routers mounted under this prefix) | `backend/app.py`, `docker-compose.yml` healthcheck on `/api/v1/monitoring/health` |
| Server entry | Dev: `backend/main.py` (uvicorn, port 8000, `--reload`); Prod: gunicorn with UvicornWorker (4 workers) | `Procfile`, `run_server.py` |
| Router organization | ~50 modules in `backend/routers/__init__.py`; grouped packages: `admin/`, `candidate/`, `ai_interview/`, `org/`, `analytics/`, `recruiter_campaigns/`, `recruiter_candidates/`, `recruiter_collaboration/`, `recruiter_enhancements/`, `recruiter_interviews/` | `backend/routers/__init__.py` |
| Services | `scoring_service.py`, `credit_service.py`, `subscription_service.py`, `subscription_lifecycle_service.py`, `candidate_subscription_service.py`, `admin_financial_service.py`, `analytics_service.py`, `eeo_analytics_service.py`, `org_analytics_service.py`, `backend/services/feature_service.py`, `rubric_match_service.py`, `email_service.py`, `report_builder.py`, `calendar_service.py`, `cv_service.py`, `background_check_service.py`, `adverse_action_service.py` | `backend/*.py`, `backend/services/*.py` |
| Dependencies / auth | `get_current_user`, `get_optional_user`, `require_candidate/recruiter/admin/mentor`, `require_company_admin`, `require_org_admin`, `require_credits`, `get_interview_access`, `get_current_company_id` | `backend/dependencies.py` |
| Models | SQLAlchemy models under `backend/models/` (foundation, evaluation, core, ats, finance) | `backend/models/__init__.py` |
| Database setup | SQLAlchemy engine/session in `backend/models/base.py`; backward-compat shim `backend/database.py`; Alembic migrations (`alembic/`); no `create_all` at import (Alembic is source of truth) | `backend/models/base.py`, `backend/app.py` (P0-01 note), `alembic/` |
| Background jobs | APScheduler `AsyncIOScheduler` in `backend/scheduler.py` (interview reminders, offer expiration, scheduled reports, storage cleanup, subscription-period cron, pending-payment reminders); background workers with own `SessionLocal()` | `backend/scheduler.py`, `backend/automation_worker.py`, `backend/email_sequence_worker.py`, `backend/webhook_dispatcher.py`, `backend/jobs/scoring.py`, `backend/routers/recruiter_campaigns/upload.py` |
| Security middleware | CORS, TrustedHost, BodySizeLimit, Metrics, RateLimit; JWT (jose), bcrypt, CSRF, rate limiting (Redis, fails open), tenant isolation, file upload validation | `backend/app.py`, `backend/dependencies.py`, `backend/security.py`, `backend/tenant.py`, `backend/rate_limit_middleware.py`, `backend/body_size_middleware.py`, `backend/file_security.py` |
| AI modules | `backend/ai/` (llm, prompts, security, validation, privacy, token_tracker, cost_controller, bias_detection, cv_analysis, scoring_jobs, worker, resilience) | `backend/ai/*.py` |
| Rubric engine | Deterministic rubric engine under `backend/rubric/` (rubric_engine, rubric_loader, rubric_schema, rubric_snapshotter, scoring_aggregator, skill_mapper, evidence_analyzer, config_resolver) + `backend/rubric/rubric_router.py` | `backend/rubric/*.py` |
| Repository layer | `backend/repository/` exports `MetricsRepository` | `backend/repository/__init__.py` |
| Encryption | Fernet-backed `EncryptedText` TypeDecorator for PII columns; secret encryption for SystemConfig sensitive keys | `backend/encryption.py`, `backend/secret_encryption.py` |

---

## 5. Database / Models

Model registry and import order: `backend/models/__init__.py` (base → foundation → evaluation → core → ats → finance).

| Model | Table | Purpose | Key Relations | Evidence |
|---|---|---|---|---|
| User | users | Platform account; role/tier; `hashed_password`, `temp_password` | CandidateProfile, RecruiterProfile, AdminProfile, CompanyMember | `backend/models/foundation/user.py` |
| Company | companies | Tenant; plan_id, KYB fields, seats, billing info | CompanyMember, SubscriptionPlan, User | `backend/models/foundation/company.py` |
| CompanyMember | company_members | User↔Company membership with role | Company, User | `backend/models/foundation/company.py` |
| SubscriptionPlan | subscription_plans | Paid/free plans (credits_monthly, limits, plan_group) | PlanVersion | `backend/models/foundation/subscription.py` |
| PlanVersion | plan_versions | Immutable price/limit snapshot (grandfathering) | SubscriptionPlan | `backend/models/foundation/subscription.py` |
| SystemConfig | system_config | Key/value config (incl. encrypted sensitive keys) | — | `backend/models/foundation/` |
| FeatureFlag | feature_flags | Toggle system with audiences/rollout | — | `backend/models/foundation/user.py` |
| AuditLog | audit_logs | Immutable audit trail of admin/mutation events | — | `backend/models/foundation/user.py` |
| ConsentLog | consent_logs | Immutable consent records | User | `backend/models/foundation/user.py` |
| CandidateProfile | candidate_profiles | Candidate user-scoped profile (company_id nullable) | User | `backend/models/evaluation/profile.py` |
| RecruiterProfile | recruiter_profiles | Recruiter profile mirror (single source of truth reads) | User | `backend/models/evaluation/profile.py` |
| EvaluationSession | evaluation_sessions | AI interview session; optimistic `version_id`; status/interview_state | Application, EvaluationResult, InterviewTurn | `backend/models/evaluation/evaluation.py` |
| EvaluationResult | evaluation_results | Canonical scoring result (final_score, verdict, score_breakdown) | EvaluationSession, Rubric | `backend/models/evaluation/evaluation.py` |
| InterviewTurn | interview_turns | Per-question turn records | EvaluationSession | `backend/models/evaluation/evaluation.py` |
| Rubric | rubrics | Evaluation rubric (job-linked or standalone); criteria_json; versioned | Job, BatchJob, EvaluationResult | `backend/models/evaluation/scoring.py` |
| RubricScoringDetail | rubric_scoring_details | Per-skill scoring rows (source `cv` for CV rubric breakdown) | EvaluationResult | `backend/models/evaluation/` |
| RubricSnapshot | rubric_snapshots | Immutable rubric at evaluation time | EvaluationSession, Job | `backend/models/evaluation/` |
| EvaluationConfigSnapshot | evaluation_config_snapshots | Immutable evaluation config at eval time | BatchJob (active_snapshot_id) | `backend/models/evaluation/config_snapshot.py` |
| Job | jobs | Job posting; version_id optimistic lock; rubric_id | Application, JobSkill, JobCategory | `backend/models/core/job.py` |
| BatchJob | batch_jobs | Campaign batch; rubric_id, active_snapshot_id, worker_status | Job, Rubric, Application, EvaluationConfigSnapshot | `backend/models/core/batch_job.py` |
| JobSkill / JobEvaluationFramework / JobAIConfig / JobCategory / JobPipelineStage | job_skills, job_evaluation_framework, job_ai_configs, job_categories, job_pipeline_stages | Job wizard step data | Job | `backend/models/core/job_extended.py` |
| Application | applications | Candidate application; status enum; evaluation_state; EncryptedText PII | User, Job, BatchJob, Candidate, CvDocument | `backend/models/ats/application.py` |
| Candidate | candidates | Deduplicated candidate entity (unique company+email) | Application, TalentPoolCandidate | `backend/models/ats/candidate.py` |
| CvDocument | cv_documents | Persisted CV text/analysis_json/detected_role | Application, EvaluationSession | `backend/models/ats/` |
| Qualification | qualifications | Candidate qualification documents (company_id nullable) | Application | `backend/models/ats/application.py` |
| Interview | interviews | Scheduled recruiter interview (uq app+scheduled_time) | Application, InterviewParticipant, InterviewFeedback | `backend/models/ats/` |
| Offer | offers | Job offers with esign; version_id lock | Application, OfferTemplate | `backend/models/ats/` |
| CreditWallet | credit_wallets | Credit balance with optimistic `version` lock (unique user) | User, CreditTransaction | `backend/models/finance/credits.py` |
| CreditTransaction | credit_transactions | Immutable signed ledger; unique idempotency_key | CreditWallet | `backend/models/finance/credits.py` |
| UsageEvent | usage_events | Append-only AI usage metering (cost_usd) | — | `backend/models/finance/credits.py` |
| Subscription | subscriptions | Active subscription row (plan, status, period) | User, Plan, Transaction | `backend/models/finance/subscription.py` |
| SubscriptionHistory | subscription_history | Immutable lifecycle audit | Subscription | `backend/models/finance/subscription.py` |
| Transaction | transactions | Payments; proof workflow (proof_status/verified_by/review_notes), fiscal fields | User, Invoice | `backend/models/finance/finance.py` |
| Invoice | invoices | B2B invoices (INV-YYYY-0001), client_mf, status | Transaction | `backend/models/finance/finance.py` |
| LMS models | courses, sections, lessons, quizzes, enrollments, lesson_progress, course_reviews, coupons, career_roadmaps | Learning modules | Course → Section → Lesson, etc. | `backend/models/core/lms.py` |
| Messaging models | conversations, conversation_participants, messages | In-platform messaging | User | `backend/models/ats/messaging.py` |
| TalentPool / TalentPoolCandidate | talent_pools, talent_pool_candidates | Candidate pools | Candidate | `backend/models/ats/talent_pool.py` |

---

## 6. Main Modules Found

| Module | Exists? | Status | Backend Evidence | Frontend Evidence | Notes |
|---|---|---|---|---|---|
| Auth | Yes | Complete | `backend/routers/auth.py` (signup, login, OTP, verify-email, reset/change password, Google, refresh, logout, guest-login) | `frontend/src/services/auth.service.ts`, `frontend/src/features/auth/pages/*` | |
| Admin | Yes | Complete | `backend/routers/admin/` (users, subscriptions, credits, plans, finance, invoices, kyb, organizations, payments, jobs, interviews, courses, tickets, settings, system, marketing, cms, analytics, verifications) | `frontend/src/features/admin/pages/*` (25 pages) | |
| Company / Organization | Yes | Complete | `backend/routers/org/` (members, billing, analytics) | `frontend/src/features/org/pages/*` | Role `company` (was `organization`) |
| Recruiter | Yes | Complete | `backend/routers/recruiter_dashboard.py`, `recruiter_settings.py`, `recruiter_jobs.py`, `recruiter_job_wizard.py`, `recruiter_offers.py`, `recruiter_reports.py`, `recruiter_skill_trees.py`, etc. | `frontend/src/features/recruiter/pages/*` (24 pages) | |
| Campaign Manager / BatchJob | Yes | Complete | `backend/routers/recruiter_campaigns/` (management, upload, candidates, templates, team, tracking) | `frontend/src/features/recruiter/pages/campaign-*.tsx` | |
| Jobs | Yes | Complete | `backend/routers/recruiter_jobs.py`, `candidate/jobs.py`, `public.py` | `frontend/src/features/jobs/pages/*`, `frontend/src/services/jobs.service.ts` | |
| Applications | Yes | Complete | `backend/routers/candidate/applications.py`, `recruiter_candidates/applications.py` | `frontend/src/features/candidates/pages/application-detail.tsx`, `applications-tracker.tsx` | |
| Candidates | Yes | Complete | `backend/routers/candidate_management.py`, `recruiter_candidates/{search,scoring,invitations,integrations,email}.py` | `frontend/src/features/candidates/pages/candidates-list.tsx` | |
| CV upload | Yes | Complete | `backend/routers/candidate/cv.py` (`/upload-cv`), `backend/routers/uploads.py`, `backend/cv_service.py` | `frontend/src/features/cv-builder/pages/cv-builder-page.tsx` | |
| CV analysis | Yes | Complete | `backend/ai/cv_analysis.py`, `backend/scoring_service.py`, `backend/routers/candidate/cv.py` (`/analyze`) | `frontend/src/features/cv-review/pages/cv-review-page.tsx` | |
| Rubrics | Yes | Complete | `backend/rubric/rubric_router.py`, `backend/routers/recruiter_skill_trees.py` | `frontend/src/features/rubrics/pages/rubrics-page.tsx`, `skill-tree-*.tsx` | |
| Skill trees | Yes | Complete | `backend/routers/recruiter_skill_trees.py` (standalone create, AI generate, detail, edit, duplicate) | `frontend/src/features/recruiter/pages/skill-tree-*.tsx` | |
| AI interview | Yes | Complete | `backend/routers/ai_interview/` (chat, session, evaluation, questions, media) | `frontend/src/features/interviews/pages/interview-room.tsx`, `interview-analysis.tsx` | |
| Evaluation / scoring | Yes | Complete | `backend/scoring_service.py`, `scoring_engine.py`, `backend/rubric/` | `frontend/src/features/recruiter/pages/recruiter-interview-analysis.tsx` | |
| Reports | Yes | Complete | `backend/routers/recruiter_reports.py`, `analytics/reports.py`, `report_builder.py`, `report_scheduler.py` | `frontend/src/features/reports/pages/*` | |
| Analytics | Yes | Complete | `backend/routers/analytics/` (insights, reports, monitoring), `analytics_service.py`, `admin_analytics_service.py`, `org_analytics_service.py`, `eeo_analytics_service.py` | `frontend/src/features/analytics/pages/analytics-dashboard.tsx` | |
| Billing / credits | Yes | Complete | `backend/routers/admin/{subscriptions,credits,plans,finance,invoices}.py`, `org/billing.py`, `candidate/subscriptions.py`, `credit_service.py`, `subscription_lifecycle_service.py`, `admin_financial_service.py` | `frontend/src/features/admin/pages/{finance-dashboard,payments,payment-proofs}.tsx`, `org/pages/org-billing.tsx` | |
| Notifications / email | Yes | Complete | `backend/routers/notifications.py`, `email_service.py`, `email_utils.py`, `email_sequence_worker.py` | `frontend/src/services/notifications.service.ts` | |
| Messaging | Yes | Complete | `backend/routers/messages.py`, `backend/models/ats/messaging.py` | `frontend/src/features/messages/pages/messages-page.tsx` | |
| Calendar | Yes | Complete | `backend/routers/calendar.py`, `calendar_service.py` | `frontend/src/features/calendar/pages/calendar-page.tsx` | |
| Courses / LMS | Yes | Complete | `backend/routers/courses.py`, `admin/courses.py`, `backend/models/core/lms.py` | `frontend/src/features/courses/pages/courses-list.tsx` | |
| Mentor | Yes | Partial | `backend/routers/mentor.py` (stats, earnings-chart, students), achievements, skill-progress | `frontend/src/features/mentor/pages/{mentor-students,mentor-wallet}.tsx` | Several mentor routes are ComingSoon placeholders |
| GDPR / consent | Yes | Complete | `backend/routers/gdpr.py`, `consent.py`, `gdpr_erasure.py`, `ConsentLog` | — | Art. 17 erasure, consent agreements |
| Feature flags | Yes | Complete | `backend/routers/feature_flags.py`, `backend/services/feature_service.py` | `frontend/src/services/` (uses `/feature-flags/config`) | |
| Support | Yes | Partial | `backend/routers/support.py`, `admin/tickets.py`, `SupportTicket` model | `frontend/src/features/admin/pages/support.tsx` | |
| Job fair | No | Not found | No `job_fair*` router or module found | Not found | |
| Agency workflow | No | Not found | No dedicated `agency*` module found | Not found | |
| Hiring copilot | Yes | Partial | `backend/routers/copilot.py`, `copilot_admin.py`, `hiring.py` (chat, embed-candidates) | `frontend/src/features/recruiter/pages/copilot.tsx` | |
| JD bias detection | Yes | Complete | `backend/routers/jd_bias.py`, `backend/bias_detection_jd.py` | `frontend/src/services/jd-bias.service.ts` | |
| EEO | Yes | Complete | `backend/routers/recruiter_eeo.py`, `candidate/eeo.py`, `eeo_analytics_service.py` | `frontend/src/services/eeo.service.ts` | |
| Background checks | Yes | Complete | `backend/routers/recruiter_background_checks.py`, `background_check_service.py`, `adverse_action_service.py` | `frontend/src/services/background-checks.service.ts` | |
| Career roadmap | Yes | Complete | `backend/routers/career.py` (`/career/plan`) | `frontend/src/services/candidate.service.ts` (career/roadmap) | |
| Chatbot | Yes | Complete | `backend/routers/chatbot.py` | `frontend/src/features/recruiter/pages/chatbot-leads.tsx` | |
| LinkedIn integration | Yes | Partial | `backend/routers/linkedin.py` (auth, post-job, import-profile) | — | |

---

## 7. Core Workflows That Exist

### 7.1 Authentication Flow

| Step | Description | Evidence |
|---|---|---|
| Signup | `POST /auth/signup`; candidate/recruiter accounts; OTP email verification; consent logging | `backend/routers/auth.py:349` |
| Org signup | `POST /auth/signup/org`; creates Company with billing/KYB fields, issues role `company` | `backend/routers/auth.py:546` |
| Email verification | OTP generation + `POST /auth/verify-otp`, `POST /auth/resend-otp`; `GET /auth/verify-email/{token}` | `backend/routers/auth.py:708,774,1122` |
| Login | `POST /auth/login` (bcrypt, backoff check); sets auth + CSRF cookies | `backend/routers/auth.py:963` |
| Guest login | `POST /auth/guest-login` for invited candidates; interview-scoped access | `backend/routers/auth.py:875`, `backend/dependencies.py:399` |
| Password | `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/change-password` | `backend/routers/auth.py:1300,1370,1458` |
| Session | `GET /auth/me`, `PUT /auth/me`, `POST /auth/refresh`, `POST /auth/logout` | `backend/routers/auth.py:1153,1181,1657,1247` |
| Google | `GET /auth/google/login`, `GET /auth/google/callback` | `backend/routers/auth.py:1513,1555` |
| Frontend | Login/register/verify/OTP pages; cookie + CSRF + 401 auto-refresh in apiClient | `frontend/src/features/auth/pages/*`, `frontend/src/lib/api-client.ts` |

### 7.2 Candidate Job Apply Flow

| Step | Description | Evidence |
|---|---|---|
| Job discovery | Public job board `GET /jobs/public` and `GET /jobs/public/{job_id}`; candidate matches `GET /candidate/jobs/matches` | `backend/routers/public.py`, `backend/routers/candidate/jobs.py:221` |
| Job detail | `GET /candidate/jobs/{job_id}` | `backend/routers/candidate/jobs.py:327` |
| Apply | `POST /candidate/jobs/{job_id}/apply`; dedupe check; reuses latest CV text or synthesizes from builder data | `backend/routers/candidate/jobs.py:375-414` |
| CV upload/analysis | `POST /candidate/analyze` (requires 3 credits) → Application (status `analyzing`) → `sync_cv_document` → `ScoringService.set_cv_only` → status `analyzed`/`failed` | `backend/routers/candidate/cv.py:568`, `backend/scoring_service.py` |
| Application status | Statuses incl. pending, screening, interviewing, offer, rejected, analyzed, applied, invited, active, hired, offer_declined, withdrawn, etc. | `backend/models/ats/application.py:52` (CHECK constraint) |
| Candidate dashboard | `GET /candidate/dashboard`, applications tracker, withdraw endpoint | `backend/routers/candidate/applications.py` |

### 7.3 Recruiter Campaign Manager Flow

| Step | Description | Evidence |
|---|---|---|
| Campaign create | `POST /recruiter/campaigns` and `/recruiter/campaigns/full`; links BatchJob to Job + Rubric | `backend/routers/recruiter_campaigns/management.py` |
| CV upload | `POST /recruiter/campaigns/{batch_id}/upload/cv` / `/upload-cvs`; PDF validation, email extraction, duplicate detection, placeholder email `no-email-{uuid8}@import.local`; creates Applications (status `pending`) | `backend/routers/recruiter_campaigns/upload.py:427` |
| Background analysis | `background_analyze_batch` opens own SessionLocal, validates company_id, runs `extract_cv_details` + rubric context, writes CV score | `backend/routers/recruiter_campaigns/upload.py:92` |
| Candidate list | `GET /recruiter/campaigns/{batch_id}/candidates` (CampaignCandidate schema incl. cv_rubric_weighted, cv_evidence, interview state) | `backend/routers/recruiter_campaigns/candidates.py` |
| Invite candidate | `POST /recruiter/campaigns/{batch_id}/candidates/{app_id}/invite` (email with temp password for new accounts) | `backend/routers/recruiter_campaigns/candidates.py` |
| Bulk invite | `POST /recruiter/campaigns/{batch_id}/invite-all` | `backend/routers/recruiter_campaigns/candidates.py` |
| Invite qualified | `POST /recruiter/jobs/{job_id}/invite-qualified` (threshold) | `frontend/src/services/candidates.service.ts`, `backend/routers/recruiter_campaigns/candidates.py` |
| Shortlist / nudge / stale invites | `PATCH .../shortlist`, `POST .../nudge`, `GET .../stale-invites` | `backend/routers/recruiter_campaigns/candidates.py` |
| Exports | `GET /recruiter/campaigns/{batch_id}/export/csv` and `export/pdf` | `backend/routers/recruiter_campaigns/candidates.py` |
| Tracking/analytics | Email open/click tracking, campaign stats, batch_counters | `backend/routers/recruiter_campaigns/tracking.py`, `backend/models/core/batch_job.py` (`batch_counters`) |

### 7.4 AI Interview Flow

| Step | Description | Evidence |
|---|---|---|
| Start/access | Invited candidate (guest or registered) opens interview; `InterviewRoomRoute` allows guest cookie; question generation `POST /ai/generate-interview` | `frontend/src/app/guards/auth-guard.tsx`, `backend/routers/ai_interview/questions.py` |
| Resume/session | `POST /ai/interview/resume` (loads turns, time_left, skill metrics), pause, time, end | `backend/routers/ai_interview/session.py` |
| Chat turns | `POST /ai/interview/chat` (adaptive turn generation, engine state, DIMENSION_WEIGHTS); practice endpoint | `backend/routers/ai_interview/chat.py` |
| Proctoring | `POST /ai/interview/sync-proctoring`; violations tracked; `POST /ai/interview/report-fraud` | `backend/routers/ai_interview/session.py`, `evaluation.py:787` |
| Media | Video upload/segment, voice STT/TTS (`/ai/voice/*`) | `backend/routers/ai_interview/media.py` |
| Final evaluation | On end → status EVALUATING → `run_background_final_evaluation` → `ScoringService.set_evaluation_result` (verdict, integrity penalty, skill metrics); one-time company credits consumed | `backend/routers/ai_interview/evaluation.py`, `backend/scoring_service.py` |
| Completion emails | Recruiter + candidate completion emails | `backend/routers/ai_interview/evaluation.py` |

### 7.5 Candidate Analysis View

| Step | Description | Evidence |
|---|---|---|
| History | `GET /candidate/interviews/history` | `backend/routers/candidate/interviews.py:165` |
| Analysis | `GET /candidate/interviews/{app_id}/analysis` — own analysis via `get_interview_access` (guests included); loads CvDocument, EvaluationResult, turns, rubric summary, live score fallback; auto-expire/reject after 7 days | `backend/routers/candidate/interviews.py:279` |
| Frontend | Interview analysis page (guest allowed) | `frontend/src/features/interviews/pages/interview-analysis.tsx`, `frontend/src/app/router.tsx` (InterviewAnalysisRoute) |

### 7.6 Recruiter Analysis View

| Step | Description | Evidence |
|---|---|---|
| Scores endpoint | `GET /recruiter/applications/{app_id}/scores` — final_score, cv_score, rubric_score, category_breakdown, skill_breakdown, evidence, recommendation, trust, cv_* breakdown (from CvDocument.analysis_json + RubricScoringDetail source="cv") | `backend/routers/recruiter_candidates/scoring.py` |
| Detail page | `GET /recruiter/applications/{id}` — candidate profile, analysis, integrity, notes, tabs | `backend/routers/recruiter_candidates/applications.py` |
| Ranked candidates | `GET /recruiter/jobs/{job_id}/candidates/ranked` | `backend/routers/recruiter_candidates/scoring.py` |
| Frontend | Recruiter interview analysis page (tabs incl. Rubric Breakdown), application detail with CV Evaluation tab | `frontend/src/features/recruiter/pages/recruiter-interview-analysis.tsx`, `frontend/src/features/candidates/pages/application-detail.tsx` |

### 7.7 Admin Operations Flow

| Step | Description | Evidence |
|---|---|---|
| Users | `GET/POST/PUT /admin/users*` | `backend/routers/admin/` |
| Plans | Plan CRUD with PlanVersion snapshotting | `backend/routers/admin/plans.py` |
| Subscriptions | Approve/reject/change-plan/expire/reinstate/start-trial; payment-proof review (list/detail/file/verify/reject) | `backend/routers/admin/subscriptions.py` |
| Credits | Wallet list/detail, grant, signed adjust | `backend/routers/admin/credits.py` |
| Finance | Overview/revenue/customers/credits/forecast + CSV/PDF export | `backend/routers/admin/finance.py`, `backend/admin_financial_service.py` |
| KYB | List/approve/reject company KYB | `backend/routers/admin/kyb.py` |
| Content/opportunities/courses/blogs | CMS CRUD | `backend/routers/admin/cms.py`, `admin/courses.py`, `admin/marketing.py` |
| System | Health, logs, backup, background jobs, audit trail, drift | `backend/routers/admin/system.py` |
| Frontend | Admin dashboard, users, organizations, subscriptions, payment-proofs, finance, KYB, support | `frontend/src/features/admin/pages/*` |

---

## 8. API / Router Map

| Router/File | Purpose | Main Prefix / Area | Evidence |
|---|---|---|---|
| `backend/routers/auth.py` | Authentication (signup, login, OTP, verify, passwords, Google, refresh) | `/auth` | `backend/routers/auth.py:82` |
| `backend/routers/public.py` | Public marketing/job/course/blog/opportunity endpoints | public (no prefix) | `backend/routers/public.py` |
| `backend/routers/candidate/` | Candidate portal: profile, applications, cv, interviews, jobs, subscriptions, qualifications, eeo, saved-jobs | `/candidate/*` | `backend/routers/candidate/` |
| `backend/routers/ai_interview/` | AI interview chat, session, evaluation, questions, media | `/ai/interview/*`, `/ai/*` | `backend/routers/ai_interview/` |
| `backend/routers/admin/` | Admin: users, plans, subscriptions, credits, finance, invoices, kyb, organizations, payments, jobs, interviews, courses, tickets, settings, system, marketing, cms, analytics, verifications | `/admin/*` | `backend/routers/admin/` |
| `backend/routers/org/` | Org portal: members, billing, analytics | `/org/*` | `backend/routers/org/` |
| `backend/routers/recruiter_jobs.py` | Job CRUD, wizard, generate-job, my jobs, invite-qualified | `/recruiter/jobs*` | `backend/routers/recruiter_jobs.py` |
| `backend/routers/recruiter_job_wizard.py` | Job wizard steps 1–5, publish, AI suggestions | `/recruiter/jobs/wizard*` | `backend/routers/recruiter_job_wizard.py` |
| `backend/routers/recruiter_campaigns/` | Campaign manager: management, upload, candidates, templates, team, tracking | `/recruiter/campaigns*` | `backend/routers/recruiter_campaigns/` |
| `backend/routers/recruiter_candidates/` | Applications, search, scoring, invitations, integrations, email | `/recruiter/applications*`, `/recruiter/candidates*` | `backend/routers/recruiter_candidates/` |
| `backend/routers/candidate_management.py` | Candidate assignment, interactions | `/recruiter/candidates` | `backend/routers/candidate_management.py:20` |
| `backend/routers/recruiter_skill_trees.py` | Skill tree/rubric library (standalone, AI generate, detail, edit, duplicate) | `/recruiter/skill-trees*` | `backend/routers/recruiter_skill_trees.py` |
| `backend/rubric/rubric_router.py` | Rubric templates, per-job rubrics, score-answer, scoring-all, explain, compare | `/rubric/*` | `backend/rubric/rubric_router.py` |
| `backend/routers/recruiter_offers.py` | Offer create/send/withdraw/respond/esign | `/recruiter/offers*` | `backend/routers/recruiter_offers.py` |
| `backend/routers/recruiter_reports.py` | Report CRUD, build, snapshots, schedule, export | `/recruiter/reports*` | `backend/routers/recruiter_reports.py` |
| `backend/routers/recruiter_settings.py` | Recruiter settings, company logo, subscription status | `/recruiter/*` | `backend/routers/recruiter_settings.py` |
| `backend/routers/recruiter_dashboard.py` | Recruiter dashboard stats | `/recruiter/dashboard` | `backend/routers/recruiter_dashboard.py` |
| `backend/routers/recruiter_enhancements/` | Actions, analytics, automation, notes, previews, scorecards, stages, webhooks | `/recruiter/enhancements*` | `backend/routers/recruiter_enhancements/` |
| `backend/routers/recruiter_interviews/` | Interview scheduling, management, feedback | `/recruiter/interviews*` | `backend/routers/recruiter_interviews/` |
| `backend/routers/recruiter_collaboration/` | Team, comments, ratings, activity | `/recruiter/collaboration*` | `backend/routers/recruiter_collaboration/` |
| `backend/routers/recruiter_eeo.py` | EEO reporting/dashboard | `/recruiter/eeo*` | `backend/routers/recruiter_eeo.py` |
| `backend/routers/recruiter_background_checks.py` | Background checks + adverse action | `/recruiter/background-checks*` | `backend/routers/recruiter_background_checks.py` |
| `backend/routers/analytics/` | Insights, reports, monitoring (health/metrics/prometheus) | `/analytics`, `/reports`, `/monitoring` | `backend/routers/analytics/` |
| `backend/routers/courses.py` | LMS enroll, curriculum, progress, reviews, konnect webhook | `/courses*` | `backend/routers/courses.py:30` |
| `backend/routers/messages.py` | Conversations/messages | `/messages` | `backend/routers/messages.py:26` |
| `backend/routers/notifications.py` | Notifications | `/notifications` | `backend/routers/notifications.py:11` |
| `backend/routers/calendar.py` | Calendar integrations (ICS, Google, Outlook) | `/calendar` | `backend/routers/calendar.py:21` |
| `backend/routers/mentor.py` | Mentor stats/earnings/students | `/mentor` | `backend/routers/mentor.py:20` |
| `backend/routers/chatbot.py` | Chatbot conversation + leads | `/chatbot` | `backend/routers/chatbot.py:15` |
| `backend/routers/career.py` | Career roadmap | `/career` | `backend/routers/career.py:14` |
| `backend/routers/gdpr.py` + `consent.py` | Data erasure, consent | `/gdpr` | `backend/routers/gdpr.py:19`, `consent.py:36` |
| `backend/routers/feature_flags.py` | Feature flag CRUD/config | `/feature-flags` | `backend/routers/feature_flags.py:21` |
| `backend/routers/tracking.py` | Anonymous email open/click tracking (HMAC) | `/track` | `backend/routers/tracking.py` |
| `backend/routers/uploads.py` | File upload endpoints | `/uploads` | `backend/routers/uploads.py` |
| `backend/routers/pages.py` | SPA serving, redirects, legacy `.html` catch-all | `/` | `backend/routers/pages.py` |
| `backend/routers/payments.py` | Stripe/Konnect payment intents + webhooks | `/payments` | `backend/routers/payments.py:45` |
| `backend/routers/copilot.py` + `copilot_admin.py` | Hiring copilot chat, embed candidates | `/hiring` | `backend/routers/copilot.py:17`, `copilot_admin.py:13` |
| `backend/routers/hiring.py` | Hiring helper endpoints | `/hiring` | `backend/routers/hiring.py:14` |
| `backend/routers/jd_bias.py` | JD bias analyze/rewrite | `/jd` | `backend/routers/jd_bias.py:14` |
| `backend/routers/ai_sales.py` | AI sales leads/outreach | `/admin/ai/sales` | `backend/routers/ai_sales.py:19` |
| `backend/routers/ai_utils.py` | AI utils (translate) | `/ai` | `backend/routers/ai_utils.py:14` |
| `backend/routers/onboarding.py` | Candidate onboarding + CV analysis JSON | `/onboarding` | `backend/routers/onboarding.py:28` |
| `backend/routers/support.py` | Support tickets | `/support` | `backend/routers/support.py` |
| `backend/routers/linkedin.py` | LinkedIn integration | `/linkedin` | `backend/routers/linkedin.py:15` |

---

## 9. Frontend Route Map

| Route | Page/Component | Role | Purpose | Evidence |
|---|---|---|---|---|
| `/` , `/landing` | LandingPage | public | Marketing landing | `frontend/src/app/router.tsx` |
| `/auth/login`, `/auth/register`, `/auth/register-company`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/verify-email`, `/auth/verify-otp` | Auth pages | public | Authentication | `frontend/src/app/router.tsx` |
| `/auth/google/callback` | GoogleCallbackPage | public | Google OAuth callback | `frontend/src/app/router.tsx` |
| `/pricing`, `/blogs`, `/blog/:slug`, `/opportunities`, `/privacy`, `/terms`, `/careers`, `/careers/:jobId`, `/catalog` | Marketing pages | public | Public marketing/careers | `frontend/src/app/router.tsx` |
| `/dashboard` | RoleBasedDashboard | all authenticated | Role-scoped dashboard | `frontend/src/app/router.tsx`, `frontend/src/features/dashboard/pages/role-based-dashboard.tsx` |
| `/admin/dashboard` | AdminDashboardPage | admin | Admin dashboard | `frontend/src/app/router.tsx` |
| `/jobs` | RoleBasedJobs | candidate/recruiter/admin | Job board | `frontend/src/app/router.tsx` |
| `/jobs/new` | JobWizardPage | recruiter/admin | Job creation wizard | `frontend/src/app/router.tsx` |
| `/jobs/:id` | RoleBasedJobDetail | candidate/recruiter/admin | Job detail | `frontend/src/app/router.tsx` |
| `/candidates` | CandidatesListPage | recruiter/admin/mentor | Candidate list | `frontend/src/app/router.tsx` |
| `/candidates/:id` | ApplicationDetailPage | recruiter/admin/mentor | Application detail | `frontend/src/app/router.tsx` |
| `/recruiter/applications` | ApplicationsPage | recruiter/admin/mentor | Applications list (job + name filters, drawer) | `frontend/src/app/router.tsx`, `frontend/src/features/recruiter/pages/applications-page.tsx` |
| `/pipeline` | PipelineBoardPage | recruiter/admin | Pipeline board | `frontend/src/app/router.tsx` |
| `/campaigns`, `/campaigns/new`, `/campaigns/:id`, `/campaigns/compare` | Campaign pages | recruiter/admin | Campaign manager | `frontend/src/app/router.tsx` |
| `/interviews` | RoleBasedInterviews | candidate/recruiter/admin/mentor | Interviews | `frontend/src/app/router.tsx` |
| `/interviews/new`, `/interviews/:id` | Interview pages | recruiter/admin | Scheduling | `frontend/src/app/router.tsx` |
| `/interviews/room`, `/interviews/room/:sessionId` | InterviewRoomPage | candidate + guest cookie | AI interview room | `frontend/src/app/router.tsx` (InterviewRoomRoute) |
| `/interviews/:id/analysis`, `/interview-analysis`, `/candidate/interview-analysis`, `/recruiter/interview-analysis` | InterviewAnalysisPage | candidate/recruiter/admin + guest | Analysis | `frontend/src/app/router.tsx` (InterviewAnalysisRoute) |
| `/applications`, `/applications/:id` | Candidate applications tracker/detail | candidate | Candidate applications | `frontend/src/app/router.tsx` |
| `/profile`, `/candidate/profile`, `/cv-builder`, `/cv-review`, `/qualifications`, `/achievements`, `/skill-progress`, `/marketplace`, `/onboarding` | Candidate pages | candidate | Candidate profile/CV | `frontend/src/app/router.tsx` |
| `/analytics`, `/reports` | Analytics/Reports | recruiter/admin | Reporting | `frontend/src/app/router.tsx` |
| `/skill-trees`, `/skill-trees/:id`, `/skill-tree-create`, `/rubrics` | Skill tree/rubric pages | recruiter/admin/mentor | Rubric library | `frontend/src/app/router.tsx` |
| `/courses` | CoursesListPage | candidate/admin/mentor | Learning | `frontend/src/app/router.tsx` |
| `/messages`, `/calendar` | Messages/Calendar | all 4 roles | Communication | `frontend/src/app/router.tsx` |
| `/admin/*` (users, organizations, kyb, subscriptions, finance, payments, payment-proofs, invoices, content, courses, ai-monitoring, support, etc.) | Admin pages | admin | Platform admin | `frontend/src/app/router.tsx` |
| `/org`, `/org/dashboard`, `/org/members`, `/org/analytics`, `/org/billing` | Org pages | company | Org portal | `frontend/src/app/router.tsx` |
| `/mentor/students`, `/mentor/wallet`, etc. | Mentor pages | mentor/admin | Mentor area | `frontend/src/app/router.tsx` |
| `/settings`, `/settings/:tab` | SettingsPage | all | Settings | `frontend/src/app/router.tsx` |
| Redirects | `/comparison`, `/skill-tree`, `/subscription`, `/documents`, `/cv-selection`, `/help`, `/notifications` | all | Legacy route redirects | `frontend/src/app/router.tsx` |
| `*` | `<Navigate to="/dashboard">` | authenticated | Catch-all | `frontend/src/app/router.tsx` |

---

## 10. AI Architecture

| AI Module | Purpose | Evidence | Notes |
|---|---|---|---|
| `backend/ai/llm.py` | Core LLM entry: `call_groq_cascade`, Gemini fallback, embedding, token budget, cost check, circuit breaker, injection scanning (user messages), unconditional PII masking, JSON mode | `backend/ai/llm.py` | Providers: Groq primary, Gemini fallback, optional local Ollama |
| `backend/ai/resilience.py` | Per-provider circuit breakers (CLOSED/OPEN/HALF_OPEN) | `backend/ai/resilience.py` | Groq outage does not block Gemini |
| `backend/ai/security.py` | `PIIMappingStore` (thread-safe LRU, sha256 masked IDs), `AISecurity` prompt-injection detection + sanitization | `backend/ai/security.py` | |
| `backend/ai/validation.py` | `AIOutputValidator`, `VALIDATION_SCHEMA_REGISTRY`, strict output validation | `backend/ai/validation.py` | |
| `backend/ai/privacy.py` | `scrub_pii`, `count_pii_categories`, audit AI calls | `backend/ai/privacy.py` | |
| `backend/ai/token_tracker.py` | Token counting/budgets/truncation per model context window | `backend/ai/token_tracker.py` | |
| `backend/ai/cost_controller.py` | Groq/Gemini pricing, budget checks, usage recording | `backend/ai/cost_controller.py` | |
| `backend/ai/prompts.py` | `PROMPT_VERSIONS` registry, CV extraction/skills/interview prompts, prompt escape + injection patterns | `backend/ai/prompts.py` | |
| `backend/ai/cv_analysis.py` | `analyze_cv`, `extract_cv_details` (system-role prompt), `extract_skills_from_cv`, confidence/clusters/benchmarks | `backend/ai/cv_analysis.py` | Falls back to explicit dict on provider failure (never fabricates scores) |
| `backend/ai/bias_detection.py` | Bias detection for AI scoring | `backend/ai/bias_detection.py` | |
| `backend/ai/scoring_jobs.py` | Background bias audits, drift, calibration, recalibration (company-scoped) | `backend/ai/scoring_jobs.py` | |
| `backend/ai/worker.py` | `InterviewWorkerQueue` Redis queue with in-process fallback | `backend/ai/worker.py` | |
| `backend/routers/candidate/cv.py` | `/candidate/analyze` (3 credits) runs CV analysis + persistence | `backend/routers/candidate/cv.py:568` | |
| `backend/routers/ai_interview/questions.py` | `POST /ai/generate-interview` (5 credits) question generation | `backend/routers/ai_interview/questions.py` | |
| PII masking | Unconditional before external providers; `mask_candidate_data` for non-Pro recruiter responses | `backend/ai/llm.py`, `backend/security.py:112` | |

---

## 11. Scoring / Evaluation Architecture

| Component | Purpose | Evidence | Notes |
|---|---|---|---|
| `ScoringService.compute_final_score` | Canonical formula: `final_score = cv_score*cv_w + rubric_score*rubric_w + human_score*human_w + coverage_bonus*cov_w` (coverage_bonus = rubric_coverage_pct * 0.10); no-rubric path folds rubric weight into cv | `backend/scoring_service.py:103` | Only writer of `EvaluationResult`; 3-attempt StaleDataError retry |
| `ScoringService.set_cv_only` | Persist CV-only score (no rubric) | `backend/scoring_service.py:282` | |
| `ScoringService.set_cv_rubric` | Persist rubric-weighted CV score + `RubricScoringDetail` rows (source=`cv`), idempotent delete-then-insert | `backend/scoring_service.py:310` | |
| `ScoringService.set_evaluation_result` | Persist AI interview final evaluation (upsert by session, clamps 0–100, FAILED-state guard, merges breakdown) | `backend/scoring_service.py:372` | |
| `ScoringService.set_verdict` / `report_fraud` | Verdict persistence / fraud reporting | `backend/scoring_service.py` | |
| `rubric_match_service.py` | Deterministic rubric-weighted CV scoring with per-skill evidence levels (0/25/50/75/100) | `backend/services/rubric_match_service.py` | |
| `backend/rubric/` | Rubric engine, loader, schema, snapshotter, scoring_aggregator, skill_mapper, evidence_analyzer, config_resolver | `backend/rubric/*.py` | Deterministic; LLM only extracts skills/evidence |
| `EvaluationResult` | Canonical scoring result (final_score, verdict, scoring_status, score_breakdown, skill_metrics) | `backend/models/evaluation/evaluation.py` | |
| `EvaluationSession` | Interview session; `version_id` optimistic lock; status/interview_state enums | `backend/models/evaluation/evaluation.py` | |
| `RubricScoringDetail` | Per-skill scoring detail rows (source `cv`) | `backend/models/evaluation/` | |
| `EvaluationConfigSnapshot` | Immutable evaluation config at eval time (`active_snapshot_id` on BatchJob) | `backend/models/evaluation/config_snapshot.py` | AI engine reads only from snapshot |
| `RubricSnapshot` | Immutable rubric snapshot at eval time | `backend/models/evaluation/` | |
| Recruiter scores API | `GET /recruiter/applications/{app_id}/scores` (cv_skill_breakdown, cv_evidence, recommendation, trust) | `backend/routers/recruiter_candidates/scoring.py` | |
| Candidate analysis API | `GET /candidate/interviews/{app_id}/analysis` | `backend/routers/candidate/interviews.py:279` | |

---

## 12. Campaign Manager Architecture

| Component | Purpose | Evidence | Notes |
|---|---|---|---|
| `BatchJob` model | Campaign batch: job_id, rubric_id, active_snapshot_id, language, duration, difficulty, interview_instructions, template_id, worker_status | `backend/models/core/batch_job.py` | `batch_counters` computes emails/opens/clicks/qualified/avg_cv_score |
| Campaign creation | `POST /recruiter/campaigns` / `/full`; `FullCampaignCreate` (title, job_id, rubric_id, skill_tree_id, language, duration, etc.) | `backend/routers/recruiter_campaigns/management.py` | |
| CV upload | `POST /recruiter/campaigns/{batch_id}/upload/cv` + `/upload-cvs`; PDF-only, email regex, duplicate detection, placeholder email; creates Applications | `backend/routers/recruiter_campaigns/upload.py:427` | Requires assigned rubric before upload |
| Background analysis | `background_analyze_batch` (own session, company_id validation, rubric context, CV details + scoring) | `backend/routers/recruiter_campaigns/upload.py:92` | |
| Candidate list | `GET /recruiter/campaigns/{batch_id}/candidates` (CampaignCandidate: cv_score, interview_state, cv_rubric_weighted, cv_evidence, recommendation) | `backend/routers/recruiter_campaigns/candidates.py` | |
| Invite candidate | `POST /recruiter/campaigns/{batch_id}/candidates/{app_id}/invite` — temp password email for new accounts | `backend/routers/recruiter_campaigns/candidates.py` | |
| Bulk invite | `POST /recruiter/campaigns/{batch_id}/invite-all` | `backend/routers/recruiter_campaigns/candidates.py` | |
| Invite qualified | `POST /recruiter/jobs/{job_id}/invite-qualified` (threshold) | `frontend/src/services/candidates.service.ts` | |
| Shortlist / audit / stale / nudge / duplicates | `PATCH .../shortlist`, `GET .../audit`, `GET .../stale-invites`, `POST .../nudge`, `GET .../duplicate-summary` | `backend/routers/recruiter_campaigns/candidates.py` | |
| Exports | `GET .../export/csv`, `GET .../export/pdf` (tiered Top/Good/Marginal) | `backend/routers/recruiter_campaigns/candidates.py` | PDF via reportlab |
| Tracking | Email open/click tracking + sequence | `backend/routers/recruiter_campaigns/tracking.py` | HMAC tokens |
| Templates | Campaign/email templates CRUD | `backend/routers/recruiter_campaigns/templates.py` | |

---

## 13. Security & Privacy

| Security Area | Exists? | Evidence | Notes |
|---|---|---|---|
| JWT auth | Yes | `backend/dependencies.py` (jose HS256, `create_access_token`, `OAuth2PasswordBearer`) | |
| CSRF | Yes | `_set_csrf_cookie`, `/auth` endpoints exempt list; frontend `X-CSRF-Token` header handling | `backend/routers/auth.py:332`, `backend/security.py`, `frontend/src/lib/api-client.ts` |
| bcrypt passwords | Yes | `backend/dependencies.py` (cost 12–14, rehash deprecated) | |
| Rate limiting | Yes | `backend/rate_limit_middleware.py` (Redis, fails open), `backend/ai/security.py`, tracking 30 req/60s per IP | |
| Tenant isolation | Yes | `backend/tenant.py` (`get_current_company_id`, `tenant_query`, `assert_tenant_match` → 404), TenantMixin on models | |
| 404-on-tenant-mismatch | Yes | `backend/authz.py` (anti-IDOR), `backend/tenant.py` | Never 403 for missing/tenant-mismatch |
| Upload validation | Yes | `backend/file_security.py` (allowed types, blocked extensions, magic-number/MIME, size caps, malware heuristic), `backend/body_size_middleware.py` | |
| PII masking | Yes | `backend/ai/llm.py` (unconditional before providers), `backend/security.py:112` (`mask_candidate_data` for non-Pro recruiter lists) | Not applied to recruiter detail endpoint for non-Pro |
| Field encryption at rest | Yes | `backend/encryption.py` (Fernet `EncryptedText` on cv_text_anonymized, analysis_json, interview_log, email, phone, etc.) | Hard fails without key |
| Secret encryption | Yes | `backend/secret_encryption.py` (SMTP/Groq/Gemini/Konnect keys) | |
| GDPR / data erasure | Yes | `backend/routers/gdpr.py` (Art. 17), `backend/gdpr_erasure.py`, `[ERASED]` scrub | |
| Consent logs | Yes | `backend/routers/consent.py` (6 agreement types incl. AI providers), immutable `ConsentLog` | |
| Interview access tokens | Yes | `backend/dependencies.py:124,153,399` (`generate_interview_token`, `verify_interview_token`, `get_interview_access`) | Guest access for invited candidates |
| Role guards | Yes | `backend/dependencies.py` (`require_candidate/recruiter/admin/mentor`, `require_org_admin`, `check_admin`); frontend `RoleGuard` | |
| Signed URLs | Yes | `backend/signed_url.py` (HMAC bearer-bound 5-min tokens) | |
| XSS sanitization | Yes | `backend/security.py` (bleach-based `sanitize_content`, `sanitize_rich_text`) | |
| Audit trail | Yes | `AuditLog` (immutable, IP recorded), `AIAuditLog`, `SubscriptionHistory`, `ConsentLog` | |
| XFF handling | Yes | `backend/client_ip.py` (rightmost X-Forwarded-For, `CANDWAY_TRUST_XFF` opt-out) | |

---

## 14. Billing / Credits

| Billing Area | Description | Evidence |
|---|---|---|
| Plans | `SubscriptionPlan` (slug, target_audience, TND pricing, limits, `credits_monthly`, `plan_group`) + immutable `PlanVersion` for grandfathering | `backend/models/foundation/subscription.py` |
| Plan admin CRUD | Admin GET/POST/PUT/DELETE + activate/archive/duplicate; snapshots on sensitive-field changes | `backend/routers/admin/plans.py` |
| Credit wallet | `CreditWallet` (unique user, `version` optimistic lock) | `backend/models/finance/credits.py` |
| Credit ledger | `CreditTransaction` (signed, immutable, unique idempotency_key; types grant/purchase/topup/consume/refund/adjustment/promo/expire/rollback) | `backend/models/finance/credits.py` |
| Usage metering | `UsageEvent` append-only with `cost_usd` | `backend/models/finance/credits.py` |
| Credit service | `consume_credits` (atomic row lock), `grant_credits`, `adjust_credits`, `rollback_credits`, `require_credits` dependency (402 `insufficient_credits`) | `backend/credit_service.py`, `backend/dependencies.py:894` |
| Admin grants | `POST /admin/credits/{user_id}/grant`, `/adjust`; wallet list/detail | `backend/routers/admin/credits.py` |
| Subscriptions | `Subscription` + immutable `SubscriptionHistory`; lifecycle service (activate/cancel/expire/reinstate) | `backend/models/finance/subscription.py`, `backend/subscription_lifecycle_service.py` |
| Admin subscription ops | approve/reject/change-plan/expire/reinstate/start-trial; credit top-up convention; daily renewal cron | `backend/routers/admin/subscriptions.py`, `backend/scheduler.py` |
| Manual payment proofs | Transaction proof workflow: `proof_status` (uploaded/verified/rejected), `proof_verified_by/at`, `proof_review_notes`; admin review endpoints | `backend/models/finance/finance.py`, `backend/routers/admin/subscriptions.py` (payment-proofs) |
| Invoices | `Invoice` (INV-YYYY-0001, client_mf, status); PDF + TEIF XML download | `backend/models/finance/finance.py`, `backend/routers/admin/invoices.py` |
| Org billing | Company-scoped plans/subscribe/receipt/kyb/cancel; `create_company_invoice`, `approve_company_subscription`; TVA 0.19, stamp duty 1.000 TND | `backend/routers/org/billing.py` |
| Candidate billing | Usage, plans, upgrade request (SupportTicket), manual bank proof upload, invoice download | `backend/routers/candidate/subscriptions.py` |
| Recruiter billing | Subscription status/plans/upgrade/invoices/payment-config; company-managed is view-only | `backend/routers/recruiter_settings.py`, `frontend/src/services/subscription.service.ts` |
| Financial dashboard | Live KPIs (revenue/MRR/ARR, customers/churn/LTV, credits/AI cost margin, forecast) + CSV/PDF export | `backend/admin_financial_service.py`, `backend/routers/admin/finance.py` |
| Konnect | Course payments (Konnect webhook + create) | `backend/konnect_service.py`, `backend/routers/payments.py`, `backend/routers/courses.py` |

---

## 15. Deployment / Infrastructure Files Found

| File / Area | Purpose | Evidence | Notes |
|---|---|---|---|
| `Dockerfile` | Multi-stage build (node frontend → python builder → nginx → distroless runtime) | Root `Dockerfile` | |
| `docker-compose.yml` | Backend (8000), MySQL 8.0, Redis 7, nginx, Prometheus, Grafana | Root `docker-compose.yml` | Healthcheck on `/api/v1/monitoring/health` |
| `nginx.conf` | Rate limits, TLS, HSTS, CSP, reverse proxy | Root `nginx.conf` | |
| `Procfile` | gunicorn UvicornWorker, 4 workers, `backend.app:create_app()` | Root `Procfile` | |
| `run_server.py` / `start_server.bat` | Local Windows dev launcher, free-port scan 8000–8100 | Root | |
| `prometheus.yml` | Prometheus scrape config (15s) | Root `prometheus.yml` | |
| `alembic.ini` | Alembic config (`script_location = alembic`) | Root `alembic.ini` | |
| `mysql_init/` | Raw SQL init scripts (skills schema) separate from ORM | `mysql_init/skills_schema.sql` | |
| `.env.example` / `.env.production.example` | Required env var checklists (secrets checklist, production flags) | Root | Values not documented here |
| `scripts/` | deploy.sh, provision_mysql_db.py, seed_defaults/production, db_backup.py, verify_migration.py, run_tests_mysql.py, convert_mysql_to_utf8mb4.py | Root `scripts/` | |
| `backend/scripts/` | backfill_* scripts (user→profiles, cv_documents, candidates, company_ids, rubric/config snapshots), seed_demo_*, cleanup_storage.py, interview_worker.py | `backend/scripts/` | |
| `.github/` | No CI workflow files found | `.github/` | Not found |
| Monitoring endpoints | `/api/v1/monitoring/health`, `/metrics`, `/metrics/prometheus`, `readyz`, `livez`, status | `backend/routers/analytics/monitoring.py`, `backend/routers/monitoring.py` | |
| Backend logs | RotatingFileHandler with request ID + PII-masking regexes | `backend/logger.py` | |

---

## 16. Known Placeholders / Not Found Modules

| Item | Status | Evidence |
|---|---|---|
| Job fair module | Not found | No `job_fair*` router/module |
| Agency workflow | Not found | No `agency*` router/module |
| `admin/permissions` frontend route | Placeholder (ComingSoon) | `frontend/src/app/router.tsx` (`ComingSoon`) |
| `mentor/community`, `mentor/profile` | Placeholder (ComingSoon) | `frontend/src/app/router.tsx` |
| `ComingSoon` shared component | Placeholder page component | `frontend/src/shared/components/ui/coming-soon.tsx` |
| CI/CD workflows | Not found | `.github/workflows/*` no files |
| Direct AI interview start | Removed/disabled | `backend/routers/candidate/interviews.py:43` returns 410 "Direct interview start is no longer available" |
| ClamAV malware scanning | Not implemented (heuristic scanner only) | `backend/file_security.py` (`scan_for_malware` is heuristic) |
| Legacy HTML pages | Removed (React SPA only; `/{page_name}.html` catch-all serves SPA) | `backend/routers/pages.py:127` |

---

## 17. Glossary of Existing Terms

| Term | Definition (observed in code) |
|---|---|
| Campaign | Recruiter-initiated hiring batch; backed by `BatchJob` linked to a `Job` and optional `Rubric` |
| BatchJob | Campaign batch model: holds job_id, rubric_id, active evaluation-config snapshot, language/duration/difficulty, template, worker_status |
| Job | Job posting (`Job` model); recruiter-created, has skills/categories/AI config via wizard; can have `rubric_id` |
| Application | Candidate application to a job (`Application` model); status enum; owns CV data via `CvDocument`; ties to `EvaluationSession` |
| Candidate | Deduplicated candidate entity unique per company+email (`Candidate` model) |
| Recruiter | User role that creates jobs, manages candidates/campaigns, reviews scores |
| Company | Tenant entity (`Company` model); owns company-scoped data via `company_id` (TenantMixin) |
| Rubric | Evaluation rubric (`Rubric` model, tablename `rubrics`); job-linked or standalone; versioned; criteria_json |
| Skill Tree | Recruiter-facing name for reusable rubrics managed in the skill-tree library (same `rubrics` table) |
| EvaluationSession | AI interview session for one application; carries status/interview_state and optimistic lock |
| EvaluationResult | Canonical scoring result (final_score, verdict, scoring_status, score_breakdown) |
| EvaluationConfigSnapshot | Immutable copy of evaluation config used at interview time (BatchJob.active_snapshot_id) |
| RubricScoringDetail | Per-skill scoring detail rows; `source='cv'` rows carry CV rubric-weighted breakdown |
| CV Score | Score from CV analysis (AI semantic or deterministic rubric-weighted) |
| Interview Score | Score from AI interview turns/evaluation |
| Overall Score / final_score | Composite: `cv_score*cv_w + rubric_score*rubric_w + human_score*human_w + coverage_bonus*cov_w` |
| Credits | Currency for AI usage (wallet/ledger; consumed by CV analysis, interview generation, etc.) |
| Feature Flag | DB-backed toggle controlling feature availability by audience/plan/rollout |
| Tenant | A company; tenant isolation filters all company-scoped data by `company_id` |
| KYB | Know-Your-Business verification workflow for companies (documents, status pending/approved/rejected) |
| GDPR erasure | Right-to-erasure flow (`/gdpr/erasure/{user_id}`) scrubbing PII |
| ConsentLog | Immutable record of user consent agreements |
| EEO | Equal Employment Opportunity reporting |
| Proctoring | Interview integrity monitoring (tab switches, violations, trust score) |

---

## 18. Final Factual Summary

Candway is a multi-tenant recruiting platform: a React 19 SPA (Vite 7 + Tailwind v4 + react-router v7 + TanStack Query) served from `static/app`, backed by a FastAPI application mounted at `/api/v1` with SQLAlchemy models and Alembic migrations.

The backend is organized into ~50 routers grouped into candidate, recruiter, admin, org, AI-interview, and analytics packages, supported by services (scoring, credits, subscriptions, analytics, email, reports) and a tenant-isolation layer (`TenantMixin` / `backend/tenant.py`). The AI stack uses Groq with Gemini fallback and optional local Ollama, with unconditional PII masking, prompt-injection scanning, output validation, token/cost controls, and circuit breakers.

Implemented product modules include: auth, admin, org/company portal, recruiter tools (jobs, job wizard, offers, reports, skill trees, EEO, background checks), the campaign manager (BatchJob with CV upload, background analysis, invites, tracking, exports), candidate portal (profile, CV builder/review, applications, AI interviews, qualifications), AI interview + deterministic rubric-weighted scoring (`ScoringService`), LMS/courses, messaging, calendar, mentor area, notifications/email, GDPR/consent, feature flags, and monetization (plans, subscriptions, credit wallet/ledger, manual payment proofs, invoices, admin finance dashboard).

Security features present: JWT + cookies + CSRF, bcrypt, Redis rate limiting, tenant isolation with 404-on-mismatch, upload validation, field-level PII encryption at rest, secret encryption, GDPR erasure and consent logs, interview access tokens, signed URLs, and audit trails.

Not found: job fair module, agency workflow, CI/CD workflows, and ClamAV malware scanning (a heuristic scanner is used instead). A number of mentor and admin pages are `ComingSoon` placeholders.

This document describes only the current, verified state of the codebase.