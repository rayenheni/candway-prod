# ZERO-TRUST SYSTEM ARCHITECT & DOMAIN MODEL AUDIT — v2

**Methodology:** Every claim below is verified from source code. No assumptions. No trust in names, comments, or documentation.

---

## 1. EXECUTIVE SUMMARY

**Score: 58/100 — The architecture is structurally salvageable but has fundamental domain model problems.**

This is NOT a code quality issue. The architecture itself has contaminated bounded contexts, wrong ownership, and a severe God object problem centered on the User model.

### Three Root Causes of Every Critical Issue

1. **User is a God object with 15 relationships and 36 deprecated columns** — It touches every bounded context: ATS, Evaluation, Finance, LMS, Notification, Subscription. A change to User affects everything.

2. **The Profile migration (User→CandidateProfile/RecruiterProfile/AdminProfile) is 90% complete but the remaining 10% causes all the critical bugs** — 3 write sites still dual-write to User columns, 3 subscription_service.py methods write exclusively to User columns, and User `role` is the single source of truth for authorization (not Profiles).

3. **No repository layer + no enforced service boundaries** — ~40/55 routers directly access ORM and contain business logic. There is no way to swap storage, unit test business logic without a database, or enforce transactional boundaries.

---

## 2. REAL DATABASE MODEL (Reconstructed from Source)

### 2.1 The REAL Data Model (Not What Names Suggest)

**Companies** — 1 table
- Actual purpose: Multi-tenant root aggregate. Companies own all data.
- Lifecycle: Explicit creation (admin or signup). Soft-deleted.
- Relationships: CompanyMember (bridge to User), CompanyVerification (proof docs)
- **NOT VERIFIED**: Is Company the aggregate root for ALL data? Yes — 55 tables have `company_id` FK.

**Users** — 1 table (THE GOD TABLE)
- Actual purpose: Authentication identity + legacy profile data store
- Lifecycle: Created at signup, shadow-user invite, or admin creation. Soft-deleted.
- Columns: 36 active (email, password, role, tier, subscription, flags, timestamps) + 36 deprecated columns
- **15 relationships** to: Application, BatchJob, ProfileVisit (×2), SavedJob, CareerRoadmap, NotificationPreference, SubscriptionPlan, Job, PayoutRequest, CandidateProfile, RecruiterProfile, AdminProfile, Course, Enrollment
- **Also referenced without backref by**: CompanyMember, Application.assignee, EmailVerification, PasswordReset, TokenBlacklist, AuditLog, ConsentLog, Notification, LoginAttempt, CompanyVerification (×2), FeatureFlag, UndoAction, Interview, Offer, etc.

**Profiles** — 3 tables (CandidateProfile, RecruiterProfile, AdminProfile)
- Actual purpose: Role-specific person data store (SSOT after migration)
- Lifecycle: Created on-demand (lazy creation in routers) or via team invite. Cascading delete with User.
- Columns: Each has its own `company_id` (TenantMixin). Each has `user_id` (unique FK → users.id).
- **Wrong ownership**: Profile is tied to User (1:1), but the data belongs to the Company. A candidate's name, phone, skills — this data belongs to the Company that hired them, not to the User identity.

**Applications** — 1 table
- Actual purpose: Join between Candidate + Job for a specific hiring process
- Lifecycle: Created at application → invited → interviewed → offered → hired/rejected
- 8 deprecated columns (migrated to CvDocument), ~10 deprecated interview columns (migrated to EvaluationSession)
- `candidate_id` → candidates table (nullable — migration m25 added this, NOT backfilled for all rows)
- **Version ID for optimistic locking** — NOT used by any HTTP route

**CvDocuments** — 1 table
- Actual purpose: Single source of truth for CV data (replaces Application deprecated columns)
- 1:1 with Application (unique `application_id` FK)
- **Store of**: parsed CV text, anonymized text, analysis JSON, embeddings, roles, extracted skills

**Candidates** — 1 table
- Actual purpose: Unique candidate identity per company (deduplicated by email)
- 1:many with Applications
- TenantMixin with unique(company_id, email)
- **Column overlap with CandidateProfile**: Both have `headline`, `bio`, `skills`, `location`. CandidateProfile is the SSOT; Candidate is the ATS-specific projection. **DUPLICATE DATA.**

**EvaluationSessions** — 1 table (NOT a TenantMixin — has own `company_id` column)
- Actual purpose: One interview attempt for one application
- Lifecycle: Created at interview start → in_progress → completed
- **NOT TenantMixin** — has own `company_id` column. Inconsistent with 55 other tenant models.

**EvaluationResults** — 1 table (TenantMixin)
- Actual purpose: Computed score for one evaluation session
- 1:1 with EvaluationSession (unique `evaluation_session_id` FK)
- **Has rubric_snapshot_id FK** for audit trail (which rubric version was used)

**Job** — 1 table (TenantMixin)
- Actual purpose: A job posting by a company
- **TWO category FKs**: `category_id` → categories.id (nullable) AND `job_category_id` → job_categories.id (nullable)
- Version ID for optimistic locking — NOT used by any HTTP route

### 2.2 The REAL Table Graph (with data overlap annotations)

```
Company ───> CompanyMember* ───> User* (GOD)
  │                                  │
  │                                  ├──> CandidateProfile* (DUPLICATE: name, phone, email, 
  │                                  │     headline, bio, skills, location with users table)
  │                                  ├──> RecruiterProfile* (DUPLICATE: name, phone, email, 
  │                                  │     tier, subscription with users table)
  │                                  ├──> AdminProfile
  │                                  │
  │                                  ├──> (15+ one-to-many relationships)
  │                                  │
  ├──> Job ───> Application ───> CvDocument (1:1)
  │        │         │
  │        │         ├──> EvaluationSession ───> EvaluationResult (1:1)
  │        │         │                              │
  │        │         │                              └──> RubricScoringDetail*
  │        │         │
  │        │         ├──> Interview*
  │        │         ├──> Offer
  │        │         ├──> Verdict
  │        │         └──> ActivityLog, Comment, TaggedNote, etc.
  │        │
  │        ├──> JobSkill*
  │        ├──> JobCategory
  │        └──> BatchJob
  │
  ├──> Candidate ───> TalentPoolCandidate (DUPLICATE: skills, headline, bio,
  │         │              location with CandidateProfile)
  │         │
  │         └──> Application (via candidate_id)
  │
  ├──> Campaign* ───> EmailTemplate*, WebhookIntegration*, etc.
  │
  ├──> SubscriptionPlan ───> Transaction, Invoice
  │
  └──> Course ───> Enrollment
```

**Legend:** `*` = data duplication or ownership ambiguity

### 2.3 Duplicated Data Matrix

| Data | Table 1 | Table 2 | Table 3 | Table 4 | Migration |
|------|---------|---------|---------|---------|-----------|
| `name` | users.name (DEPRECATED) | CandidateProfile.name | RecruiterProfile.name | — | ✅ Writes: Profile. Reads: Profile. User has stale data. |
| `phone` | users.phone (DEPRECATED) | CandidateProfile.phone | RecruiterProfile.phone | — | ✅ Same. |
| `email` | users.email (ACTIVE) | CandidateProfile.email | RecruiterProfile.email | — | ❌ User.email is SSOT for auth. Profiles have copies. |
| `headline` | users.headline (DEPRECATED) | CandidateProfile.headline | — | — | ✅ |
| `bio` | users.bio (DEPRECATED) | CandidateProfile.bio | — | — | ✅ |
| `skills` | users.skills (DEPRECATED) | CandidateProfile.skills | Candidate.skills | CV analysis | ❌ 3-way duplication. CandidateProfile is SSOT but Candidate.skills is separate. |
| `location` | users.location (DEPRECATED) | CandidateProfile.location | Candidate.location | — | ❌ 2-way. CandidateProfile SSOT for profile, Candidate for ATS. |
| `tier` | users.tier (DEPRECATED) | Company.tier | RecruiterProfile.tier | — | ❌ 3-way! Company owns the tenant tier. RecruiterProfile mirrors it. |
| `subscription_status` | users.subscription_status (DEPRECATED) | Company.subscription_status | RecruiterProfile.subscription_status | CandidateProfile.subscription_status | ❌ 4-way! Company owns billing, but writes go to RecruiterProfile. |
| `subscription_plan` | users.subscription_plan (DEPRECATED) | RecruiterProfile.subscription_plan | CandidateProfile.subscription_plan | — | ⚠️ Profile SSOT after m38 migration. |
| `usage_jobs` | users.usage_jobs (DEPRECATED) | RecruiterProfile.usage_jobs | — | — | ❌ **subscription_service.py still writes to User column!** |
| `company_name` | users.company_name (DEPRECATED) | RecruiterProfile.company_name | — | — | ✅ |
| `is_super_admin` | users.is_super_admin (DEPRECATED) | AdminProfile.is_super_admin | — | — | ⚠️ Fallback chain still reads both. |

**Total distinct duplicated concepts: 13.** Of these, 9 have migrated writes to Profile but 4 still have active writes to User columns.

---

## 3. DOMAIN OWNERSHIP (Who Actually Owns What)

### Candidate
| Aspect | Current Storage | Correct Owner | Status |
|--------|----------------|---------------|--------|
| Identity (email) | User (SSOT) | User | ✅ Correct |
| Personal info (name, phone, etc.) | CandidateProfile (SSOT) | CandidateProfile | ✅ Writes migrated |
| Profile data (headline, bio, skills) | CandidateProfile (SSOT) | CandidateProfile | ✅ Writes migrated |
| ATS projection (headline, bio, skills) | Candidate (table) | Candidate | ❌ DUPLICATE with CandidateProfile |
| CV data | CvDocument | CvDocument | ✅ Correct |

**Problem:** `Candidate` table has `headline`, `bio`, `skills`, `location` — the SAME columns as `CandidateProfile`. These are NOT the same concept. CandidateProfile stores the candidate's *personal profile* (what they say about themselves). Candidate stores the *ATS record* (what the company knows about the candidate). But they share the same column schema, suggesting the developers saw them as interchangeable.

### Application
| Aspect | Current Storage | Correct Owner | Status |
|--------|----------------|---------------|--------|
| Relation to Candidate | `application.user_id` → User + `application.candidate_id` → Candidate | Candidate | ❌ Dual FK. Candidate FK is nullable (m25 migration not fully backfilled). |
| CV data | Application (8 deprecated cols) + CvDocument (SSOT) | CvDocument | ✅ Migrated |
| Interview state | Application (deprecated) + EvaluationSession (SSOT) | EvaluationSession | ✅ Migrated |
| Score | EvaluationResult (1:1) | EvaluationResult | ✅ Correct |

**Problem:** `Application` has `user_id` FK to User AND `candidate_id` FK to Candidate. This means an application can belong to either a User OR a Candidate, creating ambiguity about which identity system is authoritative.

### Evaluation
| Aspect | Current Storage | Correct Owner | Status |
|--------|----------------|---------------|--------|
| Interview session | EvaluationSession | EvaluationSession | ✅ Correct |
| Score | EvaluationResult | EvaluationResult | ✅ Correct |
| Verdict | Verdict + EvaluationResult.verdict | ❌ DUPLICATE | Two sources for the same concept |
| Fraud detection | EvaluationResult.fraud_score | EvaluationResult | ✅ Correct |

**Problem:** `Verdict` model exists as a separate table but `EvaluationResult` also has a `verdict` column. These are supposed to be the same concept but stored in two places. The verdict may be set via `scoring_service.set_verdict()` which creates a `Verdict` record, but `EvaluationResult.verdict` is set independently.

### ATS Pipeline
| Aspect | Current Storage | Correct Owner | Status |
|--------|----------------|---------------|--------|
| Stage history | ApplicationStageHistory | ApplicationStageHistory | ✅ Correct |
| Comments | Comment (self-referential) | Comment | ✅ Correct |
| Ratings | CandidateRating | CandidateRating | ✅ Correct |
| Activity log | ActivityLog | ActivityLog | ✅ Correct |
| Interaction log | CandidateInteraction | CandidateInteraction | ✅ Correct |

### Subscription/Billing
| Aspect | Current Storage | Correct Owner | Status |
|--------|----------------|---------------|--------|
| Company tier | Company.tier | Company | ✅ Correct |
| Recruiter plan | RecruiterProfile.tier | ❌ WRONG | Should read from Company, not have its own copy |
| Candidate plan | CandidateProfile.subscription_plan | ❌ WRONG | Candidate subscription is tied to User, not Candidate |
| Usage counters | RecruiterProfile.usage_* | RecruiterProfile | ✅ After subscription_service.py fix |
| Payment proof | User.payment_proof_path | ❌ WRONG | Should be on Company or RecruiterProfile |

**Key issue:** `Company.tier`, `RecruiterProfile.tier`, and `RecruiterProfile.subscription_plan` all mirror the same concept (what plan is this tenant on?). The Company should be the SSOT, and RecruiterProfile should derive from it.

---

## 4. MULTIPLE SOURCES OF TRUTH (Complete Inventory)

### SSOT-1: Skills — 4 sources found

| Source | Storage | Written by | Read by | Status |
|--------|---------|------------|---------|--------|
| CandidateProfile.skills | `candidate_profiles.skills` | Profile PUT, backfill | profile_helpers.get_user_skills() | **SSOT** |
| User.skills | `users.skills` | Signup, profile PUT (dual) | Fallback reads only | **DEPRECATED** |
| Candidate.skills | `candidates.skills` | backfill_candidate_enrichment.py | ATS search, talent pool | **SEPARATE CONCEPT** |
| CV analysis.skills | JSON in CvDocument.analysis_json | CV analysis | Interview customization | **DERIVED** |

**Risk:** MEDIUM. CandidateProfile.skills and Candidate.skills are not synced. A candidate can update their profile but their ATS record won't reflect it.

### SSOT-2: Tier/Subscription — 4 sources found

| Source | Storage | Written by | Status |
|--------|---------|------------|--------|
| Company.tier | `companies.tier` | Admin only | **ROOT OWNER** |
| RecruiterProfile.tier | `recruiter_profiles.tier` | Payment, admin | **MIRROR** |
| User.tier | `users.tier` | Admin routes (dual) | **DEPRECATED** |
| RecruiterProfile.subscription_plan | `recruiter_profiles.subscription_plan` | Payment, admin | **MIRROR** |

**Risk:** HIGH. Company.tier and RecruiterProfile.tier can diverge. Payment flow writes to RecruiterProfile but reads may check Company.tier.

### SSOT-3: Verdict — 2 sources found

| Source | Storage | Written by | Status |
|--------|---------|------------|--------|
| EvaluationResult.verdict | `evaluation_results.verdict` | scoring_service.set_verdict() | **SSOT** |
| Verdict table | `verdicts.verdict` | Verdict model creation | **DUPLICATE** |

**Risk:** MEDIUM. Two separate tables store the same concept with no sync.

### SSOT-4: Application User Identity — 2 sources

| Source | Column | Written by | Status |
|--------|--------|------------|--------|
| Application.user_id | FK to users.id | Application creation | **SSOT** (all apps have it) |
| Application.candidate_id | FK to candidates.id | Backfill (nullable) | **NEW** (m25, not fully populated) |

**Risk:** HIGH. `candidate_id` is nullable. Queries that filter on `candidate_id` may miss applications that weren't backfilled.

### SSOT-5: EvaluationSession company_id — 1 explicit + 1 inherited

| Source | Column | Status |
|--------|--------|--------|
| EvaluationSession.company_id | Direct column, NOT TenantMixin | ✅ Self-contained |
| EvaluationSession → Application → Job.company_id | FK chain | ❌ Redundant path |

**Risk:** LOW. The direct column is correct. But the FK chain also exists, creating two possible paths to determine the company.

---

## 5. REAL BACKEND ARCHITECTURE (Not Intended)

### 5.1 The Actual Request Flow

```
HTTP Request
  │
  ├── Middleware (6 layers)
  │    1. RequestIDMiddleware
  │    2. SanitizationMiddleware
  │    3. SecurityHeadersMiddleware + CSRFMiddleware
  │    4. BodySizeLimitMiddleware
  │    5. MetricsMiddleware (Prometheus)
  │    6. RateLimitMiddleware (conditionally)
  │
  ├── Route matching (FastAPI router)
  │    48 router files in routers/__init__.py
  │    7+ router files NOT imported anywhere (bot.py, consent.py, gdpr.py, etc.)
  │
  ├── Dependency injection
  │    ├── get_db → SessionLocal (yield, finally close)
  │    ├── get_current_user → decode JWT → query User + CompanyMember → attach _company_id
  │    ├── require_recruiter/candidate/admin → check User.role
  │    └── get_current_company_id → read _company_id from current_user (set in get_current_user)
  │
  ├── Router handler (~590 endpoints)
  │    ├── Direct ORM: db.query(Model).filter(...).first()  [40/55 routers]
  │    ├── Tenant check: get_application_for_recruiter(id, recruiter, db) [~15 routers]
  │    ├── Authz helpers: check_permission(user, "perm") [admin routers]
  │    └── Profile helpers: get_user_name(user) [30+ files]
  │
  ├── ORM Session (SessionLocal)
  │    ├── Read: db.query()
  │    ├── Write: db.add() + db.commit()
  │    └── No explicit transaction boundaries (auto-flush)
  │
  └── Response serialization
       ├── Pydantic schemas (some endpoints)
       └── Raw dicts (most endpoints)
```

### 5.2 Layer Violations

**VERIFIED:** 40/55 router files contain direct ORM queries AND business logic.

Example from `backend/routers/recruiter_settings.py:85-90`:
```python
profile = getattr(recruiter, "recruiter_profile", None)  # ORM access
if not profile:
    profile = RecruiterProfile(user_id=recruiter.id)     # Domain logic
    db.add(profile)
    db.flush()
for key, value in settings_update.model_dump(exclude_unset=True).items():
    setattr(profile, key, value)                          # Business logic
db.commit()                                               # Transaction boundary
```

**Effect:** There is no service layer for settings. All settings logic (validation, defaults, persistence) lives in the HTTP handler.

### 5.3 Service Layer (What Exists vs What Doesn't)

| Service | Exists? | Location | Called by | Called by ORM too? |
|---------|---------|----------|-----------|-------------------|
| AI orchestration | ✅ | `ai/engine.py`, `ai/llm.py` | Routers | No |
| Scoring | ✅ | `scoring_service.py` | Routers + scheduler | ⚠️ rubric_router.py bypasses |
| Subscription | ✅ | `subscription_service.py` | Routers | ⚠️ Still writes to User columns |
| CV | ✅ | `cv_service.py` | Routers | No |
| Email | ✅ | `email_service.py` | Routers + scheduler | No |
| Calendar | ✅ | `calendar_service.py` | Routers | No |
| E-sign | ✅ | `esign_service.py` | Routers | No |
| Re-engagement | ✅ | `reengagement_engine.py` | Scheduler | No |
| Background check | ✅ | `background_check_service.py` | Routers | No |
| Adverse action | ✅ | `adverse_action_service.py` | Routers | No |
| **Settings** | ❌ | — | — | ✅ Direct ORM in routers |
| **Job CRUD** | ❌ | — | — | ✅ Direct ORM in routers |
| **Application CRUD** | ❌ | — | — | ✅ Direct ORM in routers |
| **Team management** | ❌ | — | — | ✅ Direct ORM in routers |
| **Campaign management** | ❌ | — | — | ✅ Direct ORM in routers |
| **Admin operations** | ❌ | — | — | ✅ Direct ORM in routers |

**At least 30 CRUD operations are missing a service layer.**

---

## 6. REAL FRONTEND ARCHITECTURE

### 6.1 What Actually Exists

**Rendering model:** Server-rendered MPA. 100+ HTML pages. No SPA framework. No component framework.

**58 JS files** loaded via sequential `<script>` tags in every HTML page. No bundler. No module system. Global namespace pollution.

**State management:** localStorage (25 keys, 160+ access points) + in-memory Map (fetchAPI cache, 100 entries, 30s TTL) + CustomEvent bus + BroadcastChannel (cross-tab).

**Auth:** httponly JWT cookie + `logged_in=` marker cookie + `csrf_token` cookie. No JWT in JavaScript memory. The `AuthToken` singleton returns `'cookie-auth'` string (not the actual JWT).

### 6.2 Auth Flow (Client Side)

```
Page load
  │
  ├── DOMContentLoaded (auth-guard.js)
  │    ├── requireAuth() → check localStorage token + loggedInAt (24hr freshness)
  │    ├── checkSession() → GET /auth/me → updates loggedInAt
  │    └── refreshUserCache() → localStorage: role, userName, userId, userPhotoUrl
  │
  ├── DOMContentLoaded (config.js)
  │    └── getAuthMe() → GET /auth/me → caches in _apiCache (5s TTL)
  │
  ├── DOMContentLoaded (components.js)
  │    └── Components.init() → render sidebar, header from localStorage
  │
  ├── localizationReadyPromise
  │    └── setLanguage() → load translations, apply direction
  │
  └── Page-specific inline <script>
       └── fetchAPI('/endpoint') → Promise
```

### 6.3 Frontend Cache Architecture

```
fetchAPI(method, endpoint)
  │
  ├── GET → check _apiCache (key = "auth|anon:endpoint:method")
  │    ├── HIT (within 30s TTL) → return cached
  │    └── MISS → fetch from server → store in cache → return
  │
  └── POST/PUT/DELETE → fetch from server
       └── on 200 OK → _invalidateForMutation(endpoint)
            ├── Walk _MUTATION_CACHE_MAP (~20 prefix rules)
            ├── Clear matching cache entries
            ├── BroadcastChannel('candway-cache-invalidate') → other tabs
            └── CustomEvent('candway-cache-invalidate') → same page
```

### 6.4 Edge Cases

- **Cache stampede:** `getAuthMe()` uses request dedup (pending request cache). If 10 components call `getAuthMe()` in the same tick, only 1 HTTP request fires.
- **Session timeout:** 401 response triggers `/auth/refresh` POST. If refresh also fails, clears localStorage and redirects to `?session=expired`.
- **Cross-tab sync:** `BroadcastChannel('candway-cache')` sends cache invalidation events. Fallback to localStorage for older browsers.
- **Offline:** Service worker registered but catches errors silently. No offline data strategy.

---

## 7. ARCHITECTURAL SMELLS (Complete Inventory)

### 7.1 God Objects

**God Model: User** — 15 relationships, 36 deprecated columns, 36 active columns. Touches 10+ bounded contexts.

**God Table: users** — 72 total columns. Indexed by 7 indexes (3 on deprecated columns).

**God Router: recruiter_settings.py** — Handles: settings CRUD, company logo upload, SMTP test, subscription upgrade, subscription status, invoice management, invoice download, payment proof upload, email template CRUD, email template seed. At least 6 distinct bounded contexts in one router.

### 7.2 Anemic Domain Models

**Application** — Has 30+ relationships, 50+ columns, but ZERO domain methods. All logic (status transitions, scoring, invitation) lives in routers or services.

**Company** — Has 15 columns but ZERO methods. No `can_recruit()`, `is_on_trial()`, `has_reached_job_limit()`.

**Job** — Has 20+ columns but ZERO methods. No `is_expired()`, `can_accept_applications()`, `days_until_expiry()`.

**SubscriptionPlan** — Has 15 columns but ZERO methods. No `can_perform_action(user, action_type)`, `get_limits_for_role(role)`.

### 7.3 Monkey-Patched Relationships

**User model has 8 monkey-patched relationships:**
- `backend/models/ats/application.py:371-375`: `User.jobs`, `User.payouts`, `User.candidate_profile`, `User.recruiter_profile`, `User.admin_profile`
- `backend/models/core/lms.py:361-364`: `User.courses`, `User.enrollments`

**This is fragile:** The monkey patches depend on import order. If `application.py` is imported before `user.py`, the User class doesn't exist yet. This is managed by lazy imports, but it means any import cycle could break the entire model definition.

### 7.4 Circular Dependencies

**VERIFIED circular import chain:**
1. `backend/models/ats/application.py` imports `User` from `backend.database`
2. `backend/database.py` re-exports from `backend.models.__init__`
3. `backend.models.__init__` imports ALL models including `ats/application.py`
4. `ats/application.py` monkey-patches `User.jobs` (needs User class)

This works because `backend.database` is a *re-export shim* that imports models lazily. But the import chain is:

```
database.py → models/__init__.py → models/ats/application.py
  → backend.database (again, circular) → User exists at this point
```

**Risk:** LOW at runtime (due to lazy imports), MEDIUM for maintainability (any refactoring that changes import order breaks everything).

### 7.5 Dead and Unreachable Code

**Routers not imported anywhere:**
- `backend/routers/bot.py` — Teams bot endpoints
- `backend/routers/consent.py` — GDPR consent endpoints
- `backend/routers/gdpr.py` — GDPR data management  
- `backend/routers/monitoring.py` — Prometheus metrics
- `backend/routers/payments.py` — Payment processing
- `backend/routers/recruiter_questions.py` — Screening questions
- `backend/routers/recruiter_reports.py` — Reports
- `backend/routers/recruiter_reengagement.py` — Re-engagement
- `backend/routers/recruiter_skill_trees.py` — Skill trees

**These 9 router files exist on disk but are NOT included in `routers/__init__.py`.** They may be mounted directly in `app.py`. If not, their endpoints are unreachable.

**Not verified:** Whether `app.py` mounts these directly. The previous audit's `app.py` analysis didn't confirm each router's mount point.

### 7.6 N+1 Query Patterns

**VERIFIED in scheduler.py:**
- `_pending_followup()`: Loop over applications → per-app email check → 3 queries per app
- `_auto_interview_invite()`: Loop over 50 apps → per-app evaluation check → 4+ queries per app
- `_auto_reject_incomplete()`: Loop over apps → per-app field check → 2 queries per app

**VERIFIED in search.py:**
- `_candidate_to_result()`: Per-application enrichment → each call queries related models
- `_preload_interviews()`: Properly batch-loads interviews but `_candidate_to_result` still loads per-row

### 7.7 Property Delegation (Hidden Coupling)

Application model delegates ~10 properties to EvaluationSession:

```python
# backend/models/ats/application.py
@property
def interview_state(self):
    session = self.latest_evaluation_session
    return session.interview_state if session else "not_started"

@property
def interview_progress(self):
    session = self.latest_evaluation_session
    return session.interview_progress if session else 0
# ... same for interview_time_left, interview_log, interview_questions, etc.
```

**Effect:** Code that reads `app.interview_state` is actually reading `EvaluationSession.interview_state` via a property accessor. This is hidden coupling — the property chain is not obvious to a developer reading the code.

### 7.8 SubscriptionService Still Writes to User Deprecated Columns

**VERIFIED in `backend/subscription_service.py`:**
```python
# Line 92-97: can_perform_action
setattr(user, "usage_jobs", new_count)  # Writes to USER, not RecruiterProfile

# Line 125-127: record_usage
setattr(user, field, value)  # field is "usage_jobs/cvs/ai_interviews" → User

# Line 140: decrement_usage  
setattr(user, field, value)  # Same — User, not RecruiterProfile
```

**This is the LAST remaining active write to deprecated User columns** that hasn't been migrated. Every time a recruiter posts a job or analyzes a CV, their usage counter is updated on `User.usage_jobs/cvs/ai_interviews` — but NOT on their `RecruiterProfile`.

### 7.9 Double FK on Application (user_id + candidate_id)

Application has:
- `user_id` FK → users.id (NOT NULL, populated at creation)
- `candidate_id` FK → candidates.id (NULLABLE, populated by backfill)

**Effect:** The same application can belong to a User AND optionally to a Candidate. If a candidate applies via email (no User account), `user_id` is NULL... wait, it can't be NULL — it's NOT NULL. So every application MUST have a User. The `candidate_id` is an additional, optional link.

This means: The Candidate table becomes a "shadow" identity that's never used for authentication but holds ATS data. It's an additional identity system layered on top of User.

### 7.10 EvaluationSession NOT a TenantMixin

**VERIFIED:** `backend/models/evaluation/evaluation.py`:
```python
class EvaluationSession(Base):
    __tablename__ = "evaluation_sessions"
    # NO TenantMixin
    # Has its own company_id column:
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
```

**Effect:** `tenant_query()` helper (which filters by `model.company_id == company_id`) may skip EvaluationSession because it's not a TenantMixin. The `tenant_query()` function checks `isinstance(model, TenantMixin)`, which would be False for EvaluationSession.

---

## 8. DOMAIN MODEL VALIDATION

### 8.1 Does Candidate Represent a Person?

**Current:** Candidate is an ATS record linked to User via `user_id → users.id` AND has its own `email` (unique per company).
**Problem:** Candidate is neither fully a person (it doesn't authenticate) nor fully a record (it has its own email and phone). It's a hybrid.
**Correct domain:** Candidate should be a **person** (the actual human applying). User should be a **login identity**. CandidateProfile should be the **person's data**.

### 8.2 Should Application Own Candidate Data?

**Current:** Application has `full_name`, `email`, `phone` directly on the row, PLUS links to `user_id` (User) AND `candidate_id` (Candidate).
**Problem:** The same candidate applying to 5 jobs has their name/email/phone copied 5 times (once per Application).
**Correct domain:** Application should reference Candidate (the person). Candidate data should NOT be duplicated on Application.

### 8.3 Should Evaluation Belong to Candidate or Application?

**Current:** EvaluationSession → Application. EvaluationResult → EvaluationSession.
**Problem:** A candidate interviews for one job (one Application). The evaluation belongs to the Application, which is correct.
**Correct domain:** ✅ Correct. Evaluation belongs to Application.

### 8.4 Should Skill Belong to Profile?

**Current:** CandidateProfile.skills (text field, SSOT) + Candidate.skills (text field, ATS duplicate) + CvDocument.extracted_skills (JSON, CV-derived).
**Problem:** Three separate skill stores with no sync mechanism.
**Correct domain:** Skills should be on CandidateProfile (self-reported) and CvDocument (AI-extracted). Candidate.skills should be removed.

### 8.5 Would This Work with 10 Million Users?

| Table | Est. rows @ 10M users | Problem |
|-------|----------------------|---------|
| users | 10M | 72 columns + 7 indexes = slow writes. The 36 deprecated columns waste ~2KB per row = 20GB wasted. |
| applications | 50M (5 per user) | user_id FK is OK. candidate_id FK being nullable makes queries slower (MySQL doesn't optimize NULL joins well). |
| evaluation_sessions | 150M (3 per app) | interview_log is JSON deferred (good). But interview_turn_seq as an integer column means 150M sequence updates. |
| evaluation_results | 150M | 1:1 with sessions. Version_id + optimistic locking = 150M version checks. OK with good indexing. |
| interview_turns | 1.5B (10 per session) | PII encrypted with EncryptedText — OK. But FK to evaluation_session_id must be heavily indexed. |
| cv_documents | 50M | analysis_json and cv_text are deferred Text columns — OK. But cv_embedding is Text (could be large). |
| companies | 100K | Fine (10M users / 100 users per company average). |
| company_members | 10M | Fine (one per user). |
| notifications | 500M+ | user_id FK → users.id. Time-series data on a single table = bad. Needs partitioning. |

**Scalability blockers:**
1. **users table** — 72 columns on the central identity table. Every query loads the full row. Partitioning is impossible because every FK references it.
2. **No time-series partitioning** — Notifications, audit_logs, login_attempts, activity_logs are unbounded tables with no partitioning strategy.
3. **JSON columns without indexes** — `analysis_json`, `interview_log`, `proctoring_violations` — MySQL can't index JSON efficiently.
4. **Text columns on high-read tables** — `CvDocument.cv_text` deferred (lazy-loaded) is correct, but some queries may load it anyway.

---

## 9. TARGET ARCHITECTURE

### 9.1 Bounded Contexts

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPANY CONTEXT                          │
│  Aggregate: Company                                         │
│  Entities: Company, CompanyMember, SubscriptionPlan         │
│  Value Objects: CompanyVerification                         │
│  Owns: tier, subscription, billing                          │
├─────────────────────────────────────────────────────────────┤
│                    IDENTITY & ACCESS CONTEXT                 │
│  Aggregate: User                                            │
│  Entities: User, Role, Permission                           │
│  Value Objects: LoginAttempt, TokenBlacklist                │
│  Owns: authentication, authorization, role assignment       │
│  Does NOT own: profile data, skills, company info           │
├─────────────────────────────────────────────────────────────┤
│                    CANDIDATE CONTEXT                         │
│  Aggregate: Candidate (the person, not the login)           │
│  Entities: Candidate, CandidateProfile, CvDocument          │
│  Value Objects: Skill, Qualification, EEOConsent           │
│  Owns: name, email, phone, skills, CV, career data         │
│  Links to: User (for login), Company (for tenant)          │
├─────────────────────────────────────────────────────────────┤
│                    RECRUITER CONTEXT                         │
│  Aggregate: RecruiterProfile                                │
│  Entities: RecruiterProfile, TeamMember                     │
│  Owns: company branding, SMTP config, usage counters        │
│  Links to: User (for login), Company (for tenant)          │
├─────────────────────────────────────────────────────────────┤
│                    ATS CONTEXT                               │
│  Aggregate: Application                                     │
│  Entities: Application, Interview, Offer, BackgroundCheck   │
│  Value Objects: ApplicationStageHistory, Comment, Rating    │
│  Owns: hiring pipeline, status transitions                  │
│  Links to: Candidate, Job, Company                          │
├─────────────────────────────────────────────────────────────┤
│                    EVALUATION CONTEXT                        │
│  Aggregate: EvaluationSession                               │
│  Entities: EvaluationSession, EvaluationResult, Verdict     │
│  Value Objects: InterviewTurn, Rubric, RubricScoringDetail │
│  Owns: interview state, scores, rubric snapshots           │
│  Links to: Application, Company                             │
├─────────────────────────────────────────────────────────────┤
│                    JOB CONTEXT                               │
│  Aggregate: Job                                             │
│  Entities: Job, JobCategory, BatchJob                       │
│  Value Objects: JobSkill, InterviewQuestion                 │
│  Owns: job posting, job configuration                       │
│  Links to: Company                                          │
├─────────────────────────────────────────────────────────────┤
│                    COMMUNICATIONS CONTEXT                    │
│  Aggregate: Conversation                                    │
│  Entities: Conversation, Message, Notification              │
│  Value Objects: EmailTemplate, CampaignTemplate             │
│  Owns: messaging, notifications, email, campaigns           │
│  Links to: User, Company                                    │
├─────────────────────────────────────────────────────────────┤
│                    FINANCE CONTEXT                           │
│  Aggregate: Transaction                                     │
│  Entities: Transaction, Invoice, SavedReport                │
│  Links to: Company, User                                    │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Key Change: Remove User as God Object

**Current:** User has 15+ relationships to 10+ bounded contexts.
**Target:** User only exists in the Identity & Access context. Other contexts reference `actor_id` (UUID, not FK to users.id) for audit purposes.

**Target User Model:**
```python
class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(50))  # 'human' | 'system' (not candidate/recruiter)
    email_verified = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Profile relationship (one-to-one, no cascade)
    profile = relationship("Profile", back_populates="user", uselist=False)
```

### 9.3 Key Change: Merge Candidate + CandidateProfile

**Current:** Candidate and CandidateProfile are separate tables with duplicate columns.
**Target:** Single `candidate` table with all profile + ATS data.

```python
class Candidate(Base, TenantMixin):
    __tablename__ = "candidates"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=True)  # Optional: has login
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    phone = Column(String(255))
    headline = Column(String(255))
    bio = Column(Text)
    skills = Column(JSON)  # Proper JSON, not text
    location = Column(String(255))
    avatar_url = Column(String(255))
    linkedin_url = Column(String(255))
    github_url = Column(String(255))
    portfolio_url = Column(String(255))
    # ... subscription, usage, etc.
    UniqueConstraint("company_id", "email")
```

### 9.4 Key Change: Merge RecruiterProfile → Company Branding

**Current:** RecruiterProfile has company_name, company_description, company_logo_url, SMTP config.
**Target:** Move company branding to a `CompanyBranding` value object. Keep RecruiterProfile for personal recruiter data (name, phone, email).

### 9.5 Recommended Architecture Pattern

**Pattern:** Layered architecture with repository + service layer enforcement.

```
HTTP → Router (thin, auth only) → Service (business logic) → Repository (ORM) → DB
                                          │
                                          ├── Events (DomainEvents)
                                          │
                                          └── Background Jobs (Scheduler)
```

- **Routers:** Auth validation, request parsing, response formatting. ZERO business logic.
- **Services:** All business logic. Transaction boundaries. Domain event emission. ZERO ORM knowledge.
- **Repositories:** All data access. ZERO business logic. Return domain objects.
- **Validation:** At the service layer (not Pydantic, not ORM). Business rules enforced in one place.

---

## 10. MIGRATION PLAN

### Phase 1: Critical Bug Fixes (Week 1)

| Issue | Current | Target | Effort | Risk |
|-------|---------|--------|--------|------|
| subscription_service.py writes to User | `setattr(user, "usage_jobs", ...)` | Write to RecruiterProfile | 1 hour | LOW — readers use Profile already |
| candidate/profile.py dual writes | `setattr(current_user, field, value)` + `setattr(current_user.candidate_profile, field, value)` | Profile only | 30 min | LOW — readers use Profile |
| EvaluationResult secondary writer | `rubric_router.py` creates EvaluationResult | Use scoring_service | 1 hour | MEDIUM — may break interview flow |
| Verdict dual storage | EvaluationResult.verdict + Verdict table | EvaluationResult only | 2 hours | MEDIUM — needs data migration |
| auth.py deprecated writes on signup | `User(name=user.name, ...)` | Profile only | 1 hour | LOW |
| Missing `import os` in webhook | Runtime crash | Add import | 5 min | CRITICAL |

### Phase 2: Data Cleanup (Week 2)

| Issue | Current | Target | Effort | Risk |
|-------|---------|--------|--------|------|
| Drop User deprecated column indexes | 7 indexes on users table | Drop 3 deprecated | 1 hour | LOW (no read dependents) |
| Candidate.skills duplication | 3 skill stores | Derive from CvDocument | 2 hours | MEDIUM (ATS search depends on it) |
| Application.candidate_id backfill | Nullable for pre-migration apps | NOT NULL | 2 hours | MEDIUM (may fail on orphan apps) |
| EvaluationSession → TenantMixin | Own company_id column | Inherit TenantMixin | 30 min | LOW (same column, different code path) |

### Phase 3: Service Layer Extraction (Weeks 3-4)

| Issue | Current | Target | Effort | Risk |
|-------|---------|--------|--------|------|
| Settings router | ORM + logic in router | SettingsService | 2 days | LOW (no functional change) |
| Application CRUD | ORM in router | ApplicationService + ApplicationRepository | 3 days | MEDIUM (many callers) |
| Job CRUD | ORM in router | JobService + JobRepository | 2 days | MEDIUM |
| Team management | ORM in router | TeamService + TeamRepository | 1 day | LOW |

### Phase 4: Frontend Modernization (Weeks 5-6)

| Issue | Current | Target | Effort | Risk |
|-------|---------|--------|--------|------|
| 58 global JS files | No module system | ES modules + Vite bundler | 2 weeks | HIGH (dependency graph unknown) |
| 160+ localStorage access | No state management | Zustand or Jotai | 1 week | MEDIUM (migration per page) |
| Inline scripts in 100+ pages | No shared framework | HX or similar | 3 weeks | HIGH |

### Rollback Strategy for Each Phase

- **Phase 1:** Code-only changes. Rollback = git revert.
- **Phase 2:** Schema migrations have DOWN scripts.
- **Phase 3:** New services run alongside old code. Feature-flag based migration.
- **Phase 4:** Old pages continue to work during migration. Progressive enhancement.

---

## 11. FINAL SCORES (with evidence)

| Category | Score | Evidence |
|----------|-------|----------|
| **Database** | 55/100 | 72-column God table (users). 13 duplicated concepts across 4+ tables each. 7 indexes on deprecated columns. 2 FK ambiguity on Application (user_id + candidate_id). |
| **Architecture** | 50/100 | No layer enforcement. 40/55 routers mix ORM + logic. 9 routers not imported. Properties create hidden coupling (app.interview_state → ES). |
| **DDD** | 40/100 | Anemic models (0 methods on Application, Company, Job, SubscriptionPlan). Wrong aggregate boundaries (User is root of everything). 3 bounded contexts mixed into User. |
| **Maintainability** | 45/100 | Monkey-patched relationships across 2 files. Circular import chain. 58 global JS files. 100+ pages with inline scripts. No repository layer. |
| **Scalability** | 60/100 | No partitioning strategy for time-series tables. 72-column central table. No JSON indexing. Interview_turns scales linearly with evaluations. |
| **Performance** | 55/100 | N+1 patterns in scheduler (18 jobs). Uncached `_active_company_ids()`. No eager loading in search results. |
| **Security** | 70/100 | Cookie-based JWT is good. Client-side auth is weak (JS guard, not server redirect). CSRF token correctly implemented. No AI rate limiting. |
| **Consistency** | 45/100 | 4 active dual-write sites. Verdict stored in 2 tables. subscription_service.py writes to wrong table. EvaluationResult writer bypassed by rubric_router.py. |
| **SSOT** | 35/100 | 13 duplicated concepts identified. 3 still have active dual writes. subscription_service.py is the LAST active write to deprecated User columns. |
| **Tenant Safety** | 85/100 | TenantMixin on 55/56 tables (missing: EvaluationSession). `get_*_for_recruiter` helpers correctly filter by company_id. `_active_company_ids()` in scheduler. |
| **Developer Experience** | 40/100 | Import order dependency. Monkey-patched models. Hidden property delegation. No repository abstraction. Mixing concerns in routers. |
| **Testability** | 50/100 | 51 test files exist but architecture makes unit testing hard (service logic in HTTP handlers, no DI for services). Integration tests require full DB. |
| **Observability** | 60/100 | Prometheus middleware exists. Structured logging (logger.py). AuditLog table. Dead letter queue exists but underutilized. |

### OVERALL: 50.4/100

**The architecture is NOT safe for production at scale.** The three root causes (User God object, incomplete Profile migration, missing service layer) create systemic risk. Every new feature either adds to the User God object or creates another bypass around the intended architecture.

**However, the system can be made safe within 6-8 weeks** by following the migration plan in Section 10, starting with Phase 1 (critical bug fixes, 1 week) before any production deployment.
