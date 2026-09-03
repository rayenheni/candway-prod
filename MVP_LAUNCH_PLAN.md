# Candway MVP Launch Plan

**Author:** CTO & Product Strategist  
**Goal:** First 10 paying customers in 30 days  
**Mantra:** Ship the hiring loop. Nothing else.

---

## 1. MVP Feature List

### CANDIDATE (7 features)

| # | Feature | What It Does | Existing Pages | Status |
|---|---|---|---|---|
| 1 | **Authentication** | Signup, login, logout, password reset, email/OTP verify, Google OAuth | `login.html`, `login-candidate.html`, `signup.html`, `forgot-password.html`, `reset-password.html`, `verify-email.html`, `verify-otp.html`, `google-callback.html` | ✅ Ready |
| 2 | **Profile** | Name, headline, bio, skills, links, avatar | `profile.html`, `view-profile.html` | ✅ Ready |
| 3 | **CV Upload** | Upload PDF, parse text, store | `cv-upload.html`, `documents.html` | ✅ Ready |
| 4 | **AI CV Analysis** | Extract skills, detect role, generate summary + review | `cv-review.html`, `cv-builder.html` | ✅ Ready |
| 5 | **Job Applications** | Browse jobs, search/filter, apply, track status | `jobs.html` (candidate), `applications.html`, `saved-jobs.html` | ✅ Ready |
| 6 | **AI Interview** | Generate questions, record answers, submit, proctoring | `interview.html`, `interviews.html` | ✅ Ready |
| 7 | **Results** | Per-question scores, feedback, AI analysis, PDF download | `interview-analysis.html` | ✅ Ready |

### RECRUITER (7 features)

| # | Feature | What It Does | Existing Pages | Status |
|---|---|---|---|---|
| 1 | **Company Profile** | Company name, logo, description | `settings.html` (recruiter) | ✅ Ready |
| 2 | **Post Job** | Title, description, skills, location, type, salary, activate | `jobs.html`, `post-job.html`, `auto-job.html` | ✅ Ready |
| 3 | **Candidate List** | View applicants, filter, search, sort by score, view profile | `candidates.html`, `candidate-profile.html` | ✅ Ready |
| 4 | **AI Match Scores** | CV-job match %, skill gap, score breakdown | `scoring-preview.html` | ✅ Ready |
| 5 | **Candidate Ranking** | Rank candidates by AI score, adjust weights | `candidate-ranking.html`, `comparison.html` | ✅ Ready |
| 6 | **Hiring Pipeline** | Move candidates through stages (applied → screening → interview → offer → hired → rejected) | `pipeline.html` | ✅ Ready |
| 7 | **Hiring Decision** | Approve/reject with reason, notes, notify candidate | `pipeline.html`, `offers.html` | ✅ Ready |

### ADMIN (3 features)

| # | Feature | What It Does | Existing Pages | Status |
|---|---|---|---|---|
| 1 | **Users** | List users, search/filter, activate/deactivate | `users.html` | ✅ Ready |
| 2 | **Jobs** | List all jobs, moderate, activate/deactivate | `jobs.html` (admin) | ✅ Ready |
| 3 | **Basic Analytics** | Total users, jobs, applications, interviews, hires | `dashboard.html`, `analytics.html` | ✅ Ready |

### AI (3 features)

| # | Feature | What It Does | Existing Service | Status |
|---|---|---|---|---|
| 1 | **CV Analysis** | Extract skills from PDF, detect role, generate summary | `backend/ai/cv_analysis.py` | ✅ Ready |
| 2 | **Interview Analysis** | Score answers, give feedback, compute final score | `backend/ai/interview_scoring.py` | ✅ Ready |
| 3 | **Match Scoring** | Score candidate against job requirements | `backend/ai/scoring_engine.py` | ✅ Ready |

### Total MVP: 20 features, built from existing code, ZERO new features.

---

## 2. Features To REMOVE

These files/pages should be **deleted** from the codebase before launch. They add noise, maintenance burden, and confusion.

### Delete Entire Module: Mentor/LMS (11 pages)
`pages/mentor/` — all files (mentor module = separate product)

### Delete Duplicate Pages (3 pages)
| File | Reason |
|---|---|
| `pages/recruiter/compare.html` | Duplicate of `comparison.html` |
| `pages/recruiter/analytics-dashboard.html` | Duplicate of `analytics.html` |
| `pages/recruiter/report-builder.html` | Custom report builder — over-engineered for MVP |

### Delete Non-MVP Recruiter Pages (9 pages)
| File | Reason |
|---|---|
| `pages/recruiter/sourcing.html` | AI sourcing — not in MVP |
| `pages/recruiter/campaigns.html` | Campaign management — not in MVP |
| `pages/recruiter/campaigns-view.html` | Campaign detail — not in MVP |
| `pages/recruiter/reengagement.html` | Re-engagement — not in MVP |
| `pages/recruiter/ghost-report.html` | Ghost reporting — not in MVP |
| `pages/recruiter/skill-tree-create.html` | Skill trees — not in MVP |
| `pages/recruiter/bulk-invite.html` | Bulk invite campaigns — not in MVP |
| `pages/recruiter/copilot-full.html` | AI copilot — not in MVP |
| `pages/recruiter/email-templates.html` | Email templates — not in MVP |
| `pages/auth/signup-mentor.html` | Mentor — not in MVP |
| `pages/auth/login-mentor.html` | Mentor — not in MVP |

### Delete Non-MVP Admin Pages (16 pages)
| File | Reason |
|---|---|
| `pages/admin/payments.html` | Treasury — not in MVP |
| `pages/admin/subscriptions.html` | Plan management — not in MVP |
| `pages/admin/support.html` | Support tickets — not in MVP |
| `pages/admin/settings.html` | System settings — not in MVP |
| `pages/admin/content.html` | CMS — not in MVP |
| `pages/admin/courses.html` | Courses governance — not in MVP |
| `pages/admin/categories.html` | Category management — not in MVP |
| `pages/admin/announcements.html` | Announcements — not in MVP |
| `pages/admin/opportunities.html` | Opportunities — not in MVP |
| `pages/admin/marketing.html` | Marketing campaigns — not in MVP |
| `pages/admin/invoices.html` | Invoicing — not in MVP |
| `pages/admin/recruiter-usage.html` | Usage analytics — not in MVP |
| `pages/admin/prompt-management.html` | AI prompt management — not in MVP |
| `pages/admin/rubrics.html` | Rubric management — not in MVP |
| `pages/admin/rubric-builder.html` | Rubric builder — not in MVP |
| `pages/admin/ab-testing.html` | A/B testing — not in MVP |
| `pages/admin/ai_sales.html` | AI sales — not in MVP |
| `pages/admin/verifications.html` | Company verification — not in MVP |
| `pages/admin/technical.html` | Technical settings — not in MVP |

### Delete Non-MVP API Routers (keep backend code but remove from router registration)
| Router | Reason |
|---|---|
| `bot.router` | Slack/Teams integration |
| `copilot_admin.router` | Admin AI copilot |
| `ai_sales.router` | AI sales automation |
| `mentor.router` | Mentor/LMS module |
| `courses.router` | Courses/LMS module |
| `career.router` | Career roadmap |
| `payments.router` | Payment processing (manual flow — not ready) |
| `unsubscribe.router` | Email unsubscribe (premature) |
| `linkedin.router` | LinkedIn integration (premature) |
| `calendar.router` | Calendar sync (not MVP) |
| `bot.router` | Chatbot integrations (premature) |
| `assessment_webhooks.router` | 3rd party assessments (not MVP) |
| `scoring_weights_router` | Scoring A/B testing (premature) |
| `prompt_management.router` | Prompt management (admin tool) |
| `recruiter_reengagement.router` | Re-engagement campaigns |
| `recruiter_skill_trees.router` | Skill trees |
| `recruiter_sourcing.router` | AI sourcing |
| `recruiter_collaboration.router` | Team collab (not MVP) |
| `recruiter_desktop.router` | Desktop app (premature) |
| `recruiter_enhancements.router` | Enhancements (premature) |
| `copilot.router` | Recruiter copilot (not MVP) |

### Delete Non-MVP Database Models
Drop all models not listed in Section 4 (keep only 11 tables). ~85+ models to drop/ignore.

---

## 3. Features To HIDE (keep code, remove from navigation)

These features exist and work, but should be **delinked from the UI** so users don't see them. Keep the code — we may re-enable in Phase 2.

| Feature | Where | Reason |
|---|---|---|
| Onboarding wizard (multi-step) | Candidate sidebar | Replaces with simple redirect to profile |
| Saved Jobs | Candidate sidebar | Nice-to-have, not core |
| Assessments (skill validation) | Candidate sidebar | Not in MVP |
| Learning / Marketplace | Candidate sidebar | LMS module deferred |
| Messages | Candidate sidebar | Not in MVP |
| E-Signature | Candidate sidebar | Post-offer feature, Phase 2 |
| Certificate | Candidate sidebar | LMS deferred |
| Profile Visitors | Candidate sidebar | Analytics, not MVP |
| Subscription | Candidate sidebar | Monetization deferred |
| EEO Form | Candidate sidebar | Compliance, Phase 2 |
| Pricing page | Landing page header | Monetization deferred |
| Courses page | Landing page header | LMS deferred |
| Blog pages | Landing page header | Content marketing deferred |
| Opportunities page | Landing page header | Not MVP |
| Talent Pool | Recruiter sidebar | Nice-to-have, not core |
| Skill Trees | Recruiter sidebar | Advanced feature |
| Assessments | Recruiter sidebar | 3rd party integration deferred |
| Background Checks | Recruiter sidebar | Phase 3 |
| EEO Dashboard | Recruiter sidebar | Phase 2 |
| JD Bias Analytics | Recruiter sidebar | Phase 2 |
| Bot Settings | Recruiter sidebar | Phase 2 |
| Calendar Settings | Recruiter sidebar | Phase 2 |
| Team Management | Recruiter sidebar | Phase 2 |
| Billing | Recruiter sidebar | Phase 2 |
| Integrations | Recruiter sidebar | Phase 2 |
| Reports | Recruiter sidebar | Pre-built reports only, hide custom |
| Re-engagement | Recruiter sidebar | Phase 2 |
| Chatbot Leads | Recruiter sidebar | Phase 2 |
| Copilot | Recruiter sidebar | Phase 2 |
| Campaigns | Recruiter sidebar | Phase 2 |
| Messages | Recruiter sidebar | Phase 2 |

---

## 4. Database Tables Needed

### 11 tables, zero more.

```
users              → Auth, roles, basic identity
candidate_profiles → Profile data (headline, bio, skills, links)
companies          → Company name, logo, slug
company_members    → Links recruiter users to company
jobs               → Job listings (title, desc, skills, location, type, salary)
applications       → Applications (links candidate→job, status pipeline)
cv_documents       → CV files, extracted text, AI analysis, skills
evaluation_sessions → Interview sessions (state, questions, log, time)
interview_turns    → Individual Q&A turns with scores
evaluation_results → Final scores, verdict, breakdown
verdicts           → Hiring decisions (advance/reject/hire)
```

**Storage decisions:**
- Skills: stored as JSON in `candidate_profiles.skills` and `cv_documents.extracted_skills` — no separate skill table
- Pipeline stages: stored as `applications.status` string — no separate pipeline_stages table
- Score breakdown: stored as JSON in `evaluation_results.score_breakdown` — no RubricScoringDetail table
- Interview log: stored as JSON in `evaluation_sessions.interview_log` — no separate log table
- CV analysis: stored as JSON in `cv_documents.analysis_json` — no separate analysis tables
- Audit: enabled via DB triggers or application-level logging — no separate audit_log tables needed for MVP

---

## 5. API Endpoints Needed

### 89 endpoints, zero new ones. All exist today.

### Candidate Auth (11)
```
POST   /api/v1/auth/signup
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/verify-otp
POST   /api/v1/auth/resend-otp
GET    /api/v1/auth/verify-email/{token}
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
POST   /api/v1/auth/guest-login
```

### Candidate Profile (6)
```
GET    /api/v1/candidate/me
GET    /api/v1/candidate/profile
PUT    /api/v1/candidate/profile
GET    /api/v1/candidate/profile-data
GET    /api/v1/candidate/profile/comprehensive
POST   /api/v1/candidate/avatar
```

### CV & AI Analysis (5)
```
POST   /api/v1/candidate/upload-cv
POST   /api/v1/candidate/analyze
GET    /api/v1/candidate/cv-review
GET    /api/v1/candidate/cv-data
PUT    /api/v1/candidate/builder-data
```

### Job Applications (11)
```
GET    /api/v1/jobs/                         (public job board)
POST   /api/v1/candidate/jobs/{id}/apply
GET    /api/v1/candidate/jobs/matches
GET    /api/v1/candidate/invitations
POST   /api/v1/candidate/invitations/decline
GET    /api/v1/candidate/applications/me
GET    /api/v1/candidate/applications/me/history
GET    /api/v1/candidate/current-application
GET    /api/v1/candidate/applications/{id}
GET    /api/v1/candidate/dashboard
GET    /api/v1/candidate/saved-jobs
```

### AI Interview (10)
```
POST   /api/v1/ai/generate-interview
POST   /api/v1/ai/interview/chat
POST   /api/v1/ai/interview/pause
POST   /api/v1/ai/interview/resume
POST   /api/v1/ai/interview/evaluate-final
GET    /api/v1/ai/interview/time
POST   /api/v1/ai/interview/sync-proctoring
POST   /api/v1/candidate/reset-interview
GET    /api/v1/candidate/interviews/history
GET    /api/v1/candidate/interviews/{app_id}/analysis
```

### Recruiter Company (2)
```
GET    /api/v1/recruiter/settings
POST   /api/v1/recruiter/settings
```

### Recruiter Jobs (5)
```
POST   /api/v1/recruiter/jobs
GET    /api/v1/recruiter/jobs/my
POST   /api/v1/recruiter/generate-job
PATCH  /api/v1/recruiter/jobs/{id}/category
DELETE /api/v1/recruiter/jobs/{id}
```

### Recruiter Candidates (11)
```
GET    /api/v1/recruiter/candidates/list
GET    /api/v1/recruiter/candidates/search
GET    /api/v1/recruiter/candidates/search/facets
GET    /api/v1/recruiter/applications
GET    /api/v1/recruiter/applications/{id}
PUT    /api/v1/recruiter/applications/{id}/status
PUT    /api/v1/recruiter/applications/{id}/notes
PATCH  /api/v1/recruiter/applications/{id}
POST   /api/v1/recruiter/applications/bulk-update
POST   /api/v1/recruiter/applications/bulk-delete
GET    /api/v1/recruiter/applications/{id}/scores
```

### Recruiter Dashboard (5)
```
GET    /api/v1/recruiter/dashboard/stats
GET    /api/v1/recruiter/dashboard/recent
GET    /api/v1/recruiter/dashboard/recommendations
GET    /api/v1/recruiter/analytics-dashboard
POST   /api/v1/hiring/candidate/{id}/chat
```

### Admin (11)
```
GET    /api/v1/admin/users
DELETE /api/v1/admin/users/{id}
GET    /api/v1/admin/users/usage
GET    /api/v1/admin/jobs
DELETE /api/v1/admin/jobs/{id}
GET    /api/v1/admin/stats
GET    /api/v1/admin/activity
GET    /api/v1/admin/analytics/overview
GET    /api/v1/admin/analytics/growth
GET    /api/v1/admin/analytics/revenue
GET    /api/v1/admin/analytics/ai
```

### Total: 89 endpoints, 0 new, 0 modified.

---

## 6. 30-Day Launch Plan

### Week 1: FOUNDATION (Days 1-7)
**Goal:** Production-ready infra, security fixes, database cleanup.

| Day | Task |
|-----|------|
| **1** | Set up production MySQL 8.0 + Redis. Migrate from SQLite. Wire Alembic `upgrade head` at startup. |
| **2** | Set up single AI provider (Groq). Remove Gemini/DeepSeek/Ollama cascade. Sign DPA. Anonymize PII before API calls. |
| **3** | Fix encryption key: env-var only, remove dev fallback. Rotate key if one existed. |
| **4** | Fix CSRF on all mutation endpoints. Audit all 89 MVP endpoints. |
| **5** | Fix XSS: audit all 75 innerHTML instances for MVP pages, add DOMPurify to the 3 missing pages. |
| **6** | Enable RateLimitMiddleware. Set per-user limits (60/min, 600/hr). |
| **7** | Deploy staging environment. All 89 endpoints smoke-tested. |

### Week 2: CODE CLEANUP (Days 8-14)
**Goal:** Remove non-MVP code, hide non-MVP UI, simplify navigation.

| Day | Task |
|-----|------|
| **8** | **DELETE** mentor module (`pages/mentor/`), duplicate pages, non-MVP recruiter pages, non-MVP admin pages. |
| **9** | **DELETE** non-MVP routers from `app.py` router list. Comment out, don't delete files yet. |
| **10** | **HIDE** non-MVP sidebar links in candidate mode. Update `js/components.js`, `js/admin-components.js`. |
| **11** | **HIDE** non-MVP sidebar links in recruiter mode. |
| **12** | **HIDE** non-MVP admin sidebar links, public header links (courses, blog, pricing). |
| **13** | Remove deprecated DB columns from models (keep table definitions minimal). |
| **14** | Full navigation audit: test all flows as candidate, recruiter, admin. No broken links. |

### Week 3: UX POLISH (Days 15-21)
**Goal:** Ship ready for first 10 paying customers.

| Day | Task |
|-----|------|
| **15** | Add loading states (skeleton loaders) to dashboard, candidate list, job board. |
| **16** | Add empty states to all lists (no applications yet, no candidates yet, no jobs yet). |
| **17** | Add error states to all API-dependent pages. Silent failures → user-friendly messages. |
| **18** | Fix candidate onboarding flow: signup → profile → CV upload → AI analysis → job board. |
| **19** | Fix recruiter onboarding flow: signup → company profile → post job → see candidates. |
| **20** | Mobile responsiveness: test sidebar, dashboard, job board, interview on mobile. Fix critical breaks. |
| **21** | Full walkthrough test: candidate applies, takes interview, sees results. Recruiter scores, pipelines, decides. Admin monitors. |

### Week 4: TEST + LAUNCH (Days 22-30)
**Goal:** Launch to first 10 paying companies.

| Day | Task |
|-----|------|
| **22** | Write auth tests: signup, login, logout, password reset, email verify. (5 tests) |
| **23** | Write candidate tests: profile CRUD, CV upload, apply, interview, results. (10 tests) |
| **24** | Write recruiter tests: post job, list candidates, rank, pipeline, decide. (10 tests) |
| **25** | Write AI tests: CV analysis, interview scoring, match scoring. (5 tests) |
| **26** | Load test with 50 concurrent users. Fix bottlenecks. |
| **27** | Security scan: run automated scanner, fix findings. Final audit of P0 items. |
| **28** | Set up CI/CD (GitHub Actions): lint → test → deploy. |
| **29** | Prepare onboarding docs for first 10 companies. Create 1-page quickstart for recruiters. |
| **30** | **LAUNCH.** Deploy to production. Onboard first 10 paying customers. |

---

## 7. Weekly Sprint Breakdown

### Sprint 1: "Hard Hat" (Days 1-7)
- Production infra (MySQL, Redis, Groq)
- Security fixes (encryption, CSRF, XSS, rate limiting)
- Alembic migration
- Staging deploy

### Sprint 2: "Feature Triage" (Days 8-14)
- Delete all non-MVP surface area
- Hide non-MVP navigation
- Simplify DB models
- Navigation audit

### Sprint 3: "UX Finish" (Days 15-21)
- Loading states
- Empty states
- Error states
- Onboarding flows
- Mobile critical fixes

### Sprint 4: "Ship It" (Days 22-30)
- 30 tests minimum
- Load test
- Security scan
- CI/CD
- Documentation
- **LAUNCH**

---

## 8. Daily Tasks for Launch Week (Week 4)

| Day | Candidate Team | Recruiter Team | AI/Infra Team |
|-----|---|---|---|
| **22** | Test: signup + login + logout + password reset | Test: company profile + post job | Set up Groq DPA + anonymization |
| **23** | Test: profile edit + CV upload + CV analysis | Test: candidate list + search + filter | Implement CV analysis test |
| **24** | Test: job search + apply + application tracking | Test: rank candidates + pipeline + decision | Implement interview scoring test |
| **25** | Test: AI interview + results + analysis | Test: full hiring loop (post → review → decide) | Implement match scoring test |
| **26** | Fix bugs found in testing | Fix bugs found in testing | Load test 50 concurrent users |
| **27** | UX polish pass | UX polish pass | Security scan + fix findings |
| **28** | Onboard 2 beta companies | Onboard 2 beta companies | CI/CD pipeline |
| **29** | Fix beta feedback | Fix beta feedback | Monitoring + alerting |
| **30** | **LAUNCH** | **LAUNCH** | **LAUNCH** |

---

## Summary

| Item | MVP | Current Codebase | Savings |
|---|---|---|---|
| Pages | **29** | ~130 | ~100 removed/hidden |
| API Endpoints | **89** | ~300+ | ~210+ disabled |
| DB Tables | **11** | ~105 | ~94 dropped |
| AI Providers | **1** (Groq) | 7 | 6 removed |
| Features | **20** | ~80+ | ~60+ deferred |
| Team Focus | ✅ Single | ❌ Scattered | Laser focus |

**The MVP is already built. It's buried under 100 extra pages, 90 extra tables, and 200 extra endpoints. Our job is not to build — it's to excavate.**

**Ship 29 pages. Delete or hide the other 100. Launch in 30 days.**
