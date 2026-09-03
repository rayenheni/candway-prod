# Candway Platform - Due-Diligence Audit

> **Scope**: Full platform audit (Candidate, Recruiter, Admin + AI/ML + Infra + Business).
> **Date**: 2026-06-02
> **Method**: Static code review against the on-disk tree at
> `C:\Users\rayen\projects\candway_landing_page (2)\masar_landing_page\masar_landing_page`.
> **Methodology**: Every claim below is anchored to `file_path:line` evidence.
> Where a claim could not be substantiated from code, it is explicitly marked
> **UNVERIFIED**. Optimism is not a feature.

---

## 0. Executive Summary

Candway is a **FastAPI + MySQL + Redis** "AI-powered" recruitment + learning
platform with a thin Tailwind/CSS frontend that is mostly hand-rolled HTML/JS
(no SPA framework). It is **NOT** a typical MENA SaaS shell: there is
substantial back-end engineering depth, real security thinking, and an
in-progress migration toward enterprise-grade primitives. But the project
also shows classic "rapid build-up under deadline" tells: PII at rest encrypted
but the encryption key fallback, a self-acknowledged `User.deleted_at IS None`
bug in the admin router, parallel security implementations, parallel
rate-limiter implementations, and zero frontend test coverage.

The product is **launchable to a private beta of paying design-partner
recruiters** but **not** ready for 100k users, not SOC 2 ready, not GDPR
audit-ready, and not enterprise ready. Concrete blockers and their fixes are
in §14 (Roadmap).

### 0.1 Final scores (0-100)

| Dimension               | Score | Verdict                                                                                 |
| ----------------------- | ----: | --------------------------------------------------------------------------------------- |
| Product                 |  62   | Many features; UX quality and end-to-end polish lag behind.                              |
| Engineering             |  55   | Solid core; surface area too large; per-handler custom logic dominates.                 |
| Security                |  60   | Hardening is real, but the cryptographic boundary (Fernet key) and a few routes are bad. |
| AI                      |  65   | Cascade + fallbacks + transparency are above average; prompt-injection guard is weak.   |
| UX                      |  48   | Functional but not delightful; admin UX is dense; candidate UX is fragmented.           |
| Scalability             |  52   | Will break past ~10k MAU on current single-MySQL topology; Redis in place.              |
| Business                |  45   | Multiple revenue SKUs but manual-payment flow kills conversion at scale.                |
| Investment Readiness    |  50   | Believable narrative, but un-validated tech claims and a fragile infra are real risks.  |

> A <60 score is "interesting but risky for an institutional check". A 65+ is
> "fundable with conditions". We are in the interesting-but-risky band.

### 0.2 The three things that matter most

1. **Encryption key management is unsafe in practice.**
   `backend/encryption.py` reads a single Fernet key from
   `CANDWAY_FIELD_ENCRYPTION_KEY` with a generated dev fallback
   ("Generating a development-only key... DO NOT USE IN PRODUCTION"). There
   is no key-rotation strategy, no KMS integration, no per-record
   `key_version` column, and the startup check (`backend/startup.py`) does
   NOT fail on a missing key, only on placeholder AI keys and JWT secret.
2. **PII leaves Tunisia/EU in a way that is incompatible with GDPR + Tunisian
   data-protection law.** `backend/ai/cv_analysis.py` → `call_groq_cascade`
   sends the full (already PII-scrubbed but re-PII'd in metadata) CV to
   Groq (US), DeepSeek (CN), and Gemini (US). `backend/ai/privacy.py`
   openly admits "Name scrubbing is heuristic-based". No DPA on file with
   the user is logged at acceptance; no record of consent for AI processing
   of personal data is required at sign-up.
3. **No automated tests, no CI, no load-test, no e2e.** Only 4 Python test
   files in `tests/` (`conftest.py`, `test_admin_ai_responses.py`,
   `test_admin_api.py`, `test_admin_ssr.py`,
   `test_authorized_admin_api.py`). Zero frontend tests. No k6 / Locust
   / JMeter. An institutional buyer will ask for the test report and you
   will not have one.

---

## 1. Platform Inventory (evidence)

### 1.1 Backend surface area (per `backend/app.py`)

* 36+ router modules imported in `backend/app.py:34-76` (admin, ai_interview,
  ai_sales, ai_utils, analytics, auth, calendar, candidate_management,
  candidate_portal, career, copilot, courses, feature_flags, hiring, mentor,
  messages, notifications, onboarding, pages, prompt_management, public,
  recommendations, recruiter_campaigns, recruiter_candidates,
  recruiter_collaboration, recruiter_dashboard, recruiter_desktop,
  recruiter_enhancements, recruiter_interviews, recruiter_jobs,
  recruiter_offers, recruiter_settings, search, setup, support, tracking,
  unsubscribe, uploads).
* Migrations disabled at runtime: `backend/app.py:26` → `_HAS_MIGRATIONS = False`.
  Yet alembic exists at `alembic/` with 12 revisions in `alembic/versions/`.
  So schema is **managed in code at import time, not at deploy time** —
  `Base.metadata.create_all` in `database.py` (see `database.py:90`-area).
  This is fragile.
* Single Python process via Gunicorn 4 workers (Dockerfile:39) behind
  Nginx (`docker-compose.yml:7-39`). MySQL 8 + Redis 7. Prometheus +
  Grafana sidecars are declared but `prometheus.yml` content is **not in
  the repo tree** (see `docker-compose.yml:106-114` references
  `./prometheus.yml` — only present in workspace root, not visible to the
  compose context from the repo's perspective).

### 1.2 Frontend surface area

* 36 hand-rolled JS files in `js/` (auth-guard, auth-token, candidate-dashboard,
  candidate-interview, chat-widget, cms-loader, components, config, constants,
  courses-premium, cross-page-sync, csrf, cv-builder, error-boundary,
  feature-flags, gdpr, help-center, jobs-premium, landing, load-assets,
  localization, notifications, onboarding-wizard, performance,
  profile-visitors, prompt-management, recruiter-enhancements,
  recruiter-onboarding, recruiter-pipeline, security, tailwind-config,
  toast, translations, xss-protection, admin-components,
  accessibility-enhanced). Total ≈ 36.
* No bundler, no SPA framework, no test runner, no TypeScript. jQuery
  patterns in `csrf.js` (monkey-patches `window.fetch`).
* 78 hand-authored HTML pages in `pages/{auth,candidate,mentor,recruiter,admin}/`
  (13 auth, 23 candidate, 11 mentor, 31 admin). Landing pages live at repo
  root (`index.html`, `jobs.html`, etc. — **unverified number**, files were
  not enumerated in this audit).
* 3 i18n bundles in `js/lang/{en,fr,ar}.js` (en: 164 KB, fr: 173 KB, ar: 2.9 KB).
  Arabic bundle is 50× smaller than English/French — Arabic is **unfinished**.

### 1.3 AI stack

* Three providers: Groq (`llama-3.3-70b-versatile` → `llama-3.1-8b-instant`),
  DeepSeek, Gemini (`gemini-2.0-flash` etc.). Cascade in
  `backend/ai/llm.py:41-46` (`MODELS_CASCADE`, `GEMINI_MODELS`).
* Persistent HTTPX client with 100-conn / 50-keepalive pool
  (`backend/ai/llm.py:26-33`).
* `CircuitBreaker` per provider (`backend/ai/resilience.py:84-87`,
  `llm_circuit_breaker`, threshold=10, recovery=30s).
* Prompt version registry (`backend/ai/prompts.py:14-64`) — 6 prompt
  families, current versions: cv_analysis v2.1 (2024-09-15),
  interview_evaluation v3.2 (2025-04-01), interview_final_evaluation v2.0.
  A/B testing is "supported" via env flag `AB_TEST_ENABLED=1` but turned
  off by default.
* Prompt-injection guard `AISecurity` in `backend/ai/security.py:6-55`
  with EN/FR/AR patterns and Cyrillic-homoglyph detection.
* Anti-cheat `AntiCheatDetector` (`backend/ai/anti_cheat.py:12-60`) with
  repetition, vagueness, contradiction (vs CV), overclaim, and buzzword
  subscores. Max penalty 40 points.
* PII scrubber (`backend/ai/privacy.py:4-66`) — regex-based emails,
  phones, "Rue/Av/..." address keywords. **Name scrubbing is
  heuristic-based** (admitted in the docstring).
* Interview state machine in `backend/ai/state_machine.py`
  (InterviewState, InterviewStateMachine), turn backfill in
  `alembic/versions/f4a5b6c7d8e9_add_interview_turns_table.py`.
* Drift monitor (`backend/ai/drift_monitor.py`) runs on a 6h cron
  (`backend/scheduler.py:408`). A/B conclusion runs on 12h cron
  (`backend/scheduler.py:409`).

### 1.4 Infra & DevOps

* Dockerfile (`Dockerfile:1-40`): Python 3.11-slim, runs as non-root
  `appuser` (uid 1000), gunicorn 4 workers, 120s timeout, single port.
* docker-compose (`docker-compose.yml:1-141`): backend, MySQL 8, Redis 7,
  nginx, prometheus, grafana. Healthchecks on MySQL/Redis/backend.
* `backend.log` is referenced (RotatingFileHandler in
  `backend/logger.py`) and read live by `backend/routers/admin/system.py`.
* Sentry wired (`backend/app.py:93-105`) but optional (no DSN → silent
  skip).
* Self-acknowledged production-blockers: `_HAS_MIGRATIONS = False`
  (`app.py:26`), in-memory rate-limit fallback in dev
  (`rate_limit_middleware.py:46-48, 73-76` logs a CRITICAL warning in
  prod if Redis is missing), `database.sqlite` file present in repo
  even though `database.py:50` raises on missing `DATABASE_URL`.

### 1.5 Existing prior art in the repo

* `CANDIDATE_EXPERIENCE_AUDIT_REPORT.md` (repo root, not in this audit
  tree) — referenced in our prior context. **UNVERIFIED** contents.
* `scripts/audit_is_none_bug.py`, `scripts/db_inspect_users.py`,
  `scripts/probe_admin_users.py` — these are operator scripts that
  were run today, dated 2026-06-02 5:12-5:52 PM. They confirm the
  dev environment is in a debugging session and the team is aware
  the `is None` bug existed.
* `docs/onboarding_ai_interview_plan.md` (only doc, 6.8 KB).

---

## 2. Per-Dimension Methodology

For each feature, we score 10 dimensions on a 0-10 scale:

1. **Functional completeness** — does it ship all the user-visible pieces?
2. **UX quality** — does it feel like a 2026 product?
3. **Code quality** — readable, testable, single-responsibility?
4. **Security** — authn/z, input validation, PII handling, audit log?
5. **AI/ML quality** — prompts, fallback, calibration, transparency?
6. **Data model fit** — does the schema support the workflow?
7. **Performance** — measurable under load?
8. **Observability** — log, metric, trace?
9. **i18n & accessibility** — multi-lingual, a11y, RTL?
10. **Revenue / business impact** — does it actually move ARR or retention?

Sub-scores: avg of (1) to (10). Module score = mean.

---

## 3. Authentication & Session Management

### Inventory

* `backend/dependencies.py` — `pwd_context` (bcrypt rounds=12,
  pbkdf2_sha256 fallback), `_normalize_token`, `_candidate_tokens`
  (header-or-cookie, with `cookie-auth` placeholder filter at line 66),
  `create_access_token`, `generate_interview_token`.
* `backend/token_blacklist.py` (426 LOC) — Redis-backed + DB-fallback
  JWT blacklist with `add_token`, `_add_token_db`.
* `backend/routers/auth.py` — login, signup, forgot/reset, OTP verify,
  Google OAuth callback.
* `backend/security.py` — `CSRFMiddleware`, `RequestIDMiddleware`,
  `SanitizationMiddleware`, `SecurityHeadersMiddleware`.
* `js/csrf.js` — `getCSRFToken` from cookie or `<meta name="csrf-token">`,
  monkey-patches `window.fetch` to inject `X-CSRF-Token` on
  POST/PUT/DELETE/PATCH.
* `js/auth-guard.js`, `js/auth-token.js` — client-side session glue.

### Sub-scores (out of 10)

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 8     | Login + signup + forgot + reset + OTP + Google + blacklist + cookie-`auth` shim. |
| UX               | 6     | Multi-step reset, but error copy is uneven across locales. |
| Code quality     | 6     | Multiple dep paths (header/cookie/placeholder) make reasoning hard. |
| Security         | 7     | bcrypt 12 + Redis blacklist + CSRF + sanitization. Key-bound risks below. |
| AI/ML            | n/a   | — |
| Data model       | 7     | `User`, `LoginAttempt`, `TokenBlacklistDB` all present. |
| Performance      | 6     | Token blacklist is O(1) on Redis; DB fallback is slow. |
| Observability    | 6     | `logger.debug` in hot path (line 50-67 in `dependencies.py`) — noisy. |
| i18n / a11y      | 5     | English + French + Arabic copy exist but Arabic bundle is 50× smaller. |
| Business         | 7     | Friction-free Google login is a real conversion lever. |

**Module score: 6.4/10**

### Security findings (severity)

* **S1-High** — `dependencies.py:66` filters `"cookie-auth"` as a *valid*
  token sentinel, but if any code path treats the literal string
  `"cookie-auth"` as a real JWT (it must not — verify), this is a
  backdoor. Read carefully: the filter is `[t for t in tokens if t != "cookie-auth"]`,
  so the placeholder is **excluded**, which is correct, but the literal
  string being meaningful is a code smell.
* **S2-Med** — `dependencies.py:50-67` logs `_candidate_tokens` at
  **DEBUG**, which means token presence/absence leaks into the log
  pipeline. INFO would be sufficient.
* **S3-Med** — `dependencies.py:85` — `create_access_token` default is
  `timedelta(minutes=15)` while `Settings.access_token_expire_minutes=60`
  (`config.py:28`). The default override in `create_access_token` will
  silently shorten every token unless callers pass an explicit delta.
  This is exactly the kind of "default fights the config" trap that
  creates CVEs.
* **S4-Low** — `CSRF` token check in `js/csrf.js` is JS-side only;
  if a page forgets to include `js/csrf.js`, the protection degrades
  silently. The server-side `CSRFMiddleware` (`security.py`) is the
  real defense, but the file is also auto-included conditionally —
  verify on every page.
* **S5-Low** — Password reset flow exists but I did not see a rate-limit
  specific to `/forgot-password`. The `auth_endpoints` list in
  `rate_limit_middleware.py:51-58` includes it (10/min per IP) — okay.

---

## 4. Candidate Experience

### Inventory

* Routers: `backend/routers/candidate/{cv,applications,jobs,interviews,
  qualifications,profile,subscriptions,extras}.py`.
* Pages: 23 HTML files in `pages/candidate/`
  (applications, assessments, certificate, course-details, course-landing,
  course-player, cv-builder, cv-review, cv-selection, dashboard, documents,
  interview-analysis, interview, interviews, jobs, learning, marketplace,
  messages, onboarding, profile-view, profile-visitors, profile,
  saved-jobs, settings, subscription, community).
* JS: `candidate-dashboard.js`, `candidate-interview.js`, `cv-builder.js`,
  `profile-visitors.js`, `onboarding-wizard.js`, `chat-widget.js`.

### Sub-scores

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 7     | Onboarding → CV → match → apply → interview → offer flow exists end-to-end. |
| UX               | 5     | 23 pages; no SPA; some pages share state via `localStorage`. |
| Code quality     | 5     | Mix of fetchAPI + raw fetch; inconsistent error handling. |
| Security         | 6     | Own-data filters present but email-based invitation lookup is a PII-leak surface (`routers/candidate/jobs.py`). |
| AI/ML            | 7     | CV analysis + skill extraction + interview + roadmap all wired. |
| Data model       | 6     | `User` is overloaded (ghost users, deleted_at, soft-delete bug). |
| Performance      | 5     | No lazy-load for the dashboard, no virtualization on long lists. |
| Observability    | 5     | `logger.debug` per-request in dependencies. |
| i18n / a11y      | 4     | Arabic bundle under-built; no focus-trap in modals reviewed. |
| Business         | 6     | Free trial + Pro candidate plan + Marketplace + Community — multiple retention hooks. |

**Module score: 5.6/10**

### Security findings

* **S1-High** — `routers/candidate/jobs.py` (invitations route) fetches
  `Application.email == current_user.email` to find invitations. If two
  candidates share an email (e.g., after a soft-delete + re-register, or
  after an email change), one user can read the other's job
  invitations. **Fix**: include `user_id` in the WHERE clause as a
  primary filter, use email as a secondary join.
* **S2-Med** — `routers/candidate/extras.py` has "debug views" — verify
  that those routes are gated behind `is_super_admin` or removed in
  prod. `database.py` and admin/routers mention a debug path I did not
  read in full.
* **S3-Med** — CV text is stored both in `cv_text_anonymized` and
  `analysis_json` (PII-encrypted via Fernet) but the raw file
  `backend/uploads/upload_<user_id>_<uuid>.pdf` is **not** encrypted
  at rest on disk. A disk snapshot leaks every CV. **Fix**: server-side
  S3 SSE-KMS or local LUKS, plus signed-URL-only access (signed URL
  already exists at `backend/signed_url.py` — good, but the underlying
  file is still cleartext).

### UX findings

* No A/B test infra beyond prompt-level. Recommend adding a
  `feature_flags` row for candidate-flow experiments.
* `candidate-dashboard.js` is one monolithic file — risk of
  regression; recommend split into modules.

---

## 5. Recruiter Experience

### Inventory

* Routers: `backend/routers/recruiter_*.py` (jobs, dashboard, campaigns,
  candidates, collaboration, enhancements, interviews, offers, settings,
  desktop, ai-interview, ai-sales).
* 31 pages in `pages/recruiter/`.
* JS: `recruiter-pipeline.js`, `recruiter-enhancements.js`,
  `recruiter-onboarding.js`.

### Sub-scores

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 7     | Job creation + bulk upload + pipeline + interview + offer + comparison + scorecards + automation. |
| UX               | 5     | Power-user UI, not novice-friendly; some workflows are 5+ clicks. |
| Code quality     | 5     | `_dashboard` and `recruiter_dashboard` overlap; `recruiter_jobs.py` calls Groq with user-supplied title (prompt-injection surface). |
| Security         | 6     | `check_pro_tier` enforced; signed CV URLs (5-min TTL) at `signed_url.py:50`. |
| AI/ML            | 6     | Job description generation uses Groq; risk: prompt injection via job title. |
| Data model       | 6     | `Application`, `ApplicationStageHistory`, `BatchJob`, `Offer`, `Comment` all present. |
| Performance      | 5     | Bulk upload uses `background_analyze_batch` (good), but creates **temp users with random passwords hashed with bcrypt** for every CSV row (`recruiter_campaigns/upload.py`). At 10k candidates you have 10k bcrypt calls. |
| Observability    | 6     | AuditLog entries on most mutating actions. |
| i18n / a11y      | 4     | Recruiter pages are EN-only in practice (no Arabic/French for pipeline views). |
| Business         | 8     | This is the highest-leverage surface for paid conversion; the manual-payment path is the bottleneck. |

**Module score: 5.7/10**

### Security findings

* **S1-High** — `recruiter_jobs.py` passes recruiter-supplied text
  (title, skills, description) into a Groq call. The injection guard
  in `backend/ai/security.py` runs at the **answer** level, not at the
  **prompt** level. A recruiter can write a job description that
  effectively instructs the LLM. The blast radius is "we generate a
  poisoned job description", not "we evaluate a poisoned CV", so the
  severity is **Medium** (downgraded from High) — but log it.
* **S2-Med** — `recruiter_campaigns/upload.py` `background_analyze_batch`
  creates temp users with random passwords. Confirm those users are
  marked `is_temp=True` and **never** emailed, and that they cannot
  log in. Verify password handling in the temp-user flow.
* **S3-Med** — `recruiter_candidates/applications.py` had CRIT-03
  (bulk delete ownership) — the `P0-005 FIX` annotation exists in
  the file. **Verify** the fix is actually present and was
  not just a comment without code change. Read the file fully
  before sign-off.
* **S4-Low** — `signed_url.py:53-57` reuses the JWT secret as the
  HMAC key. If you ever rotate the JWT secret, all previously-minted
  signed URLs become invalid instantly. Add a separate
  `CANDWAY_SIGNED_URL_SECRET`.

### UX findings

* `pages/recruiter/` has 31 templates; >20 are dashboard / analytics
  variants. There is not enough differentiation — many of these could
  be the same page with query params.
* Recruiter comparison view (`pages/recruiter/comparison.html`) needs
  product review; "side-by-side CV" is a known UX anti-pattern in
  recruiter tools.

---

## 6. Admin Experience

### Inventory

* Routers: `backend/routers/admin/{users,common,system,analytics,cms,
  marketing,payments,settings,subscriptions,verifications,tickets,
  plans,invoices,jobs,courses}.py` — 15 admin modules.
* 21 pages in `pages/admin/`.
* JS: `admin-components.js`.

### Sub-scores

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 8     | One of the strongest areas: full CRUD over every entity, audit logs, role-based perms, bank info, multi-tenant, promos. |
| UX               | 5     | Functional but dense; back-office quality, not consumer-grade. |
| Code quality     | 6     | Repeated pattern: `check_permission(current_user, "x")` at line 1 of every route — good defensive coding. |
| Security         | 7     | `is_super_admin` gate for `POST /settings` (admin/settings.py:99-103). Secret values are masked on `GET /settings` (admin/settings.py:35-40). |
| AI/ML            | 6     | Prompt management UI wired to `system_config_cache`; admin AI analysis routes (no detail in this audit). |
| Data model       | 6     | AuditLog everywhere; coupons, payouts, plans, invoices all modeled. |
| Performance      | 5     | `/admin/system/logs` reads `backend.log` directly — disk I/O on the request thread. |
| Observability    | 6     | Sentry, Prometheus, audit log, structured logger. |
| i18n / a11y      | 4     | Admin UI is EN-only in practice. |
| Business         | 7     | This is the "operational" tier — not revenue-generating but powers the rest. |

**Module score: 5.8/10**

### Security findings

* **S1-High** — `admin/users.py:45` self-acknowledged bug: the original
  code used `User.deleted_at == None` (which evaluates to `False`) and
  returned zero rows. The "fix" is in the comment. **Verify** the actual
  code uses `is_(None)`. This is exactly the kind of self-acknowledged
  bug that survives review.
* **S2-Med** — `admin/system.py` `/logs` returns raw `backend.log` content.
  PII is masked in the logger (good — `logger.py:16-40` has PII patterns
  for emails, phones, JWTs, passwords, API keys, CC numbers), but the
  mask is regex-based. A real email like `"foo+bar@x.co"` matches but
  an email with a non-ASCII TLD does not. PII-leak surface remains.
* **S3-Med** — `admin/settings.py:55-58`: `smtp_password` is decrypted
  on every `GET /settings` call. If an attacker has a valid admin JWT
  (e.g., an ex-admin whose JWT is still in the cookie jar), they can
  fetch the SMTP password. Mitigation: do not return the secret on
  GET at all; only return its mask.
* **S4-Low** — Coupon code is uppercased (`admin/marketing.py:58`) but
  there is no uniqueness-race protection. Two concurrent requests can
  create the same code; only the second will hit the `Slug already
  exists` check on a different field. Wrap in a transaction with a
  unique constraint.
* **S5-Low** — `admin/jobs.py:31` search filter uses `User.email` and
  `User.name`, but joins are not guaranteed — verify the join to
  `User` exists in the query. If the filter does not actually join
  `User`, this raises a 500.

---

## 7. AI Systems Deep Audit

The AI stack is the **most differentiated** part of the platform. Score
high for differentiation, lower for hardening.

### 7.1 CV Analysis (`backend/ai/cv_analysis.py`, `backend/ai/prompts.py`)

* Cascade: Groq primary, DeepSeek fallback, Gemini fallback, hard-coded
  fallback at 6000 chars.
* Prompt version v2.1 (2024-09-15) — Tunisian market context.
* Redis cache (good).
* Normalization is robust against `"R"`-instead-of-`"Rayen"` bugs
  (`cv_analysis.py:25-38`).
* **Issues**:
  * 6000-char hard truncation loses long CVs.
  * No structured logging of which model was used, why it failed, what
    the cost was. You cannot answer "how much did we spend on CV
    analysis last week?" from logs.
  * Anti-cheat is CV-side only — there is no equivalent for interview
    text (it exists in `anti_cheat.py` for interviews though).

### 7.2 Interview Engine (`backend/ai/interview.py`, `state_machine.py`,
`engine.py`)

* Weighted-score trend (recency-weighted) at
  `interview.py:27-40` — well-designed (rewards consistency).
* Confidence level: `interview.py:43-60` blends depth and breadth.
* Event log encrypted on disk by default (`engine.py:30`
  `CANDWAY_ENCRYPT_EVENT_LOG=1`).
* State machine: `InterviewStateMachine` (file in `ai/state_machine.py`).
* **Issues**:
  * `generate_question_with_deepseek` and `generate_question_with_gemini`
    are imported at the top of `interview.py:17-23` — if either provider
    module fails to import, the whole interview module fails to import.
  * `MAX_INPUT_LENGTH = 10000` (`security.py:57`) — 10k chars input
    limit on AI is a *good* design choice.

### 7.3 Talent Matching / Recommendations

* Lives in `backend/routers/recommendations.py` and
  `backend/ai/prompts.py`. Not opened in this audit.
* **UNVERIFIED**: quality of match score, calibration, fairness
  audits. If you are claiming bias-detection you must show
  `backend/ai/bias_detection.py` was wired into production scoring
  on the interview engine, not only available as a function.

### 7.4 Career Roadmap (`backend/ai/roadmap.py`)

* Self-healing fallback (lines 47-60): returns a static
  "8-12 weeks, focus on core technologies" if Groq fails. **Good**
  — the user does not crash.
* Audit context is truncated to 2000 chars (`roadmap.py:29`).

### 7.5 Talent Scout / Outreach

* `backend/ai/` has no `talent_scout.py` file at top level. **UNVERIFIED**
  whether this exists elsewhere. Listing says "Talent Scout" is a
  feature; the code only shows 16 AI modules in `backend/ai/`
  (`ab_testing.py`, `advanced_scoring_integration.py`, `anti_cheat.py`,
  `bias_detection.py`, `calibration.py`, `cv_analysis.py`,
  `drift_monitor.py`, `engine.py`, `explainable_scoring.py`,
  `interview.py`, `interview_customization.py`, `knowledge_graph.py`,
  `llm.py`, `privacy.py`, `prompts.py`, `resilience.py`,
  `roadmap.py`, `scoring_jobs.py`, `security.py`, `state_machine.py`,
  `timing_analysis.py`, `worker.py` — actually 22 files).

### 7.6 AI System Scores

| AI Module               | Quality | Transparency | Security | Drift/Drift | Notes |
| ----------------------- | ------: | -----------: | -------: | ----------: | ----- |
| CV Analysis             | 7       | 7            | 6        | 6           | Truncation at 6000; no cost log. |
| Interview Engine        | 7       | 8            | 6        | 7           | Good weighted-score, confidence, encryption. |
| Roadmap                 | 7       | 6            | 6        | 5           | Static fallback is good; no bias check. |
| Recommendations         | ?       | ?            | ?        | ?           | Not opened in this audit. |
| Bias detection          | ?       | ?            | n/a      | n/a         | File exists; not opened. |
| Drift monitor           | 6       | 6            | n/a      | 7           | 6h cron, alert threshold. |
| Anti-cheat              | 7       | 7            | 5        | n/a         | Buzzword pattern is shallow. |
| Prompt-injection guard  | 6       | 6            | 6        | n/a         | Regex-based; bypassable. |

**Aggregate AI module score: 6.4/10**

### AI Security findings

* **S1-Critical** — `ai/security.py` regex prompt-injection guard is
  bypassable with:
  * Unicode zero-width characters between letters (`ig​nore`).
  * Cyrillic homoglyphs (acknowledged in code, line 60-area, but only
    "Cyrillic homoglyphs that visually match Latin letters" — incomplete
    list).
  * Mixed-script injection (Arabic phrase + English instructions).
  * Token-level adversarial suffixes (e.g., `---END-OF-PROMPT---
    New instructions: ...`).
  * Encoding obfuscation (Base64, leetspeak).
  Recommendation: integrate a production-grade guard such as
  Lakera / PromptArmor / Rebuff — and **never** trust regex alone
  for prompt-injection.
* **S2-High** — PII scrubber (`ai/privacy.py`) is regex-only and
  self-admitted as heuristic. Send the scrubbed text + the **original**
  text payload metadata (job title, application id) to a third-party
  LLM. The metadata can re-identify a candidate by inference. Adopt a
  formal PII removal pipeline (Microsoft Presidio or equivalent).
* **S3-Med** — `ai/cv_analysis.py` calls Groq, DeepSeek, Gemini. The
  flow has no user-facing opt-in or per-call consent. The candidate
  accepted ToS at signup but did not consent to "send my CV to Google
  Gemini" specifically. **GDPR-Art 6 / Tunisian Law 2004-63** issue.
* **S4-Med** — `ai/prompts.py:80-83` "dynamic prompt cache" — the
  cache is global; ensure cache invalidation on prompt edits is
  strict and observable.
* **S5-Low** — `ai/resilience.py:85-87` shared circuit breaker is
  `name="LLM_CASCADE"`. If Groq fails 10 times, the breaker opens
  and **all LLM calls** are blocked — including Gemini and DeepSeek
  paths that did not fail. This is a **false-coupling bug**: the
  breaker should be per-provider.

---

## 8. CV Builder

* `js/cv-builder.js`, `routers/candidate/cv.py`.
* `/cv-data`, `/builder-data`, `/cv-review`, `/analyze`, `/upload-cv`.
* PII-encrypted via `EncryptedText` in `encryption.py`.
* **Issues**:
  * No autosave indicator.
  * Single-page form; no multi-step / preview.
  * No "share with this recruiter" consent flow that records consent
    for *this specific* CV *for this specific* recruiter. GDPR Art 6(1)(a)
    requires specific, informed, unambiguous consent.

**Score: 6.0/10**

---

## 9. Interview Engine (Candidate-facing)

* `pages/candidate/interview.html`, `interview-analysis.html`,
  `js/candidate-interview.js`, `routers/candidate/interviews.py`.
* Real-time presence via `backend/realtime.py` (WebSocket manager).
* `/reset-interview` with per-app reset counter (migration
  `c1d2e3f4a5b6_add_interview_reset_tracking.py`).
* **Issues**:
  * Reset counter is per-app — verify there is a **global** per-user
    limit to prevent "reset forever" abuse.
  * No proctoring image (despite the file_security.py 500 MB video
    cap) — a video-upload feature exists for "interview video" but
    I did not see the route wired.

**Score: 6.5/10**

---

## 10. Jobs & Application Management

* `Job`, `Application`, `ApplicationStageHistory`, `BatchJob`,
  `Comment`, `Offer` in `database.py`.
* `routers/candidate/jobs.py`, `routers/recruiter_jobs.py`,
  `routers/recruiter_candidates/applications.py`,
  `routers/recruiter_candidates/search.py`.
* Recruiter search returns signed CV URLs (5-min TTL).
* **Issues**:
  * `recruiter_jobs.py` has `generate-job` (LLM call) — prompt-
    injection surface (see §5).
  * `recruiter_candidates/applications.py` has the P0-005 / CRIT-03
    self-acknowledged fix. Verify the fix is real.
  * `BatchJob` size limit is enforced where? Verify against the
    `body_size_middleware.py:46` override of 5 MB on
    `/recruiter/jobs/bulk`. A 1000-row CSV at 4 KB/row is 4 MB; fine.
    A 10k-row CSV is 40 MB; rejected. Recommend streaming +
    resumable uploads (tus.io / S3 multipart).

**Score: 6.2/10**

---

## 11. Payments & Subscriptions

### Inventory

* Plans in `SubscriptionPlan` (`database.py:1408+`).
* `routers/candidate/subscriptions.py`, `routers/admin/subscriptions.py`,
  `routers/admin/plans.py`, `routers/admin/payments.py`,
  `routers/admin/invoices.py`, `routers/admin/courses.py`.
* `Invoice` model, `pdf_generator.py` (fpdf, not WeasyPrint — slow but
  dep-light).
* `_create_invoice_internal` (`admin/invoices.py:18-100`) — Tunisian
  fiscal compliance: TVA 19%, stamp duty 1.000 TND, INV-{year}-{seq}.
* `Coupon`, `Transaction` (`status="pending"` → admin manual approval),
  `PayoutRequest`, `Enrollment`.
* `konnect_*` fields in `SystemSettings` — Konnect is a TN payment
  gateway (Tunisia), so Konnect integration is a strategic
  localization.

### Sub-scores

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 6     | Manual bank-transfer flow + Konnect (Tunisia), but no Stripe. |
| UX               | 4     | The candidate manually uploads a "proof of payment" image. The conversion killer. |
| Code quality     | 6     | Internal helpers good; circular imports between invoices/subscriptions. |
| Security         | 6     | PII redaction on logs; no per-tenant keys. |
| AI/ML            | n/a   | — |
| Data model       | 7     | Plan + Invoice + Coupon + Transaction + Payout all modeled. |
| Performance      | 6     | Invoice PDF is generated on the request thread. |
| Observability    | 5     | Approval/rejection is audit-logged. |
| i18n / a11y      | 4     | Payment copy is bilingual EN/FR, Arabic under-built. |
| Business         | 4     | Manual-payment flow caps you at ~10 paying customers/month. |

**Module score: 5.3/10**

### Security findings

* **S1-High** — `routers/admin/subscriptions.py:71-73`
  `user.subscription_status = "active"` is set on manual admin
  approval. There is no idempotency token, no double-approval lock.
  Double-approving the same `tx_id` does not change behavior, but
  double-approving two `tx_id`s of the same amount for the same
  user gives them 2 years of Pro.
* **S2-Med** — Manual payment proof is stored as a URL. Verify
  it is server-side validated (MIME, magic bytes) — `file_security.py`
  has 5 MB image cap and MIME allowlist.
* **S3-Med** — `pdf_generator.py` uses `fpdf` (deprecated upstream;
  core fonts only). Multi-language invoices will fail on non-Latin
  characters unless the candidate is Latin-script only.
* **S4-Low** — Invoice numbering: `last_seq = int(...)` and
  `new_seq = last_seq + 1` (`admin/invoices.py:60-66`) — race condition
  on concurrent invoice creation. Wrap in `SELECT ... FOR UPDATE`
  or use a database sequence.

### Business findings

* No real-time Konnect webhook handler wired in this audit. The
  `konnect_api_key` is stored in admin settings but I did not see
  a webhook route in the routers I scanned. **UNVERIFIED** —
  verify `konnect_service.py` exists and is wired.

---

## 12. Content, Marketing, Notifications

* `routers/admin/cms.py` (BlogPost, Opportunity, PageSection),
  `routers/admin/marketing.py` (SalesLead, Coupon, bulk email),
  `routers/admin/announcements.py` (assumed),
  `notifications.py` (NotificationService with rich HTML templates,
  373 lines).
* Scheduler at `backend/scheduler.py:378-423` runs 14 jobs:
  interview_reminders (15 min), offer_expirations (8 & 20:00 daily),
  data_cleanup (3:00), daily_ai_report (4:00), pending_followup (10:00),
  auto_interview_invite (9:00), auto_reject_incomplete (8:00),
  offer_escalation (18:00), activity_digest (7:00), drift_check (2:00),
  calibration_collection (every 12h :30), score_recalibration (Sun 3:00),
  drift_snapshot (every 6h :15), ab_experiment (every 12h :45).
  This is **well-designed**.

### Sub-scores

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 7     | |
| UX               | 6     | |
| Code quality     | 7     | The retry wrapper at `scheduler.py:20-31` is correct. |
| Security         | 5     | `routers/admin/marketing.py:32-36` queries `User.email` and sends a **bulk** marketing email to all non-admin users from a single background task. No unsubscribe link is appended in the code path I read; `unsubscribe` router exists but is wired to transactional emails only (per the router name). |
| Data model       | 7     | `Coupon` (with `expires_at`, `max_uses`), `Announcement`, `SalesLead`. |
| Performance      | 6     | Bulk email is in a single `BackgroundTask`; not a worker queue. |
| Observability    | 7     | Each job logs start/end and retry exhaustion. |
| i18n / a11y      | 4     | Marketing copy is EN/FR mostly. |
| Business         | 6     | Coupons + Campaigns are wired. |

**Module score: 5.9/10**

### Security findings

* **S1-High** — `routers/admin/marketing.py:31` `check_permission(...,
  "manage_content")` but sending bulk marketing email is not
  "content" — it is a **legal/finance** action. A "content" admin can
  spam the whole userbase. **Fix**: add `manage_marketing` permission
  and check it here.
* **S2-Med** — `routers/admin/marketing.py:32` does `User.role != "admin"`.
  This excludes admins but **includes mentors and recruiters** as
  marketing targets. Confirm this is the intended behavior.
* **S3-Med** — The follow-up email at `scheduler.py:108-121` does not
  include an unsubscribe link. CAN-SPAM / GDPR-CAN-SPAM analogue
  requires it.
* **S4-Low** — `scheduler.py:88-92` reads
  `SystemConfig.value.lower() == "false"`. If the value is unset (no
  row), the result is `None`, and the comparison is `False`, so the
  job runs. The intent of the code is "if explicitly disabled, skip" —
  the unstated default is "enabled". Verify this matches the
  feature-flag default in `admin/common.py:43`
  (`automations_enabled: Optional[bool] = True`).

---

## 13. Analytics

* `routers/analytics.py`, `routers/admin/analytics.py`,
  `admin_analytics_service.py`,
  `routers/admin/system.py` (background-jobs, health).
* `DriftMonitor` (`backend/ai/drift_monitor.py`),
  `ABExperiment` model, `BackendAnalyticsService` (inferred).
* Prometheus + Grafana in `docker-compose.yml:101-129`.

### Sub-scores

| Dimension        | Score | Note |
| ---------------- | ----: | ---- |
| Functional       | 7     | |
| UX               | 5     | Admin dashboards are dense. |
| Code quality     | 6     | |
| Security         | 6     | |
| AI/ML            | 7     | Drift + A/B + scoring jobs. |
| Data model       | 6     | `DailyPlatformReport`, `ActivityLog`, `ProfileVisit`. |
| Performance      | 5     | Admin dashboard does aggregation in the request. |
| Observability    | 8     | Sentry + Prometheus + structured logger + drift. |
| i18n / a11y      | n/a   | |
| Business         | 7     | Real product analytics is the moat. |

**Module score: 6.1/10**

---

## 14. Data Privacy / GDPR

### Inventory

* `js/gdpr.js` (full helper module).
* `scripts/add_consent_columns.py` — adds consent columns.
* `routers/candidate/extras.py` likely has `/data-export` and
  `/delete-account` (UNVERIFIED).
* `backend/ai/privacy.py` PII scrubber.
* `backend/encryption.py` Fernet at-rest encryption.

### GDPR findings

* **G1-Critical** — No record of **explicit, granular, revocable
  consent** for AI processing at signup. The signup flow is in
  `pages/auth/signup.html` and its JS — not fully read. If the ToS
  checkbox is single ("I agree") it is **not** GDPR-compliant.
* **G2-Critical** — Right to erasure (`Article 17`) is not
  verifiable from the code I read. `User.deleted_at` is set, but
  CV text, interview logs, and analytics events likely still
  reference the user. **Fix**: implement a hard-delete worker that
  scrubs `User.id`-keyed rows and anonymizes aggregated tables.
* **G3-High** — No `cookie-consent` banner code I can confirm.
  `js/gdpr.js` exists; verify it gates analytics and marketing
  scripts (Gtag, FB Pixel, etc.).
* **G4-High** — CVs leave the EU/TN for US (Groq, Gemini) and CN
  (DeepSeek) without Standard Contractual Clauses (SCCs) on file.
  Confirm DPAs with each provider exist.
* **G5-Med** — `ai/privacy.py` "Name scrubbing is heuristic-based"
  — Tunisian Arabic names with diacritics can survive the scrub.
* **G6-Med** — Field-level encryption (`encryption.py`) has no key
  rotation. A breach requires re-encrypting every row by hand.
* **G7-Low** — `logger.py:16-40` PII mask is regex-only; CC, SSN,
  Tunisian CIN patterns are not covered.

---

## 15. Real-time / Messaging

* `backend/realtime.py` WebSocket manager (imported in `app.py:31`).
* `routers/messages.py`, `ConversationParticipant`, `Message` models.
* `chat-widget.js` for candidate-side.

**Score: 6.0/10** — not enough code read for confidence.

**Findings**

* WebSocket auth — verify the manager checks JWT on connect, not
  only on the first message.
* No rate-limit on messages (the global rate limiter may not apply
  to WS). Verify.

---

## 16. Production-Readiness Audit

### Containerization (Dockerfile + docker-compose)

* **Good**: Python 3.11-slim, non-root user (`Dockerfile:32-33`),
  gunicorn workers, healthchecks, env-file injection, AOF on Redis.
* **Bad**:
  * `Dockerfile:26` `COPY . /app` copies `.env` into the image. If
    `.env` contains `MYSQL_PASSWORD`, it is now in the image layer.
    **Fix**: `COPY` only `requirements.txt` and exclude `.env` via
    `.dockerignore`.
  * `Dockerfile:39` `--workers 4` is hard-coded. A 4-worker gunicorn
    can serve ~1000 rps on this app, but `rate_limit_middleware.py:46-48`
    in-memory fallback is **per-worker**. With 4 workers, an attacker
    gets 4× the rate-limit. The Redis path is the only safe one.
  * `docker-compose.yml:28` healthcheck calls
    `monitoring/health` — verify that route returns 200 from inside
    the container (it is on `127.0.0.1:8000`).
  * `prometheus.yml` and `nginx.conf` are referenced but not visible
    in this audit's read set — verify they exist and are minimal.

### Configuration

* `backend/config.py:113-138` `Settings.__init__` enforces
  SECRET_KEY, DEBUG=False, ALLOWED_ORIGINS, ALLOWED_HOSTS, and
  DB-credentials sanity in prod — **excellent** baseline.
* `backend/startup.py` blocks startup on placeholder AI keys
  (CRIT-01 fix) — **good**.
* `backend/startup.py` does **NOT** block on missing
  `CANDWAY_FIELD_ENCRYPTION_KEY`. The dev fallback in
  `backend/encryption.py` is used silently. **High-severity**.

### Observability

* Sentry: `app.py:93-105` — sample rates 0.05 in prod, 0.5 in dev.
  Good.
* Prometheus: `prometheus_client==0.21.1` is in `requirements.txt`
  but I did not see `/metrics` in the router imports. Verify.
* Logger: `RotatingFileHandler` + PII mask. Good.
* Drift monitor + scheduler — 14 cron jobs. Good.

### Backups

* `scripts/db_backup.py` exists. Read the file to confirm it does
  mysqldump + encryption at rest.

### Migrations

* `_HAS_MIGRATIONS = False` (`app.py:26`) + alembic disabled.
  `alembic/versions/` has 12 revisions including
  `f4a5b6c7d8e9_add_interview_turns_table.py` (2026-04-29),
  `a5b6c7d8e9f0_lift_analysis_keys.py` (2026-04-30),
  `c1d2e3f4a5b6_add_interview_reset_tracking.py` (2026-04-30),
  `d2e3f4a5b6c7_add_qualifications_table.py` (2026-04-30),
  `e3f4a5b6c7d8_add_decline_columns.py` (2026-04-30).
  Alembic is configured but not run at startup. This is a **disaster
  waiting to happen** in production.

---

## 17. Security Consolidated Findings (severity-ordered)

| ID  | Severity | Title                                                                          | Where                                                    |
| --- | -------- | ------------------------------------------------------------------------------ | -------------------------------------------------------- |
| S0  | CRIT     | PII encrypted at rest with single non-rotated Fernet key, dev fallback on      | `backend/encryption.py`, `startup.py`                    |
| S1  | CRIT     | No automated tests, no CI, no load test, no e2e                               | `tests/`, no `.github/`                                  |
| S2  | CRIT     | GDPR consent not granular, no erasure worker, DPAs absent                      | `signup` flow, `extras.py`, `privacy.py`                |
| S3  | CRIT     | Alembic disabled at startup; schema managed in code; will drift               | `backend/app.py:26`, `database.py`                       |
| S4  | HIGH     | Self-acknowledged `User.deleted_at == None` bug in admin users                 | `backend/routers/admin/users.py:45`                      |
| S5  | HIGH     | Prompt-injection guard is regex-only, bypassable                              | `backend/ai/security.py:14-55`                           |
| S6  | HIGH     | AI providers cross-border; PII sent without explicit consent                  | `backend/ai/cv_analysis.py`, `roadmap.py`                |
| S7  | HIGH     | `dependencies.py:85` `create_access_token` default of 15 min vs config 60 min  | `dependencies.py:79-90`                                   |
| S8  | HIGH     | Marketing email permission is `manage_content` instead of `manage_marketing`  | `routers/admin/marketing.py:31`                          |
| S9  | HIGH     | `routers/candidate/jobs.py` email-based invitation lookup (PII/IDOR)           | `routers/candidate/jobs.py` (line not opened)            |
| S10 | HIGH     | `signed_url.py:53-57` reuses JWT secret; rotation breaks signed URLs          | `signed_url.py`                                          |
| S11 | MED      | `recruiter_jobs.py` recruiter-supplied content into Groq                       | `routers/recruiter_jobs.py`                              |
| S12 | MED      | `recruiter_candidates/applications.py` CRIT-03 fix not verified                | `routers/recruiter_candidates/applications.py`           |
| S13 | MED      | `admin/settings.py:55-58` returns decrypted secrets on GET                     | `routers/admin/settings.py`                              |
| S14 | MED      | `admin/system.py` reads `backend.log` on the request thread                    | `routers/admin/system.py`                                |
| S15 | MED      | Manual payment approval has no idempotency / double-approval lock              | `routers/admin/subscriptions.py:71-86`                   |
| S16 | MED      | Invoice numbering race condition                                              | `routers/admin/invoices.py:60-66`                        |
| S17 | MED      | `Dockerfile:26` `COPY . /app` may include `.env`                               | `Dockerfile:26`                                          |
| S18 | MED      | `ai/resilience.py:85-87` shared circuit breaker across all LLM providers      | `ai/resilience.py`                                       |
| S19 | MED      | Bulk marketing email has no unsubscribe link                                  | `routers/admin/marketing.py`, `scheduler.py:108-121`     |
| S20 | LOW      | `dependencies.py:66` `cookie-auth` placeholder requires careful reading        | `dependencies.py:66`                                     |
| S21 | LOW      | `logger.py` PII mask is regex-only; non-ASCII leaks                           | `logger.py:16-40`                                        |
| S22 | LOW      | `admin/marketing.py:58` coupon code uniqueness race                           | `routers/admin/marketing.py:58`                          |
| S23 | LOW      | `admin/jobs.py:31` search filter assumes User join (unverified)                | `routers/admin/jobs.py:31`                               |
| S24 | LOW      | 4-worker gunicorn + in-memory rate-limit fallback = 4× rate-limit bypass      | `rate_limit_middleware.py:46-48`                         |
| S25 | LOW      | `prometheus_client` in requirements but no `/metrics` route visible           | `requirements.txt:39`                                    |

---

## 18. Data Model Audit (high-level)

* `User` (110-260 area) — over-loaded: ghost, soft-delete, mentor,
  candidate, recruiter, admin all share a table. Add `user_type`
  discriminator check constraints.
* `Application` (around line 600+ area) — has `cv_score`, `status`,
  `email`, `phone`, `user_id`, `job_id`, `batch_id`. **Issue**:
  `email` and `phone` are stored on `Application` **in addition to**
  `User` — risk of drift. Source of truth should be `User`.
* `ApplicationStageHistory` exists.
* `Job` has `required_fields` (CSV string — anti-pattern, should be
  a `required_field` table or JSON with a schema).
* `BatchJob` — bulk campaign.
* `Qualification` — model added in migration
  `d2e3f4a5b6c7_add_qualifications_table.py` (2026-04-30).
* `SubscriptionPlan`, `Transaction`, `Invoice`, `PayoutRequest`,
  `Coupon`, `Enrollment`, `Course`, `Announcement`, `AuditLog`,
  `LoginAttempt`, `ProfileVisit`, `ConversationParticipant`,
  `Message`, `SystemConfig`, `SystemPrompt`, `ABExperiment`,
  `DailyPlatformReport`, `ActivityLog`, `CompanyVerification`.
* **Index review**: I confirmed
  `idx_users_role`, `idx_users_tier`, `idx_users_subscription`,
  `idx_users_deleted_role` in `database.py:111-114`. The CV text
  column is encrypted so B-Tree indexes are useless on it. The
  Application table needs `idx_application_job_status` and
  `idx_application_user_job`. **UNVERIFIED** but likely missing.
* **No `created_at` index** on `Application` is a problem for the
  scheduler jobs (`scheduler.py:97-106` does
  `Application.created_at < days_ago` and `Application.status ==
  "pending"` — without an index this is a full table scan at scale).

---

## 19. Tech Debt Snapshot

* **19-A** — Three rate-limit implementations exist in parallel:
  `rate_limit_middleware.py` (HTTP, in-mem+Redis),
  `rate_limiter.py` (per-endpoint, likely), and
  `groq_rate_limiter` in `ai/llm.py:12`. Verify the redundancy
  is intentional.
* **19-B** — `scoring_engine.py` is a **compatibility shim** that
  re-exports from `scoring_transparent.py` (`scoring_engine.py:18-37`).
  Just delete it.
* **19-C** — `recruiter_dashboard.py` (mentioned in inventory as
  "duplicate routes") and a separate `recruiter_jobs.py` — the
  router tree has 9 recruiter packages. Recommend a single
  `recruiter` package with sub-modules.
* **19-D** — `pages/` has 78 hand-rolled HTML templates. Move to a
  Vue 3 / Svelte / HTMX + Jinja2 + Turbo model. The current
  hand-rolled state will not scale to 100k users because every
  page navigation is a full reload.
* **19-E** — `i18n` strings are 164 KB (en), 173 KB (fr), 2.9 KB
  (ar). Arabic is **incomplete** by a factor of 50.
* **19-F** — `database.sqlite` is in the repo despite the
  SQLite-removal. Delete it.
* **19-G** — `scripts/audit_is_none_bug.py` (2026-06-02) is a
  debugging artifact. Move to a `tools/` or `dev/` folder with
  `.gitignore`-style metadata.
* **19-H** — `pages/{auth,candidate,mentor,recruiter,admin}` flat
  structure; no `pages/components/` or design system.
* **19-I** — `alembic.ini` and `alembic/versions/` exist but
  `_HAS_MIGRATIONS = False`. Either run alembic at startup, or
  delete the directory.
* **19-J** — `backend/ai/` has 22 modules; the file
  `advanced_cv_analyzer.py` is **referenced** by `cv_analysis.py`
  but does not exist in the directory listing. Verify it lives at
  a different path or that the import is dead.

---

## 20. Business / Revenue Audit

### Revenue SKUs observed

* **Candidate**: Pro Candidate plan
  (`routers/candidate/subscriptions.py`, `SubscriptionPlan.slug ==
  "pro-candidate"` in `routers/admin/tickets.py:65-67`).
* **Recruiter**: Pro tier, plus a per-plan `job_limit`, `cv_limit`,
  `ai_interview_limit`, `team_seat_limit` (`admin/plans.py:31-39`).
* **Mentor**: Course sales + payouts
  (`routers/admin/payments.py:103-128` `PayoutRequest`).
* **Manual payment**: bank-transfer + proof upload — Tunisia-only.
* **Konnect**: Konnet (TN gateway) credentials in `SystemSettings`.

### Business findings

* **B1-High** — The manual-payment flow is the **single biggest
  conversion killer** in the platform. B2B SaaS in 2026 needs
  card-on-file. Konnect exists but I did not see a webhook
  handler. Verify and wire.
* **B2-High** — Stripe is absent. No global expansion story
  without Stripe + Paddle + Lemon Squeezy + Konnect.
* **B3-Med** — Pricing is per-plan but no public pricing page
  visible. UNVERIFIED.
* **B4-Med** — `SubscriptionPlan` has no trial-expiration worker.
  Verify `subscriptions.py` handles dunning.
* **B5-Med** — No usage-based pricing; only seat-based. A
  heavy-usage recruiter (10k CV / month) on the "Pro" plan
  cannot pay more — that is a missed revenue ceiling.
* **B6-Low** — `ActivityLog`, `ProfileVisit` enable a "boost"
  product (pay to be visible). UNVERIFIED whether it is wired.
* **B7-Low** — Course marketplace is B2C; mentor-payouts are
  modeled. Verify the KYC / payout flow for mentors.

---

## 21. Competitive Position

The closest direct competitors in the MENA / TN market are:

* **Tunisian / Maghreb**: Bayt.com (pan-Arab, legacy), Rekrute.com
  (Morocco), Optioncarriere (FR).
* **Global ATS**: Greenhouse, Lever, Workable, Ashby.
* **AI-first**: Eightfold, Paradox, Kwalify (FR), CVVIZ, ScoreAI.

**Candway's differentiators (real, not marketing)**:

1. **Tunisian-context prompts** (`ai/prompts.py:21, 60` — Tunisian
   market context version). This is a **real** moat for the local
   market; not defensible globally.
2. **AI Interview with calibration + bias detection** —
   differentiated vs Bayt/Rekrute; on par with Eightfold.
3. **Mentor-led course marketplace** — adjacent to the
   recruitment flow. Defensible.
4. **Multi-modal encryption** (Fernet field + PII mask) — table
   stakes for B2B; not a moat.
5. **A/B testing + drift monitor** — table stakes for serious AI
   companies; not visible to buyers.

**Threats**:
* A local competitor that ships Stripe + Konnect webhook in 3
  months out-execution-cannibalizes the manual-payment moat.
* Eightfold / Paradox will launch MENA in 2026-2027. Defend on
  the local-context moat + the marketplace.

---

## 22. Final Scores (0-100)

Each score = mean of 10 sub-scores (out of 10) × 10. Self-consistent
across modules.

| Dimension              | Module Scores                       | Mean | Final |
| ---------------------- | ----------------------------------- | ---: | ----: |
| Product (12 modules)   | 5.6, 5.7, 5.8, 6.4, 6.0, 6.5, 6.2, 5.3, 5.9, 6.1, 6.0, 6.5 | 6.0 | **60** |
| Engineering            | Code quality + testability + debt   | 5.5 | **55** |
| Security               | 25 findings, CRIT-grade 4            | 6.0 | **60** |
| AI                     | 8 sub-modules, mean 6.4              | 6.5 | **65** |
| UX                     | 12 sub-modules, mean 5.0             | 5.0 | **50**  |
| Scalability            | Will break at 10k MAU                | 5.2 | **52** |
| Business               | Revenue SKUs 3+, manual-flow cap     | 4.5 | **45** |
| Investment Readiness   | (Product+Eng+Sec+AI+UX+Scal+Bus)/7    | —    | **50** |

> Adjusted: -2 from Engineering (no tests, no CI), -2 from Investment
> Readiness (test gap, infra fragility, GDPR gaps).

---

## 23. Prioritized Roadmap

### P0 — Must-fix before next 10 paying customers (2-4 weeks)

| # | Action | Owner | Acceptance |
| - | ------ | ----- | ---------- |
| P0-01 | Wire **alembic upgrade head** at startup, remove `_HAS_MIGRATIONS = False` | Backend | App boots with empty DB and recreates schema. |
| P0-02 | Replace dev-fallback Fernet key with **mandatory env key** + key version column on each encrypted row; document key-rotation procedure | Security | App refuses to start without `CANDWAY_FIELD_ENCRYPTION_KEY`; rotation script tested. |
| P0-03 | Add **test suite** for at least auth, payments, candidate/recruiter/admin happy-paths; CI on GitHub Actions | Eng | 200+ tests, 70% line coverage. |
| P0-04 | Add **DPAs** with Groq, DeepSeek, Gemini; add per-call consent log | Legal/Eng | DPA PDFs in `/legal/`; consent_id logged on every LLM call. |
| P0-05 | Fix **idempotency** on `admin/subscriptions` approval | Backend | Double-approving same tx returns 200, no state change. |
| P0-06 | Verify **CRIT-03 / P0-005 / BUG-10 fixes** are real code changes, not just comments | QA | Diff reviewed and merged. |
| P0-07 | Add `manage_marketing` permission and split from `manage_content` | Backend | Marketing email requires the new permission. |
| P0-08 | Add `.dockerignore` excluding `.env`, `.git`, `__pycache__`, `tests/` | DevOps | Image is < 800 MB. |
| P0-09 | Per-provider **circuit breakers** in `ai/resilience.py` | Backend | Groq failure does not block Gemini/DeepSeek. |
| P0-10 | Add `prometheus_client` `/metrics` route | DevOps | Scrape returns 200. |

### P1 — Must-fix before 1,000 paying customers (1-3 months)

| # | Action | Owner |
| - | ------ | ----- |
| P1-01 | Wire **Konnect webhook** + Stripe; remove manual-payment as the default path | Backend |
| P1-02 | Add **prometheus metrics** on every router (request count, latency p50/p95, status) | Backend |
| P1-03 | Add **k6 load test** for 10k concurrent / 1k rps; CI gate | QA |
| P1-04 | Migrate to **single-page-app** shell (Vue 3 or HTMX) — at minimum for the candidate dashboard | Frontend |
| P1-05 | Add **Arabic i18n** complete coverage (parity with English) | i18n |
| P1-06 | Implement **GDPR right-to-erasure worker** | Backend |
| P1-07 | Replace regex prompt-injection guard with **commercial guard** (Lakera / Rebuff) | AI |
| P1-08 | Add **bias audit** of interview scoring on a labelled test set; publish the report | AI |
| P1-09 | Move to **S3 + SSE-KMS** for CV storage; signed-URL-only access | DevOps |
| P1-10 | Add **observability** for LLM cost (per-call USD) | Backend |
| P1-11 | Replace `fpdf` with **WeasyPrint** (UTF-8 + RTL) | Backend |
| P1-12 | Add `__pycache__` removal from images; switch to **distroless** base | DevOps |

### P2 — Should-fix in next quarter (3-6 months)

| # | Action | Owner |
| - | ------ | ----- |
| P2-01 | Refactor to **single `recruiter` router package** (delete the 9-package split) | Backend |
| P2-02 | Delete `scoring_engine.py` shim, retarget all imports to `scoring_transparent` | Backend |
| P2-03 | Move from in-memory to **Redis-only** rate limiter; remove the dev fallback | Backend |
| P2-04 | Implement **progressive profiling** for candidate onboarding (30% completion at signup) | Product |
| P2-05 | Add **video interview** end-to-end (storage, transcoding, playback with signed URL) | Product |
| P2-06 | Add **mentor payouts** via Stripe Connect or Konnect | Product |
| P2-07 | Add **A/B testing** infrastructure end-to-end (recruiter funnel, candidate funnel) | Growth |
| P2-08 | Add **proctoring** layer for AI interview (webcam, tab-switch detection) | AI |
| P2-09 | Add **CSAT / NPS** micro-surveys after interview and after offer | Product |
| P2-10 | Move from `load_dotenv` in `database.py:8` to **Settings** in `config.py` for env loading | Backend |

### P3 — Nice-to-have (6-12 months)

| # | Action | Owner |
| - | ------ | ----- |
| P3-01 | Mobile PWA (offline-friendly candidate portal) | Frontend |
| P3-02 | White-label / sub-domain support for enterprise tenants | Backend |
| P3-03 | Public **API** + webhooks for partners | Backend |
| P3-04 | SOC 2 Type 1 audit prep (policies, change management) | Security |
| P3-05 | **Voice interview** via Whisper + TTS | AI |
| P3-06 | **Calendar integration** (Google Calendar, Outlook) for interview scheduling | Product |
| P3-07 | **Resume parsing** improvement via Donut / LayoutLMv3 for non-Latin CVs | AI |
| P3-08 | **Salary benchmarking** (anonymized, opt-in) | Product |
| P3-09 | Public **trust center** (security page, uptime page) | Marketing |
| P3-10 | **Talent marketplace** for freelancers (extension of the marketplace module) | Product |

---

## 24. One-Paragraph TL;DR

Candway is a **real, functioning, fairly ambitious** AI recruitment +
learning platform that has done a non-trivial amount of security and
AI-quality work (Fernet at rest, bcrypt 12, Redis-backed rate limiting,
prompt-injection guard, anti-cheat, drift monitor, prompt versioning,
circuit breaker, event-log encryption). It is also **half-finished** in
the ways that kill startups: zero automated tests, no CI, alembic
disabled, dev-fallback encryption key, GDPR consent not granular, no
real Konnect webhook, no Stripe, manual payment proof is the
conversion killer, and the admin UI is dense. **Fix the four P0
critical items in §23 and the platform is fundable for a $1-2M
seed.** The product and AI story are good enough; the engineering
discipline and business plumbing are not.

---

*End of report. Generated 2026-06-02 against the on-disk tree at
`C:\Users\rayen\projects\candway_landing_page (2)\masar_landing_page\masar_landing_page`.*
