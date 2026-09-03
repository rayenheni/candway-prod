# CANDWAY PLATFORM — FINAL PRE-LAUNCH PRODUCTION READINESS AUDIT

**Audit Date:** June 29, 2026  
**Audit Scope:** Full repository — backend, frontend, database, AI system, DevOps, security  
**Files Audited:** 200+ Python files, 100+ HTML/JS files, Docker/CI/config files  
**Methodology:** Zero-trust static analysis, pattern matching, architecture verification  

---

## 1. EXECUTIVE SUMMARY

Candway is a recruitment intelligence platform with AI-powered interviews, skill tree evaluations, and pipeline management. The codebase shows significant engineering investment with well-structured modules, recent architecture hardening (17/18 architecture score), and thoughtful patterns (config snapshots, evaluation sessions, circuit breakers).

**However, the platform is NOT ready for production launch.**

**Total Issues Found: 185+ unique issues**

| Severity | Count | Action Required |
|----------|-------|-----------------|
| **Critical** | 34 | **Blocking — must fix before launch** |
| **High** | 62 | Must fix within first sprint post-launch |
| **Medium** | 55 | Schedule within first month |
| **Low** | 34 | Track and prioritize |

### Most Critical Risks

1. **Live secrets committed to git** (`.env` with SECRET_KEY, DB passwords, GROQ_API_KEY, encryption key)
2. **Company isolation is broken** — 7 critical cross-tenant data access vulnerabilities found
3. **AI prompt injection** — all prompts use unsanitized f-string interpolation
4. **JWT tokens stored in localStorage** across 60+ frontend pages (no HttpOnly)
5. **230+ XSS vectors** via unsanitized `innerHTML` in frontend
6. **No virus/malware scanning** on file uploads (placeholder only)
7. **No offer management or background check** — "hired" status set without any validation
8. **Test suite broken** — scoring tests, circuit breaker tests, encryption tests all failing
9. **CI/CD pipeline is a no-op** — deploy stage is placeholder, security checks all use `continue-on-error: true`
10. **Non-deterministic AI scoring** — `random.randint(-8, 8)` used for per-skill score variance

---

## 2. ARCHITECTURE SCORE: 68/100

**Strengths:** Clean module separation (backend/ai/, backend/rubric/, backend/models/), config snapshot pattern, evaluation session state machine, circuit breaker resilience pattern.

**Weaknesses:** Company isolation is incomplete (+20 routers without any `company_id` filter), dual upload directories, inconsistent async patterns, no row-level security.

---

## 3. SECURITY SCORE: 42/100

**Critical Security Issues:**

| # | Issue | Location | Risk |
|---|-------|----------|------|
| 1 | .env secrets committed to git | `.env` | Complete platform compromise |
| 2 | JWT + Bearer tokens in localStorage | 60+ HTML pages | Full account takeover via XSS |
| 3 | Unsanitized innerHTML (230+ XSS vectors) | All frontend pages | Stored XSS, cookie theft |
| 4 | All prompts use f-string interpolation | `backend/ai/prompts.py` | AI prompt injection |
| 5 | Gemini API key in URL query param | `backend/ai/llm.py:685` | Key leaked in logs |
| 6 | Stripe webhook no auth when secret missing | `payments.py:179-194` | Free payment bypass |
| 7 | Webhook dispatcher hardcoded fallback key | `webhook_dispatcher.py:46` | Webhook forgery |
| 8 | CORS allows credentials with origins list | `app.py:197-211` | Session hijacking via subdomain |
| 9 | SECRET_KEY reused in 6+ contexts | Multiple files | Key compromise = full system breach |
| 10 | Grafana default admin password | `docker-compose.yml:130` | Monitoring access to attacker |

---

## 4. PERFORMANCE SCORE: 55/100

**Key Issues:**

- **170+ missing indexes on foreign key columns** — every JOIN on unindexed FKs performs full table scan
- **N+1 queries** in candidate listing endpoints (`recruiter_candidates/search.py:191-238`)
- **No pagination** on multiple list endpoints (`.all()` without `.limit()`)
- **Large JSON columns not deferred** on several models
- **No gzip compression** in nginx
- **No keepalive connections** to upstream backend (new TCP connection per request)
- **No CDN or object storage** — files served through Python app server
- **No container resource limits** — single container can OOM host

---

## 5. AI SYSTEM SCORE: 45/100

**Critical AI Issues:**

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | Prompt injection via f-string templates | `prompts.py` (all functions) | Attacker can hijack LLM behavior |
| 2 | Only last user message scanned for injection | `llm.py:178-196` | Injection in earlier messages bypassed |
| 3 | Non-deterministic random scoring | `evaluation.py:542-560` | Same interview → different scores |
| 4 | No company_id isolation in evaluations | `evaluation.py:369,1043` | Cross-tenant data access |
| 5 | No tamper-proof audit trail for AI decisions | `llm.py:486-498` | Cannot prove scores for compliance |
| 6 | Module-level ORM imports in AI engine | `prompts.py:98`, `validation.py:151` | Architecture violation |
| 7 | Direct DB queries bypassing snapshot | `validation.py:154-171` | Scoring state inconsistency |
| 8 | Unsafe JSON parsing with bare `except:` | `llm.py:402,412,453,459,537` | Silent data corruption |
| 9 | Redis queue no authentication | `worker.py:30-76` | Interview data exposure |
| 10 | Gemini circuit breaker uses wrong cascade breaker | `llm.py:619` | Gemini outage blocks Groq calls |

---

## 6. FRONTEND SCORE: 38/100

**Critical Frontend Issues:**

| # | Issue | Count |
|---|-------|-------|
| 1 | JWT tokens in localStorage (should be HttpOnly cookies) | 60+ pages |
| 2 | Unsanitized `innerHTML` with API data (XSS) | 230+ instances |
| 3 | Broken JavaScript on all mentor pages (syntax errors) | 6 pages |
| 4 | No CSP security headers | All 100+ pages |
| 5 | Direct fetch() bypasses centralized CSRF/wrapper | 63 instances |
| 6 | Hardcoded localhost API URL fallbacks | 3 JS files |
| 7 | console.log leaking sensitive data in production | 142 instances |
| 8 | No loading/error/empty states | Multiple pages |
| 9 | Inline event handlers blocking CSP enforcement | 941+ instances |
| 10 | Missing CSRF tokens on auth form submissions | 6+ pages |

---

## 7. BACKEND SCORE: 50/100

**Key Backend Issues:**

- **Setup router accessible in production** (database credentials in URL)
- **Stripe/DocuSign/Konnect webhooks unauthenticated** when secrets missing
- **No CSRF validation on cookie-based auth** endpoints
- **Password reset token in URL query param** (leaked in logs)
- **Mass assignment vulnerability** in candidate profile update
- **Rate limiting falls back to in-memory** (bypassed with multi-worker)
- **Public endpoint leaks SystemConfig** (all rows loaded into memory)
- **No offer management entity** — "hired" set without any workflow
- **No background check flow** — candidates can be hired unvetted
- **Pipeline stage transitions unvalidated** — any status to any status
- **Score overrides lack audit trail** — stored in nested JSON
- **Email/SMS no global rate limit** — 100K emails per recruiter possible
- **GDPR data retention not implemented** — PII lives forever
- **Campaign creation rate limit bypassed** — missing `await`

---

## 8. DATABASE SCORE: 52/100

**Key Database Issues:**

- Missing `ondelete="CASCADE"` on 170+ foreign keys (GDPR deletion impossible)
- Missing indexes on 30+ foreign key columns (full table scans)
- Missing composite unique constraints for tenant isolation
- Migration m11/m16 drop columns without data integrity checks
- Migration m19 downgrade sets `job_id=0` (FK violation guaranteed)
- Missing `sa.Enum` for 30+ status/state fields
- GDPR consent fields missing `nullable=False`
- JSON columns without `default=list` (NoneType errors)
- Self-referencing FKs without indexes
- Large text columns not using `Text` vs `String` appropriately

---

## 9. SCALABILITY SCORE: 45/100

| User Tier | Readiness | Bottleneck |
|-----------|-----------|------------|
| **10 users** | ✅ Ready | — |
| **100 users** | ✅ Ready | — |
| **1,000 users** | ⚠️ At risk | N+1 queries, missing indexes, memory limits |
| **10,000 users** | ❌ Not ready | No pagination, connection pool, OOM risks |
| **100,000 users** | ❌ Not ready | No horizontal scaling, CDN, async workers, sharding |

**Key Scalability Blocks:**
- No pagination on multiple endpoints (`.all()` loads all rows)
- No connection pooling limits configured
- No read replicas for analytics queries
- Background jobs not company-scoped — process ALL tenants
- File served through Python app (no CDN/X-Accel)
- No container resource limits
- No horizontal scaling support (in-memory rate limiting)

---

## 10. PRODUCTION READINESS SCORE: 40/100

**Gating Issues (Must Fix Before Launch):**

### BLOCKER-1: Secrets exposed in git
**Location:** `.env` (tracked in git)
- SECRET_KEY, GROQ_API_KEY, DB passwords, Redis password, Fernet encryption key
- Rotate ALL credentials immediately

### BLOCKER-2: Company isolation broken
**7 critical breaches:**
- `stages.py:255` — Application lookup without ownership check
- `automation.py:182` — Application lookup without ownership check
- `invitations.py:239,246` — BatchJob/Application without filter
- `actions.py:200,316` — Interview cross-tenant access
- `management.py:21,57,84,128,158` — Interview cross-tenant access
- `jobs/scoring.py` — All bg jobs process ALL tenants
- `email_sequence_worker.py:14-44` — All tenants' emails processed

### BLOCKER-3: AI prompt injection
**Location:** `backend/ai/prompts.py` (all functions)
- User-controlled content embedded in prompts via f-strings
- XML/JSON boundary escaping required

### BLOCKER-4: Frontend XSS + localStorage auth
**Location:** 60+ pages, 230+ innerHTML instances
- JWT in localStorage = XSS → account takeover
- Migrate to HttpOnly cookies

### BLOCKER-5: Test suite broken
**Location:** Multiple files
- Scoring engine tests fail (renamed method)
- Circuit breaker tests fail (conftest clash)
- Encryption tests fail (env var conflict)
- CI excludes 50% of tests
- No coverage enforcement

### BLOCKER-6: CI/CD pipeline non-functional
**Location:** `.github/workflows/`
- Deploy stage is placeholder comments
- Security checks use `continue-on-error: true`
- Two overlapping workflow files run in parallel

### BLOCKER-7: Non-deterministic AI scoring
**Location:** `evaluation.py:542-560`
- `random.randint(-8, 8)` creates artificial variance
- Same interview → different scores = indefensible

### BLOCKER-8: Webhook authentication bypass
- Stripe/DocuSign/Konnect/HackerRank/Codility webhooks
- All accept unauthenticated payloads when secrets missing
- Konnect webhook accepts GET requests (CSRF via `<img>` tag)

---

## 11. LAUNCH DECISION: **NOT READY**

**Reasoning:** 34 critical issues found, 8 of which are launch-blocking. The most severe issues (secrets in git, company isolation, prompt injection, XSS with localStorage auth) represent existential risk to the platform and its users.

### Remediation Estimate

| Phase | Effort | Issues Addressed |
|-------|--------|-----------------|
| **Phase 1 (Week 1)** | 3-4 engineers | BLOCKERs 1-4 (secrets, isolation, injection, XSS) |
| **Phase 2 (Week 2)** | 2-3 engineers | BLOCKERs 5-8 (tests, CI, scoring, webhooks) |
| **Phase 3 (Weeks 3-4)** | 3-4 engineers | Database (CASCADE, indexes, migrations), rate limiting |
| **Phase 4 (Weeks 5-6)** | 2 engineers | DevOps (resource limits, monitoring, structured logging) |
| **Phase 5 (Weeks 7-8)** | 2 engineers | Business logic (offer mgmt, background check, GDPR) |

**Estimated time to launch-ready: 6-8 weeks with full engineering team.**

---

## 12. TOP 50 HIGHEST PRIORITY ISSUES

### Critical (Sorted by Risk)

| # | Severity | Category | Location | Summary |
|---|----------|----------|----------|---------|
| 1 | CRITICAL | Secrets | `.env` | Live secrets (SECRET_KEY, DB passwords, GROQ, encryption key) committed to git |
| 2 | CRITICAL | Company Isolation | `stages.py:255` | Application lookup without ownership check — cross-tenant data access |
| 3 | CRITICAL | Company Isolation | `automation.py:182` | Cross-tenant automation rule execution |
| 4 | CRITICAL | Company Isolation | `invitations.py:239,246` | Cross-tenant invite sending |
| 5 | CRITICAL | Company Isolation | `jobs/scoring.py` | All background jobs process ALL tenants |
| 6 | CRITICAL | Company Isolation | `email_sequence_worker.py:14-44` | Email sequences process ALL tenants |
| 7 | CRITICAL | Company Isolation | `management.py:21,57,84,128,158` | Interview cross-tenant access |
| 8 | CRITICAL | Company Isolation | `actions.py:200,316` | Interview data leaked before auth check |
| 9 | CRITICAL | AI | `prompts.py` (all) | Prompt injection via unsanitized f-string templates |
| 10 | CRITICAL | AI | `llm.py:178-196` | Only last user message scanned for injection |
| 11 | CRITICAL | AI | `evaluation.py:542-560` | Non-deterministic random scoring (`random.randint`) |
| 12 | CRITICAL | AI | `llm.py:685` | Gemini API key in URL query parameter |
| 13 | CRITICAL | AI | `evaluation.py:369,1043` | No company_id isolation in AI evaluations |
| 14 | CRITICAL | Frontend | 60+ pages | JWT Bearer tokens stored in localStorage |
| 15 | CRITICAL | Frontend | 230+ instances | Unsanitized innerHTML — XSS vulnerabilities |
| 16 | CRITICAL | Frontend | 6 mentor pages | Broken JavaScript (syntax errors from bad find-replace) |
| 17 | CRITICAL | Testing | Project root | No coverage configuration or enforcement |
| 18 | CRITICAL | Testing | `ci.yml` | CI only runs 50% of tests (excludes `tests/`) |
| 19 | CRITICAL | Testing | `test_audit_findings.py` | Scoring engine tests failing (renamed method) |
| 20 | CRITICAL | Testing | `test_circuit_breakers.py` | Circuit breaker tests failing (conftest clash) |
| 21 | CRITICAL | DevOps | `ci-cd.yml:171-179` | Deploy stage is a no-op (placeholder) |
| 22 | CRITICAL | DevOps | `ci.yml` + `ci-cd.yml` | Two overlapping CI workflows run in parallel |
| 23 | CRITICAL | DevOps | `ci-cd.yml:60,66,122,128` | `continue-on-error: true` on ALL security checks |
| 24 | CRITICAL | DevOps | `docker-compose.yml:130` | Grafana default admin password |
| 25 | CRITICAL | DevOps | `docker-compose.yml` | No container resource limits on any service |
| 26 | CRITICAL | DevOps | `docker-compose.yml:109,125` | Prometheus/Grafana use `latest` tags |
| 27 | CRITICAL | Webhooks | `payments.py:179-194` | Stripe webhook accepts unauthenticated payloads |
| 28 | CRITICAL | Webhooks | `recruiter_offers.py:589-605` | DocuSign webhook bypasses HMAC in non-prod |
| 29 | CRITICAL | Webhooks | `courses.py:120-121` | Konnect webhook accepts GET requests (CSRF) |
| 30 | CRITICAL | Webhooks | `webhook_dispatcher.py:46` | Hardcoded fallback signing secret |
| 31 | CRITICAL | Database | 170+ FKs | Missing `ondelete="CASCADE"` — GDPR deletion impossible |
| 32 | CRITICAL | Database | ~30 users.id FKs | User deletion orphans 30+ child tables |
| 33 | CRITICAL | Database | `m16_downgrade.py` | Migration downgrade uses `sa.Integer` (not `sa.Integer()`) |
| 34 | CRITICAL | Biz Logic | `applications.py:358` | Pipeline stage transitions completely unvalidated |

### High (Selected Top 16)

| # | Severity | Category | Location | Summary |
|---|----------|----------|----------|---------|
| 35 | HIGH | Security | `config.py:27` | JWT uses HS256 symmetric — no key separation |
| 36 | HIGH | Security | Multiple files | SECRET_KEY reused in 6+ security contexts |
| 37 | HIGH | Security | `nginx.conf` | No TLS/SSL configured |
| 38 | HIGH | Security | `linkedin.py:68-89` | OAuth state not stored as cookie |
| 39 | HIGH | Security | `auth.py:1357-1375` | No refresh token rotation |
| 40 | HIGH | Database | 30+ columns | Missing indexes on foreign key columns |
| 41 | HIGH | Database | `m11_drop`, `m16_drop` | Migrations drop columns without data integrity check |
| 42 | HIGH | Database | `m19_downgrade` | Sets `job_id=0` → FK violation guaranteed |
| 43 | HIGH | Company Isolation | `realtime.py` | WebSocket channels not isolated by company |
| 44 | HIGH | Company Isolation | `uploads.py:59` | File upload paths lack company_id namespace |
| 45 | HIGH | Company Isolation | `redis_cache.py` | Cache keys lack company_id prefix |
| 46 | HIGH | Performance | `recruiter_candidates/search.py` | N+1 queries in candidate listing |
| 47 | HIGH | Performance | Multiple endpoints | Missing pagination (`.all()` without `.limit()`) |
| 48 | HIGH | Biz Logic | `scoring.py:176-180` | Score resolution uses `[0]` instead of latest session |
| 49 | HIGH | Biz Logic | `scoring.py:1392-1543` | Ranking weights accept arbitrary query params |
| 50 | HIGH | Biz Logic | `invitations.py:230-234` | No global email rate limit per recruiter |

---

## 13. NOTABLE STRENGTHS

Despite the severity of findings, several areas show strong engineering:

1. **Architecture hardening** — Recent fixes to config snapshots, rubric loading, scoring service architecture
2. **Evaluation state machine** — Well-defined `EvaluationSession.status` transitions
3. **Circuit breaker pattern** — Resilience for LLM provider calls
4. **Prompt injection detection** — Security module exists (needs hardening)
5. **CSRF protection framework** — `csrf.py` and `CSRFMiddleware` provide foundation
6. **GDPR consent tracking** — `ConsentLog`, `marketing_consent`, `data_processing_consent` fields
7. **Field-level encryption** — `secret_encryption.py` for PII protection
8. **Rate limiting infrastructure** — Redis-based rate limiter exists (needs enforcement)
9. **Test architecture enforcement** — `test_architecture_enforcement.py` validates ORM import rules
10. **Deferred JSON columns** — Large blobs marked deferred to avoid loading on every query

---

## 14. VERIFICATION NOTES

The following areas could not be fully verified without runtime access:

- **WebSocket behavior** under concurrent load
- **Stripe webhook** signature verification edge cases
- **Redis queue** authentication configuration in production
- **MySQL-specific behavior** (tests run on SQLite)
- **Actual LLM response quality** and edge case handling
- **Cloud infrastructure** (no cloud configs present — BYO deployment)
- **Load testing** results (Locust scripts exist but not run)
- **Mobile responsiveness** of frontend pages

These are marked as **NOT VERIFIED** and should be explicitly tested before launch.

---

## 15. FINAL VERDICT

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          CANDWAY PLATFORM — PRE-LAUNCH AUDIT              ║
║                                                           ║
║  Architecture Score:     68/100                           ║
║  Security Score:         42/100                           ║
║  Performance Score:      55/100                           ║
║  AI System Score:        45/100                           ║
║  Frontend Score:         38/100                           ║
║  Backend Score:          50/100                           ║
║  Database Score:         52/100                           ║
║  Scalability Score:      45/100                           ║
║  Testing Score:          40/100                           ║
║                                                           ║
║  Production Readiness:   40/100                           ║
║                                                           ║
║  ─────────────────────────────────────────────             ║
║                                                           ║
║  LAUNCH DECISION:  ❌ NOT READY                           ║
║                                                           ║
║  34 Critical Issues Blocking                              ║
║  8 Launch-Blocking Blocker Issues                         ║
║  Estimated 6-8 Weeks to Remediate                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```
