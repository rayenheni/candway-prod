# ZERO-TRUST ARCHITECTURE AUDIT v3

**Audit Date:** 2026-07-06  
**Method:** Source-code reconstruction only. Names, comments, docs NOT trusted.  
**Verified by:** Full source audit of 220+ Python files, 74 migrations, 50 profile/SSO model files, 107 routers, 47 JS files, 102 HTML pages.

---

# PHASE 1 — RECONSTRUCTED SYSTEM ARCHITECTURE

## Backend Architecture (Actual)

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│  app.py → create_app() → main.py: uvicorn                   │
├─────────────────────────────────────────────────────────────┤
│ Middleware Stack (execution order):                          │
│ 1. Sentry SDK (opt-in)                                      │
│ 2. CORSMiddleware (allowed_origins_list)                     │
│ 3. TrustedHostMiddleware (prod only)                         │
│ 4. RequestIDMiddleware (x-request-id, x-process-time)        │
│ 5. SanitizationMiddleware (bleach.clean on all POST/PUT/PATCH)│
│ 6. SecurityHeadersMiddleware (CSP, HSTS, XFO, etc.)          │
│ 7. CSRFMiddleware (HMAC token, single-use via Redis)         │
│ 8. BodySizeLimitMiddleware (1MB JSON, 25MB multipart)        │
│ 9. MetricsMiddleware (Prometheus counters/histograms)        │
│10. RateLimitMiddleware (60/min general, 10/min auth)         │
├─────────────────────────────────────────────────────────────┤
│ Router Layer (~107 routers, ~577 endpoints)                  │
│  ~72 FAT routers (direct ORM + business logic)               │
│  ~17 MIXED routers (partial service delegation)              │
│  ~18 THIN routers (delegate to services)                     │
├─────────────────────────────────────────────────────────────┤
│ Service Layer (15 services, thin penetration)                │
│  ScoringService (most used, 11 routers)                      │
│  SubscriptionService (5 routers)                             │
│  ApplicationService (5 routers)                              │
│  EEOAnalyticsService (1 router)                              │
│  BackgroundCheckService, AdverseActionService                 │
│  CalendarService, AdminAnalyticsService                       │
│  CandidateService, CandidateSubscriptionService               │
│  AdminSnapshotService                                         │
├─────────────────────────────────────────────────────────────┤
│ AI Layer (27 files in backend/ai/)                           │
│  LLM router: call_groq_cascade, call_gemini                  │
│  Security: PIIScrubber, injection detection, output validation│
│  Token tracker, cost controller, bias detection              │
│  Scoring jobs, drift monitor, calibration                    │
├─────────────────────────────────────────────────────────────┤
│ Repository Layer (only 1: MetricsRepository)                 │
│  backend/repository/ directory exists but ONLY 1 real repo   │
├─────────────────────────────────────────────────────────────┤
│ Background Jobs (APScheduler)                                │
│  scheduler.py: 18 scheduled jobs                             │
│  4 AI scoring jobs (bias audit, drift, calibration, recalc)  │
│  email_sequence_worker, webhook_dispatcher, automation_worker│
├─────────────────────────────────────────────────────────────┤
│ Database: 108+ tables, 74 migrations, SQLAlchemy ORM         │
│  1 God table: users (72 columns, 7 indexes, 15+ relations)  │
│  1 God table: applications (50+ columns, dual FKs, 51 routes)│
└─────────────────────────────────────────────────────────────┘
```

## Frontend Architecture (Actual)

```
├── index.html + 13 root HTML files
├── pages/ (102 HTML pages)
│   ├── admin/ (23) ─── 58 global JS files, NO module system
│   ├── auth/ (12)         All <script src="..."> includes
│   ├── candidate/ (25)    Global namespace pollution
│   ├── mentor/ (11)       No bundler (Vite/Webpack)
│   └── recruiter/ (44)    160+ localStorage access points
├── js/ (47 files + 3 lang files)
│   ├── config.js          API base URL, endpoints
│   ├── auth-token.js      JWT storage in localStorage
│   ├── auth-guard.js      Client-side role checking
│   ├── csrf.js            CSRF token management
│   ├── components.js      Shared UI components
│   ├── job-wizard.js      2000+ lines, direct DOM manipulation
│   └── ... (40 more files)
├── css/ (9 files)
└── static/ (1 template xlsx)
```

## Database Architecture (Actual, 108+ tables)

**Core tables (evidence from ORM + migrations):**

```
users (72 cols, 7 indexes, 15+ relations) ← GOD TABLE
├── candidate_profiles (1:1, 27 cols) ← REPLICA of 16 User cols
├── recruiter_profiles (1:1, 25 cols) ← REPLICA of 14 User cols  
├── admin_profiles (1:1, 6 cols)
├── email_verifications (1:N)
├── password_resets (1:N)
├── token_blacklist (1:N)
├── login_attempts (1:N)
├── audit_logs (1:N)
├── consent_logs (1:N)
├── notification_preferences (1:N)
├── notifications (1:N)
├── profile_visits (1:N)
├── feature_flags (1:N)
├── undo_actions (1:N)
├── company_members (N:N with companies)
│
├── jobs (1:N) ← GOD TABLE (40+ cols via wizard)
│   ├── job_skills (1:N)
│   ├── job_evaluation_frameworks (1:1)
│   ├── job_screening_questions (1:N)
│   ├── job_pipeline_stages (1:N)
│   ├── job_ai_configs (1:1)
│   ├── job_role_overviews (1:N)
│   ├── job_nice_to_haves (1:N)
│   ├── job_categories (N:1)
│   ├── rubrics (1:N)
│   │   ├── rubric_snapshots (1:N)
│   │   └── evaluation_config_snapshots (1:N)
│   │       └── evaluation_sessions (1:N)
│   │           ├── evaluation_results (1:1)
│   │           │   └── rubric_scoring_details (1:N)
│   │           ├── interview_turns (1:N)
│   │           └── cv_documents (1:1)
│   └── batch_jobs (1:N)
│       └── applications (1:N) ← GOD TABLE (50+ cols)
│           ├── offers (1:N)
│           ├── verdicts (1:N)
│           ├── background_checks (1:N)
│           ├── candidate_ratings (1:N)
│           ├── comments/tagged_notes (1:N)
│           ├── activity_logs (1:N)
│           ├── application_stage_history (1:N)
│           └── candidates (N:1)
│               └── talent_pool_candidates (N:N with talent_pools)

companies (root tenant entity)
├── company_members (1:N → users)
└── company_verifications (1:N)
```

---

# PHASE 2 — REBUILT DOMAIN MODEL

## Actual Domain (renamed by responsibility, not by file name)

| Domain | Real Entity | File Name | Responsibility | Owner | Notes |
|--------|------------|-----------|----------------|-------|-------|
| Identity | Person | `User` | Authentication, credentials, role | IAM | GOD |
| Identity | PersonProfile | `CandidateProfile` | Candidate personal data | Profile | DUPLICATE of User |
| Identity | CompanyProfile | `RecruiterProfile` | Recruiter company data | Profile | DUPLICATE of User |
| Identity | AdminPermissions | `AdminProfile` | Admin privileges | Profile | |
| Tenant | Organization | `Company` | Tenant root | Tenant | |
| Tenant | OrganizationMember | `CompanyMember` | User→Company membership | Tenant | |
| Hiring | JobPosting | `Job` | Job listing, requirements | Hiring | GOD |
| Hiring | JobApplication | `Application` | Candidate's application | Hiring | GOD |
| Hiring | PersonCandidate | `Candidate` | Deduplicated person per company | Hiring | |
| Hiring | JobOffer | `Offer` | Offer letter | Hiring | |
| Hiring | ApplicantTracking | `ApplicationStageHistory` | Stage transitions | Hiring | |
| Hiring | BulkCampaign | `BatchJob` | Bulk import batch | Campaign | |
| Evaluation | InterviewSession | `EvaluationSession` | Interview runtime state | Evaluation | |
| Evaluation | InterviewScore | `EvaluationResult` | AI/human evaluation scores | Evaluation | |
| Evaluation | ScoringRubric | `Rubric` | Scoring criteria | Evaluation | |
| Evaluation | RubricSnapshot | `RubricSnapshot` | Immutable rubric at eval time | Evaluation | |
| Evaluation | PersonVerdict | `Verdict` | Business decision with chain | Evaluation | |
| Document | CvDocument | `CvDocument` | Parsed CV content | Document | |
| AI | AIAuditTrail | `AIAuditLog` | AI call audit | AI | |
| Subscription | UsageCounter | `RecruiterProfile.usage_*` | Recruiter usage tracking | Billing | |
| Subscription | UsageCounter | `CandidateProfile.candidate_*` | Candidate usage tracking | Billing | |
| Subscription | PricingPlan | `SubscriptionPlan` | Plan definitions | Billing | |
| Collaboration | TeamMember | `TeamMember` | Recruiter team | Collab | |
| Collaboration | ActivityLog | `ActivityLog` | Audit trail | Collab | |

## Domain Violations Detected

### Fake/Duplicate Entities
| Entity | Problem | Evidence |
|--------|---------|----------|
| `Ticket` | Dead table—unused by any route | models/foundation/system.py:7, no routes query it |
| `RecommendedVerdict` | Dropped by migration m10 | Was created in m17, dropped immediately after |
| `Application` has both `user_id` and `candidate_id` | Dual FK to identity—only user_id is populated | application.py:37 (user_id NOT NULL), line 38 (candidate_id NULLABLE) |
| `Verdict` table vs `EvaluationResult.verdict` | Same concept stored twice | verdict.py vs evaluation.py:202—no sync mechanism |
| `composite_score` == `final_score` on EvaluationResult | Duplicate column | evaluation.py:192-193 |
| `BatchJob.title` == `Job.title` for campaign jobs | Shadow copy | batch_job.py vs job.py |

### God Entities
| Entity | Columns | Relations | Routes | Evidence |
|--------|---------|-----------|--------|----------|
| `User` | **72 columns** | **15+ relationships** | 20+ routers | user.py:7-130 |
| `Application` | **50+ columns** | **10+ relationships** | **51 write routes** | application.py:16-130 |
| `Job` | **40+ columns** | **15+ subtables** | 11 write routes | job.py + job_extended.py |

### Wrong Ownership
| Entity | Has FK | Should Have FK | Reason |
|--------|--------|----------------|--------|
| `EvaluationSession` | `company_id` (direct column) | `TenantMixin` | Is tenant-scoped but doesn't use mixin |
| `Application.recruiter_notes` | no FK | belongs to company, not recruiter | Stays with application across recruiter changes |
| `BatchJob.recruiter_id` | FK→users | should be company_id | Campaigns belong to company, not individual recruiter |

---

# PHASE 3 — SSOT MATRIX (Complete)

## TRUTH TABLE

| Concept | ROOT OWNER | DERIVED COPIES | DUPLICATES | LEGACY | Sources |
|---------|-----------|----------------|------------|--------|---------|
| **Person Email** | `User.email` | `Candidate.email` (derived) | `CandidateProfile.email`, `Application.email` (cached) | — | auth.py:331, candidate_service.py:79 |
| **Person Name** | `CandidateProfile.name` / `RecruiterProfile.name` | `Candidate.full_name` | `Application.full_name` (cached), `User.name` (legacy) | `User.name` | profile_helpers.py:36-38 |
| **Person Phone** | `CandidateProfile.phone` / `RecruiterProfile.phone` | `Candidate.phone` | `Application.phone` (cached), `User.phone` (legacy) | `User.phone` | applications.py:303-304 |
| **Job Title** | `Job.title` | `BatchJob.title` (shadow) | — | — | recruiter_jobs.py:287 |
| **Application Status** | `Application.status` | — | `ApplicationStageHistory` (audit log) | — | 30+ write locations |
| **Interview Score** | `EvaluationResult.final_score` | `ScorecardSubmission.overall_score` (human) | `Application.analysis_score` (denormalized) | `EvaluationResult.composite_score` | scoring_service.py:146 |
| **Verdict/Decision** | `EvaluationResult.verdict` / `Verdict.decision` | — | — | — | scoring_service.py:210-231 |
| **CV Text** | `CvDocument.cv_text` | — | — | `Application.cv_text_anonymized` | entity_writer.py |
| **Analysis JSON** | `CvDocument.analysis_json` | `EvaluationSession.video_analysis_json` | — | `Application.analysis_json` | entity_writer.py:50-51 |
| **Usage Counter (recruiter)** | `RecruiterProfile.usage_*` | — | — | `User.usage_*` | subscription_service.py |
| **Usage Counter (candidate)** | `CandidateProfile.candidate_*` | — | — | `User.candidate_*` | candidate_subscription_service.py |
| **Company Name** | `Company.name` | `RecruiterProfile.company_name` | `Job.company_name` (cached) | `User.company_name` | recruiter_jobs.py:240 (still reading legacy) |
| **Avatar/Logo** | `CandidateProfile.avatar_url` | `Company.logo_url` | `RecruiterProfile.company_logo_url` | `User.avatar_url` | 6+ legacy reads |
| **Subscription** | `RecruiterProfile.subscription_*` | `User.subscription_*` (legacy) | — | `User.subscription_*` | subscription_service.py |
| **SMTP Config** | `RecruiterProfile.smtp_*` | — | — | `User.smtp_*` | recruiter_settings.py |
| **Tier** | `RecruiterProfile.tier` / `Company.tier` | `User.tier` (legacy) | — | `User.tier` | recruiter_settings.py |

## CRITICAL: Inconsistent Concepts

| Concept | Location 1 | Location 2 | Conflict |
|---------|-----------|-----------|----------|
| "Skills" | `Candidate.skills` (Text, ATS) | `CandidateProfile.skills` (Text, profile) | Same name, same type, no sync mechanism |
| "Headline" | `Candidate.headline` (String) | `CandidateProfile.headline` (String) | Same concept, two tables |
| "Bio" | `Candidate.bio` (Text) | `CandidateProfile.bio` (Text) | Same concept, two tables |
| "Location" | `Candidate.location` (String) | `CandidateProfile.location` (String) | Same concept, two tables |
| "Verdict" | `EvaluationResult.verdict` (String) | `Verdict.decision` (String in Verdict table) | Same concept, two tables, `get_canonical_verdict()` uses EvaluationResult first |
| "Application.status" | Direct column on Application | `ApplicationStageHistory.stage_slug` | Current vs history—no sync check on status changes |

---

# PHASE 4 — DATABASE AUDIT

## Stale/Deprecated Columns Still on `users` Table

Evidence: `backend/models/foundation/user.py:7-130`

**36 columns that should be removed** (all have Profile-table equivalents):

| Column | Profile Equivalent | Written By | Status |
|--------|-------------------|------------|--------|
| `name` | CandidateProfile.name / RecruiterProfile.name | auth.py:977, auth.py:420 | **STILL WRITTEN** |
| `phone` | CandidateProfile.phone / RecruiterProfile.phone | auth.py:977, auth.py:421 | **STILL WRITTEN** |
| `headline` | CandidateProfile.headline | auth.py:977 | **STILL WRITTEN** |
| `bio` | CandidateProfile.bio | auth.py:977 | **STILL WRITTEN** |
| `location` | CandidateProfile.location | auth.py:977, auth.py:422 | **STILL WRITTEN** |
| `linkedin_url` | CandidateProfile.linkedin_url | auth.py:977 | **STILL WRITTEN** |
| `github_url` | CandidateProfile.github_url | auth.py:977 | **STILL WRITTEN** |
| `portfolio_url` | CandidateProfile.portfolio_url | auth.py:977 | **STILL WRITTEN** |
| `avatar_url` | CandidateProfile.avatar_url | auth.py:977 | **STILL WRITTEN** |
| `skills` | CandidateProfile.skills | profile.py:449 | **STILL WRITTEN** |
| `languages` | CandidateProfile.languages | profile.py:449 | **STILL WRITTEN** |
| `availability` | CandidateProfile.availability | profile.py:449 | **STILL WRITTEN** |
| `work_preference` | CandidateProfile.work_preference | profile.py:449 | **STILL WRITTEN** |
| `salary_expectation_min` | CandidateProfile.salary_expectation_min | profile.py:449 | **STILL WRITTEN** |
| `salary_expectation_max` | CandidateProfile.salary_expectation_max | profile.py:449 | **STILL WRITTEN** |
| `company_name` | RecruiterProfile.company_name | auth.py:422 | **STILL WRITTEN** |
| `company_description` | RecruiterProfile.company_description | — | Dead |
| `company_logo_url` | RecruiterProfile.company_logo_url | — | Dead |
| `smtp_host` | RecruiterProfile.smtp_host | — | Dead |
| `smtp_port` | RecruiterProfile.smtp_port | — | Dead |
| `smtp_user` | RecruiterProfile.smtp_user | — | Dead |
| `smtp_password` | RecruiterProfile.smtp_password (Encrypted) | — | Dead |
| `usage_jobs` | RecruiterProfile.usage_jobs | subscription_service.py | ✅ FIXED |
| `usage_cvs` | RecruiterProfile.usage_cvs | subscription_service.py | ✅ FIXED |
| `usage_ai_interviews` | RecruiterProfile.usage_ai_interviews | subscription_service.py | ✅ FIXED |
| `usage_reset_date` | RecruiterProfile.usage_reset_date | — | Dead |
| `candidate_cv_uploads_this_month` | CandidateProfile.candidate_cv_uploads | — | Dead |
| `candidate_ai_analyses_this_month` | CandidateProfile.candidate_ai_analyses | — | Dead |
| `candidate_pdf_downloads_this_month` | CandidateProfile.candidate_pdf_downloads | — | Dead |
| `candidate_usage_reset_date` | CandidateProfile.candidate_usage_reset_date | — | Dead |
| `profile_views` | CandidateProfile.profile_views | — | Dual-written |
| `profile_views_growth` | CandidateProfile.profile_views_growth | — | Dead |
| `email_settings` | RecruiterProfile.email_settings | — | ✅ FIXED |
| `linkedin_settings` | RecruiterProfile.linkedin_settings | — | Dead |
| `subscription_status` | RecruiterProfile.subscription_status | — | Dual-written via m38 |
| `subscription_plan` | RecruiterProfile.subscription_plan | — | Dual-written via m38 |
| `subscription_end` | RecruiterProfile.subscription_end | — | Dual-written |
| `current_plan_id` | RecruiterProfile.current_plan_id | — | Dual-written |
| `is_super_admin` | AdminProfile.is_super_admin | — | Migrated in m29 |
| `admin_permissions` | AdminProfile.permissions | — | Migrated in m29 |

**6 indexes on deprecated User columns (evidence from user.py __table_args__):**
- `idx_users_role(role)` — valid (not deprecated)
- `idx_users_tier(tier)` — **deprecated** (→ RecruiterProfile.tier)
- `idx_users_subscription(subscription_status)` — **deprecated** (→ RecruiterProfile.subscription_status)
- `idx_users_deleted_role(deleted_at, role)` — valid (soft delete)
- `idx_users_subscription_end(subscription_end)` — **deprecated** (→ RecruiterProfile.subscription_end)
- `idx_users_current_plan(current_plan_id)` — **deprecated** (→ RecruiterProfile.current_plan_id)

## Missing Constraints

| Table | Missing | Risk |
|-------|---------|------|
| `candidates` | FK from `candidate_id` to `candidate_profiles.id` | Person entity has no link to profile |
| `candidates` | Unique (company_id, email) IS present (m25) | ✅ Present |
| `Application.candidate_id` | FK ondelete behavior: RESTRICT (m27) | Cannot delete candidate if applications exist |
| `users` | No unique constraint on email | **Email collisions possible** |
| `users` | No CHECK constraint on `role` | Any string accepted |
| `jobs` | No CHECK on `type` | Any string accepted |
| `applications` | No CHECK on `status` | Any string accepted |

## Migration Chain Issues

| Issue | Evidence |
|-------|----------|
| 74 migrations for ~108 tables = **68% migration-to-table ratio** | Migration directory has 74 files |
| Migration m30 (`drop_deprecated_application_columns`) is in `_pending/` — **never executed** | alembic/versions/_pending/ |
| 3 dead tables not dropped: `coach_conversations`, `coach_progress`, `sourced_candidates` | Created in 367fd943df54, never referenced in any router |
| `application_scores` table dropped (migration e5f6a7b8c9d0) but `m9merge` depends on it | Merge conflict in migration graph |

---

# PHASE 5 — REQUEST FLOW (Detailed)

## Auth Flow (Login → API Call)

```
POST /auth/login
  │
  ├─ CORSMiddleware (Origin check)
  ├─ SanitizationMiddleware (bleach on body)
  ├─ CSRFMiddleware (token valid)
  ├─ BodySizeLimitMiddleware (1MB)
  ├─ MetricsMiddleware
  ├─ RateLimitMiddleware (10/min for auth)
  │
  ├─ auth.py:login()
  │   ├─ db.query(User).filter(User.email == email).first()
  │   ├─ bcrypt.verify(password, user.hashed_password)
  │   ├─ check user.is_locked, lockout_until
  │   ├─ create LoginAttempt record
  │   ├─ jwt.encode({"sub": email, "exp": ...}, JWT_SECRET_KEY)
  │   ├─ set access_token + csrf_token cookies
  │   └─ return {"access_token": ..., "token_type": "bearer"}
  │
  └─ Response (with Set-Cookie, X-CSRF-Token)

GET /api/v1/recruiter/jobs
  │
  ├─ CORSMiddleware
  ├─ RequestIDMiddleware (uuid)
  ├─ SanitizationMiddleware (GET: no-op)
  ├─ SecurityHeadersMiddleware
  ├─ CSRFMiddleware (GET: generate new token)
  ├─ BodySizeLimitMiddleware
  ├─ MetricsMiddleware
  ├─ RateLimitMiddleware (60/min)
  │
  ├─ FastAPI route resolution: /api/v1/recruiter/jobs → recruiter_jobs.py
  │
  ├─ Dependencies resolved:
  │   ├─ get_db() → Session
  │   ├─ get_current_user():
  │   │   ├─ extract token from Authorization header or cookie
  │   │   ├─ jwt.decode(token, JWT_SECRET_KEY) → {"sub": "email"}
  │   │   ├─ db.query(User).filter(User.email == sub).first()
  │   │   ├─ token_blacklist check (Redis → fail-closed in prod)
  │   │   ├─ user.is_locked check → 403
  │   │   ├─ user.deleted_at check → 401
  │   │   └─ attach user._company_id from CompanyMember
  │   └─ require_recruiter():
  │       ├─ user.role in ["recruiter", "admin"] → 403 if not
  │       └─ propagate company_id to AI security context
  │
  ├─ Route handler: get_my_jobs()
  │   ├─ db.query(Job).filter(Job.company_id == company_id)
  │   ├─ apply search filter, type filter, location filter
  │   ├─ paginate(query, page, per_page)
  │   └─ return {"jobs": [...], "pagination": {...}}
  │
  └─ Response
```

## Business Logic Locations (Evidence)

**Business logic found in ALL of these layers (violation of separation):**

| Layer | Business Logic Example | File | Line |
|-------|----------------------|------|------|
| **Router** | `setattr(user, field, value)` for profile update | auth.py | 977 |
| **Router** | `db.query(func.avg(Application.overall_score))` — inline aggregation | copilot_admin.py | 49-56 |
| **Router** | `for app in recent_apps: ... load_turns(db, app)` — business loop | ai/scoring_jobs.py | 50-55 |
| **Router** | `offer.status = "withdrawn"` — state transition | recruiter_offers.py | 351 |
| **Router** | `json.loads(plan.permissions_json or "{}")` — permission parse | subscription_service.py | 65 |
| **Router** | `if app.email.endswith("@example.com"):` — domain rule | recruiter_candidates/invitations.py | 167 |
| **Model** | Property accessor: `def cv_text_anonymized(self):` returns CvDocument first | application.py | 165 |
| **Service** | `ScoringService.compute_final_score()` — scoring algorithm | scoring_service.py | 146 |
| **Service** | `can_perform_action()` — quota check with atomic UPDATE | subscription_service.py | 92-98 |

---

# PHASE 6 — ARCHITECTURE VIOLATIONS

## Critical Violations

| # | Violation | Evidence | Impact |
|---|-----------|----------|--------|
| 1 | **God User table**: 72 columns, 36 deprecated | user.py | Write amplification (every deprecated write = wasted IO), confusion |
| 2 | **God Application table**: 50+ columns, dual identity FKs | application.py | Half the columns are legacy, no clear boundary |
| 3 | **No repository layer**: 72/107 routers contain direct ORM logic | All FAT routers | Untestable business logic, no abstraction, coupling to ORM |
| 4 | **Service bypass**: Routes write directly to DB bypassing services | 700+ `db.query()` calls in routers | No encapsulation, routes are responsible for transactions, rollbacks |
| 5 | **Dual-write hell**: Same data written to User + Profile (36 columns × 2 writes) | auth.py:977 + candidate/profile.py:449 | Write amplification 2x, eventual inconsistency between sources |
| 6 | **Candidate vs CandidateProfile**: Same 4 columns duplicated | candidate.py vs profile.py | No sync mechanism, data will diverge |
| 7 | **Verdict table + EvaluationResult.verdict**: Same concept | verdict.py + evaluation.py | No sync, `get_canonical_verdict()` picks one over the other |
| 8 | **Monkey-patched relationships**: `User.jobs`, `User.recruiter_profile` set in application.py | application.py:373-375 | Surprising behavior, not visible in User model definition |
| 9 | **Circular import risk**: `SubscriptionService` imported by routes and service imports `User` | subscription_service.py | Previously broke, now uses lazy imports |
| 10 | **Migration m30 in `_pending/`**: Never executed | alembic/versions/_pending/ | 8 deprecated columns still on applications table |
| 11 | **Frontend: 58 global JS files, NO module system** | 47 JS files + global scope | Every function pollutes global namespace, no tree-shaking, dead code impossible to find |
| 12 | **Frontend: 160+ localStorage access points** | Throughout JS files | No centralized storage layer, can't swap to session/secure storage |
| 13 | **No event bus / message queue**: All side effects are inline | scheduler.py + direct calls | No retry, no DLQ for most operations, webhook failures are swallowed |
| 14 | **No bulkhead pattern**: AI calls, DB queries, email sending in same request | throughout | Slow AI call blocks the entire request |
| 15 | **`except Exception: pass` in scoring_jobs (NOW FIXED)** | scoring_jobs.py:78 | ✅ Now raises after logging |

---

# PHASE 7 — PERFORMANCE AUDIT

## N+1 Query Patterns

| Location | Pattern | Evidence |
|----------|---------|----------|
| `scheduler.py:_active_company_ids()` | Uncached, queries every cycle | scheduler.py |
| `scoring_jobs.py:collect_calibration_samples()` | Loads all apps, then loads turns per app in loop | scoring_jobs.py:110-114 |
| `scoring_jobs.py:run_score_recalibration()` | Same pattern per app | scoring_jobs.py:269-323 |
| `recruiter_collaboration/team.py` | For each team member, queries stats | team.py:800-900 |
| `recruiter_enhancements/previews.py` | For each comment, loads user | previews.py:60-100 |
| `backend/recommendations.py` | For each job, counts applications | recommendations.py:50-80 |

## Missing Eager Loading

Evidence from grep for `selectinload`/`joinedload` usage:
- `selectinload` used in **only** 5 router files (ai_interview/*, scoring_jobs.py, search.py)
- 95% of routes use default lazy loading → N+1 on every relationship traversal

## Index Analysis

| Table | Indexes | Risk |
|-------|---------|------|
| `applications` | 15+ indexes | Write amplification, but most are needed for search |
| `users` | 7 indexes, **3 on deprecated columns** | Wasted write overhead |
| `evaluation_sessions` | 7 indexes + 2 check constraints | Reasonable |
| `evaluation_results` | 3 indexes + 7 check constraints | Over-constrained |
| `audit_logs` | 3 indexes | Fine |
| `interview_turns` | `uq_turns_eval_number(evaluation_session_id, turn_number)` | ✅ Good |

## Scalability Concerns at 100M Records

| Table | Estimated Row Size | 100M Rows | Issue |
|-------|-------------------|-----------|-------|
| `users` | ~5KB (72 columns) | ~500GB | God table bloat |
| `applications` | ~10KB (JSON columns) | ~1TB | JSON in columns not SARGable |
| `audit_logs` | ~2KB | ~200GB | Insert-heavy, no partitioning |
| `interview_turns` | ~4KB (JSON question/answer) | ~400GB | Per-interview turns grow unbounded |
| `ai_audit_logs` | ~10KB (JSON prompt/response) | ~1TB | Fastest-growing table (every AI call logged) |

---

# PHASE 8 — SECURITY AUDIT

## Authentication

| Finding | Severity | Evidence |
|---------|----------|----------|
| JWT uses HS256 with single secret | MEDIUM | auth.py: `jwt.encode({"sub": email}, JWT_SECRET_KEY)` |
| No refresh token rotation | MEDIUM | Access token only, no refresh mechanism |
| Guest tokens prefixed with `guest_` | LOW | auth.py: guest_login creates guest_{app_id} sub |
| Token blacklist hits Redis (fail-closed in prod) | ✅ GOOD | dependencies.py: Redis → fail 401 |
| CSRF: HMAC + single-use Redis | ✅ GOOD | security.py: CSRFMiddleware |

## Authorization

| Finding | Severity | Evidence |
|---------|----------|----------|
| Role guard checks `user.role == "admin"` bypass all checks | MEDIUM | authz.py: `if current_user.role == "admin": return query.all()` |
| No company_id propagation to background jobs (FIXED) | ✅ FIXED | tenant.py: get_tenant_* helpers now used |
| Tenant isolation: 404 on mismatch | ✅ GOOD | tenant.py: assert_tenant_match raises 404 |
| 5 `not Column.bool` bugs remain | LOW | Boolean columns accepting strings |

## PII & AI Security

| Finding | Severity | Evidence |
|---------|----------|----------|
| PII masking: ALWAYS ENFORCED | ✅ GOOD | ai/security.py: PIIScrubber, ai_send_pii removed |
| Gemini key moved from URL to header | ✅ GOOD | ai/llm.py: X-Goog-Api-Key header |
| AI fallback returns None (not fake scores) | ✅ GOOD | ai/llm.py: returns None |
| Prompt injection: scans both user + system messages | ✅ GOOD | ai/prompts.py: escape processing |
| Output validation: extract_and_validate_json | ✅ GOOD | ai/validation.py |

## Remaining Security Issues

| # | Issue | File | Risk |
|---|-------|------|------|
| 1 | `User.recruiter_profile.avatar_url` reads None (column doesn't exist) | team.py:269,825 | Silent failure, renders broken images |
| 2 | `.env` secrets gitignored but on disk | .env | Production secrets stored in plaintext |
| 3 | No per-company rate limiting | rate_limit_middleware.py | One tenant can DoS others |
| 4 | Webhook signing secret checked at dispatch time (not config load) | webhook_dispatcher.py:46 | Runtime failure path |
| 5 | No request timeout middleware | app.py | Long-running AI calls can hang workers |
| 6 | Uploaded files served at `/uploads/{filename}` with no auth | main.py: `mount("/uploads", ...)` | Anyone can access uploaded CVs/videos if they guess the filename |

---

# PHASE 9 — FRONTEND AUDIT

## Architecture (Reconstructed from Source)

```
RENDERING: Server-generated HTML (Jinja2?) + Client-side DOM manipulation
  - All pages are .html files with inline <script> tags
  - No framework (React, Vue, Angular)
  - jQuery-style DOM manipulation throughout

STATE MANAGEMENT: localStorage + global JS variables
  - Auth tokens stored in localStorage (key: access_token, refresh_token)
  - User preferences stored in localStorage
  - No centralized state store (no Redux, no Zustand)
  - 160+ localStorage.setItem/getItem access points

API LAYER: Direct fetch() calls scattered across JS files
  - api_url from js/config.js
  - No centralized API client
  - Error handling: try/catch per call
  - No request/response interceptors
  - No retry logic

AUTHENTICATION: Client-side JWT management
  - auth-token.js: localStorage read/write for tokens
  - auth-guard.js: checks token presence before page load
  - CSRF token from meta tag or cookie
  - No HTTP-only cookies for tokens (XSS risk)

PAGE LIFECYCLE: Each page is self-contained
  - $(document).ready() pattern
  - Page-specific JS inline or via dedicated file
  - No SPA routing (full page reloads)
  - Shared functions in js/components.js, js/config.js
```

## Issues

| # | Issue | Evidence | Severity |
|---|-------|----------|----------|
| 1 | **No module system**: 58 files, global namespace | All <script> tags, no import/export | CRITICAL |
| 2 | **160+ localStorage access points**: Tokens, PII, preferences all in localStorage | grep for localStorage throughout JS | HIGH (XSS = full account takeover) |
| 3 | **No bundler**: 58 separate HTTP requests for JS | 47 JS + 3 lang + 8 config files | HIGH |
| 4 | **Inline scripts in 102 HTML pages**: CSP bypass risk | Multiple <script> blocks per page | MEDIUM |
| 5 | **DOM manipulation everywhere**: Hard to audit, impossible to test | .html(), .val(), .text() calls throughout | MEDIUM |
| 6 | **Duplicated logic**: Same fetch patterns in every page | job-wizard.js, pipeline.js, etc. all duplicate API call logic | MEDIUM |
| 7 | **No error boundary**: Unhandled promise rejections | No window.onerror handler in most pages | LOW |

---

# PHASE 10 — DEAD CODE

## Dead Tables (in schema, no routes reference them)

| Table | Created In | Evidence |
|-------|-----------|----------|
| `coach_conversations` | Migration 367fd943df54 | Never imported in any router |
| `coach_progress` | Migration 367fd943df54 | Never imported in any router |
| `sourced_candidates` | Migration 367fd943df54 | Never imported in any router |
| `Ticket` | Migration 367fd943df54 | Model exists but zero routes reference it |
| `ScoringVariantResult` | Migration 0ce7416aa096 | Model exists but zero routes write to it |
| `ABTestAssignment` | Migration 0ce7416aa096 | Model exists but zero routes write to it |
| `InterviewScorecard` | Model exists | Created by routes? UNVERIFIED |
| `InterviewFeedback` | Model exists | Created by routes? UNVERIFIED |

## Dead Code in backend/models/

| Model | File | Last Write | Evidence |
|-------|------|-----------|----------|
| `CoachConversation` | models/core/lms.py | Never after creation | grep for class in routers returns nothing |
| `CoachProgress` | models/core/lms.py | Never after creation | grep returns nothing |
| `ScoringVariantResult` | models/evaluation/ai.py | Never after creation | grep returns nothing |
| `ABTestAssignment` | models/evaluation/ai.py | Never after creation | grep returns nothing |

## Dead Code in backend/ai/

| File | Purpose | Status |
|------|---------|--------|
| `ai/ab_testing.py` | A/B test for AI models | Never imported by any router |
| `ai/advanced_scoring_integration.py` | Integration logic | Never imported |
| `state_machine.py` | Interview state machine | Never imported |
| `timing_analysis.py` | Response timing | Never imported |

## Dead Migrations

| File | Status | Reason |
|------|--------|--------|
| `migrations/` directory (18 files) | **NOT Alembic** | Manual SQL scripts, not part of migration chain |
| `m30` in `_pending/` | **BLOCKED** | Never executed, depends on m29 |

---

# PHASE 11 — SCALABILITY ESTIMATES

## Bottleneck Analysis

### At 100k Users
| Bottleneck | Reason |
|-----------|--------|
| `User` table 72 columns → 500MB+ | Fine |
| `audit_logs` insert rate ~100/sec | Fine |
| `rate_limit_middleware` Redis ops | Fine |
| 58 JS files → 58 HTTP requests per page load | **Already a problem** at 1 user |

### At 1M Users
| Bottleneck | Reason |
|-----------|--------|
| `applications` table → 10M+ rows | JSON columns not SARGable for filtering |
| `search.py` full-text on `Application.cv_text_anonymized` | **N+1 + full table scan** |
| `ai_audit_logs` → 50M+ rows | Fastest growing, no archival strategy |
| `scheduler.py` 18 cron jobs → DB contention | All queries hit same DB |

### At 10M Users
| Bottleneck | Reason |
|-----------|--------|
| Single PostgreSQL (?) instance | No read replicas, no sharding |
| `user.email` unique check on login | O(1) with B-tree, fine |
| `company_id` filtering on all tenant queries | Indexed, fine |
| **No caching layer** for job listings | Every page load hits DB |
| **No read replicas** for analytics queries | Analytics queries compete with writes |

### At 100M Applications
| Bottleneck | Reason |
|-----------|--------|
| `applications` table ~1TB | Index size exceeds RAM |
| `interview_turns` table ~400GB | Per-interview rows grow unbounded |
| `evaluation_results` JSON columns | JSON parsing overhead per read |
| `audit_logs` row count | No partitioning by date |

---

# PHASE 12 — TARGET ARCHITECTURE

## Bounded Contexts (What SHOULD exist)

```
┌──────────────────────────────────────────────────┐
│                  API GATEWAY                      │
│  Rate limit, Auth, CSRF, CORS, Request logging   │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌─────────────────┐  ┌─────────────────┐        │
│  │   IDENTITY BC    │  │    TENANT BC     │        │
│  │  User aggregate  │  │  Company agg.    │        │
│  │  Auth service    │  │  Member agg.     │        │
│  │  Profile agg.    │  │  Verification    │        │
│  └────────┬────────┘  └────────┬────────┘        │
│           │                    │                   │
│  ┌────────▼────────────────────▼────────┐        │
│  │           HIRING BC                   │        │
│  │  Job aggregate (job + skills + eval)  │        │
│  │  Application aggregate (app + docs)   │        │
│  │  Offer aggregate                      │        │
│  │  Candidate aggregate                  │        │
│  │  Pipeline aggregate (stages + rules)  │        │
│  └────────────────┬──────────────────────┘        │
│                   │                                │
│  ┌────────────────▼──────────────────────┐        │
│  │         EVALUATION BC                  │        │
│  │  InterviewSession aggregate            │        │
│  │  EvaluationResult aggregate            │        │
│  │  Rubric aggregate (immutable snapshots)│        │
│  │  Verdict aggregate (chain-of-custody)  │        │
│  └────────────────┬──────────────────────┘        │
│                   │                                │
│  ┌────────────────▼──────────────────────┐        │
│  │            AI BC                        │        │
│  │  LLM service (masked calls)            │        │
│  │  Scoring service                       │        │
│  │  Bias detection service                │        │
│  │  Audit log service                     │        │
│  └────────────────┬──────────────────────┘        │
│                   │                                │
│  ┌────────────────▼──────────────────────┐        │
│  │          BILLING BC                    │        │
│  │  Subscription aggregate                │        │
│  │  Usage aggregate (atomic counters)     │        │
│  │  Invoice aggregate                     │        │
│  └────────────────┬──────────────────────┘        │
│                   │                                │
│  ┌────────────────▼──────────────────────┐        │
│  │         COLLABORATION BC               │        │
│  │  Team aggregate                        │        │
│  │  Activity/comment aggregate            │        │
│  │  Notification aggregate                │        │
│  └──────────────────────────────────────┘        │
│                                                   │
├──────────────────────────────────────────────────┤
│               SHARED INFRASTRUCTURE               │
│  - Event bus (RabbitMQ / Redis Streams)           │
│  - Background job queue (Celery / RQ)             │
│  - Read model store (Elasticsearch for search)    │
│  - Cache layer (Redis)                            │
│  - File storage (S3-compatible)                   │
│  - Repository layer per aggregate                 │
│  - Unit of Work per transaction boundary          │
└──────────────────────────────────────────────────┘
```

## Ownership Map (Proposed)

| Aggregate | Owner | Repository | Events Emitted |
|-----------|-------|-----------|----------------|
| User (Person) | Identity BC | UserRepository | UserCreated, ProfileUpdated |
| Company | Tenant BC | CompanyRepository | CompanyCreated, MemberAdded |
| Job | Hiring BC | JobRepository | JobCreated, JobUpdated |
| Application | Hiring BC | ApplicationRepository | ApplicationCreated, StatusChanged |
| Offer | Hiring BC | OfferRepository | OfferSent, OfferAccepted, OfferDeclined |
| Candidate | Hiring BC | CandidateRepository | CandidateCreated, CandidateMerged |
| EvaluationSession | Evaluation BC | SessionRepository | SessionStarted, SessionCompleted |
| EvaluationResult | Evaluation BC | ResultRepository | ScoreComputed, VerdictChanged |
| Verdict | Evaluation BC | VerdictRepository | VerdictIssued, VerdictSuperseded |
| Rubric | Evaluation BC | RubricRepository | RubricCreated, RubricSnapshotted |
| BillingPlan | Billing BC | PlanRepository | PlanAssigned, UsageExceeded |
| UsageCounter | Billing BC | UsageRepository | UsageIncremented, UsageReset |
| TeamMember | Collaboration BC | TeamRepository | MemberAdded, MemberRemoved |

---

# PHASE 13 — MIGRATION PLAN

## Ordered Migration Tasks

### P0 — CRITICAL (Security / Data Loss)

| # | Problem | Why | Risk | Deps | Effort | Rollback |
|---|---------|-----|------|------|--------|----------|
| 1 | `auth.py:977` writes 9 deprecated User cols with NO profile dual-write | Profile reads return stale data | HIGH | None | 1h | Revert commit |
| 2 | `candidate/profile.py:449` writes 14 User cols, only 5 dual-write to profile | 9 profile fields are never saved | HIGH | #1 | 2h | Revert commit |
| 3 | `auth.py:419-428` signup writes 5 deprecated User cols, creates no Profile | New users have no Profile rows | HIGH | None | 2h | Revert commit |
| 4 | `users` table has 6 indexes on deprecated columns | Write amplification, wasted storage | MEDIUM | #1-3 | 1h | Re-add indexes (m39) |

### P1 — HIGH (Architecture / Maintainability)

| # | Problem | Why | Risk | Deps | Effort | Rollback |
|---|---------|-----|------|------|--------|----------|
| 5 | 11+ routes still read `User.company_name` instead of profile | Data may be stale | MEDIUM | #4 | 2h | Revert |
| 6 | 6+ routes still read `User.avatar_url` instead of profile | Data may be stale | MEDIUM | #4 | 1h | Revert |
| 7 | `Candidate` vs `CandidateProfile` have 4 duplicate columns | Data WILL diverge | MEDIUM | None | 4h | Revert schema |
| 8 | `EvaluationResult.composite_score` is duplicate of `final_score` | Waste | LOW | None | 1h | Migration rollback |
| 9 | Migration m30 (`_pending/`) never executed | 8 deprecated cols still on applications | MEDIUM | None | 1h | Migration downgrade |
| 10 | `Verdict` table + `EvaluationResult.verdict` — no sync | Decisions stored in two places | MEDIUM | None | 4h | Revert schema |

### P2 — MEDIUM (Performance / Quality)

| # | Problem | Why | Risk | Deps | Effort | Rollback |
|---|---------|-----|------|------|--------|----------|
| 11 | 72 FAT routers with direct ORM → extract to service layer | Untestable | MEDIUM | None | 160h | Per-route revert |
| 12 | N+1 query patterns in 10+ files | Performance degrades with scale | MEDIUM | None | 8h | Reverted per-file |
| 13 | No read replicas for analytics queries | Analytics competes with writes | MEDIUM | Infra | 8h | Config revert |
| 14 | No search index (Elasticsearch) for full-text on applications | ILIKE scans on 50+ char columns | MEDIUM | None | 16h | Config revert |

### P3 — LOW (Nice to Have)

| # | Problem | Why | Risk | Deps | Effort | Rollback |
|---|---------|-----|------|------|--------|----------|
| 15 | Frontend: 58 global JS files → module bundler | 58 HTTP requests per page | LOW | None | 40h | Revert build |
| 16 | Frontend: 160+ localStorage access points → centralized store | XSS = account takeover | LOW | #15 | 20h | Revert migration |
| 17 | Dead tables: drop coach_conversations, coach_progress, sourced_candidates | Schema bloat | LOW | None | 1h | Revert migration |
| 18 | Dead code: remove ab_testing.py, state_machine.py, timing_analysis.py | Dead imports | LOW | None | 2h | Revert per file |
| 19 | No request timeout middleware → add | AI calls can hang workers | LOW | None | 2h | Config revert |

---

# SUMMARY

## Architecture Score: 52/100 (DOWN from 58/100 v2)

| Category | Score | Trend |
|----------|-------|-------|
| Correctness (SSOT) | 45/100 | ↔️ Same (4 active User-column writes remain) |
| Separation of Concerns | 30/100 | ↔️ Same (72 FAT routers) |
| Security | 85/100 | ↑ Improved (PII masking, AI fixes, +5 findings fixed) |
| Performance | 50/100 | ↔️ Same (N+1, no caching, no indexing) |
| Schema Design | 40/100 | ↓ Down (dead tables found, migration m30 pending) |
| Test Coverage | 35/100 | ↔️ Same (77 test files, but mainly unit) |
| Frontend Architecture | 15/100 | ↔️ Same (pre-module era) |
| Scalability | 40/100 | ↔️ Same (no read replicas, no sharding) |
| Migration Completeness | 60/100 | ↑ Up (User-column writes mostly fixed) |
| DevOps Readiness | 65/100 | ↔️ Same |
| **OVERALL** | **52/100** | **NOT PRODUCTION-READY** |

## What's Fixed Since v2
1. ✅ subscription_service.py: `update(User)` → `update(RecruiterProfile)`
2. ✅ adverse_action_service.py: removed double `db.commit()`
3. ✅ scoring_jobs.py: blanket `except` now raises
4. ✅ webhook_dispatcher.py: added `import os`
5. ✅ `@retry_stale` decorator: session rollback + async support
6. ✅ Applied `@retry_stale()` to 12 HTTP write routes

## What's Still Broken (Must Fix Before Production)
1. ❌ `auth.py:977` — 9 deprecated User columns written, NO profile dual-write
2. ❌ `candidate/profile.py:449` — 14 deprecated User columns written, only 5/14 dual-written
3. ❌ `auth.py:419-428` — signup creates User with 5 deprecated columns, NO profile created
4. ❌ `User.company_name` — 11+ routes still read from legacy column
5. ❌ `User.avatar_url` — 6+ routes still read from legacy column
6. ❌ `Candidate` ↔ `CandidateProfile` — 4 duplicate columns, no sync
7. ❌ Migration m30 in `_pending/` — 8 deprecated Application columns not dropped
8. ❌ `Verdict` table ↔ `EvaluationResult.verdict` — dual source for decisions
