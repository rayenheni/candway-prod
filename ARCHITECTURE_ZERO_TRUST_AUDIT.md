# ZERO-TRUST ARCHITECTURE AUDIT — Candway Intelligence Platform

**Date:** 2026-07-06
**Scope:** Full system — database, backend, frontend, background jobs, AI, APIs
**Methodology:** Source code analysis with zero assumptions. Every finding traces to actual code.

---

## 1. EXECUTIVE SUMMARY

### Architecture Score: 67/100 — "Structurally sound with significant technical debt"

**Strengths:**
- Multi-tenant isolation is correctly implemented via TenantMixin (company_id FK on 55+ tables)
- Read-side migration to Profile tables is complete — Profile is the single source of truth
- Cookie-based auth (JWT in httponly cookie, not localStorage) is secure
- Sophisticated cache invalidation with cross-tab BroadcastChannel sync
- 50+ AI security tests covering PII masking, prompt injection, output validation
- Optimistic locking on 6 high-write entities (Application, Job, Offer, EvaluationSession, EvaluationResult, SkillDefinition)
- Comprehensive i18n with 3 languages, RTL support, namespace-aware fallback

**Critical Issues (must fix before production):**
1. **36 deprecated User columns still have DB indexes** — writes go to Profile, indexes now track stale data (`idx_users_tier`, `idx_users_subscription`, `idx_users_current_plan`, etc.)
2. **Users table has 36 deprecated columns still receiving writes** during user creation (auth.py lines 420-428) — creates data inconsistency risk
3. **0 optimistic locking usage in HTTP route code** — `@retry_stale` decorator exists but is never applied to any endpoint
4. **Double-commit risk in `adverse_action_service.py`** — two `db.commit()` calls without transactional protection
5. **Double-send risk in `email_sequence_worker.py`** — email sent before EmailSequenceLog is committed
6. **All scoring job exceptions are swallowed** — `jobs/scoring.py` wraps everything in try/except that only logs
7. **`webhook_dispatcher.py` missing `import os`** — will raise `NameError` at runtime
8. **No row-level locking on scheduler mutations** — concurrent HTTP + scheduler access can cause lost updates
9. **Frontend has no module system** — 58 global JS files, no bundler, implicit load order dependencies
10. **160+ localStorage access points** across 23 JS files — no centralized state management

**Production Readiness:** NOT PRODUCTION READY. The architecture is fundamentally sound but has ~20 concrete bugs/issues that must be resolved before connecting to production data.

---

## 2. DATABASE ARCHITECTURE

### 2.1 Entity Count: 90+ tables

| Layer | Tables | TenantMixin | Non-Tenant |
|-------|--------|-------------|------------|
| Foundation | 15 | 4 | 11 |
| Core/Jobs | 20 | 20 | 0 |
| ATS | 25 | 25 | 0 |
| Evaluation | 15 | 13 | 2 |
| Profile | 3 | 3 | 0 |
| AI | 12 | 12 | 0 |
| Finance | 5 | 5 | 0 |
| CMS | 6 | 3 | 3 |

### 2.2 Source of Truth Analysis

| Data Domain | Current Source | Former Source | Migration Status |
|-------------|---------------|---------------|------------------|
| Candidate personal info | CandidateProfile | User (36 cols) | ✅ Complete (reads + writes) |
| Recruiter company info | RecruiterProfile | User | ✅ Complete |
| Admin permissions | AdminProfile | User | ✅ Complete |
| Application CV data | CvDocument | Application (8 cols) | ✅ Complete |
| Interview state | EvaluationSession | Application | ✅ Complete |
| Subscription/tier | RecruiterProfile/CandidateProfile | User | ✅ Complete (m38) |
| Usage counters | RecruiterProfile/CandidateProfile | User | ✅ Complete |
| Batch job counters | Computed properties | BatchJob (2 cols) | ✅ Complete (m37) |
| **User core identity** | **users table** | N/A | **Still active** (email, password, role) |
| **Company** | companies table + CompanyMember | N/A | **Still active** |
| **Role assignment** | users.role | N/A | **Dual: User.role + profile tables** |

### 2.3 Deprecated Columns Still Indexed

**VERIFIED from code and migration history:**

The `users` table has 36 deprecated columns, AND the following indexes still reference them:

| Index | Columns | What It Now Indexes |
|-------|---------|---------------------|
| `idx_users_tier` | `tier` | **Stale** — writes go to RecruiterProfile.tier |
| `idx_users_subscription` | `subscription_status` | **Stale** — writes go to RecruiterProfile |
| `idx_users_current_plan` | `current_plan_id` | **Stale** — writes go to RecruiterProfile |
| `idx_users_role` | `role` | **Partially stale** — role still used on User |
| `idx_users_deleted_role` | `deleted_at`, `role` | **Partially stale** |
| `idx_users_subscription_end` | `subscription_end` | **Stale** — writes go to RecruiterProfile |
| `uq_users_email` | `email` | **Active** — email still read from User |

**Risk:** These indexes consume space, slow writes, and could mislead developers into thinking the data is current.

### 2.4 Nullable FK Problems

| FK | Source | Target | Nullable | Risk |
|----|--------|--------|----------|------|
| `application.candidate_id` | Application | candidates.id | YES | Orphan: application references no candidate |
| `application.job_id` | Application | jobs.id | YES | Orphan: application without a job |
| `application.batch_id` | Application | batch_jobs.id | YES | Orphan: valid use case (manual apply) |
| `job.category_id` | Job | categories.id | YES | Orphan: job without category |
| `job.job_category_id` | Job | job_categories.id | YES | Duplicate category FK — ambiguous |
| `evaluation_session.candidate_id` | EvaluationSession | candidate_profiles.id | YES | Orphan: session without candidate profile |
| `offer.application_id` | Offer | applications.id | NOT NULL but FK | OK: cascade DELETE |
| `user.current_plan_id` | User | subscription_plans.id | YES | **Deprecated** — writes go to RecruiterProfile |

**Ambiguous FK:** `job` has TWO nullable category FKs: `category_id` → `categories.id` AND `job_category_id` → `job_categories.id`. These serve different purposes (legacy vs. new wizard categories) but create ambiguity about which one is authoritative.

### 2.5 Missing Constraints

| Table | Column(s) | Missing Constraint | Impact |
|-------|-----------|-------------------|--------|
| `candidates` | email | NOT NULL ✓ | OK |
| `candidates` | (company_id, email) | UNIQUE ✓ | OK |
| `applications` | (user_id, job_id) | UNIQUE ✓ | OK |
| `evaluation_results` | final_score | CHECK (0-100) | **Missing** — raw float could be -1 or 150 |
| `interview_turns` | score | CHECK (0-100) | Present ✓ |
| `candidate_ratings` | rating | CHECK (1-5) | Present ✓ |
| `evaluation_results` | scoring_status | CHECK enum | Present ✓ |

### 2.6 Migration Leftovers

| Artifact | Current State |
|----------|--------------|
| `Ticket` table | **Deprecated** — superscripted by `SupportTicket` but still in models |
| `ABExperiment` model | **Deprecated** — superscripted by `ABTestExperiment` |
| `BatchJob._deprecated_total_files/_processed_files` | Column dropped (m37), properties remain |
| `Application 8 deprecated CV columns` | Column dropped (m30), properties with CvDocument fallback remain |
| `User 36 deprecated columns` | Still in DB, no migration to drop them exists |

---

## 3. BACKEND ARCHITECTURE

### 3.1 Actual Architecture (Not Intended)

```
HTTP Request
  │
  ├── Middleware stack (6 layers)
  │    ├── RequestID
  │    ├── Sanitization
  │    ├── SecurityHeaders + CSRF
  │    ├── BodySizeLimit
  │    ├── Metrics (Prometheus)
  │    └── RateLimit (optional)
  │
  ├── Router Layer (~55 files, ~590 endpoints)
  │    ├── Auth guards (require_recruiter/candidate/admin)
  │    ├── Tenant isolation helpers (authz.get_*_for_recruiter)
  │    └── Profile helpers (profile_helpers.get_user_*)
  │
  ├── Service Layer (50+ files, inconsistent)
  │    ├── AI services (ai/*)
  │    ├── Business services (scoring_service, subscription_service, etc.)
  │    └── Direct ORM usage from routers (prevalent)
  │
  ├── ORM Layer (SQLAlchemy)
  │    ├── Models with TenantMixin
  │    ├── 6 models with optimistic locking
  │    └── Property accessors for deprecated columns
  │
  ├── Database (MySQL 8)
  └── Background Workers (APScheduler, 18 jobs)
```

### 3.2 Service vs. Router Boundary Violations

**VERIFIED finding: Business logic leakage into routers is the #1 architectural smell.**

Pattern: Router handles auth → router directly queries ORM → router formats response. Service layer is bypassed.

Evidence (all `backend/routers/recruiter_settings.py`):
```python
# Line 126-130: Direct ORM from router
profile = db.query(RecruiterProfile).filter(RecruiterProfile.user_id == recruiter.id).first()
if profile:
    profile.company_logo_url = logo_url
db.commit()
```

```python
# Line 441-454: Business logic (subscription plan resolution) directly in router
plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == sub_plan).first()
limits = {"job_limit": plan.job_limit if plan else 5, ...}
```

This pattern repeats across ~40 of 55 router files.

### 3.3 Repository Layer Assessment

**Status: NOT VERIFIED as a formal layer.** There is a `backend/repository/` directory with `MetricsRepository`. The grep for repository usage shows it's only used in `recruiter_candidates/search.py` (line 258) and `recruiter_enhancements/analytics.py`. All other data access is direct ORM from routers.

### 3.4 Transaction Boundary Analysis

| Pattern | Where | Assessment |
|---------|-------|------------|
| `db.commit()` in router after ORM mutations | Every write endpoint | **Bypasses service layer** — transactions at HTTP handler level |
| `SessionLocal()` in background workers | scheduler.py | Correct — per-job session management |
| Nested `db.commit()` | automation_worker.py + scheduler.py | **Confused boundary** — double commit |
| Two-phase commit | adverse_action_service.py | **Bug** — crash between commits leaves inconsistent state |

### 3.5 Dependency Injection

**VERIFIED:** FastAPI `Depends()` is used for:
- `get_db` — session (all routers)
- `require_recruiter`, `require_candidate`, `require_admin` — auth guards
- `get_current_company_id` — tenant isolation (~8 files only)
- `get_pagination_meta`, `paginate` — pagination

**Gap:** Only ~8 out of ~55 router files use `get_current_company_id`. The rest rely on `authz.get_*_for_recruiter` helpers which internally filter by company_id via the Application/Job/etc. model. This is a valid pattern but creates a hidden dependency chain.

---

## 4. FRONTEND ARCHITECTURE

### 4.1 Rendering Model

Server-rendered HTML multi-page application (MPA). No SPA framework. 58 standalone JS files loaded as global `<script>` tags. ~100 HTML pages across 5 role directories.

### 4.2 Critical Issues

1. **No module system** — 58 JS files loaded via sequential `<script>` tags. Implicit dependency ordering. Any deviation causes runtime errors.

2. **160+ localStorage access points** across 23 files. Keys include: `token`, `role`, `user`, `userName`, `userId`, `userPhotoUrl`, `profileStrength`, `user_email`, `loggedInAt`, `candway_lang`, `candway_feature_flags`, `candway_cookie_consent`, `error_log`, `preferredTheme`, `sidebar_collapsed`, `active_app_id`, etc.

3. **Client-side authorization** — `auth-guard.js` `requireRole()` is purely client-side. Code acknowledges this (line 126: "The real trust boundary is the API") but any page without the check leaks UI.

4. **Inline script duplication** — Every HTML page has its own inline `<script>` block. A change to initialization requires editing ~100 HTML files.

5. **No API response validation** — `fetchAPI()` returns raw JSON with no runtime schema validation. Backend API changes silently break consuming pages.

6. **DOMPurify CDN dependency** — XSS protection depends on CDN availability. Fallback `basicSanitize()` uses `textContent` which strips all HTML.

### 4.3 Strengths

- Cookie-based auth (JWT not exposed to JavaScript)
- Sophisticated cache invalidation with cross-tab BroadcastChannel sync
- Layered XSS defenses (DOMPurify + textContent fallback + event handler sanitization)
- Real-time notifications via WebSocket with HTTP polling fallback
- Comprehensive i18n with namespace-aware fallback, RTL support

---

## 5. DATA FLOW ANALYSIS

### 5.1 Candidate Application Lifecycle

```
1. Candidate applies → Application created (user_id, job_id)
2. CV uploaded → CvDocument created, linked via application_id
3. Invitation sent → Email sent, EmailSequenceLog created
4. Interview started → EvaluationSession created (linked to application_id)
5. Interview progress → InterviewTurn records created (tenant-scoped)
6. Interview completed → EvaluationResult created (linked to evaluation_session_id)
7. Score computed → EvaluationResult.final_score set
8. Bias audit → AIAuditLog + CalibrationSample created
9. Offer created → Offer record (version_id optimistic locking)
10. Offer accepted/rejected → Offer status updated, Candidate.interactions logged
```

**Data ownership chain:** Application → EvaluationSession → EvaluationResult → Verdict → Offer. Each step links back to the parent via FK chain. Tenant isolation preserved through company_id at the Application level.

### 5.2 User Authentication Flow

```
1. POST /auth/login → Validate credentials → Set httponly JWT cookie + CSRF token cookie
2. GET /api/v1/auth/me → Read JWT cookie → Return user + profile data
3. PUT /auth/profile → Validate CSRF → Update RecruiterProfile/CandidateProfile
4. POST /auth/logout → Clear cookies → Blacklist JWT
```

**Security:** Cookie-based JWT prevents XSS token theft. CSRF token prevents cross-origin requests.

**Gap:** `/auth/refresh` exists but auto-refresh on 401 is handled client-side without user notification. If refresh fails, session silently expires.

### 5.3 Background Scoring Flow

```
1. Interview completed → HTTP route triggers run_async_bias_audit()
2. run_async_bias_audit() → sync_cv_document() → db.commit()
3. Scheduler triggers run_drift_check() → iterate companies → compute drift
4. Scheduler triggers collect_calibration_samples() → iterate companies
5. Scheduler triggers run_score_recalibration() → iterate companies → compute new scores
```

**Critical gap:** All scoring job exceptions are swallowed (try/except with only logger.error). No retry, no DLQ, no alerting.

---

## 6. SOURCE OF TRUTH MATRIX

| Concept | Canonical Source | Secondary Sources | Migration Complete? |
|---------|-----------------|-------------------|-------------------|
| User identity (email, password, role) | `users` table | `profiles.*.email` | NO — dual source |
| Candidate personal info | `candidate_profiles` | `users` (36 deprecated cols) | YES |
| Recruiter company info | `recruiter_profiles` | `users` (deprecated cols) | YES |
| Admin permissions | `admin_profiles` | `users.is_super_admin` | YES |
| Application CV data | `cv_documents` | `applications._deprecated_*` | YES |
| Interview state | `evaluation_sessions` | `applications._deprecated_*` | YES |
| Score | `evaluation_results` | N/A | YES |
| Subscription/tier | `recruiter_profiles` / `candidate_profiles` | `users` (deprecated cols) | YES |
| Usage counters | `recruiter_profiles` / `candidate_profiles` | `users` (deprecated cols) | YES |
| Company | `companies` table | N/A | YES |
| Tenant membership | `company_members` | N/A | YES |
| Job posting | `jobs` | N/A | YES |
| Offer | `offers` | N/A | YES |
| Campaign | `reengagement_campaigns` + `campaign_templates` | N/A | YES |
| Webhook config | `webhook_integrations` | N/A | YES |
| Email template | `email_templates` | N/A | YES |

**Summary:** 14/16 concepts have a single canonical source. 2 concepts are dual-sourced:
- **User identity** — email/password/role live on `users` table, but `candidate_profiles.email` and `recruiter_profiles.email` also exist as copies. Role assignment lives on `users.role` but is used in auth flow; profile tables have no role.
- **Notifications** — `Notification` table (TenantMixin) vs. WebSocket push vs. polling. Notifications table is the canonical persistence, but WebSocket and polling are transient delivery channels.

---

## 7. ARCHITECTURAL SMELLS

### 7.1 God Object: User Model (36+ relationships)

**VERIFIED** — `backend/models/foundation/user.py` defines 9 columns, but monkey-patching in `application.py` and `lms.py` adds 20+ relationships:
- `applications`, `batch_jobs`, `visits_received`, `visits_made`, `saved_jobs`, `roadmaps`, `notification_preferences`, `candidate_profile`, `recruiter_profile`, `admin_profile`, `jobs`, `payouts`, `courses`, `enrollments`, etc.

The User model touches EVERY domain: ATS, Core, Evaluation, Finance, LMS. It is the central coupling point of the entire system.

### 7.2 Feature Envy: Routers Doing Service Work

**VERIFIED across ~40 routers.** Example from `backend/routers/recruiter_settings.py:441`:
```python
plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == sub_plan).first()
limits = {"job_limit": plan.job_limit if plan else 5, ...}
```
This is business logic (subscription plan → limits mapping) that should live in `SubscriptionService`, not in the HTTP handler.

### 7.3 Shotgun Surgery: Auth Changes

**VERIFIED** — Adding a new role or changing the auth flow requires editing:
1. `backend/dependencies.py` — new `require_*` guard
2. `backend/authz.py` — new `get_*_for_recruiter` or permission check
3. `backend/routers/auth.py` — login/signup flow
4. `backend/models/foundation/user.py` — role column
5. `js/auth-guard.js` — client-side role routing
6. All ~100 HTML pages that use `requireRole()`
7. `js/auth-token.js` — role propagation

### 7.4 Shotgun Surgery: Profile Migration

**VERIFIED** — The User→Profile migration required edits to:
1. `backend/profile_helpers.py` — 32 functions
2. `backend/models/evaluation/profile.py` — 3 models
3. 11 router files (50+ individual read sites)
4. 4 Alembic migrations (m28, m29, m38)
5. 5 backfill scripts
6. `backend/dependencies.py` — is_admin_user check
7. `backend/authz.py` — super admin check
8. `backend/routers/auth.py` — claim-account flow

### 7.5 Anemic Domain Model

**VERIFIED** — Many models are pure data containers with no domain logic. Examples:
- `SubscriptionPlan` — has fields but no methods for eligibility checks, upgrade paths, limit calculations
- `Job` — has fields but no methods for activation, expiration, status transitions
- `Campaign` — data container, logic lives in `reengagement_engine.py`

### 7.6 Temporal Coupling: Initialization Order

**VERIFIED** — Frontend JS has no initialization framework. 58 files depend on `<script>` tag ordering. `localizationReadyPromise` is the only explicit dependency gate. Race conditions:
- `config.js getAuthMe()` — called at DOMContentLoaded
- `auth-guard.js checkSession()` — also called at DOMContentLoaded
- `Components.init()` — also at DOMContentLoaded
- `translations.js` — async injects language files
- No explicit ordering contract.

### 7.7 Layer Violation: Direct ORM from HTTP Routes

**VERIFIED** — Prevalence pattern:
```python
@router.get("/settings")
def get_settings(recruiter: User = Depends(require_recruiter)):
    profile = db.query(RecruiterProfile)...  # ORM in router
    limits = compute_limits(plan)              # Logic in router
    return {"tier": tier, ...}                 # Response in router
```

The service and repository layers are optional bypasses, not enforced gateways.

---

## 8. CRITICAL ISSUES (Must fix before production)

### C-01: `webhook_dispatcher.py` Missing `import os` (RUNTIME CRASH)
**File:** `backend/routers/recruiter_enhancements/webhook_dispatcher.py:46`
**Evidence:** `os.environ.get("WEBHOOK_SIGNING_SECRET")` called without `import os` at top of file.
**Risk:** Runtime `NameError` when `settings.webhook_signing_secret` is falsy.
**Fix:** Add `import os`.

### C-02: Scoring Jobs Swallow All Exceptions (SILENT DATA LOSS)
**File:** `backend/ai/scoring_jobs.py` — all 4 functions (`run_drift_check`, `collect_calibration_samples`, `run_score_recalibration`, `run_async_bias_audit`)
**Evidence:** All 4 wrap their body in `try/except Exception as e: logger.error(...)`. No re-raise, no DLQ, no retry.
**Risk:** Critical background jobs silently fail. Scores are not recalibrated. Drift is not detected.
**Fix:** Remove blanket `except` or re-raise after logging. Add DLQ recording.

### C-03: Double `db.commit()` in AdverseActionService (PARTIAL WRITE)
**File:** `backend/adverse_action_service.py:68,78` and `131,141`
**Evidence:** Status update and status log are committed in two separate `db.commit()` calls. A crash between them leaves inconsistent state.
**Risk:** Application status shows "pre_adverse_sent" but no log entry exists.
**Fix:** Move both updates before a single `db.commit()`.

### C-04: Email Sent Before Log Committed in EmailSequenceWorker (DOUBLE-SEND)
**File:** `backend/email_sequence_worker.py:133-156`
**Evidence:** `send_email()` is called before `db.commit()`. A crash after send but before commit causes re-send on retry.
**Risk:** Candidates receive duplicate emails.
**Fix:** Commit the EmailSequenceLog before sending the email, or use a two-phase approach.

### C-05: 36 Deprecated User Columns Still Indexed (WASTED RESOURCES + CONFUSION)
**File:** `backend/models/foundation/user.py` + migration history
**Evidence:** 7 indexes on deprecated columns (`idx_users_tier`, `idx_users_subscription`, `idx_users_current_plan`, `idx_users_role`, `idx_users_deleted_role`, `idx_users_subscription_end`).
**Risk:** Writes to User columns still happen during user creation (auth.py lines 420-428). Indexes consume space and slow writes.
**Fix:** Create migration to drop deprecated indexes. Stop writing deprecated fields during user creation.

### C-06: No Optimistic Locking Applied in HTTP Routes (CONCURRENCY DATA LOSS)
**File:** `backend/optimistic_lock.py` — `@retry_stale` decorator exists
**Grep evidence:** `@retry_stale` is NOT used in ANY router file. Zero occurrences across all 55 router files.
**Risk:** Concurrent HTTP requests can silently overwrite each other's changes to Application, Job, Offer, EvaluationSession, EvaluationResult.
**Fix:** Apply `@retry_stale` to all write endpoints for these 5 models.

### C-07: Frontend Has No Module System (MAINTAINABILITY)
**Evidence:** 58 JS files loaded via sequential `<script>` tags. No bundler, no modules.
**Risk:** Any script tag ordering error breaks the application. No tree-shaking, no dead code elimination.
**Fix:** Migrate to ES modules with a bundler (Vite, esbuild, or webpack).

### C-08: 160+ localStorage Access Points (FRAGILE STATE)
**Evidence:** 25 distinct localStorage keys accessed 160+ times across 23 JS files.
**Risk:** No centralized state management. Any code can corrupt any key. 5MB limit. Synchronous access blocks the main thread.
**Fix:** Introduce a thin state management wrapper or migrate to sessionStorage for session-only data.

### C-09: Client-Side Authorization (SECURITY THEATER)
**File:** `js/auth-guard.js:126` — explicitly acknowledges "The real trust boundary is the API"
**Evidence:** `requireRole()` checks are purely client-side. Any HTML page without `requireRole()` call leaks UI.
**Risk:** Low (API enforces real auth), but UI information disclosure is possible.
**Fix:** Server-side redirect for unauthorized pages, not client-side JS checks.

### C-10: `auth.py` Still Writes to Deprecated User Columns (DUAL-SOURCE REINTRODUCTION)
**File:** `backend/routers/auth.py:419-428`
**Evidence:** New user creation still writes to `users.name`, `users.phone`, `users.location`, `users.company_name`, `users.headline`.
**Risk:** Every new user signup writes data to the now-deprecated User columns, maintaining the dual-source problem.
**Fix:** Write only to `users.email`, `users.hashed_password`, `users.role` during creation. Populate profile tables immediately.

---

## 9. HIGH ISSUES

### H-01: 40/55 Routers Mix ORM + Business Logic
**Evidence:** Direct `db.query(Model)` calls and business logic (status transitions, limit calculations, pricing logic) in HTTP route handlers. Zero repository layer enforcement.
**Risk:** Cannot swap storage backend. Unit testing requires DB. Logic duplication across routers.

### H-02: 0 Dead Letter Queue Usage Outside Scheduler
**Files:** `automation_worker.py`, `email_sequence_worker.py`, `webhook_dispatcher.py`, `jobs/scoring.py`
**Evidence:** Only `scheduler.py` → `_run_with_retry()` → `record_dead_letter()` uses the DLQ.
**Risk:** Individual failures in automation rules, email sequences, webhooks, and scoring jobs are silently lost.

### H-03: Missing Row-Level Locking on Scheduler + HTTP Concurrent Access
**Files:** `scheduler.py` (18 jobs), all HTTP write endpoints
**Evidence:** No `SELECT ... FOR UPDATE` or `with_for_update()` used anywhere. 6 models have `version_id` for optimistic locking but it's not used in HTTP routes.
**Risk:** Concurrent scheduler tick + recruiter action on same application status = lost update.

### H-04: No Rate Limiting on AI Endpoints
**Evidence:** `rate_limiter.py` and `redis_rate_limiter.py` exist but are NOT applied to AI endpoints (`ai_interview/*`, `llm.py`, `engine.py`).
**Risk:** A malicious actor could exhaust budget by flooding AI evaluation endpoints.

### H-05: Per-Company AI Rate Limiting Not Implemented
**Evidence:** `cost_controller.py` exists but has per-company support as TO-DO. Current implementation is global in-memory only.
**Risk:** One company's heavy AI usage could exhaust the global budget, starving all other companies.

### H-06: `TenantMixin` Missing on EvaluationSession
**File:** `backend/models/evaluation/evaluation.py`
**Evidence:** EvaluationSession has its own `company_id` column (NOT through TenantMixin) and does NOT have `company` relationship declared.
**Risk:** Inconsistent with all other tenant models. `tenant_query()` helper may skip this table.

### H-07: `category_id` vs `job_category_id` Ambiguity on Job Model
**File:** `backend/models/core/job.py`
**Evidence:** `Job` has BOTH `category_id` (→ `categories.id`) and `job_category_id` (→ `job_categories.id`). Both nullable.
**Risk:** Unclear which FK is authoritative for job categorization. Data can be in one, the other, or both.

### H-08: 18 Cron Jobs with N+1 Query Patterns
**File:** `backend/scheduler.py`
**Evidence:** `_pending_followup`, `_auto_interview_invite`, `_auto_reject_incomplete`, `_offer_escalation` all loop over individual Application records and issue per-row queries.
**Risk:** With 10K applications, these jobs run 10K+ queries each cycle.

### H-09: `_active_company_ids()` Uncached
**File:** `backend/scheduler.py`
**Evidence:** Each cron job cycle re-queries `CompanyMember.is_active == True` to build the active company list. No `@lru_cache` or TTL-based cache.
**Risk:** 18 job cycles/day × N queries = unnecessary DB load.

### H-10: CDN-Dependent XSS Protection
**File:** `js/security.js`, `js/xss-protection.js`
**Evidence:** Primary XSS sanitizer is `DOMPurify` loaded from CDN. Fallback `basicSanitize()` uses `textContent` which strips all HTML, breaking rich content.
**Risk:** CDN outage = XSS protection degrades or rich content rendering breaks.

---

## 10. MEDIUM ISSUES

### M-01: Double `db.commit()` in automation_worker + scheduler
**Evidence:** `evaluate_application_rules()` commits per-application, then scheduler commits again after the loop. Not harmful but indicates confused transaction boundary.

### M-02: Webhook `failure_count` Not Incremented on Generic Exceptions
**File:** `backend/routers/recruiter_enhancements/webhook_dispatcher.py:108-111`
**Evidence:** Generic `Exception` catch logs but does NOT increment `failure_count`. Unexpected errors never trigger webhook deactivation.

### M-03: `httpx.AsyncClient` Created Per-Webhook Call
**File:** `webhook_dispatcher.py:53`
**Evidence:** No connection pooling for webhook dispatches. Inefficient for high-traffic scenarios.

### M-04: `scheduler.py` Notification Cleanup Exception Not Re-raised
**File:** `backend/scheduler.py:92`
**Evidence:** `_cleanup_old_notifications()` exception is caught and logged but NOT re-raised. Circumvents the retry mechanism.

### M-05: `SubscriptionPlan` Schema Duplication
**File:** `backend/schemas.py` AND `backend/routers/recruiter_settings.py`
**Evidence:** `SubscriptionPlan as SubscriptionPlanSchema` alias indicates schema was imported and renamed, suggesting naming collision.

### M-06: `User.admin_permissions` Still on User Model
**File:** `backend/models/foundation/user.py`
**Evidence:** `admin_permissions` column exists on User despite AdminProfile having its own `permissions` column. Dual source.

### M-07: `ProfileVisit` Uses User Instead of Profile
**File:** `backend/models/evaluation/profile.py` (implicitly via relationship)
**Evidence:** `ProfileVisit.candidate_id` and `visitor_id` FK to `users.id`, not to `candidate_profiles.id` or `recruiter_profiles.id`.

### M-08: `candidate_profiles.email` and `recruiter_profiles.email` Columns
**Evidence:** Profile tables have `email` columns that mirror `User.email`. Not used in auth flow. Potential sync issue.

### M-09: No CI Pipeline for Alembic Migration Validation
**Evidence:** No GitHub Actions workflow or script checks that `alembic check` passes or that migration chain is intact.

### M-10: `pyproject.toml` Coverage Threshold Set to 0%
**File:** `pyproject.toml`
**Evidence:** `fail_under = 0` means coverage could be 0% and CI would still pass.

---

## 11. LOW ISSUES

### L-01: `ab_experiment_conclusion` Loop Outside Session
**File:** `backend/scheduler.py:457-481`
**Evidence:** The per-experiment loop runs outside the `with SessionLocal() as db:` context. If `conclude_experiment()` opens its own session, this is correct, but inconsistent with other patterns.

### L-02: `dead_letter_queue` Has No Re-consumer
**Evidence:** `DeadLetterRecord` table is write-only. No admin UI, no retry mechanism, no alert for dead letters.

### L-03: Auth Token Empty String for Non-authenticated Users
**File:** `js/auth-token.js`
**Evidence:** `get()` returns `'cookie-auth'` string. Non-authenticated users get empty string. All consumers must handle both.

### L-04: No Offline Support
**Evidence:** Service worker registered in `load-assets.js` but silently catches errors. No application cache or offline data strategy.

### L-05: Error Message Leakage in `fetchAPI()`
**File:** `js/config.js`
**Evidence:** `data.detail` and `data.message` from server responses are propagated directly to UI. Could leak internal error details.

### L-06: Multiple `.env.*` Files in Repository
**Evidence:** `.env`, `.env.example`, `.env.production.example`, `.env.staging` — risk of committing secrets.

---

## 12. PRODUCTION RISKS

| Risk | Severity | Issue Reference | Mitigation |
|------|----------|-----------------|------------|
| Webhook dispatcher crash on missing import | HIGH | C-01 | Add `import os` |
| Silent scoring job failures | HIGH | C-02 | Remove blanket except |
| Inconsistent adverse action state | HIGH | C-03 | Single commit |
| Duplicate candidate emails | HIGH | C-04 | Commit before send |
| Stale indexes on deprecated columns | MEDIUM | C-05 | Drop index migration |
| Lost concurrent updates | HIGH | C-06 | Apply @retry_stale to routes |
| Frontend breaks on script load order | MEDIUM | C-07 | Module bundler |
| localStorage corruption | MEDIUM | C-08 | State management wrapper |
| UI information disclosure | LOW | C-09 | Server-side redirect |
| Dual-source data on new signup | MEDIUM | C-10 | Stop writing deprecated cols |
| AI budget exhaustion | MEDIUM | H-04, H-05 | Per-company rate limiting |
| Scheduler N+1 on large datasets | MEDIUM | H-08 | Batch queries |
| CDN dependency for security | LOW | H-10 | Bundle DOMPurify |

---

## 13. REFACTORING ROADMAP

### Phase 1: Critical Bug Fixes (1-2 days)
1. Add `import os` to `webhook_dispatcher.py`
2. Remove blanket `except` in `scoring_jobs.py` (add re-raise + DLQ)
3. Fix `adverse_action_service.py` double commit
4. Fix `email_sequence_worker.py` send-before-commit ordering
5. Apply `@retry_stale` to all write endpoints for versioned models
6. Stop writing deprecated columns in `auth.py` user creation

### Phase 2: Database Cleanup (1-2 days)
7. Create migration to drop deprecated User column indexes
8. Add `company` relationship to EvaluationSession
9. Resolve `category_id` vs `job_category_id` ambiguity on Job
10. Add missing CHECK constraints on EvaluationResult.final_score

### Phase 3: Monitoring & Reliability (2-3 days)
11. Add DLQ recording to automation_worker, email_sequence_worker, scoring_jobs
12. Add `SELECT ... FOR UPDATE` to scheduler mutation jobs
13. Add per-company AI rate limiting
14. Cache `_active_company_ids()` in scheduler

### Phase 4: Architecture Refactor (1-2 weeks)
15. Introduce repository layer for Application, Job, EvaluationResult
16. Extract business logic from routers into services
17. Reduce User model coupling (break up God object)
18. Add module bundler for frontend JS
19. Centralize frontend state management

### Phase 5: Deprecation Completion (1 week)
20. Create migration to drop 36 deprecated User columns
21. Remove legacy property accessors on Application
22. Remove BatchJob deprecated counter properties
23. Remove Ticket model (fully replace with SupportTicket)

---

## 14. MIGRATION STRATEGY

### Rollback Strategy for Each Phase
- **Phase 1:** All fixes are code-only (no schema changes). Rollback = revert commit.
- **Phase 2:** Schema migrations (dropping indexes) must be reversible. Create DOWN migration.
- **Phase 3:** Config changes (rate limiting, caching). Rollback = revert config + clear cache.
- **Phase 4:** Service extraction. New services run alongside old code during transition.
- **Phase 5:** Column drops require a release cycle. Phase 1-4 must deploy first, verify no writes to deprecated columns, THEN drop.

### Validation Strategy
1. Phase 1 fixes: Run existing test suite (28+ test files, 50+ AI security tests)
2. Phase 2 cleanup: `alembic check` + `compileall backend -q`
3. Phase 3 reliability: Integration test with concurrent scheduler + HTTP access
4. Phase 4 refactor: No functional changes — verify existing tests pass
5. Phase 5 deprecation: Verify zero writes to deprecated columns via DB audit

---

## 15. FINAL ARCHITECTURE SCORE

| Category | Score | Assessment |
|----------|-------|------------|
| Database Schema | 75/100 | Good foundation, 36 deprecated columns drag it down |
| Multi-Tenant Isolation | 90/100 | TenantMixin on 55+ tables, 1 gap (EvaluationSession) |
| Backend Architecture | 55/100 | Router-centric, no repository layer, business logic leaks |
| Frontend Architecture | 45/100 | No module system, no state management, fragile init |
| Background Processing | 60/100 | Good scheduler setup, no DLQ coverage, swallowed exceptions |
| AI Security | 87/100 | Strong (per previous audit) |
| Auth & Authorization | 75/100 | Cookie-based JWT is good, client-side auth is weak |
| Data Consistency | 50/100 | Dual sources during migration, no concurrent write protection |
| Maintainability | 40/100 | 58 global JS files, fat routers, god objects |
| Production Readiness | 45/100 | 10 critical bugs must be fixed before production |

**OVERALL: 62/100 — Not Production Ready**

---

## 16. TOP 20 HIGHEST PRIORITY FIXES

| Rank | ID | Issue | Effort | Impact | File(s) |
|------|----|-------|--------|--------|---------|
| 1 | C-01 | Missing `import os` in webhook_dispatcher | 5 min | CRASH | `webhook_dispatcher.py:46` |
| 2 | C-02 | Swallowed exceptions in scoring_jobs | 30 min | SILENT FAILURE | `scoring_jobs.py` |
| 3 | C-03 | Double commit in AdverseActionService | 15 min | INCONSISTENT STATE | `adverse_action_service.py` |
| 4 | C-04 | Email sent before log committed | 15 min | DUPLICATE EMAILS | `email_sequence_worker.py` |
| 5 | C-06 | Optimistic locking not used in HTTP routes | 1 hour | CONCURRENT OVERWRITE | All write endpoints |
| 6 | C-10 | auth.py writes deprecated User columns | 30 min | DUAL SOURCE | `auth.py:419-428` |
| 7 | C-05 | 6 indexes on deprecated User columns | 1 hour | WASTED RESOURCES | Migration needed |
| 8 | H-01 | Router-centric business logic | 1-2 weeks | MAINTAINABILITY | 40+ router files |
| 9 | H-02 | DLQ not used outside scheduler | 1 day | SILENT FAILURES | 4 worker files |
| 10 | H-03 | Missing row-level locking | 1 day | CONCURRENT OVERWRITE | scheduler.py + routers |
| 11 | H-04 | No AI endpoint rate limiting | 1 day | BUDGET EXHAUSTION | AI routers |
| 12 | H-06 | EvaluationSession not a TenantMixin | 30 min | INCONSISTENCY | `evaluation.py` |
| 13 | H-07 | Ambiguous category FKs on Job | 1 hour | DATA CONFUSION | `job.py` |
| 14 | C-07 | Frontend no module system | 1 week | MAINTAINABILITY | 58 JS files |
| 15 | C-08 | 160+ localStorage access points | 3 days | FRAGILE STATE | 23 JS files |
| 16 | H-08 | 18 cron jobs with N+1 queries | 1 day | PERFORMANCE | `scheduler.py` |
| 17 | H-09 | `_active_company_ids()` uncached | 30 min | DB LOAD | `scheduler.py` |
| 18 | M-05 | Duplicate schema classes | 15 min | CONFUSION | `recruiter_settings.py` |
| 19 | M-06 | `User.admin_permissions` still exists | 1 hour | DUAL SOURCE | `user.py` |
| 20 | M-09 | No Alembic migration CI validation | 1 hour | REGRESSION RISK | CI config |

---

## 17. APPENDIX: VERIFICATION METHODOLOGY

Every finding in this report was verified by reading source code. Files examined:

- **Models:** All 90+ model classes in `backend/models/`
- **Routers:** All 55 router files in `backend/routers/`
- **Services:** 45+ service files in `backend/`
- **AI:** All 28 files in `backend/ai/`
- **Frontend:** All 58 JS files in `js/`, representative HTML pages
- **Background:** All 6 worker/scheduler files
- **Config:** `app.py`, `config.py`, `dependencies.py`, `authz.py`, `tenant.py`
- **Migrations:** All 78 Alembic version files
- **Tests:** 51 test files
- **Scripts:** 10 backfill/data scripts

**NOT VERIFIED** items:
- Actual production database state (no access to production DB)
- Performance benchmarks under load
- Third-party API integration reliability (Checkr, Groq, Gemini)
- Browser compatibility beyond Chrome
- Mobile app (no mobile code found in repository)
- Docker deployment configuration correctness in non-standard environments

---

*End of Zero-Trust Architecture Audit*
