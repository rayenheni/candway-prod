# Candway Platform Analysis — Recruiter & Candidate, Market Readiness

> Status: analysis report · Date: 2026-08-15
> Scope: recruiter platform, candidate platform, end-to-end hiring workflow, frontend UX/polish, market-readiness verdict.

---

## 1. Executive Summary

Candway is a genuinely complete ATS on both sides — recruiter, candidate, AI interview, scoring, offers/e-sign, billing/credits, org portal, admin finance. Tenant isolation and AI security hardening are production-grade. However:

- **One critical business-flow bug**: completed AI interviews never advance the application stage (`app.status` stays `"invited"`), so the pipeline/funnel looks wrong after every interview.
- **7 confirmed silent navigation failures**: all bounce the user to `/dashboard` via the `*` catch-all.
- **~25 built-and-wired recruiter features are orphaned** (no sidebar entry).
- **Fabricated social proof and "coming soon" placeholders** exist in customer-facing pages.

**Verdict:** usable/demo-able for a happy-path pilot; **not ready for open public launch** until the blocking items below are fixed.

---

## 2. What Exists (the good — strengths)

### 2.1 Recruiter platform
- Job wizard (5 steps, rubric-linked), job CRUD, public job board with real company logos/verification.
- Campaigns: create → batch → CV upload → background AI analysis → candidate list → invites.
- Candidate search (facets, ranked, talent pool), AI interviews (rubric-driven), rubric/skill-tree builder with AI generation.
- Offers + DocuSign e-sign, background checks, EEO analytics, reports/analytics, team collaboration, re-engagement.
- Subscription/billing/credits (Sprint 19: S1–S10), KYB, org portal, admin finance dashboard.
- ~140 recruiter endpoints confirmed registered and wired to frontend services (verified in analysis).

### 2.2 Candidate platform
- Registration → onboarding → profile (real availability/salary/work-type/languages/relocation) → CV upload/analysis → job boards → apply → AI interview room (live scoring, proctoring, anti-gaming) → analysis page → offer e-sign.
- Invite flow end-to-end fixed (temp password in email, guest analysis access).

### 2.3 Hardening
- Company-scoped tenant isolation (`authz.py`, `tenant.py`).
- PII masking before any external AI call; AI output validation.
- Rubric-weighted deterministic CV scoring.
- Credit ledger with idempotency + optimistic locking.
- 128+ backend tests, 4 locales, SPA-only frontend (legacy HTML removed).

---

## 3. Critical Business-Flow Problem

### 3.1 Blocker: completed interviews don't advance the application stage
- `run_background_final_evaluation` (`backend/routers/ai_interview/evaluation.py:56-516`) marks the evaluation session `completed` but **never writes `app.status`**. The app stays `"invited"`.
- The only place that advances to `screening` is the manual endpoint `evaluate_final_interview` (`evaluation.py:748-749`) — but the frontend **never calls it** (`interview-room.tsx` navigates away via `goPostInterview()`).
- **Impact**: after a candidate finishes an interview the recruiter pipeline still shows "Invited"; the funnel under-counts; there's no visual "interview done" state without a manual status change.

### 3.2 Secondary flow issues
- **Backend status vocabularies disagree**:
  1. Display map: `recruiter_candidates/search.py:50-59`
  2. Funnel buckets: `recruiter_jobs.py:724-729`
  3. `ApplicationStatus` enum (`backend/enums.py:9-42`, 13 values) vs DB CHECK (`backend/models/ats/application.py:52`, 18 values) — enum is missing `analyzed`, `failed`, `active`, `analyzing`, `analysis_failed` (all 5 are DB-valid and written by the CV-analysis flow, but unrepresentable via the enum; they are not covered by the legacy aliases either).
  - Note: the candidate UI (`applications-tracker.tsx:31`) defines its own display keys (`in_review`/`interview`/`offered`) but **maps backend statuses into them** via `normalizeStatus` (`applications-tracker.tsx:91-92`), so this is a display-layer mapping — not a hard server mismatch — though it collapses several real statuses (`reviewed`/`analyzing`/`analyzed` → `in_review`) and loses fidelity.
- **Apply-time CV analysis bypasses the credit gate**: `run_cv_analysis` → `extract_cv_details`/`analyze_cv` is not wrapped in `require_credits("cv_analysis", 3)` (only `candidate/cv.py /analyze` is gated).
- **Per-turn chat scoring + final evaluation are not credit-gated** (deferred by design) → AI interviews can run at unlimited cost per company.
- **Background task session handling inconsistent**: `apply_to_job` passes the request-scoped `db` into a background worker (`candidate/jobs.py:527-539` via `safe_execute`) vs. the own-`SessionLocal` pattern used in `evaluation.py`.
- **Ownership model is clean**: company-scoped (`authz.py` `_recruiter_owns_application` etc.), `recruiter_id` retained only for attribution — matches the AGENTS.md constraint.

---

## 4. Frontend UX / Navigation Failures

### 4.1 Six confirmed silent navigation failures (all → `/dashboard` via catch-all `router.tsx:435`)
> Routes are registered as **relative paths under `/`** (`router.tsx:264-334`), so the real URLs are `/ghost-report`, `/background-checks/:id`, `/candidate-ranking`, `/campaigns`, `/campaigns/:id` — but the components navigate with a spurious `/recruiter/` prefix. (Correction to v1: this was verified against the actual route table.)
| Broken target | Where | Correct route |
|---|---|---|
| `/recruiter/ghost-report?app=` | `candidate-profile.tsx:175` | `/ghost-report` |
| `/recruiter/background-checks/{id}` | `background-checks.tsx:51` | `/background-checks/:id` |
| `/recruiter/candidate-ranking` | `candidate-profile.tsx:566` | `/candidate-ranking` |
| `/recruiter/campaigns` | `campaign-compare.tsx:96` | `/campaigns` |
| `/recruiter/campaigns/{id}` | `campaign-compare.tsx:183` | `/campaigns/:id` |
| `/assessments` (no route exists) | `candidate-profile.tsx:973` | remove button or add route |
| `/interviews/new?application_id=` (page reads `?appId=`) | `candidate-profile.tsx:294` | use `appId` param |

> Note: the interview-analysis breadcrumb/back link (`recruiter-interview-analysis.tsx:355,369`) uses `interviewId`, which is aliased to `appId` (`interviewId = appId` at line 261) — i.e. the application id. Since `/candidates/:id` is application-scoped, that link is actually **correct**, not broken. (Correction to v1 of this report.)

### 4.2 Orphaned features (built + wired, no sidebar entry)
Sidebar (`sidebar.tsx` recruiterNav 66-93) exposes ~10 of ~35 routes. Not reachable via nav:
Offers, Team, Billing, Copilot, Background Checks, Talent Pool, EEO, Email Templates, Skill Tree Library, Candidate Ranking, Chatbot Leads, JD Editor, Auto Job, Compare, Bias Analytics, Reports List, Bulk Invite, Re-engagement, Scoring Preview, Esign Offer, Calendar Settings.

### 4.3 Dead buttons / fake actions
- Notifications bell — no onClick (`topbar.tsx:196-198`).
- Marketplace Filters — no onClick (`marketplace.tsx:106-108`).
- Candidate-ranking Filters — toast only (`candidate-ranking.tsx:90`).
- Chatbot leads Contact/Assign/Dismiss — "Coming Soon" toasts.
- Background-check Approve/Flag/Rescreen — "Coming Soon" toasts.
- 2FA enable — "coming soon" toast; GitHub login — "coming soon" toast.
- Bias analytics "Export Report" — success toast, no export.

### 4.4 i18n & polish
- `nav.technical` / `nav.ab_testing` missing from all 4 dictionaries → rendered raw in admin sidebar (`sidebar.tsx:201,203`).
- 31 duplicate keys in `ar` (`recruiter.skillTreeDetail.*`) + 38 in `tn` (`recruiter.skillTreeCreate.*`) — source of build warnings.
- `ar`/`tn` have ~75–116 fewer keys than `en`/`fr` → silent English fallback.
- `nav.badge.today: '2 Today'` hardcoded with literal "2" in all locales.
- 5 `console.log('[DnD] ...')` debug lines in `pipeline-board.tsx:199-207` on every drag.

### 4.5 Fabricated / hardcoded data in customer-facing UI
- Landing "Trusted by 500+ hiring managers" + initials avatars (`landing-page.tsx:256-267`).
- Marketing `/pricing` `FALLBACK_PLANS` hardcoded prices (`pricing.tsx:9-32`); landing shows `99/149 TND` while `/pricing` shows `149/1430` — inconsistent.
- Marketplace course cards fabricated `reviews: 0`, `students: 0`, `trending: false` (`marketplace.tsx:14,29-41`).
- Dashboard stat cards hardcode `trend: 'up'` (`recruiter-dashboard.tsx:24,27`, `candidate-dashboard.tsx:59-80`).
- `VITE_DEMO_MODE` mock users/roles in `env.d.ts` — "Must be false in production."
- "being ported to our new React architecture" placeholder reachable via `/admin/permissions`, `/mentor/community`, `/mentor/profile`.

### 4.6 Misc UX
- Landing "Courses" links to protected `/courses` while marketing layout uses `/catalog` (anonymous users redirected to login).
- `role`/`email` deep-link params (`?role=recruiter`, `?email=`) ignored by `register.tsx` (no `useSearchParams`; `defaultValues.role='candidate'`) → every "Hire talent" CTA opens a candidate-preselected form.
- Native `window.prompt()`/`window.confirm()` in 4 pages (`kyb-manager.tsx:50`, `organizations.tsx:149`, `payment-proofs.tsx:83`, `skill-tree-detail.tsx:94`) instead of the toast/modal system.
- Landing mobile menu omits AR from language selector.

---

## 5. Market-Readiness Verdict

| Dimension | Score | Notes |
|---|---|---|
| Core hiring loop (happy path) | 7/10 | Works end-to-end for demo/pilot |
| Recruiter feature breadth | 9/10 | Complete modern ATS feature set |
| Candidate experience | 7/10 | Good, some rough edges |
| Navigation / findability | 4/10 | 7 silent bounces + 25 orphaned features |
| Polish / trust | 5/10 | Fabricated social proof, dead buttons, raw i18n keys |
| Monetization | 6/10 | Credit system solid; AI interview not credit-gated |
| Security / tenancy | 9/10 | Production-grade |
| **Overall market readiness** | **5/10** | **Pilot-ready, not launch-ready** |

**Ready to market for:** early-access / pilot customers on the happy path; AI-interview + rubric scoring as the differentiator.

**Not ready for open launch until blockers fixed** (see §6).

---

## 6. Suggested Priority Order

| # | Action | Impact | Effort |
|---|---|---|---|
| 1 | Advance `app.status` on interview completion (background eval) + align the 3 status vocabularies | **Blocker — fixes funnel/pipeline** | 1 day |
| 2 | Fix the 7 broken nav targets + interview-analysis breadcrumb id | **Blocker — trust** | 0.5 day |
| 3 | Wire or hide dead buttons; add sidebar entries for orphaned features (or intentionally remove) | High | 0.5 day |
| 4 | Remove fabricated social proof + "coming soon" marketing text; fix pricing inconsistency | High | 2 hr |
| 5 | i18n: dedupe ar/tn keys, add missing keys, remove console.logs | Medium | 2 hr |
| 6 | Credit-gate apply-time CV analysis; decide AI-interview pricing model | Business | 1 day |
| 7 | Replace native alert/confirm/prompt with toast/modal system | Medium | 0.5 day |
| 8 | Wire `role`/`email` params in register.tsx; point landing Courses at `/catalog` | Medium | 1 hr |

---

## 7. Evidence Index (key file references)

### Backend
- `backend/routers/ai_interview/evaluation.py:56-516` — background final evaluation (no `app.status` write); `:748-749` manual evaluate-final advances to `screening`.
- `backend/routers/ai_interview/chat.py:381-395` — interview start gate (`invited/interviewing/shortlisted`); `:704,1101` triggers background eval.
- `backend/routers/ai_interview/session.py:185` — `_ALLOWED_INTERVIEW_START_STATUSES`.
- `backend/routers/candidate/jobs.py:375-543` — apply flow; `:484-490` company fallback; `:527-539` background CV analysis with request-scoped db.
- `backend/routers/candidate/applications.py:112+` — `run_cv_analysis` status writes (`screening`/`analyzed`/`analysis_failed`).
- `backend/routers/recruiter_candidates/search.py:50-59` — display status map; `:87-89` ownership filter.
- `backend/routers/recruiter_jobs.py:724-729` — funnel buckets.
- `backend/routers/recruiter_candidates/scoring.py:1372-1551` — `/scores` endpoint.
- `backend/authz.py:85-190` — company-scoped ownership helpers.
- `backend/credit_service.py` — consume/rollback/grant/adjust/usage; `backend/dependencies.py:894-948` `require_credits`.
- `backend/models/ats/application.py:52` — status CHECK (18 values); `backend/enums.py:9-42` — `ApplicationStatus` enum (13 values; 5 DB-valid values unrepresentable: `analyzed`, `failed`, `active`, `analyzing`, `analysis_failed`).

### Frontend
- `frontend/src/app/router.tsx` — routes; `:435` `*` catch-all → `/dashboard`.
- `frontend/src/layouts/dashboard/sidebar.tsx:66-93` — recruiter nav (10 routes); `:201,203` missing i18n keys.
- `frontend/src/features/candidates/pages/candidate-profile.tsx:175,294,566,973` — broken nav targets.
- `frontend/src/features/recruiter/pages/background-checks.tsx:51`, `campaign-compare.tsx:96,183` — broken nav targets.
- `frontend/src/features/recruiter/pages/recruiter-interview-analysis.tsx:355,369` — breadcrumb id misuse.
- `frontend/src/features/candidate/pages/applications-tracker.tsx:31,91-92` — candidate display vocab + `normalizeStatus` mapping.
- `frontend/src/features/pipeline/pages/pipeline-board.tsx:199-207` — debug console.logs.
- `frontend/src/features/landing/pages/landing-page.tsx:256-267,890` — fabricated social proof, pricing inconsistency.
- `frontend/src/features/marketing/pages/pricing.tsx:9-32` — fallback hardcoded plans.
- `frontend/src/features/auth/pages/register.tsx:42` — ignores `role`/`email` params.
- `frontend/src/i18n/dictionaries.ts` — `recruiter.skillTreeDetail.*` block duplicated intra-locale in `ar` (~:3904 & :4155) and `tn` (~:5032 & :5416); `nav.technical`/`nav.ab_testing` missing from all locales.

---

## 8. Recommended Next Step

Start with **Priority #1** (interview-completion status advancement + status vocabulary alignment) and **Priority #2** (broken navigation targets). Both are low-risk, high-impact, and make the product demo-safe.