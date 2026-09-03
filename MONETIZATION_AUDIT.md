# Candway — Complete Monetization Architecture Audit & Production-Grade Billing Redesign

**Date:** 2026-08-01 · **Scope:** every billing model, payment flow, AI feature, quota, feature flag, and enforcement point in the codebase. Benchmarked against LinkedIn Recruiter, Greenhouse, Lever, Ashby, Workable, Recruitee, Teamtailor, Indeed, ZipRecruiter, SeekOut, Eightfold.

> This is a **redesign plan**, not a cosmetic fix. The current system cannot survive production scale: it has no credits, no metering, no renewals, no trials, no refunds, and — most critically — **~90% of AI cost is unmonetized and unquoted**. The plan below fixes the leaks and installs a LinkedIn/Notion-style credits + subscriptions engine.

---

# 0. EXECUTIVE SUMMARY

## Verdict
**Monetization Maturity Score: 3.5 / 10.** The *plumbing* (plans, invoices, Konnect, admin approval, TVA/stamp math) exists, but it is **non-functional as a revenue engine**:

| Problem | Severity | Evidence |
|---|---|---|
| **~90% of AI cost is free and unquoted** | CRITICAL | Only 3 endpoints enforce any quota; ~40 AI call sites are ungated (see Part 4) |
| **Konnect subscription payments never complete** | CRITICAL | Konnect webhook only flips LMS `Enrollment`; no code ever marks a subscription `Transaction` succeeded (`courses.py:122` vs `payments.py`) |
| **Stripe charges USD on TND-priced plans** | HIGH | `payments.py:121-122` `int(plan.price_monthly*100)` hardcoded `currency="usd"` |
| **`require_pro_tier` is exact-match → blocks `pro_plus`/`enterprise`** | HIGH | `dependencies.py:716`, `search.py:115` |
| **Two sources of truth for tier** (deprecated `User.tier` vs `RecruiterProfile.tier`) | HIGH | `ai_quota_service.py:454,539,574` reads `User.tier`; writes go to `RecruiterProfile` |
| **No renewals, trials, grace, refunds, proration, dunning** | HIGH | Zero occurrences of `renewal`/`refund`/`prorate`/`trial` consumption in billing code |
| **Paid plans exist only in `pricing.html` — never seeded in DB** | HIGH | Free plans lazy-created; paid slugs (`pro-candidate`) only referenced in tickets fallback |
| **Candidate fulfillment is broken** | HIGH | All approve paths only mutate `recruiter_profile` (`admin/subscriptions.py:154`) |
| **Candidate `check_*_limit()` is dead code** | HIGH | `candidate_subscription_service.py:100-191` never invoked by routers |
| **Per-interview turn has no quota** | HIGH | `ai_interview/chat.py:761` `evaluate_answer` — 1 LLM call per turn, ungated |
| **Unbounded AI loops** | HIGH | `reengagement_engine.py:82` up to **200 LLM calls/job**; sourcing `score_candidate` N calls |
| **`platform_fee_percent` (20%) stored but never used** | LOW | `settings.py:89-90` — marketplace commission opportunity sitting idle |
| **`free_trial` SystemConfig flag is inert** | LOW | Written at `admin/settings.py:56`, never read |

## What the redesign delivers
1. **Universal AI Credits wallet** — one ledger (`credit_wallets` + `credit_transactions` + `usage_events`) replacing the 7 scattered counters. Credits are the COGS-matching currency (AI is your only real cost).
2. **Real subscription lifecycle** — `subscriptions` table with `trialing/active/past_due/canceled/expired`, auto-renewal, dunning, proration, refunds.
3. **Fix the payment rails** — Konnect subscription webhook, Stripe currency, per-transaction `plan_id`.
4. **Seed paid plans** so DB == marketing page.
5. **Revenue model:** freemium → subscriptions → AI credit top-ups → enterprise contracts → marketplace commissions.

**Revenue upside (illustrative):** at the competitor benchmark price points (see Part 8), even 500 Tunisian recruiters × 149 TND Pro + 2,000 candidates × 29 TND Pro + credit top-ups ≈ **600K–900K TND/year (~$190K–290K)** with >80% gross margin on AI (AI cost ≈ $0.001/unit vs 8–30× markup).

---

# PART 1 — CURRENT STATE (Complete Map)

## 1.1 Subscription plans

Model: `SubscriptionPlan` — `backend/models/foundation/subscription.py:5-46` (global table, **not** TenantMixin).

| Column | Default |
|---|---|
| `name`, `slug` (unique), `target_audience` (`candidate`/`recruiter`) | |
| `price_monthly` / `price_yearly` / `currency` | 0.0 / 0.0 / `"TND"` |
| `features` (JSON string) / `permissions_json` (feature matrix) | `"{}"` |
| `job_limit` / `cv_limit` / `ai_interview_limit` / `team_seat_limit` | 5 / 50 / 10 / 1 |
| `candidate_cv_uploads_limit` / `candidate_ai_analyses_limit` / `candidate_pdf_downloads_limit` / `candidate_job_matches_limit` | 2 / 1 / 0 / 5 |
| `is_active` / `is_featured` | True / False |

**No seed migration.** Only 2 free plans are lazy-created:
- `free_recruiter` ("Free Tier", 3 jobs / 20 CV / 5 interviews) — `subscription_service.py:35-54`
- `free-candidate` ("Free Starter", 2 CV / 1 AI analysis / 0 PDF / 5 matches) — `candidate_subscription_service.py:39-68`

## 1.2 Marketing pricing (the REAL prices — `pricing.html`)

**Candidates** (all `HT` + 19% VAT + 1.000 TND stamp duty):
| Plan | Price | Limits |
|---|---|---|
| Free | 0 TND | 2 CV uploads, 1 AI analysis, 5 matches, no PDF, no courses, no mentorship |
| **Pro** (popular) | **29 TND** | 10 CV uploads, 10 AI analyses, unlimited matches, 5 PDFs, 3 courses, AI roadmap, priority support |
| Premium | 49 TND | Unlimited everything, premium badge, all courses, 1-on-1 mentorship, featured in recruiter search, career coach |

**Recruiters** (all `HT` + 19% VAT + 1.000 TND stamp duty):
| Plan | Price | Limits |
|---|---|---|
| Starter | 49 TND | 5 jobs, 50 CV reviews, 10 AI interviews, 1 seat, no Talent Scout, no Ghost Formatter |
| **Professional** (popular) | **149 TND** | 25 jobs, 200 CV reviews, 50 AI interviews, +seats, Talent Scout, Ghost Formatter |
| Enterprise | 499 TND | custom |

## 1.3 The tier vocabulary mess (3 incompatible systems)

| System | Values | Written by | Read by |
|---|---|---|---|
| `RecruiterProfile.tier` | `free`/`pro` | `payments.py:238`, `admin/subscriptions.py:156`, `admin/users.py:303`, `admin/tickets.py:131` | `subscription_service.py` |
| Deprecated `User.tier` | same | (migration only) | **`ai_quota_service.py:454,539,574`** ← wrong source |
| Inline tuple checks | `pro`,`pro_plus`,`enterprise`,`admin` | — | `search.py`, `scoring.py`, `previews.py`, `scheduling.py` |
| `require_tier` / `require_pro_tier` | **exact match** | — | `dependencies.py:690,709`; `search.py:701` |

> **`require_pro_tier` (dependencies.py:716) and `search.py:115` use `== "pro"`, so a `pro_plus` or `enterprise` recruiter gets 402 on the talent pool and wrongly-masked candidate data.** This is a live production bug.

## 1.4 Quota / counter fields

**RecruiterProfile** (`models/evaluation/profile.py:74-132`): `usage_jobs`, `usage_cvs`, `usage_ai_interviews`, `usage_reset_date`, `tier`, `subscription_status`, `subscription_end`, `current_plan_id`.

**CandidateProfile** (`models/evaluation/profile.py:12-71`): `candidate_cv_uploads_this_month`, `candidate_ai_analyses_this_month`, `candidate_pdf_downloads_this_month`, `candidate_usage_reset_date`, `subscription_status`, `subscription_plan`. **No tier column, no current_plan_id.**

**Legacy mirrored columns** on `User` (`models/foundation/user.py:28-33,70-79,89-92`) — deprecated, writes now go to profiles.

## 1.5 Quota engines

| Engine | Location | Mechanics |
|---|---|---|
| `SubscriptionService.can_perform_action` | `subscription_service.py:88-133` | Atomic `UPDATE ... SET field=field+1 WHERE field<limit`; returns `False` on exceed; callers raise 403 |
| `SubscriptionService.has_feature` | `:69-86` | reads `plan.permissions_json`; expiry check `_subscription_expired` `:56-67` |
| `CandidateSubscriptionService.check_*_limit` | `candidate_subscription_service.py:100-191` | Atomic increment-or-raise; **UNUSED** (dead code) |
| `AIQuotaService` | `ai_quota_service.py` | Redis daily/monthly counters + USD cost ceilings; only 3 endpoints wired |
| `_subscription_expired` | `subscription_service.py:56-67` | Only expiry check in the system; **no dunning/downgrade/email** |

**AIQuotaService tier table** (`ai_quota_service.py:43-93`):

| Resource | free | pro | enterprise | admin |
|---|---|---|---|---|
| daily / monthly AI calls | 25 / 250 | 500 / 5,000 | 500 / 10,000 | 999,999 |
| daily / monthly CV analyses | 10 / 50 | 100 / 1,000 | 100 / 2,000 | 999,999 |
| daily / monthly interviews | 5 / 25 | 50 / 500 | 100 / 2,000 | 999,999 |
| max tokens / request | 1,000 | 4,000 | 8,000 | 8,000 |
| cost ceiling $ daily / monthly | 0.50 / 5.00 | 10.00 / 150.00 | 20.00 / 500.00 | 1,000 / 10,000 |

> **AIQuotaService is ~90% unused.** Only `check_interview_quota` (questions.py:31), `check_cv_analysis_quota` (cv.py:650), and `chat_backup.py:972` (dead router) use it. The free 25/day, 250/mo call caps would be your abuse shield — they aren't deployed on 40+ call sites.

## 1.6 Billing tables

**`Transaction`** (`models/finance/finance.py:5-43`) — TenantMixin, `user_id`, `amount`, `currency`(default TND), `status` (String, **no enum — casing varies**: `"pending"`, `"succeeded"`, `"Failed"`), `description`, `proof_url`, `amount_ht/tva_amount/stamp_duty/amount_ttc`, `approved_at/by`, `rejected_at/by`, `idempotency_key`. **No `plan_id`.**

**`Invoice`** (`:51-89`) — `invoice_number` (unique, `INV-YYYY-NNNN`), `amount_ht`, `tva_rate`(19), `tva_amount`, `retenue_source`, `stamp_duty`(1.000), `total_ttc`, `client_name/mf/address` (from approved `CompanyVerification`), `status` (model comment says draft/paid/cancelled; **code writes `paid` and `unpaid`**), `pdf_url`, `due_date`.

**`Enrollment`/`Coupon`** (`models/lms.py`) — courses only; `Coupon` has `discount_percent`, `max_uses` (LMS-specific, not subscription coupons).

## 1.7 Payment providers (3 parallel paths)

1. **Manual bank receipt** — `POST /candidate/upgrade/manual` (`candidate/subscriptions.py:142`) + `POST /recruiter/subscription/upgrade` (`recruiter_settings.py:304`). Uploads proof → `Transaction(pending)` → admin approve/reject (`admin/subscriptions.py`) → tier bump + 365 days + auto-invoice.
2. **Stripe** — `POST /payments/stripe/create-intent` (`payments.py:72`). ⚠️ Charges **USD cents** for **TND-priced** plans. Webhook (`:164`) verified via `STRIPE_WEBHOOK_SECRET`, idempotent by event id, `FOR UPDATE` lock, bumps `RecruiterProfile` to pro + 1 year.
3. **Konnect** — `POST /payments/konnect/create` (`payments.py:283`). `konnect_service.py` calls `init_payment` (TND millesimes `amount*1000`), webhook → `courses.py:122` which **only flips Enrollment.status**. **A subscription Transaction never transitions to `succeeded` via Konnect — the paid Konnect subscription flow is broken end-to-end.**

## 1.8 Invoices & tax

`admin/invoices.py:18-103` `_create_invoice_internal`: TVA 19% + stamp 1.000 TND, `INV-{year}-{seq:04d}` numbering, client MF from approved KYB. TEIF XML export via `xml_generator.py:5-89` (hardcoded supplier MF `1234567/A/M/000`, customer default `"PASSAGER"`). Fiscally functional; hardcoded values are a compliance smell.

## 1.9 Lifecycle features — **ALL MISSING**

| Feature | Status |
|---|---|
| Trial | `free_trial` SystemConfig flag **written but never read** (inert) |
| Grace period | none |
| Refund | **zero occurrences** in codebase |
| Proration | **zero** |
| Auto-renewal | **zero** — only manual admin `extend` (`admin/subscriptions.py:331`) |
| Dunning / overdue | **zero** |
| Downgrade (self-service) | none (admin cancel only) |
| Cancellation (self-service) | none |
| `subscription_status="expired"` | never written anywhere |
| Marketplace commission | `platform_fee_percent=20` in SystemConfig, **never applied** |

---

# PART 2 — AI FEATURES (Every LLM Capability, Costed & Priced)

## 2.1 Provider costs (real numbers from `cost_controller.py`)

| Model | Input/1M | Output/1M |
|---|---|---|
| Groq llama-3.3-70b-versatile | $0.59 | $0.79 |
| Groq llama-3.1-8b-instant | $0.05 | $0.08 |
| Gemini 2.0 Flash | $0.10 | $0.40 |

Cascade: 70b → 8b → Gemini → self-heal → `None`. Per-call token budget = 90% of context window (`token_tracker.py`).

## 2.2 Feature × cost × protection matrix

| # | Feature | Call sites | Calls/inv | Est. AI cost | Gate today | Recommended |
|---|---|---|---|---|---|---|
| 1 | **AI interview (question gen + per-turn eval + final eval)** | `questions.py:88`, `chat.py:761`, `evaluation.py:255,530` | N+2 (≈17 for 15 turns) | ~$0.02–0.06 (70b worst), ~$0.11 if Gemini | question-gen only; **turns ungated** | 1 credit/turn + 5 credits/interview |
| 2 | **CV analysis / extract** | `cv_analysis.py:276,366,400,488`, `cv_service.py:102`, `cv.py:326,463` | 1 | ~$0.002 | `/upload-cv` only; **`/analyze` and `/applications` bypass** | 3 credits/CV |
| 3 | **AI job matches** | `jobs.py` via `ScoringService` | 1/candidate | ~$0.002 | none | included in plan (capped) |
| 4 | **AI candidate search / rerank** | `search.py:454` | 1 | ~$0.001 | `require_pro_tier` (buggy exact match) | Pro + 1 credit/search |
| 5 | **Copilot / hiring assistant** | `copilot.py:42`, `copilot_engine.py:46,155`, `hiring.py:121` | 2/turn | ~$0.002/turn | none | 1 credit/turn |
| 6 | **Career roadmap** | `roadmap.py:37,85,104`, `career.py:22` | 1–3 | ~$0.003 | none | Premium + 4 credits |
| 7 | **JD writer + wizard AI (8 suggest endpoints)** | `recruiter_jobs.py:89`, `job_wizard.py:588–861`, `auto_job_creator.py:128,160,198` | 1 each; 3/auto-create | ~$0.001 each | none | 1 credit each |
| 8 | **JD bias detection + rewrite** | `bias_detection_jd.py:169,239` | 2 | ~$0.003 | rate-limit only | 2 credits |
| 9 | **Ghost data reports** | `scoring.py:1498,1621` | 1 | ~$0.002 | feature flag (works) | Pro feature |
| 10 | **Re-engagement** | `reengagement_engine.py:82`, `recruiter_reengagement.py:326` | **up to 200/job** | **$0.20–0.40/job** | none | credit per candidate + hard cap |
| 11 | **AI sourcing** | `sourcing_agent.py:150,379` | 1 + N | scales with N | none | credit/candidate |
| 12 | **AI invitations** | `invitations.py:334` | 1 | ~$0.001 | none | 1 credit |
| 13 | **Score comparison** | `scoring.py:922,943` | 1 | ~$0.001 | none | 1 credit |
| 14 | **Interview debrief summary** | `actions.py:292` | 1 | ~$0.001 | none | 1 credit |
| 15 | **Resume parsing (upload/onboarding)** | `onboarding.py:745,1021,1199`, `applications.py:107` | 1 | ~$0.002 | **none** | 3 credits |
| 16 | **Recommendations engine** | `recommendations.py:123` | 1 | ~$0.002 | none | plan-capped |
| 17 | **Career chatbot** | `career_chatbot.py:98,190` | 2/turn | ~$0.002 | none | 1 credit/turn |
| 18 | **Translation** | `ai_utils.py:125` | 1 (cached) | ~$0.001 | none | 1 credit |
| 19 | **Voice TTS/STT** | `media.py:275,328` | 1 | infra cost | none | metered bytes/min |
| 20 | **Skill/quiz/course gen (mentor/LMS)** | `roadmap.py:118,137`, `rubric_router.py:1187` | 1 | ~$0.001 | none | course revenue model |
| 21 | **Admin AI daily report** | `admin_analytics_service.py:267` | 1/day | ~$0.01 | admin only | internal |

## 2.3 Highest abuse blast radius (the real money leaks)

1. **`reengagement_engine.py:82`** — `compute_candidate_job_match` loops over **up to 200 past applications**, 1 LLM call each. One `/analyze/{job_id}` = ~$0.30. Ungated.
2. **`ai_interview/chat.py:761`** — per-turn eval, unlimited turns, no quota. One long interview = 20+ calls.
3. **`candidate/cv.py:521` POST /analyze** — ungated CV analysis (sibling `/upload-cv` at `:650` IS gated — obvious bypass).
4. **`candidate/applications.py:166` POST /applications** — triggers background `analyze_cv` (`:107`), counter incremented `:141` but never checked.
5. **`recruiter_campaigns/upload.py`** bulk CV upload — gated by `usage_cvs`, but 20 free analyses per month is generous and loopable.
6. **`media.py` TTS/STT** — bandwidth + STT cost, unquota'd.
7. **`career_chatbot` / `copilot`** — unlimited turns, trivial to script.

---

# PART 3 — MISSING MONETIZATION (Features costing YOU money, given FREE)

Ranked by **Revenue Potential × Effort** (1–10 each):

| Rank | Feature | Rev | Effort | Advantage | Risk | Today | Opportunity |
|---|---|---|---|---|---|---|---|
| 1 | **AI interview (candidate practice)** | 9 | 4 | 10 (moat) | Low | Free, ungated | **The hook.** Free = 1 interview/mo; Pro = 30; Premium = unlimited. 1 credit/turn. |
| 2 | **AI candidate search / contact reveal** | 9 | 3 | 8 (LinkedIn model) | Low | Pro-gated but exact-match bug; masking not enforced as credit | Sell "contact credits" (email/phone unlock) like SeekOut credits |
| 3 | **CV analysis / enriched review** | 8 | 2 | 7 | Low | `/analyze` ungated | 3 credits; enforce `check_ai_analysis_limit` (dead code!) |
| 4 | **PDF report downloads** | 8 | 1 | 6 | Low | Free despite `candidate_pdf_downloads_limit=0` | **Already configured as paywall — just unenforced.** 1 credit/PDF |
| 5 | **AI re-engagement + sourcing** | 8 | 3 | 9 | Med | Free | credit/candidate + hard caps; this is your "AI Sourcer" upsell |
| 6 | **Career roadmap / career intelligence** | 7 | 2 | 7 | Low | Free | Premium tier; 4 credits |
| 7 | **Job matches beyond quota** | 7 | 1 | 6 | Low | Free | `candidate_job_matches_limit` exists, unenforced |
| 8 | **Profile boost / featured in search** | 7 | 3 | 8 | Low | Free | Premium add-on (badge exists in UI) |
| 9 | **1-on-1 mentorship** | 8 | 5 | 7 | Med | Free/route only | paid sessions / % split |
| 10 | **Courses (LMS)** | 7 | 2 | 6 | Low | Paid via Konnect already | add marketplace commission (`platform_fee_percent`) |
| 11 | **Background checks (Checkr)** | 6 | 2 | 5 | Med | Free, untiered | pass-through + 20–30% markup |
| 12 | **DocuSign e-sign** | 5 | 1 | 4 | Low | Free | per-doc fee |
| 13 | **EEO-1 / compliance reports** | 6 | 2 | 7 | Low | Free | Enterprise-only |
| 14 | **Translation** | 4 | 1 | 3 | Low | Free | 1 credit |
| 15 | **Qualifications verification** | 6 | 4 | 6 | Med | Free upload | verification fee / badge |

---

# PART 4 — ENDPOINT AUDIT (file:line, the enforcement matrix)

## 4.1 Currently enforced (the only 8 gates in the product)

| Gate | File:Line | Behavior |
|---|---|---|
| Job create | `recruiter_job_wizard.py:406`, `recruiter_jobs.py:279` (create), `:377` (clone) | 403 via `can_perform_action` |
| Bulk CV analyze | `recruiter_campaigns/upload.py:260` | 403 |
| Talent pool search | `recruiter_candidates/search.py:701` | 402 `require_pro_tier` (**exact-match bug**) |
| Ghost reports | `recruiter_candidates/scoring.py:1498,1621` | 403 feature flag |
| CV upload | `candidate/cv.py:650` (`check_cv_analysis_quota`) + `:670-677` (manual counter) | 402/403 |
| Interview generate | `ai_interview/questions.py:31` (`check_interview_quota`) | 402 |
| Interview reset | `candidate/interviews.py:94` | rate limit |
| Desktop license | `recruiter_desktop.py:21` | 403 tier check |

## 4.2 UNPROTECTED — AI cost surfaces (every one of these = free money burning)

**Candidate (auth only, zero quota):**
- `candidate/applications.py:166` POST /applications → background `analyze_cv` (:107) — **no quota**
- `candidate/cv.py:521` POST /analyze — **no quota** (sibling /upload-cv is gated → trivial bypass)
- `career.py:22` POST /career/plan — AI roadmap, no quota
- `ai_interview/chat.py` /chat — **every turn**, no quota
- `ai_interview/session.py`, `evaluation.py`, `media.py` (:275 upload-video, :328 TTS) — no quota
- `onboarding.py:745, :1021, :1199` — optional-user AI, no quota
- `ai_utils.py:67` /ai/translate — no quota
- `candidate/applications.py:1558` /pdf — **free**, though `candidate_pdf_downloads_limit` exists
- `ai_interview/chat_backup.py:972` — has quota gate but is a **dead router** (not imported in `ai_interview/__init__.py`)

**Recruiter (require_recruiter only, no tier/quota):**
- `jd_bias.py:31` /jd/analyze — only 20/hr/IP rate limit
- `copilot.py:25`, `copilot_admin.py:15` — AI, no quota
- `hiring.py` /hiring/candidate/{id}/chat — role check only
- `recruiter_questions.py:40` /questions/generate — AI, no quota
- `recruiter_reengagement.py:46` /analyze/{job_id} → **up to 200 LLM calls + SMTP**
- `recruiter_sourcing.py` /source/{job_id} → background sourcing + SMTP invites
- `recruiter_enhancements/actions.py:191` /debrief/{interview_id} — AI, no quota
- `recruiter_candidates/search.py:180` /search/advanced → AI rerank (:454), no quota
- `recruiter_candidates/invitations.py:309` /generate-invitation (AI); `:42` reinvite, `:223` bulk-invite (SMTP)

**Paid 3rd-party / storage — untiered:**
- `recruiter_offers.py:169` POST /send — **DocuSign** (real money, no gate)
- `recruiter_background_checks.py:28` /initiate — **Checkr** (real money, no gate)
- `candidate/profile.py:672` /avatar, `candidate/qualifications.py:106` /upload, `ai_interview/media.py:275` upload-video — storage, no quota

## 4.3 Critical enforcement bugs

| Bug | Location | Impact |
|---|---|---|
| Exact-match `require_pro_tier` | `dependencies.py:716`, `search.py:115` | `pro_plus`/`enterprise` get 402 on talent pool + data masking |
| Tier read from deprecated `User.tier` | `ai_quota_service.py:454,539,574` | pro users billed quota as free |
| Double-count risk | `can_perform_action` increments; `record_usage` increments again (`subscription_service.py:135`) | usage inflated |
| Candidate approvals only touch recruiter_profile | `admin/subscriptions.py:154` | candidates approved via admin get no fulfillment |
| `chat_backup.py` gate inert | not imported | quota illusion |
| Konnect subscription never completes | webhook only flips Enrollment | lost revenue + stuck `pending` rows |
| Candidate `check_*_limit` dead code | `candidate_subscription_service.py:100-191` | CV/PDF/match paywalls not enforced |
| Plan slug resolved from user profile, not transaction | `admin/subscriptions.py:137`, `tickets.py:104-113` | user can game plan at approval time |

---

# PART 5 — UNIVERSAL AI CREDITS SYSTEM (Design)

## 5.1 Concept
Replace the 7 scattered counters with **one wallet + one ledger + one event stream**. Credits are the only COGS-matching currency: 1 credit ≈ 1 AI call. Subscriptions grant monthly credit allocations; everything metered; top-ups and promo grants append to the ledger.

## 5.2 Credit weights (value-based, not token-based — stable for users)

| Action | Credits |
|---|---|
| Interview turn (eval) | 1 |
| Interview (question gen + up to 15 turns + final eval) | 20 |
| CV analysis | 3 |
| CV enriched review | 4 |
| Resume parse (onboarding/apply) | 3 |
| Career roadmap | 4 |
| JD generation / wizard AI suggestion | 1 |
| JD bias analysis | 2 |
| AI search rerank | 1 |
| Copilot / hiring chat turn | 1 |
| Re-engagement / sourcing per candidate | 1 |
| Score comparison / debrief / invitation | 1 |
| PDF report download | 1 |
| Translation | 1 |

## 5.3 Wallet semantics
- **Balance**: `credit_wallets.balance` DECIMAL(18,4), monotonic ledger (never UPDATE in place — always append `credit_transactions`, derive balance; or optimistic-lock `version` column + `FOR UPDATE`).
- **Allocation**: on subscription cycle (subscription `current_period_start` → `+1 month`), a `grant` transaction of `plan.credits_monthly`.
- **Expiry**: soft — unused credits roll over ≤ 3× monthly allocation, expire after 90 days (LinkedIn's own policy; drives top-up behavior).
- **Top-ups**: credit packs via Konnect/Stripe → `purchase` transaction → instant grant.
- **Refunds**: signed `refund` transaction referencing original; never mutate history.
- **Rollback**: if the downstream AI call fails after a pre-reservation, a compensating `reversal` transaction restores credits (or reserve-on-success for resilience).
- **Idempotency**: every `credit_transactions` row carries `idempotency_key` (provider event id, request id, or job id).
- **Concurrency**: `SELECT ... FOR UPDATE` on wallet row, or `UPDATE ... WHERE version = N` optimistic lock; debit reserved-while-in-flight.
- **Audit**: every transaction has `actor_type` (user/system/admin/promo), `actor_id`, `reference_type/reference_id` (application/session/job), `provider`, `model`, `tokens`, `cost_usd`.

## 5.4 Enforcement dependency
New FastAPI dependency `require_credits(action, credits=1)`:
1. Resolve actor → wallet (or current plan allocation).
2. Check subscription status (`active`/`trialing`, else 402 with upgrade_url).
3. Reserve credits; on DB failure → 402 "Insufficient credits".
4. Run action; on success commit; on failure `reversal`.
5. Write `usage_events` row for analytics.

## 5.5 Multi-currency settlement (Stripe/Konnect/manual/promo/admin/enterprise)
Single `transactions` interface with `provider` enum + `provider_ref`. Promo/admin/enterprise credits are `grant` transactions with `actor_type` auditing — no payment provider required. All settlement is just "ledger entries," which makes refunds/proration/cancellation trivial.

---

# PART 6 — DATABASE DESIGN (Production-grade tables)

New migration set (see Part 10 for order). All tables are TenantMixin (company_id, indexed, FK RESTRICT) unless noted.

### 6.1 `credit_wallets`
`id, company_id, user_id (unique per user), balance DECIMAL(18,4) NOT NULL DEFAULT 0, currency VARCHAR(10) DEFAULT 'CRED', version INT NOT NULL DEFAULT 0, created_at, updated_at`

### 6.2 `credit_transactions` (the ledger)
`id, wallet_id FK, company_id, user_id, amount DECIMAL(18,4) (signed), type ENUM('grant','purchase','consume','refund','reversal','expire','admin','promo'), resource VARCHAR(64) (e.g. interview_turn), reference_type VARCHAR(64), reference_id BIGINT, actor_type ENUM('user','system','admin','promo','provider'), actor_id BIGINT, provider ENUM('konnect','stripe','manual','none'), provider_ref VARCHAR(128), model VARCHAR(64), tokens_in INT, tokens_out INT, cost_usd DECIMAL(10,6), status ENUM('pending','succeeded','failed','reversed') DEFAULT 'succeeded', idempotency_key VARCHAR(128) UNIQUE, created_at` — index `(wallet_id, created_at)`, `(company_id, resource, created_at)`.

### 6.3 `usage_events` (immutable metering stream, write-only)
`id, company_id, user_id, resource, credits, quantity, cost_usd, provider, model, tokens_in, tokens_out, status_code, latency_ms, source, created_at` — monthly partition or table-per-month; index `(company_id, resource, created_at)`, `(user_id, created_at)`. This powers admin analytics (MRR, cost per feature, abuse detection) — today this data does not exist anywhere.

### 6.4 `subscriptions` (the lifecycle core)
`id, company_id, user_id, plan_id FK subscription_plans, status ENUM('trialing','active','past_due','canceled','expired') DEFAULT 'active', billing_cycle ENUM('monthly','yearly'), current_period_start, current_period_end, cancel_at_period_end BOOL, seats INT DEFAULT 1, provider ENUM('stripe','konnect','manual','none'), provider_sub_id VARCHAR(128), auto_renew BOOL DEFAULT True, trial_end, created_at, updated_at` — replaces `RecruiterProfile.tier/subscription_status/subscription_end/current_plan_id` and `CandidateProfile.subscription_*`.

### 6.5 `subscription_items`
`id, subscription_id FK, plan_id FK, quantity INT, unit_price DECIMAL(12,3), currency` — supports seat billing and plan-line add-ons (e.g., 5 seats × Pro).

### 6.6 `payment_attempts`
`id, company_id, transaction_id FK, provider, provider_charge_id, amount, currency, status ENUM('pending','succeeded','failed','refunded'), failure_code, failure_message, created_at`.

### 6.7 `coupons` + `discounts`
`coupons: id, code UNIQUE, type ENUM('percent','fixed'), value DECIMAL, currency, max_uses, used_count, max_redemptions_per_user, first_subscription_only BOOL, expires_at, is_active`. `discounts: id, coupon_id, subscription_id, applied_at, prorated_amount`.

### 6.8 `tax_rates`
`id, country_code, region, tax_type ENUM('VAT','stamp_duty','retention'), rate DECIMAL(5,2), is_active, valid_from`. Move TVA 19% + stamp 1.000 TND out of hardcoded `admin/invoices.py` into data.

### 6.9 `enterprise_contracts`
`id, company_id, plan_id, seats, term_start, term_end, annual_commit DECIMAL, custom_price DECIMAL, billing_contact_id, sales_owner_id, auto_renew BOOL, created_at`.

### 6.10 `seat_allocations`
`id, company_id, subscription_id FK, user_id, role, status ENUM('active','pending','removed'), assigned_at` — enforce `team_seat_limit` (currently a dead column).

### 6.11 `plan_versions`
`id, plan_id FK, version INT, name, price_monthly, price_yearly, features_json, permissions_json, job_limit, cv_limit, interview_limit, credits_monthly, valid_from, valid_to`. Grandfathered pricing snapshot.

### 6.12 `feature_flags` (move out of `permissions_json`)
`id, key, enabled BOOL, rollout_pct, plans JSON (allowed plan slugs), overrides JSON, created_at, updated_at` — allows admin self-serve flags + A/B rollout.

### 6.13 Amendments to existing tables
- `subscription_plans`: add `credits_monthly INT DEFAULT 0`, `plan_group VARCHAR(20)` (candidate/recruiter), `is_published BOOL`.
- `transactions`: add `plan_id FK`, normalize `status` via migration to enum values `pending/succeeded/failed/refunded` (fix casing), add `provider` enum.
- `invoices`: keep; write `paid`/`unpaid`/`canceled` consistently; pull tax from `tax_rates`.

---

# PART 7 — BUSINESS MODEL (Tunisia / MENA / International)

## 7.1 Principles
- **B2B recruiters = subscription + seats + credits** (value-based, benchmarked to ATS market, see Part 8).
- **B2C candidates = freemium, low price, credit-hook on AI** (AI interview is the retention loop).
- **International = USD pricing, self-serve Stripe; Tunisia = TND pricing, Konnect + manual bank (regulatory).**
- **Pay-as-you-go = credit top-ups** for spikes (same engine as subscriptions).

## 7.2 Recommended pricing matrix

### Recruiters (TND for Tunisia / USD for international)
| Plan | TND/mo | USD/mo | Jobs | CV/mo | AI interviews | Credits/mo | Seats | Key gates |
|---|---|---|---|---|---|---|---|---|
| Free | 0 | 0 | 3 | 20 | 5 | 25 | 1 | basic search, no contact unlock |
| **Starter** | 49 | $49 | 10 | 100 | 25 | 150 | 1 | contact unlock up to 25/mo |
| **Professional** | 149 | $149 | 50 | 500 | 100 | 750 | 3 | Talent Scout, Ghost Reports, AI search |
| Enterprise | 499+ | $499+ | ∞ | ∞ | ∞ | 5,000+ / custom | ∞ | EEO-1, API, SSO, custom contracts |

### Candidates (TND)
| Plan | Price | CV/mo | AI analyses | Interviews/mo | PDFs | Roadmap | Courses | Mentorship |
|---|---|---|---|---|---|---|---|---|
| Free | 0 | 2 | 1 | 1 | 0 | ✗ | ✗ | ✗ |
| **Pro** | 29 TND | 10 | 10 | 30 | 5 | ✓ | 3 | ✗ |
| Premium | 49 TND | ∞ | ∞ | ∞ | ∞ | ✓ | all | 1/mo |

### Credit packs (pay-as-you-go, TND)
| Pack | Credits | Price | Est. AI cost | Gross margin |
|---|---|---|---|---|
| Starter | 100 | 10 TND (~$3) | ~$0.10 | ~97% |
| Popular | 500 | 40 TND (~$13) | ~$0.50 | ~96% |
| Power | 2,000 | 140 TND (~$45) | ~$2.00 | ~96% |
| Agency | 10,000 | 600 TND (~$190) | ~$10.00 | ~95% |

> 1 credit ≈ 1 AI call ≈ $0.001 real cost. Even the smallest pack prices credits at ~15–30× COGS. AI is effectively 95%+ gross margin once monetized — **this is the single biggest revenue unlock in the product.**

### One-off / fee revenue
| Product | Price | Notes |
|---|---|---|
| Background check (Checkr) | pass-through + 25% | untiered today — real money |
| DocuSign e-sign | 5 TND/doc | untiered today |
| Featured profile (candidate) | 15 TND/mo | badge exists in UI |
| Priority application | 10 TND | fast-track flag |
| Qualifications verification badge | 30 TND one-time | annual re-verify 10 TND |
| Course enrollment (marketplace) | 10–25% platform fee | `platform_fee_percent` exists, unused |
| Placement fee (agencies, future) | 10–20% of salary | marketplace commission |
| Enterprise onboarding | 1× setup fee | benchmark: $3K–20K (see Part 8) |

---

# PART 8 — COMPETITOR COMPARISON

| Competitor | Model | Pricing (2026, researched) | Candway takeaway |
|---|---|---|---|
| **LinkedIn Recruiter** | seat subscription + InMail credits + job slots | Lite **$170/mo**; Corporate **$8,999–12,960/seat/yr**; InMail overage **$10/credit**; 15–22% annual increase | **Your InMail analog = contact-unlock credits + AI credits.** Pooled credits, rollover ≤3×, 90-day expiry — copy this exactly. |
| **Greenhouse** | ATS, headcount-based, quote | ~$12K base + **$240/seat** + $3–5K setup + 8–15% renewal escalation | Enterprise ceiling. Your Enterprise tier should mirror seat pricing + implementation fee. |
| **Ashby** | ATS, transparent, seat-based | **$400/mo** entry, ~$120/seat, month-to-month | Your Pro ($149/mo) is a fraction — great price point to undercut; add month-to-month. |
| **Lever** | ATS, quote-only | ~$4K/yr entry; $15–40K mid | Proves CRM/sourcing bundling carries premium. |
| **Workable** | ATS, headcount-based | **$149–299/mo** | Your Starter ($49) ≈ $16 vs their $149 — 10× undercut; price is not the constraint, enforcement is. |
| **Recruitee** | ATS + CRM, quote | ~$50–90/seat/mo range | Seat pricing benchmark for MENA SMEs. |
| **Teamtailor** | ATS, seat-based | ~$99/seat/mo | Seat-pricing validation. |
| **Indeed** | PPC / per-app + resume subs | Sponsored $5–$25/app; **Resume $120–300/mo** | Your **contact-unlock credits = Indeed Resume** ($120/mo = ~$40 for 30 contacts). Monetize candidate DB access. |
| **ZipRecruiter** | per job slot | **$299–899/mo/slot** | Per-posting revenue is proven at massive prices — job slots as an add-on SKU. |
| **SeekOut** | seat, annual | **$2,150/yr Lite**; $20K+ mid; credits don't roll over (complaint) | Pre-sell contact credits; keep rollover (differentiator). |
| **Eightfold** | enterprise talent intelligence | **$50K–500K+/yr** ($7–10/emp/mo), 3–6mo implementation | Long-term white-label/enterprise AI target; not near-term. |

**Premium differentiators Candway can own (nobody else bundles):**
1. **Full AI interview loop for both sides** (recruiter-built questions, candidate practice, auto-evaluation) — LinkedIn/ATS have no equivalent.
2. **Tunisian fiscal compliance out of the box** (TEIF XML, TVA 19%, stamp duty, Konnect) — domestic moat.
3. **AI credits as a single currency** — simpler than Indeed/LinkedIn's fragmented credits.
4. **Under-competitor pricing** in MENA (10× under Workable/Ashby).

---

# PART 9 — SECURITY & ABUSE AUDIT

| Area | Current state | Risk | Fix |
|---|---|---|---|
| **Payment security** | Stripe webhook HMAC-verified; Konnect HMAC verified (`courses.py:141`); manual receipt requires admin approve | LOW | ✓ keep; add `payment_attempts` log |
| **Invoice integrity** | Sequential numbering, `FOR UPDATE` lock on last invoice; `client_mf` from KYB | MED (race on concurrent numbering under load; hardcoded supplier MF) | add unique constraint + retry-on-collision; parameterize MF |
| **Currency handling** | **Stripe charges USD on TND plans** (`payments.py:121`) | **HIGH** | charge in plan currency; block mixed-currency |
| **Double spending / replay** | Stripe event id idempotency ✓; Konnect uses paymentRef as key; `Idempotency-Key` on admin approve ✓; `FOR UPDATE` locks | LOW–MED (Stripe webhook replays ✓; Konnect webhook idempotent ✓) | add idempotency_key to all new ledger writes |
| **Credit fraud** | N/A (no credits exist yet) | — | design: ledger-only balance, idempotency, FOR UPDATE, per-IP/per-user purchase rate limit, admin-grant audit trail |
| **Subscription bypass** | **40+ AI endpoints unquoted**; `require_pro_tier` exact-match bug; candidate limits dead code | **CRITICAL** | enforce via `require_credits` dependency everywhere |
| **API abuse / rate limits** | Redis AI quota (mostly unused); `simple_rate_limiter`; qualifications 20/hr & 60/day; upgrade rate-limited 2/5min | MED | enforce AI quota on ALL AI endpoints; per-company cost ceilings via `cost_controller` (needs company_id in worker — currently missing, `interview_worker.py`) |
| **Admin abuse** | `manage_finance`/`check_admin` gating; admin bypass on quotas (by design) | LOW | full AuditLog on every approve/reject/extend/grant; immutable ledger |
| **Replay of webhooks** | Stripe ✓; Konnect paymentRef ✓ | LOW | ✓ |
| **Self-serve bypass** | users can call ungated endpoints directly (curl) | **HIGH** | server-side enforcement only (never trust UI) |
| **File upload abuse** | avatar/qualification/video unquota'd storage | MED | per-user/month storage quota |

---

# PART 10 — OUTPUT

## 10.1 Architecture diagram

```
                          ┌─────────────────────────────────────────────────┐
                          │              CANDWAY BILLING CORE              │
                          │                                                 │
  Stripe ──────┐          │  ┌──────────────┐   ┌───────────────────────┐   │
  Konnect ─────┼── webhooks│  │ payments.py  │──▶│ Transaction (ledger) │   │
  Manual ──────┘           │  │ (signed,     │   │  +plan_id+provider   │   │
                          │  │  idempotent) │   └──────────┬────────────┘   │
                          │  └──────────────┘              │                │
                          │                        ┌───────▼────────┐        │
  subscriptions table ────┼──────────────────────▶ │ subscriptions  │        │
  (trialing/active/…,      │                        │ + items + seats │        │
   renew, dunning)        │                        └───────┬────────┘        │
                          │                                │ grants           │
  ┌──────────────┐        │                        ┌───────▼────────┐        │
  │ credit_wallets│        │  ┌──────────────────┐  │ credit_        │        │
  │ (balance,    │◀───────┼──│  require_credits │──│ transactions    │        │
  │  version)    │        │  │  (FastAPI dep)   │  │ (immutable)     │        │
  └──────────────┘        │  └────────┬─────────┘  └───────┬────────┘        │
                          │           │ reserve            │ audit           │
                          │  ┌────────▼─────────┐  ┌───────▼────────┐        │
                          │  │ 40+ AI endpoints │  │ usage_events   │        │
                          │  │ (now metered)    │  │ (analytics)    │        │
                          │  └──────────────────┘  └────────────────┘        │
                          └─────────────────────────────────────────────────┘
   Billing: admin approve/reject · invoices (TEIF) · coupons · tax_rates
   Funnel:  pricing.html → plans API → Konnect/Stripe → subscription → credits
```

## 10.2 Revenue model (targets)
- **MRR = Σ subscriptions + credit top-ups + one-off fees.**
- Target mix after 24 months: 55% subscriptions, 25% credit top-ups, 12% enterprise contracts, 8% one-off (checks/sign/featured).
- Unit economics: AI cost < $0.001/credit vs price 15–30× → gross margin >95% on credits; platform opex ≈ hosting + providers.

## 10.3 Feature matrix (what each plan unlocks — proposed)

| Feature | Free | Starter/Pro | Professional | Enterprise |
|---|---|---|---|---|
| ATS core (jobs, pipeline, notes, offers, interviews) | ✓ | ✓ | ✓ | ✓ |
| Candidate DB + basic search | ✓ | ✓ | ✓ | ✓ |
| Contact unlock | — | 25/mo | 100/mo | ∞ |
| AI CV analysis (credits) | 20/mo | 100/mo | 500/mo | ∞ |
| AI interviews (credits) | 5/mo | 25/mo | 100/mo | ∞ |
| AI search rerank | — | — | ✓ | ✓ |
| Talent Scout (sourcing/re-engagement) | — | — | ✓ | ✓ |
| Ghost Reports | — | — | ✓ | ✓ |
| Team seats | 1 | 1 | 3 | ∞ |
| EEO-1 / compliance | — | — | — | ✓ |
| API / SSO / custom contract | — | — | — | ✓ |

## 10.4 Migration plan (ordered, ROI-first)

**Wave 0 — Stop the bleeding (this week):**
1. Fix `require_pro_tier` exact-match → membership check (`pro`, `pro_plus`, `enterprise`) — `dependencies.py:716`, `search.py:115`.
2. Fix `ai_quota_service` tier source → `RecruiterProfile.tier`/plan, not `User.tier`.
3. Enforce `check_pdf_download_limit` on `/candidate/applications/{id}/pdf` (`applications.py:1558`) and `check_ai_analysis_limit` on `/candidate/cv/analyze` (`cv.py:521`) + POST /applications.
4. Add quota to per-turn interview eval (`chat.py:761`) and `/ai/interview/chat`.
5. Fix Stripe currency: charge plan currency, reject cross-currency (`payments.py:121`).
6. Add Konnect subscription webhook handler → mark `Transaction succeeded` (currently never).
7. Seed paid plans (Pro/Premium/Starter/Professional/Enterprise) via Alembic so DB == `pricing.html`.
8. Pass `company_id` into `interview_worker.py` task payload so cost budgets apply in workers.

**Wave 1 — Metering core (2–4 weeks):**
9. Create `usage_events` (write-only) — instrument all AI call sites to log.
10. Create `credit_wallets` + `credit_transactions`; implement `require_credits` dependency.
11. Backfill current usage counters into wallet balances.
12. Add admin analytics: credits burned/feature, cost per feature, MRR.

**Wave 2 — Subscription lifecycle (4–8 weeks):**
13. `subscriptions` + `subscription_items` + `seat_allocations` tables; migration from profile columns.
14. Auto-renewal cron + dunning emails (grace 3 days, then suspend) + `past_due`/`expired` states.
15. Trial: `free_trial` SystemConfig now wired — 14-day candidate Pro trial, 14-day recruiter Starter trial.
16. Self-service cancel/downgrade/reactivate + proration on plan change.
17. Refunds admin UI (ledger `refund` transactions + Stripe/Konnect reversal).

**Wave 3 — Monetization depth (2–3 months):**
18. `coupons`/`discounts`/`tax_rates`/`enterprise_contracts`/`plan_versions`/`feature_flags`.
19. Contact-unlock credits (masked data → credit reveal), PDF credits, background-check & DocuSign markup.
20. Course marketplace commission (`platform_fee_percent`), featured profiles, priority applications, verification badges.
21. Per-company credit pools + admin grants + promo codes.
22. Analytics dashboards for funnel + abuse detection (thresholds: >X calls/IP, >Y cost/company/day).

## 10.5 API changes (new/changed)
- `POST /billing/subscriptions` (create w/ plan, cycle, provider) · `GET /billing/subscription` · `POST /billing/subscriptions/{id}/cancel|reactivate|change-plan` · `POST /billing/subscriptions/{id}/payment-method`
- `GET /billing/wallet` · `POST /billing/credits/topup` (Konnect/Stripe) · `GET /billing/usage` (credits + cost)
- `POST /billing/coupons/apply` · `POST /billing/refunds`
- `POST /payments/konnect/subscription-webhook` (new) — transitions Transactions to `succeeded`
- `POST /billing/credits/grant` (admin/promo, audit-logged)
- Change `Transaction.status` values to `pending|succeeded|failed|refunded` (migration + code)
- Add `plan_id` to `Transaction` at creation (all 3 flows)

## 10.6 Risk analysis
| Risk | Mitigation |
|---|---|
| Migration of existing manual-paid users | snapshot into `subscriptions` with `provider='manual'`, `current_period_end` from `subscription_end` |
| Credit fraud at scale | ledger-only, idempotency keys, FOR UPDATE, per-user purchase caps, anomaly alerts |
| Konnect reliability | keep manual receipt fallback; monitor webhook delivery; reconciliation cron |
| Tunisian fiscal audit | keep TEIF/tax logic, parameterize MF, stamp duty via `tax_rates` |
| User resistance to credits | generous plan allocations; rollover ≤3×; clear in-app meter (mirror Notion/Cursor UI) |
| AI provider outage → auto-downgrade of UX | current `None`-fallback already forces honest "unavailable" — keep; do not fake results |

## 10.7 Quick wins (ROI ranking)
1. Fix exact-match tier bug — 30 min, unblocks paying Enterprise users.
2. Enforce PDF + CV-analyze + application paywalls (dead code) — 2 hrs, immediate upsell pressure.
3. Fix Stripe currency + seed paid plans — 3 hrs.
4. Add quota to interview per-turn eval — 1 hr, biggest AI cost leak.
5. Wire Konnect subscription webhook — 4 hrs, un-blocks paid Konnect path.
6. Instrument `usage_events` write-only — 1 day, unlocks all future analytics.

## 10.8 Critical issues (must fix before scale)
1. Exact-match tier bug (`dependencies.py:716`, `search.py:115`).
2. 40+ ungated AI endpoints (Part 4.2) — abuse + cost exposure.
3. Konnect subscription never completes.
4. Stripe/TND currency mismatch.
5. Two tier sources of truth.
6. Candidate fulfillment broken on admin approval.
7. No renewals/dunning → revenue collapses at renewal month.
8. Dead-code candidate limits → paywalls bypassed.
9. `platform_fee_percent`, `free_trial` flags inert.

## 10.9 Future opportunities (12+ months)
- **AI Sourcer as a managed service** — autonomous sourcing + outreach; charge per qualified candidate or % of hire.
- **Placement marketplace** — agencies post to Candway; Candway takes commission on successful hires.
- **Enterprise talent intelligence** (Eightfold lane) — $50K+/yr tier for internal-mobility + workforce analytics.
- **White-label API** — resell AI interviews/matching to other ATS via API + metered credits.
- **Job slot market** — ZipRecruiter-style per-posting pricing for high-volume roles.
- **Pay-per-application** for employers (Indeed model) once candidate volume is critical mass.

---

### Closing
The Candway product has **genuine competitive features** (dual-sided AI interviews, Tunisian fiscal stack, under-priced tiering). The revenue engine, however, is a **prototype**: payments don't complete end-to-end, AI is ~90% free, and there is no metering, renewal, trial, or refund machinery. **Wave 0 (8 fixes, ~1 week)** stops the leaks and unblocks charging today; **Waves 1–3** install the LinkedIn/Notion-grade credits + subscription engine that the codebase clearly deserves and the market prices support.

*Every file:line reference above was verified against the codebase during this audit.*
