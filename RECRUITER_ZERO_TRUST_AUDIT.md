# CANDWAY RECRUITER PLATFORM — ZERO-TRUST AUDIT REPORT

**Date:** 2026-07-03  
**Auditor:** Principal Software Architect / Security Engineer  
**Scope:** Complete zero-trust audit of ALL recruiter-facing features  
**Files Audited:** ~200+ source files (~50,000+ lines across backend, frontend, models, routers, services, AI, config, deployment)  
**Methodology:** Source code only — no documentation, comments, or labels trusted.

---

# EXECUTIVE SUMMARY

The Candway Recruiter Platform has strong **security foundations** (PII masking, CSRF protection, tenant isolation framework, encryption at rest) and well-designed **AI safety guardrails** (prompt injection defense, output validation, cost control). The domain model covers the full recruiting lifecycle comprehensively.

**However**, the platform is **NOT production-ready** in its current state. Critical bugs in the scheduler (all 18 cron jobs silently execute the wrong function), unresolved cascade gaps (application deletion will fail in production), critical IDOR vulnerabilities (unsubscribe endpoint), and systemic observability deficits (no JSON logging, no distributed tracing, fragmented metrics) represent **production launch blockers**.

**Key finding:** The scheduler lambda closure bug (`scheduler.py:626`) renders ALL background job functionality non-functional — interview reminders, offer expiration alerts, data cleanup, AI drift detection, email sequences, and scheduled reports never execute their intended logic.

**Overall Score: 58/100** (below production threshold of 75/100)

---

# SCORE CARD

| Dimension | Score | Status |
|-----------|:-----:|--------|
| **Production Readiness** | **43/100** | ❌ NOT READY |
| **Architecture** | **65/100** | ⚠️ Needs refactoring |
| **Security** | **72/100** | ⚠️ Gaps need remediation |
| **Performance** | **55/100** | ❌ N+1, no caching |
| **UX** | **60/100** | ⚠️ Inconsistent, race conditions |
| **Scalability** | **30/100** | ❌ WebSocket in-memory, scheduler in-process |
| **Maintainability** | **45/100** | ❌ 2,900-line page, duplicated logic |
| **Data Integrity** | **48/100** | ❌ Cascade gaps, orphan records |
| **AI Security** | **87/100** | ✅ Production ready |
| **Overall** | **58/100** | ❌ NOT PRODUCTION READY |

---

# TOP PRODUCTION LAUNCH BLOCKERS

### BLOCKER-1: Scheduler Lambda Closure Bug — All Jobs Execute Wrong Function
**Severity:** CRITICAL  
**File:** `backend/scheduler.py:621-628`  
**Root Cause:** Python lambda captures `coro` by reference, not value. After the loop, `coro` holds the last value (`_scheduled_reports`). All 18 cron jobs run `_scheduled_reports` instead of their intended function.  
**Evidence:** `args=[lambda: coro(), job_id]` — `coro` is not captured as a default argument.  
**Impact:** Interview reminders NEVER send. Offer expirations NEVER fire. Data cleanup NEVER runs. AI drift detection NEVER executes. Email sequences NEVER process.  
**Fix:** Change to `args=[lambda c=coro: c(), job_id]`

### BLOCKER-2: Application Deletion Will Fail in Production
**Severity:** CRITICAL  
**File:** `backend/models/ats/application.py:180-183` (and 7 child models)  
**Root Cause:** 7 child tables (`ExtractedSkill`, `EmailSequenceLog`, `ReEngagementCandidate`, `CalibrationSample`, `AIAuditLog`, `InterviewTurn` via application_id path, `Qualification`) have FK to `applications.id` with NO cascade rule and NO ORM-level cascade.  
**Impact:** Attempting to delete an Application will raise a foreign key constraint violation at the database level.  
**Fix:** Add `cascade="all, delete-orphan"` relationships for all 7 child models, or add `ondelete='CASCADE'` to FKs.

### BLOCKER-3: Unsubscribe IDOR — Anyone Can Unsubscribe Any Candidate
**Severity:** CRITICAL  
**File:** `backend/routers/unsubscribe.py:17-41`  
**Root Cause:** `GET /unsubscribe/{app_id}` uses raw integer `app_id` with zero authentication, zero CSRF protection.  
**Impact:** Anyone who iterates app_id values (1, 2, 3, ...) can unsubscribe any application without authorization.  
**Fix:** Replace with HMAC-signed tokens (as already implemented in `email_sequence_worker.py:14-22`).

### BLOCKER-4: `.env.staging` Contains Committed Live Secrets
**Severity:** CRITICAL  
**File:** `.env.staging`  
**Root Cause:** `.env.staging` contains live `SECRET_KEY`, `CANDWAY_FIELD_ENCRYPTION_KEY`, `DATABASE_URL` with password, `GROQ_API_KEY`, `MYSQL_ROOT_PASSWORD`, `REDIS_PASSWORD` — all committed to git.  
**Impact:** Anyone with repo access has production credentials. Secrets must be rotated immediately.  
**Fix:** Rotate ALL secrets. Add `.env.staging` to `.gitignore`. Use CI secret injection.

### BLOCKER-5: Scheduler Runs In-Process with Web Workers
**Severity:** CRITICAL  
**File:** `backend/scheduler.py`, `Procfile`  
**Root Cause:** `AsyncIOScheduler` runs inside the same gunicorn worker process as HTTP requests.  
**Impact:** Long-running cron jobs block HTTP requests. OOM in scheduler kills web process. No worker separation in `Procfile`.  
**Fix:** Extract scheduler to separate process with a `Procfile worker` entry.

### BLOCKER-6: No JSON Logging / No Distributed Tracing
**Severity:** CRITICAL  
**File:** `backend/logger.py`  
**Root Cause:** Logger uses `Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")` — plain text, no structured fields, no request_id propagation.  
**Impact:** Cannot grep logs by request ID. Log aggregation tools (ELK/Loki/CloudWatch) cannot parse structured fields. Debugging production issues requires manual correlation.  
**Fix:** Replace with JSON formatter. Include `request_id` in every log line.

---

# ALL FINDINGS BY SEVERITY

## CRITICAL (8 findings)

| ID | Finding | File | Impact |
|----|---------|------|--------|
| C-01 | Scheduler lambda closure — all 18 jobs run `_scheduled_reports` | `scheduler.py:624` | All background jobs non-functional |
| C-02 | Application deletion cascade gap — 7 child tables block delete | `ats/application.py:180` | Operational failure on app delete |
| C-03 | Unsubscribe IDOR — no auth on `GET /unsubscribe/{app_id}` | `routers/unsubscribe.py:17` | Anyone can unsubscribe any candidate |
| C-04 | `.env.staging` committed with live secrets | `.env.staging` | Full credential leak |
| C-05 | Scheduler runs in-process with web workers | `scheduler.py`, `Procfile` | HTTP blocked by background jobs |
| C-06 | No JSON logging / no distributed tracing | `logger.py` | Production debugging impossible |
| C-07 | `Job.company` shadows `TenantMixin.company` relationship | `core/job.py:21` | Silent type error — `job.company` returns string not Company |
| C-08 | EEOConsent has NO tenant isolation (PII: gender, race, disability) | `ats/application.py:342` | Cross-tenant PII leak |

## HIGH (18 findings)

| ID | Finding | File | Impact |
|----|---------|------|--------|
| H-01 | `report_builder.py` has NO company_id filtering | `report_builder.py:108,382` | Cross-company data access via recruiter_id |
| H-02 | Email templates have NO HTML escaping — XSS via candidate name | `notifications.py`, `email_service.py` | Script execution in email clients |
| H-03 | Google OAuth tokens stored in plaintext | `routers/calendar.py:256,384` | Token theft = calendar/email access |
| H-04 | No notification preference system (GDPR) | N/A | Regulatory compliance gap |
| H-05 | `check_offer_expirations()` is a no-op stub | `notifications.py:312` | Offer expirations never alerted |
| H-06 | No `max_instances=1` on any scheduled job | `scheduler.py:621` | Duplicate job execution in multi-worker |
| H-07 | No dead letter queue for failed background jobs | All workers | Failed jobs lost permanently |
| H-08 | Prometheus metrics fragmented — HTTP metrics lost | `metrics.py`, `monitoring.py` | Missing request rate/error/duration |
| H-09 | Long-running DB transactions during email sends in scheduler | `scheduler.py` | DB connections held for minutes |
| H-10 | Rabbit hole: WebSocket in-memory state — no Redis backplane | `realtime.py` | Horizontal scaling breaks WS |
| H-11 | Rate limiting defaults to in-memory with multi-worker warning | `rate_limit_middleware.py` | 60 req/min * N workers bypass |
| H-12 | Race condition: Email sequence worker — duplicate emails | `email_sequence_worker.py:70` | Candidates get duplicate emails |
| H-13 | N+1 in EEO coverage detail — 1 query per job | `eeo_analytics_service.py:528-543` | 200+ queries for 100 jobs |
| H-14 | Analytics weekly/daily trends use N queries instead of GROUP BY | `analytics_service.py:186-206` | 11 queries where 2 suffice |
| H-15 | Frontend localStorage role cache never refreshed | `components.js:1296-1301` | Stale auth state in UI |
| H-16 | No SRI hashes on CDN resources (supply chain attack vector) | All pages | Compromised CDN = arbitrary JS execution |
| H-17 | WebSocket reconnection uses fixed 3s delay, no exponential backoff | `js/notifications.js:394-416` | Connection flood during incidents |
| H-18 | Graceful shutdown is incomplete — no drain, no cleanup | `startup.py:shutdown_event()` | Transaction corruption on restart |

## MEDIUM (31 findings)

| ID | Finding | File | Impact |
|----|---------|------|--------|
| M-01 | Bare `except:` handlers (18 instances across 12 files) | Multiple | Swallows KeyboardInterrupt/SystemExit |
| M-02 | 5 `not Column.bool` bugs (non-auth files) | Multiple | Incorrect SQLAlchemy comparisons |
| M-03 | EvaluateSession has inline company_id but NO TenantMixin | `evaluation/evaluation.py:45` | Breaks `tenant_query()` helper |
| M-04 | 4 models (CvDocument, ExtractedSkill, CandidateProfile, AdminProfile) not tenant-scoped | Multiple | Cross-tenant data leak |
| M-05 | 8 LMS child models not tenant-scoped | `core/lms.py` | Tenant isolation bypass |
| M-06 | No unique constraint on `Job(title, company_id)` | `core/job.py` | Duplicate job postings |
| M-07 | InterviewTurn XOR cascade mismatch with application_id path | `evaluation/ai.py:44-68` | Deletion deadlock |
| M-08 | `Rubric.is_active` is Integer, not Boolean | `evaluation/scoring.py:42` | Non-boolean values possible |
| M-09 | Multiple duplicate email risks | `scheduler.py`, `notifications.py` | Candidates get duplicates |
| M-10 | No email queue — SMTP failure silently drops emails | `email_service.py:157` | Critical emails lost |
| M-11 | No per-company/per-user email rate limiting | `email_service.py` | CAN-SPAM compliance risk |
| M-12 | Missing notification emails for 7+ events | Multiple routers | Candidates uninformed |
| M-13 | WebSocket connection model mixes user/app IDs | `app.py:380`, `realtime.py` | Message routing collisions |
| M-14 | Missing real-time events for team actions | Multiple routers | Must refresh page for updates |
| M-15 | No timezone awareness in interview reminders | `notifications.py:260` | Reminders fire at wrong time |
| M-16 | No TTL/cleanup for stored notifications | `models/foundation/user.py:275` | Unbounded table growth |
| M-17 | `mark_all_notifications_read` filter is a no-op (`not` operator) | `routers/notifications.py:142` | All notifications marked read |
| M-18 | Google Calendar integration is non-functional | `routers/calendar.py:252-256` | Auth code never exchanged for token |
| M-19 | Race condition in `ScoringService.compute_final_score()` | `scoring_service.py:126-182` | Silently discards unrelated changes |
| M-20 | Race condition in `AdverseActionService.check_dispute_period()` | `adverse_action_service.py:162-170` | Duplicate final adverse notices |
| M-21 | Race condition in webhook failure counter | `webhook_dispatcher.py:73-95` | Delayed webhook deactivation |
| M-22 | In-memory aggregation in ReportBuilder (up to 10k rows) | `report_builder.py:120` | Memory bottleneck at scale |
| M-23 | Frontend: Infinite scroll never triggers for Kanban view | `js/recruiter-pipeline.js:144` | Users cannot see page 2+ |
| M-24 | Frontend: Per-page selector has no onChange handler | `pages/recruiter/candidates.html:390-392` | Cannot change page size |
| M-25 | Frontend: Optimistic updates without rollback on failure | `js/recruiter-enhancements.js:40-81` | Cards disappear on API failure |
| M-26 | Frontend: DOMPurify loaded with `defer` after dependent script | All pages | XSS fallback on slow connections |
| M-27 | `Ticket` vs `SupportTicket` — duplicated domain concept | `foundation/system.py:7-51` | Data fragmentation |
| M-28 | `ABExperiment` vs `ABTestExperiment` — duplicated domain concept | `evaluation/ai.py:175-241` | Confusion about AB testing |
| M-29 | `CandidateProfile` overlaps with `Candidate` model | `evaluation/profile.py:12` | Split candidate data |
| M-30 | 10+ deprecated columns remain on `Application` | `ats/application.py:46-65` | Confusion about source of truth |
| M-31 | Migration chain has broken `down_revision` (m22) | `alembic/versions/` | Cannot rollback migrations |

## LOW (24 findings)

| ID | Finding | File |
|----|---------|------|
| L-01 | Text-as-JSON in 3 models (`Comment.mentions`, `PipelineAutomationRule.*_json`, `DailyPlatformReport.report_json`) | Multiple |
| L-02 | `Opportunity.link` is String(255) — may truncate URLs | `foundation/cms.py:119` |
| L-03 | `PageSection` missing unique constraint on `(page_slug, section_slug)` | `foundation/system.py:105-106` |
| L-04 | `AuditLog.company_id` nullable | `foundation/user.py:209` |
| L-05 | `ActivityLog.application_id` nullable | `ats/pipeline.py:151` |
| L-06 | No cascade on `OfferTemplate.recruiter_id` FK | `ats/offer.py:17` |
| L-07 | `TranslationCache` has no `updated_at` | `foundation/system.py:79-97` |
| L-08 | Interview reminders per-item commit creates partial state | `notifications.py:284-286` |
| L-09 | Schedule drift on restart — missed runs not caught up | `scheduler.py` |
| L-10 | Missing indexes on scheduler query patterns | `scheduler.py` |
| L-11 | `broadcast()` doesn't clean dead connections | `realtime.py:122` |
| L-12 | Dual heartbeat mechanism (redundant) | `realtime.py` + `app.py` |
| L-13 | No retry on bot delivery failure (Slack/Teams) | `bot_notifications.py` |
| L-14 | Bot OAuth tokens stored in plaintext | `models/ats/campaign.py:52-53` |
| L-15 | Frontend: No character count on message input | `pages/recruiter/messages.html:157` |
| L-16 | Frontend: Bulk "Delete Selected" — no confirmation dialog | `pipeline.html:880` |
| L-17 | Frontend: JWT payload parsed from localStorage without signature verification | `components.js:48-61` |
| L-18 | Frontend: Inline event handlers as XSS sinks | All pages |
| L-19 | Frontend: Pipeline search input not debounced — API call per keystroke | `js/recruiter-pipeline.js:136-140` |
| L-20 | Frontend: Search debounce shared across multiple inputs | `dashboard.html:948` |
| L-21 | Frontend: Pagination controls reset search filters | `pages/recruiter/candidates.html:458-478` |
| L-22 | Frontend: Cross-tab BroadcastChannel fragile — no reconnection | `js/cross-page-sync.js:13-26` |
| L-23 | `ProfileVisit` vs `ActivityLog` — overlapping tracking | `foundation/user.py:315` vs `ats/pipeline.py:143` |
| L-24 | `DriftSnapshot` is standalone — no FK to any entity | `evaluation/ai.py:154-170` |

---

# QUICK WINS (Can fix in <1 hour each)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | Fix scheduler lambda: `lambda c=coro: c()` | 1 line | Restores ALL background jobs |
| 2 | Add `onchange` handler to per-page selector | 3 lines | Unlocks page size customization |
| 3 | Fix `mark_all_read`: `not` → `~` or `is_read == False` | 1 line | Fixes notification marking |
| 4 | Add `html.escape()` to user-supplied values in email templates | 5 lines | Prevents email XSS |
| 5 | Rotate `.env.staging` secrets + add to `.gitignore` | 5 min | Stops credential leak |
| 6 | Add `if not paginationMeta.has_next` guard on infinite scroll | 2 lines | Prevents duplicate page loads |
| 7 | Show Load More button when infinite scroll fails | 1 line | Fixes pipeline page 2+ |
| 8 | Add confirmation dialog to bulk delete | 5 lines | Prevents accidental deletion |
| 9 | Add `SRI` integrity hashes to CDN scripts | 10 min | Supply chain attack prevention |
| 10 | Add `max_instances=1` to all APScheduler jobs | 1 line | Prevents duplicate execution |

---

# LONG-TERM REFACTORING PLAN

## Phase 1: Launch Blockers (Week 1)
1. Fix scheduler lambda bug
2. Fix cascade gaps on Application models
3. Replace unsubscribe IDOR with HMAC tokens
4. Rotate all committed secrets
5. Extract scheduler to separate process

## Phase 2: Data Integrity (Week 2)
1. Add TenantMixin to EEOConsent, CvDocument, ExtractedSkill, CandidateProfile, AdminProfile
2. Rename `Job.company` to `Job.company_name`
3. Add missing unique constraints
4. Consolidate `Ticket`/`SupportTicket`, `ABExperiment`/`ABTestExperiment`
5. Fix InterviewTurn cascade mismatch

## Phase 3: Observability (Week 2-3)
1. Replace logging with JSON formatter
2. Add request_id propagation to all log lines
3. Unify Prometheus metrics into single registry
4. Add `/readyz` and `/livez` endpoints
5. Add OpenTelemetry instrumentation

## Phase 4: Services Refactoring (Week 3-4)
1. Extract `_get_recruiter_job_ids()` shared helper
2. Replace N+1 analytics queries with SQL GROUP BY
3. Fix EEO service N+1 (coverage detail)
4. Add company_id filtering to `report_builder.py`
5. Add email queue with retry logic

## Phase 5: Frontend (Week 4-5)
1. Add loading skeletons to all pages
2. Fix localStorage role cache (add TTL, refresh on focus)
3. Add CSRF protection without overriding global `fetch`
4. Fix pipeline infinite scroll for Kanban
5. Add SRI hashes to all external scripts
6. Standardize error/empty states

## Phase 6: Resilience (Week 5-6)
1. Add dead letter queue for failed background jobs
2. Add circuit breakers for external services (Checkr, SMTP)
3. Implement exponential backoff in scheduler retries
4. Add graceful shutdown with connection draining
5. Implement WebSocket Redis backplane for horizontal scaling

## Phase 7: Notifications (Week 6-7)
1. Add `NotificationPreference` model
2. Add missing notification emails for 7+ events
3. Implement notification cleanup/TTL
4. Fix Google Calendar integration (token exchange)
5. Encrypt OAuth tokens at rest

## Phase 8: Production Hardening (Week 7-8)
1. Add DB statement timeout
2. Add connection leak detection
3. Add per-company AI rate limiting
4. Add Redis persistence for PII mapping/cost controller
5. Add per-company email rate limiting
6. Add session timeout to frontend cache

---

# TECHNICAL DEBT REPORT

## Architecture Debt
- **Monolithic candidate.html (2,903 lines):** Single file contains all candidate detail logic — AI chat, scoring, calendar, timeline, notes, rubrics. No component separation. Unmaintainable.
- **Duplicated query logic:** 9+ copies of "fetch jobs by recruiter" pattern. Missing abstraction layer.
- **Two Prometheus registries:** Metrics fragmented across global and custom registries. HTTP metrics collected but never exposed.
- **Two CSRF mechanisms:** `csrf.js` overrides `window.fetch` globally while `config.js::fetchAPI()` also adds CSRF headers.

## Data Debt
- **10+ deprecated columns** on `Application` table (migration debt)
- **3 Text-as-JSON columns** with no DB validation
- **17 legacy migration scripts** in `backend/migrations/` not referenced by Alembic
- **105 models** with inconsistent TenantMixin usage (8 models should have it but don't)

## Security Debt
- **18 bare `except:`** handlers across 12 files
- **5 `not Column.bool`** SQLAlchemy comparison bugs
- **Inline event handlers** on every page (XSS sinks)
- **JWT payload parsed client-side** without signature verification
- **CDN resources** loaded without SRI hashes

## Test Debt
- **624 tests total** but several DB-dependent tests timeout
- **No E2E tests** for recruiter workflows
- **No frontend tests** at all (zero)
- **No integration tests** for WebSocket/realtime
- **No performance tests** for analytics queries

---

# PRODUCTION READINESS VERDICT

## ❌ NOT PRODUCTION READY

The Candway Recruiter Platform has made excellent progress on AI security (87/100) and has a comprehensive domain model covering the full recruiting lifecycle. However, **6 critical production launch blockers**, **18 high-severity issues**, and systemic operational deficits (observability, resilience, scalability) make the platform unsafe for production deployment in its current state.

### Must-Fix Before Production
1. Scheduler lambda closure bug (all background jobs broken)
2. Application deletion cascade gaps (7 FK constraint failures)
3. Unsubscribe IDOR (anyone can unsubscribe any candidate)
4. `.env.staging` committed secrets (immediate rotation needed)
5. Scheduler in-process with web workers (blocks HTTP)
6. No JSON logging / no distributed tracing (production debuggability)

### Should-Fix Before Production
- Email XSS via unescaped candidate names
- ReportBuilder missing company_id filtering
- N+1 analytics queries (EEO, trends)
- WebSocket reconnection with exponential backoff
- CDN resources without SRI hashes

### Safe to Defer Post-Launch
- Redis backplane for WebSocket horizontal scaling
- Per-company AI rate limiting
- Notification preference system
- Google Calendar integration fix (currently non-functional anyway)
- Email queue with retry (critical but mitigated by synchronous fallback)

## Estimated Remediation Time: 4-6 weeks with 2 engineers

---

*End of Report — 81 findings across 8 audit dimensions*
