# Candway Architecture Audit Report — Part 2 (Sections 12-22)

## 12. Candidate UX: Ideal vs Current

| UX Element | Current | Ideal | Gap | Priority |
|---|---|---|---|---|
| **Application status** | ✅ Status badges, next steps | — | — | — |
| **Interview invitation** | ✅ Email + interview-access page | — | — | — |
| **Interview completed** | ✅ Status change, analysis available | — | — | — |
| **Strengths** | ✅ Listed in candidate analysis | — | — | — |
| **Growth areas** | ✅ Weaknesses + gaps | — | — | — |
| **Learning recommendations** | ✅ Recommendations + roadmap | — | — | — |
| **Own skill profile** | ✅ Skill tree tab in profile | — | — | — |
| **Ranking visibility** | ❌ Not shown | Should NOT be shown | — | — |
| **Other candidates** | ❌ Not shown | Should NOT be shown | — | — |
| **Recruiter notes** | ❌ Not shown | Should NOT be shown | — | — |
| **Private trust penalties** | ❌ Not shown | Should NOT be shown | — | — |
| **Rubric breakdown** | ✅ Category scores + gaps | — | — | — |
| **Download report** | ✅ PDF download | — | — | — |

**Candidate UX assessment**: The candidate view is **well-separated** from recruiter views. Candidates see only their own data: status, feedback, strengths, weaknesses, recommendations, and rubric breakdown. They do NOT see ranking, other candidates, recruiter notes, or internal trust penalties. This is correct.

**Gap**: Candidate analysis page (`candidate-interview-analysis.tsx`) already shows `is_rubric_driven`, `rubric_version`, `rubric_score`, `rubric_coverage_pct`, `category_breakdown`, `skill_breakdown`, and `gaps` — this is **more transparency than ideal**. The product decision should be made: does the candidate need the full rubric breakdown, or only high-level strengths/growth areas?

---

## 13. Backend API Architecture

| Method | Endpoint | Purpose | Role required | Tenant safe? | Status | Issues |
|---|---|---|---|---|---|---|
| `POST` | `/auth/login` | Login | public | N/A | ✅ | |
| `POST` | `/auth/signup` | Candidate signup | public | N/A | ✅ | |
| `POST` | `/auth/signup/org` | Org signup | public | N/A | ✅ | |
| `POST` | `/auth/guest-login` | Guest interview access | public | N/A | ✅ | |
| `POST` | `/auth/refresh` | Token refresh | authenticated | N/A | ✅ | |
| `GET` | `/auth/me` | Current user profile | authenticated | N/A | ✅ | |
| `GET` | `/recruiter/campaigns` | List campaigns | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/campaigns/full` | Create campaign | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/campaigns/upload-cvs` | Upload CVs + background analysis | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/campaigns/preview-match` | Preview CV vs rubric | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/campaigns/{id}/candidates` | List candidates | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/campaigns/{id}/candidates/{app_id}/invite` | Invite candidate | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/campaigns/{id}/invite-all` | Bulk invite | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/campaigns/{id}/export/csv` | Export CSV | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/campaigns/{id}/export/pdf` | Export PDF | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/campaigns/rubrics` | List rubrics for campaign | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/skill-trees` | List rubrics | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/skill-trees/standalone` | Create library rubric | recruiter | ✅ company | ✅ | |
| `POST` | `/recruiter/skill-trees/ai/generate` | AI generate rubric | recruiter | ✅ company | ✅ | |
| `PUT` | `/recruiter/skill-trees/{id}` | Edit rubric (new version) | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/skill-trees/{id}/detail` | Rubric detail + linked jobs | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/applications/{id}/scores` | Recruiter score breakdown | recruiter | ✅ company | ✅ | |
| `GET` | `/recruiter/jobs/{id}/candidates/ranked` | Ranked candidates | recruiter | ✅ company | ✅ | |
| `POST` | `/ai/interview/chat` | Interview chat | candidate/guest | ✅ tenant | ✅ | |
| `POST` | `/ai/interview/start` | Start interview | candidate/guest | ✅ tenant | ✅ | |
| `POST` | `/ai/interview/end` | End interview | candidate/guest | ✅ tenant | ✅ | |
| `POST` | `/ai/interview/resume` | Resume interview | candidate/guest | ✅ tenant | ✅ | |
| `GET` | `/candidate/interviews/{id}/analysis` | Candidate analysis | candidate/guest | ✅ tenant | ✅ | |
| `POST` | `/candidate/applications/{id}/withdraw` | Withdraw application | candidate | ✅ owner | ✅ | |
| `GET` | `/admin/finance/overview` | Finance KPIs | admin | N/A | ✅ | |
| `GET` | `/admin/credits` | Credit wallet list | admin | N/A | ✅ | |
| `POST` | `/admin/credits/{id}/grant` | Grant credits | admin | N/A | ✅ | |
| `GET` | `/monitoring/health` | Health check | public | N/A | ✅ | |
| `GET` | `/monitoring/metrics/prometheus` | Prometheus metrics | public | N/A | ✅ | |

**Key observation**: The API is **well-tenant-scoped** for recruiter operations. All campaign, job, candidate, and rubric endpoints resolve `company_id` from the authenticated recruiter's `CompanyMember` record. Background workers open their own sessions and validate tenant membership.

---

## 14. Data Model Architecture

| Model | Table | Purpose | Key relationships | Issues |
|---|---|---|---|---|
| **User** | `users` | Authentication + role + deprecated columns | `candidate_profile`, `recruiter_profile`, `admin_profile` (monkey-patched) | Deprecated columns still present, profile-first reads |
| **Company** | `companies` | Tenant organization | `CompanyMember`, `Job`, `BatchJob`, `Rubric` | `plan_id` + billing columns added in m51 |
| **CompanyMember** | `company_members` | User-company link with role | `User`, `Company` | Active/inactive, role (owner/recruiter/admin) |
| **Job** | `jobs` | Job posting | `Company`, `Recruiter`, `Rubric`, `BatchJob`, `Application` | `rubric_id` re-pointed on edit |
| **BatchJob** | `batch_jobs` | Campaign | `Recruiter`, `Job`, `Rubric`, `EvaluationConfigSnapshot`, `Application` | `active_snapshot_id` for frozen interview config |
| **Application** | `applications` | Candidate application | `User`, `Candidate`, `Job`, `BatchJob`, `CvDocument`, `EvaluationSession` | 8 deprecated columns migrated to CvDocument |
| **Candidate** | `candidates` | Enriched candidate data | `Company`, `Application` | `company_id` nullable (user-scoped until apply) |
| **Rubric** | `rubrics` | Evaluation rubric | `Job`, `BatchJob`, `EvaluationSession`, `EvaluationResult`, `RubricSnapshot` | Versioning via edit → new version |
| **RubricSnapshot** | `rubric_snapshots` | Immutable rubric copy | `Rubric`, `EvaluationSession` | |
| **EvaluationConfigSnapshot** | `evaluation_config_snapshots` | Frozen interview config | `BatchJob`, `EvaluationSession` | `resolved_rubric_json`, `config_json` |
| **EvaluationSession** | `evaluation_sessions` | Interview session state | `Application`, `Rubric`, `RubricSnapshot`, `EvaluationConfigSnapshot`, `EvaluationResult` | `interview_log` JSON column |
| **EvaluationResult** | `evaluation_results` | Canonical scores | `EvaluationSession` (1:1), `Rubric`, `RubricSnapshot` | `cv_score`, `rubric_score`, `final_score`, `score_breakdown` |
| **RubricScoringDetail** | `rubric_scoring_details` | Per-skill evidence | `EvaluationResult` | Only for interview, NOT CV |
| **CvDocument** | `cv_documents` | CV file + extracted text | `Application`, `EvaluationSession` | `analysis_json`, `cv_text_anonymized` |
| **InterviewTurn** | `interview_turns` | Q&A per turn | `EvaluationSession`, `User` | `answer`, `score`, `rubric_scores` |
| **CreditWallet** | `credit_wallets` | User credit balance | `User` | `company_id` nullable (standalone recruiters) |
| **CreditTransaction** | `credit_transactions` | Immutable credit ledger | `CreditWallet` | Idempotent `(resource, reference_id)` |
| **Subscription** | `subscriptions` | Active subscription | `User`, `SubscriptionPlan`, `PlanVersion` | Status lifecycle: trialing/active/past_due/expired |
| **Notification** | `notifications` | User notifications | `User` | |
| **AuditLog** | `audit_logs` | Security audit trail | `User`, `Company` | |

### Relationship Map (Simplified)

```
Company (tenant)
  ├── CompanyMember (user roles)
  │     └── User
  │           ├── CandidateProfile
  │           ├── RecruiterProfile
  │           ├── AdminProfile
  │           ├── Application (as user_id)
  │           ├── BatchJob (as recruiter_id)
  │           ├── Job (as recruiter_id)
  │           └── CreditWallet
  ├── Job
  │     ├── Rubric (current active)
  │     ├── BatchJob
  │     └── Application
  ├── BatchJob
  │     ├── Rubric (campaign-level override)
  │     ├── EvaluationConfigSnapshot (active_snapshot_id)
  │     └── Application
  └── Rubric
        ├── RubricSnapshot (versions)
        └── EvaluationResult

Application
  ├── CvDocument (CV text + analysis)
  ├── Candidate
  ├── EvaluationSession
  │     ├── EvaluationConfigSnapshot
  │     ├── RubricSnapshot
  │     ├── InterviewTurn
  │     └── EvaluationResult
  │           ├── RubricScoringDetail (interview evidence)
  │           └── [MISSING: CV rubric evidence]
  └── Interview
```

---

## 15. Security & Privacy Architecture

| Security item | Current status | Risk | Evidence | Recommendation |
|---|---|---|---|---|
| **Secrets handling** | ⚠️ `.env` on disk (gitignored) | Medium | `.env` exists, needs rotation before prod | Rotate all secrets, use secret manager |
| **JWT** | ✅ HS256, 15-min expiry, blacklist | Low | `dependencies.py:110` | — |
| **CSRF** | ✅ HMAC single-use tokens | Low | `security.py:329-562` | — |
| **Rate limiting** | ✅ Redis sliding window, fail-open | Low | `redis_rate_limiter.py` | — |
| **Tenant isolation** | ✅ company_id on all tenant models, 404 on mismatch | Low | `tenant.py`, `authz.py` | — |
| **Upload security** | ✅ Magic bytes, MIME, size limits, ZIP bomb | Low | `file_security.py` | — |
| **PII masking** | ✅ Unconditional before external AI | Low | `ai/security.py` PIIMasker | — |
| **Prompt injection** | ✅ 28+ patterns, both user+system messages | Low | `ai/security.py:228-391` | — |
| **Consent** | ✅ ConsentLog + GDPR erasure | Low | `gdpr_erasure.py` | — |
| **Interview token** | ✅ HMAC + single-use + Redis | Low | `dependencies.py:124-238` | — |
| **Email temp password** | ✅ Bcrypt cost 6 for ghost accounts | Low | `upload.py` | — |
| **Public routes** | ✅ Minimal: health, metrics, public jobs, marketing | Low | `router.tsx` + backend | — |
| **Admin access** | ✅ is_admin_user() + AdminProfile | Low | `dependencies.py` | — |
| **`str(e)` leaks** | ⚠️ 56 instances in production code | Medium | `str(e)` in llm.py, cv_analysis.py, worker.py, etc. | Replace with generic messages |
| **CSP unsafe-inline** | ⚠️ `style-src` allows `unsafe-inline` | Medium | `nginx.conf` CSP | Remove after frontend bundle migration |
| **InnerHTML XSS** | ⚠️ Legacy HTML pages removed, React SPA only | Low | 619+ innerHTML vectors eliminated | — |

---

## 16. Billing / Credits Architecture

| Area | Current status | Evidence | Issues | Recommendation |
|---|---|---|---|---|
| **Plans** | ✅ 6 paid plans + free tier | `SubscriptionPlan` + `PlanVersion` models, m47 migration | `credits_monthly` + `plan_group` added | — |
| **Subscriptions** | ✅ Full lifecycle | `Subscription` + `SubscriptionHistory` + `subscription_lifecycle_service.py` | Daily renewal cron, grace period | — |
| **Credit wallet** | ✅ Atomic debit, idempotent | `CreditWallet` + `CreditTransaction` + `credit_service.py` | `company_id` nullable for standalone recruiters | — |
| **Credit consumption** | ✅ 15+ endpoints wired | `require_credits()` dependency | CV analysis (3), career roadmap (4), JD writer (2), etc. | — |
| **Admin grants** | ✅ `adjust_credits()`, `grant_credits()` | `admin/credits.py` router | Immutable ledger, overdraw rejection | — |
| **Manual billing** | ✅ Receipt upload + admin approve | `org/billing.py` + `admin/subscriptions.py` | Company billing with KYB | — |
| **Self-service billing** | ✅ Plan selection + payment config | `recruiter/pages/billing.tsx` | Company-managed recruiters blocked from self-upgrade | — |
| **Stripe/Konnect** | ⚠️ Konnect referenced but not fully integrated | `konnect_service.py` | Partial integration | Complete Konnect webhook flow |
| **Invoices** | ✅ PDF generation + download | `Invoice` model + `pdf_generator.py` | fpdf 1.7.2 `output()` bug fixed | — |
| **Candidate vs recruiter billing** | ✅ Separate flows | Candidate `subscription_service.py` + recruiter `subscription_service.py` | | — |
| **Campaign credit costs** | ⚠️ Not explicitly tracked per campaign | `CampaignCost` model exists | Not wired to campaign creation | Wire campaign cost tracking |
| **AI interview credit costs** | ✅ 5 credits per generation | `questions.py` inline consume | Background evaluation not charged (deferred) | Consider charge-at-submit design |

---

## 17. Background Jobs / Async Architecture

| Job / Worker | Trigger | What it does | Status | Issues |
|---|---|---|---|---|
| **Background CV analysis** | `asyncio.create_task` on upload | `background_analyze_batch()` — PII mask, AI extract, score, persist | ✅ | Own session, tenant guard |
| **Email sequence worker** | Scheduler cron | `_daily_reengagement_digest` + email sequence | ✅ | Reads `RecruiterProfile.email` |
| **Schedulers** | APScheduler | Interview reminders, offer expirations, cleanup, platform report, auto-interview invite, renewal/credit-grant | ✅ | Retries 3x with backoff |
| **Interview final evaluation** | Chat completion trigger | `run_background_final_evaluation()` — aggregate scores, persist result, send emails | ✅ | Own session, tenant guard |
| **Notifications** | Scheduler + inline | Interview reminders, offer alerts, comment notifications | ✅ | |
| **Cron jobs** | Daily 01:00 | Subscription renewal, credit grant, re-engagement digest, AB experiment conclusion | ✅ | |
| **Failure handling** | `_run_with_retry()` | 3 attempts with exponential backoff, dead letter queue | ✅ | |
| **Redis fallback** | Worker unavailable | `_execute_inline()` — direct `call_groq_cascade` with timeout | ✅ | |
| **Webhook dispatcher** | Event triggers | `dispatch_webhook()` — company-scoped integrations | ✅ | Own session, company_id filter |

**Key observation**: All background jobs that touch tenant data now open their own `SessionLocal()` and validate `company_id`. This was a critical fix from the forensic audit.

---

## 18. Reports & Analytics Architecture

| Report / Metric | Current source | Exists? | Issues | Recommendation |
|---|---|---|---|---|
| **Campaign analytics** | `batch_counters()` + `/stats` endpoint | ✅ | Real-time from Application rows | — |
| **Recruiter analytics** | `GET /recruiter/analytics-dashboard` | ✅ | Funnel, sources, time-to-hire | — |
| **Candidate reports** | `GET /recruiter/applications/{id}/scores` + PDF | ✅ | Full breakdown + PDF export | — |
| **Shortlist reports** | Export CSV/PDF from campaign detail | ✅ | | — |
| **Interview reports** | `generate_interview_pdf()` in evaluation.py | ✅ | PDF with scores, questions, evidence | — |
| **Export PDF/CSV** | Multiple endpoints | ✅ | CSV via export endpoints, PDF via FPDF | — |
| **Admin analytics** | `AdminAnalyticsService` + `/admin/analytics/*` | ✅ | Platform-wide metrics | — |
| **Finance analytics** | `AdminFinancialService` + `/admin/finance/*` | ✅ | Revenue, customers, credits, forecast | — |
| **EEO analytics** | `EEOAnalyticsService` | ✅ | Diversity reporting | — |
| **Prometheus metrics** | `/monitoring/metrics/prometheus` | ✅ | HTTP requests, LLM circuit state, cost | — |

---

## 19. Deployment Architecture

| Deployment area | Current status | Evidence | Issues | Recommendation |
|---|---|---|---|---|
| **Dockerfile** | ✅ 4-stage multi-stage build | `Dockerfile` | Frontend → Python → Nginx → Distroless | — |
| **Docker Compose** | ✅ Full stack | `docker-compose.yml` | Backend, Nginx, MySQL 8.0, Redis 7, Prometheus, Grafana | — |
| **Nginx** | ✅ TLS 1.2/1.3, rate limiting, security headers | `nginx.conf` | CSP `unsafe-inline` for CSS | Remove after React bundle migration |
| **CI/CD** | ❌ Not configured | No `.github/workflows/` | No automated tests/deploy | Add GitHub Actions |
| **Deploy scripts** | ⚠️ `Procfile` + `scripts/db_backup.py` | `Procfile` matches Dockerfile | No blue-green or rolling deploy | Add deployment automation |
| **Env files** | ✅ `.env.example`, `.env.staging`, production templates | Multiple `.env*` files | `.env` with secrets on disk | Rotate, use secret manager |
| **DB migrations** | ✅ Alembic, m22→m59 | `alembic/versions/`, `alembic.ini` | Auto-upgrade only for dev/staging | Never enable auto-upgrade in prod |
| **Redis** | ✅ Singleton with fail-open | `redis_manager.py` | Single Redis for rate limit + cache + queue | Consider Redis Cluster for scaling |
| **Storage/uploads** | ✅ Docker volume | `upload_data` → `/app/backend/uploads` | — | — |
| **Health checks** | ✅ `/health`, `/readyz`, `/metrics` | `monitoring.py` | | — |
| **Backups** | ⚠️ `scripts/db_backup.py` | SQLite copy + mysqldump | MySQL password in URL | Use `.my.cnf` or secret manager |
| **Monitoring** | ✅ Prometheus + Grafana | `prometheus:v2.53.0`, `grafana:11.0.0` | | — |

---

## 20. Known Bugs / Architecture Risks

| Risk / Bug | Area | Severity | Evidence | Business impact | Recommended fix |
|---|---|---|---|---|---|
| **CV score not rubric-weighted** | CV Analysis | **P1** | `extract_cv_details()` returns generic `overall_score` | Rankings misaligned with rubric; recruiter cannot trust CV score as evaluation metric | Implement rubric-weighted CV scorer |
| **No CV rubric evidence** | Evaluation | **P1** | `RubricScoringDetail` only for interview; no CV evidence rows | Recruiter cannot see WHY a CV scored a certain value | Add CV evidence persistence |
| **Snapshot gap (CV vs interview)** | Architecture | **P1** | `EvaluationConfigSnapshot` created at interview start, not CV analysis | CV and interview may use different rubric versions if edited between upload and interview | Freeze snapshot at Application creation or batch upload |
| **`str(e)` info leaks** | Security | **P2** | 56 instances across 28 files | Internal error details exposed to clients | Replace with generic messages |
| **CSP `unsafe-inline`** | Security | **P2** | `nginx.conf` `style-src` | XSS risk if any HTML injection occurs | Remove after frontend bundle migration |
| **No CI/CD** | DevOps | **P2** | No `.github/workflows/` | No automated testing or deployment | Add GitHub Actions |
| **`.env` secrets on disk** | Security | **P2** | `.env` exists (gitignored) | Risk if server compromised | Rotate, use secret manager |
| **Konnect integration partial** | Billing | **P2** | `konnect_service.py` exists but not fully wired | Payment flow incomplete | Complete webhook handling |
| **Campaign cost tracking** | Billing | **P2** | `CampaignCost` model exists but not wired | Cannot track per-campaign credit consumption | Wire to campaign creation/upload |
| **Duplicate score label systems** | UX | **P3** | `scoring_transparent.py` vs `scoring.py` have different label thresholds | Inconsistent candidate experience | Standardize on one system |
| **Deprecated User columns** | Data model | **P3** | 36 deprecated columns still in `users` table | Schema bloat, migration risk | Drop in future migration after full profile migration |

---

## 21. Implementation Readiness

### 1. Is the current architecture ready for the requested feature?
**Partially ready.** The core infrastructure exists:
- ✅ `EvaluationConfigSnapshot` for frozen rubric/config
- ✅ `RubricScoringDetail` for per-skill evidence
- ✅ `ScoringService.compute_final_score()` with canonical formula
- ✅ `aggregate_scores()` for rubric-weighted aggregation
- ✅ `EvaluationResult` with all required score columns
- ✅ Campaign wizard with rubric selection
- ✅ CV upload + background analysis flow
- ✅ AI interview with rubric-driven turns

**What is missing:**
- ❌ Rubric-weighted CV scoring engine
- ❌ CV rubric evidence persistence (`RubricScoringDetail` for CV)
- ❌ Snapshot creation before CV analysis (not just at interview start)
- ❌ Unified CV+interview rubric score aggregation

### 2. What decisions must be made first?
1. **Snapshot timing**: Should `EvaluationConfigSnapshot` be created at campaign upload time, Application creation time, or interview start time? (Current: interview start only)
2. **CV rubric evidence granularity**: Should CV scoring create one `RubricScoringDetail` per skill (like interview), or a single summary row?
3. **Candidate rubric transparency**: Should candidates see the full rubric breakdown, or only high-level categories?
4. **Fallback behavior**: If rubric-weighted CV scoring fails, should we fall back to generic AI score or fail explicitly?
5. **Performance**: Rubric-weighted CV scoring adds LLM calls — should it be async (background) or synchronous (slower upload response)?

### 3. What should NOT be changed?
- `EvaluationResult` schema (already supports all needed fields)
- `ScoringService.compute_final_score()` formula (canonical, tested)
- `EvaluationConfigSnapshot` structure (already complete)
- `RubricScoringDetail` schema (extend, don't replace)
- Frontend route structure (already well-organized)
- Authentication/authorization (already secure)

### 4. What should be reused?
- `EvaluationConfigSnapshot` — freeze at CV analysis time too
- `RubricScoringDetail` — reuse with `source="cv"` or `source="interview"`
- `ScoringService.set_evaluation_result()` — already handles both CV and interview paths
- `aggregate_scores()` — reuse logic for CV evidence aggregation
- `_build_rubric_context()` — extend to structured weights, not just text
- `extract_skills_from_cv()` — already extracts skills, just needs scoring
- Frontend `RubricBreakdownTab` — extend to show CV evidence alongside interview evidence

### 5. What is the safest minimal implementation path?
1. **Create `backend/rubric/cv_scorer.py`** — new module for rubric-weighted CV scoring
   - Input: `cv_text`, `EvaluationConfigSnapshot`
   - Process: For each rubric skill, evaluate CV evidence → score 0-100
   - Output: `{skill_scores: {skill_key: score}, coverage_pct, evidence: [...]}`
   - Persist: `RubricScoringDetail` rows with `source="cv"`
2. **Modify `background_analyze_batch()`** in `upload.py`
   - After `extract_cv_details()`, call `cv_scorer.score_cv()`
   - Aggregate skill scores → `rubric_score_cv`
   - Call `ScoringService.set_cv_only(cv_score=rubric_score_cv)` or new method
3. **Ensure snapshot exists before CV analysis**
   - In `background_analyze_batch()`, if `batch.active_snapshot_id` is None, create one via `ConfigurationResolver.resolve()`
4. **Frontend**: Extend `recruiter-interview-analysis.tsx` RubricBreakdownTab to show CV evidence rows with `source="cv"` badge
5. **Extend `get_application_scores()`** to return `cv_evidence[]` alongside `evidence[]`

### 6. What tests are required?
- `test_cv_scorer.py`: rubric-weighted CV scoring against known CVs
- `test_cv_scoring_details.py`: CV evidence persistence in `RubricScoringDetail`
- `test_snapshot_cv_consistency.py`: snapshot created before CV analysis, reused at interview start
- Update `test_set_evaluation_result.py`: CV-only path with rubric scores
- Update `test_ai_security.py`: ensure PII masking covers new CV scorer prompts
- E2E: upload CV → see rubric-weighted CV score → invite → interview → see unified breakdown

### 7. What can be deferred?
- Candidate-facing rubric breakdown transparency (P3)
- Skill-level CV evidence for self-uploaded CVs (only campaign upload needs it first)
- Historical data migration (existing CV scores can remain generic)

---

## 22. Final Recommendation

### Recommendation: **Implement in phases**

**Do NOT attempt a single big-bang implementation.** The architecture is 80% ready; the missing 20% is the rubric-weighted CV scoring bridge. Implement in 3 phases:

---

### P0: Rubric-Weighted CV Scoring (Core Fix)

**Goal**: Make CV score rubric-weighted, matching the interview scoring system.

**Files affected**:
| File | Action |
|---|---|
| `backend/rubric/cv_scorer.py` | **NEW** — rubric-weighted CV scoring engine |
| `backend/routers/recruiter_campaigns/upload.py` | Modify `background_analyze_batch()` to call cv_scorer |
| `backend/models/evaluation/scoring.py` | Extend `RubricScoringDetail` if needed (or reuse with `source="cv"`) |
| `backend/scoring_service.py` | Add `set_cv_rubric_score()` or extend `set_cv_only()` |
| `backend/tests/test_cv_scorer.py` | **NEW** — unit tests |
| `frontend/src/features/recruiter/pages/recruiter-interview-analysis.tsx` | Extend RubricBreakdownTab to show CV evidence |

**Implementation steps**:
1. Create `cv_scorer.py` with `score_cv(cv_text, snapshot, company_id)` function
2. For each skill in snapshot's resolved rubric, extract evidence from CV text → score 0-100
3. Aggregate skill scores by rubric weights → `rubric_score_cv`, `coverage_pct`
4. Persist evidence as `RubricScoringDetail` rows with `source="cv"`
5. In `background_analyze_batch()`, after `extract_cv_details()`, call `cv_scorer.score_cv()`
6. Call `ScoringService.set_cv_only(cv_score=rubric_score_cv)` — reuses existing formula
7. Frontend: show CV evidence in RubricBreakdownTab with "CV" badge

**Acceptance criteria**:
- CV score reflects rubric weights (e.g., if rubric says "Python 40%, SQL 30%, Docker 30%", a CV with strong Python but no Docker scores accordingly)
- `RubricScoringDetail` rows with `source="cv"` exist for each scored skill
- Recruiter sees CV evidence alongside interview evidence in unified breakdown
- Candidate analysis page shows rubric-driven CV breakdown
- All existing tests pass + 8 new tests pass

---

### P1: Snapshot Consistency + Evidence Unification

**Goal**: Ensure CV and interview share the same frozen evaluation configuration.

**Files affected**:
| File | Action |
|---|---|
| `backend/rubric/config_resolver.py` | Ensure snapshot creation at campaign upload if missing |
| `backend/routers/recruiter_campaigns/management.py` | Create snapshot in `create_full_campaign()` |
| `backend/rubric/interview_starter.py` | Verify snapshot reuse, don't recreate |
| `backend/routers/recruiter_candidates/scoring.py` | Unify CV + interview evidence in response |
| `backend/tests/test_snapshot_consistency.py` | **NEW** — snapshot shared between CV and interview |

**Implementation steps**:
1. In `create_full_campaign()`, if `rubric_id` provided, pre-create `EvaluationConfigSnapshot` and set `batch.active_snapshot_id`
2. In `InterviewStarter.start()`, reuse existing snapshot (already implemented) — verify it never creates a new one when `active_snapshot_id` exists
3. Unify `get_application_scores()` response: merge `cv_evidence[]` and `interview_evidence[]` into single `evidence[]` with `source` field
4. Frontend: render unified evidence timeline (CV first, then interview)

---

### P2: Polish + Edge Cases

**Goal**: Handle edge cases and improve UX.

**Items**:
1. Fallback behavior: if rubric-weighted CV scoring fails (e.g., malformed rubric), fall back to generic AI score with `needs_review=True`
2. Historical data: existing CV scores remain as-is (no migration needed — they are valid generic scores)
3. Candidate rubric transparency: add toggle for "Show detailed rubric breakdown" in candidate settings
4. Performance: add Redis cache for rubric-weighted CV scores (1-hour TTL, same as current AI cache)
5. Campaign cost tracking: wire `CampaignCost` to track credits consumed per campaign

---

### Testing Checklist

| Test | Command | Expected |
|---|---|---|
| Compile backend | `python -m compileall backend -q` | Clean |
| Run AI security tests | `pytest backend/tests/test_ai_security.py -q` | 75/75 pass |
| Run scoring tests | `pytest backend/tests/test_set_evaluation_result.py -q` | 8/8 pass |
| Run new CV scorer tests | `pytest backend/tests/test_cv_scorer.py -q` | 8/8 pass |
| Run snapshot tests | `pytest backend/tests/test_snapshot_consistency.py -q` | 5/5 pass |
| Frontend build | `npm run build` | Succeeds |
| Frontend typecheck | `npx tsc --noEmit` | No new errors |
| Live E2E | Upload CV → see rubric-weighted score → invite → interview → unified breakdown | Pass |

---

### Acceptance Criteria Summary

1. **CV Score is rubric-weighted**: A CV for a "Python-heavy" rubric scores higher on Python skills than on Docker skills, matching the rubric's weight distribution.
2. **CV evidence is persisted**: `RubricScoringDetail` rows with `source="cv"` exist for each scored skill, showing the CV text evidence.
3. **Snapshot is shared**: `EvaluationConfigSnapshot` created at campaign upload is reused at interview start — same frozen rubric.
4. **Unified breakdown**: Recruiter sees CV evidence + interview evidence in a single rubric breakdown, clearly labeled by source.
5. **No breaking changes**: All existing endpoints, models, and frontend pages continue to work. New fields are additive.
6. **Tests pass**: All existing tests continue to pass. New tests cover CV scorer, snapshot consistency, and evidence unification.

---

*Report generated: 2026-08-14*
*Scope: Read-only architecture audit of Candway Recruitment Platform*
*Status: Analysis complete, implementation pending approval*
