# Candway — Complete Product Audit

**Audited by:** Lead PM / CTO / UX Architect / AI Systems Designer  
**Date:** June 21, 2026  
**Platform:** Candway AI Hiring Ecosystem  
**Codebase:** ~130+ HTML pages, ~67 JS files, ~105 DB models, ~300+ API endpoints, 7+ AI providers

---

## 1. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | Python 3.9+, FastAPI, Uvicorn/Gunicorn | Single-file router pattern |
| ORM | SQLAlchemy 2.0 with Alembic | ~105 models |
| Database | MySQL 8.0 (prod), SQLite (dev) | |
| Cache | Redis 5.x | Rate limiting, token blacklist, session |
| Frontend | Vanilla JS, server-rendered HTML, Tailwind CSS | No SPA framework (React/Vue/Angular) |
| Auth | JWT (python-jose), bcrypt, CSRF middleware | Cookie + Bearer |
| AI (Primary) | Groq (Llama 3) | Low-latency inference |
| AI (Secondary) | Google Gemini | Cascade fallback |
| AI (Tertiary) | DeepSeek | Third fallback |
| AI (Local) | Ollama | Self-hosted option |
| Monitoring | Prometheus, Sentry | Metrics + error tracking |
| Infra | Docker, Nginx, systemd | Gunicorn workers |

---

## 2. Complete Feature Inventory

### 2.1 CANDIDATE MODULE (27 pages, ~15 API routers)

| Feature | Status | Completeness | Issues |
|---|---|---|---|
| **Authentication** | ✅ Done | Login, signup (3-step), forgot/reset password, email verify, OTP, Google OAuth, role-specific login pages | i18n gaps on some pages |
| **Dashboard** | ✅ Done | Stats (profile strength, job matches, interviews, course progress), skill graph (Chart.js), activity feed, AI insights panel, dark/light theme | No skeleton loaders for dynamic data |
| **Profile Management** | ✅ Done | Tabbed: Personal Info, Skills, Experience, Education, Certifications, AI Analysis | Profile completion ring animation timing off |
| **CV Builder** | ✅ Done | Drag-and-drop builder, template selection, AI content suggestions, PDF export | Needs more templates |
| **CV Review** | ✅ Done | AI-powered CV review, grade ring, improvement suggestions | Scoring accuracy concerns |
| **CV Selection** | ✅ Done | Browse/select CV templates | |
| **Document Management** | ✅ Done | Upload/download/delete, categorization, verification badge | |
| **AI Interview** | ✅ Done | Video/audio controls, question display, 30-min timer, answer recording, submit, proctoring | Score visible in real-time (UX issue), interview reset trap (3 resets = permanent lockout) |
| **Interview History** | ✅ Done | Past interviews list, status badges, score summary, replay | |
| **Interview Analysis** | ✅ Done | AI scores per competency, transcript, feedback, improvement tips | |
| **Job Board** | ✅ Done | Search, filter (location, remote, skills, salary), save/apply | |
| **Job Applications** | ✅ Done | Full tracking with status pipeline, timeline | |
| **Learning Dashboard** | ✅ Done | Course progress, recommended, enrolled list, achievement badges | |
| **Course Player** | ✅ Done | Video player, lesson sidebar, progress tracking, full-screen layout | |
| **Skill Assessments** | ✅ Done | Top skills display, assessment cards, score rings | |
| **E-Signature** | ✅ Done | PDF preview, signature field, sign button | |
| **Messaging** | ✅ Done | Conversation list, chat view, send message, file attachment | |
| **Subscription** | ✅ Done | Current plan, upgrade/downgrade, payment history | Manual payment approval only |
| **Settings** | ✅ Done | Email/password change, notification prefs, privacy, delete account, theme | |
| **EEO Form** | ✅ Done | Voluntary diversity info | |
| **Onboarding Wizard** | ✅ Done | Multi-step: profile setup, skill selection, preferences, goal setting | |
| **Profile Visitors** | ✅ Done | Visitor list with timestamps | |
| **Career Roadmap** | ✅ Done | AI-generated career roadmap | Nice-to-have, not core |
| **Certificate** | ✅ Done | Certificate of completion for courses | |

### 2.2 RECRUITER MODULE (43 pages, ~20 API routers)

| Feature | Status | Completeness | Issues |
|---|---|---|---|
| **Dashboard** | ✅ Done | KPI row (active jobs, total candidates, interviews, hires, avg score), pipeline graph, recent candidates, quick actions | |
| **Job Management** | ✅ Done | CRUD, status toggle, duplicate, publish/unpublish, candidate count | |
| **Post Job** | ✅ Done | Title, company, location, type, salary range, description, requirements, skills tags | |
| **Auto Job (AI)** | ✅ Done | Enter title + skills, AI generates full JD | |
| **Candidate List** | ✅ Done | Search, filter by job/stage/score/location, bulk actions, CSV export | |
| **Candidate Profile** | ✅ Done | AI score, skill graph, work history, education, interview results, move-to-stage buttons | |
| **Candidate Ranking** | ✅ Done | Multi-dimensional scoring, weight sliders (CV/Interview/Rubric/AI), A/B test weights, export | |
| **Pipeline (Kanban)** | ✅ Done | Drag-and-drop stages: Sourced → Applied → Screening → Interview → Offer → Hired → Rejected | |
| **Offer Management** | ✅ Done | Offer letter composer, status tracking, e-sign tracking | |
| **Interview Management** | ✅ Done | Scheduled/pending/completed, calendar view, reschedule/cancel | |
| **Interview Analysis** | ✅ Done | AI summary, competency scores, comparison to job requirements | |
| **Talent Pool** | ✅ Done | Saved collections, add candidates, team share, notes | |
| **AI Sourcing** | ✅ Done | Search by skills/location/experience, AI candidate recommendations | |
| **Skill Trees** | ✅ Done | Create, view, list visualization, matching candidates | |
| **Scoring Preview** | ✅ Done | See how candidates are scored, adjust weights | |
| **Reports Dashboard** | ✅ Done | Hiring funnel, source effectiveness, time-to-hire, diversity | |
| **Custom Report Builder** | ✅ Done | Drag-and-drop metrics, filters, date range, save/share/schedule | |
| **Re-engagement** | ✅ Done | Dormant candidates, bulk email campaign, templates | |
| **Team Management** | ✅ Done | Members, roles/permissions, invite, activity log | |
| **Settings** | ✅ Done | Profile, billing, integrations, notification prefs, API keys | |
| **Integrations** | ✅ Done | ATS, LinkedIn (OAuth) | |
| **Campaign Manager** | ✅ Done | Bulk invite (CSV upload, preview, email templates, send), analytics | |
| **Email Templates** | ✅ Done | Template list + editor, restore defaults, create new | |
| **Background Checks** | ✅ Done | FCRA-compliant, pre-adverse/final adverse action modal | |
| **EEO Dashboard** | ✅ Done | OFCCP compliance dashboard, diversity analytics | |
| **JD Bias Analytics** | ✅ Done | Inclusivity metrics across jobs, bias scores | |
| **Bot Settings** | ✅ Done | Slack + Microsoft Teams integration, commands, status | |
| **Calendar Sync** | ✅ Done | Google Calendar + Outlook OAuth, sync toggle | |
| **Chatbot Leads** | ✅ Done | Filter by days/stage, search by role | |
| **Candidate Comparison** | ✅ Done | Side-by-side radar charts, winner card, PDF export | |
| **Recruiter Copilot** | ✅ Done | AI chat with preset buttons (Find Candidates, Analytics) | |
| **Billing** | ✅ Done | Billing info, payment methods, invoice history | Manual payment flow |
| **Assessments** | ✅ Done | Create/send/manage assessments | |
| **Onboarding** | ✅ Done | Setup wizard for new recruiters | |

### 2.3 ADMIN MODULE (23 pages, ~5 API routers)

| Feature | Status | Completeness | Issues |
|---|---|---|---|
| **Dashboard** | ✅ Done | KPI stat cards, Chart.js graphs, recent activity, quick actions | |
| **User Management** | ✅ Done | Full CRUD, sort/filter, role badges, permissions, bulk actions | `manage_marketing` permission missing from ALLOWED_PERMISSIONS |
| **Job Management** | ✅ Done | Job table, status toggles, approve/reject, job editor modal | |
| **Analytics** | ✅ Done | User growth, revenue, engagement, date range picker | |
| **Verifications** | ✅ Done | Company verification, document preview, approve/reject | |
| **Subscriptions** | ✅ Done | Plan CRUD (Free/Pro/Premium), subscriber count, revenue | |
| **Support** | ✅ Done | Ticket list + detail + reply form, file attach | |
| **Settings** | ✅ Done | Tabbed: General, Security, Email, API Keys, AI Config, Localization, Maintenance | Dev URLs hardcoded |
| **Rubrics Management** | ✅ Done | Rubric listing, CRUD, preview modal | |
| **Rubric Builder** | ✅ Done | Drag-and-drop builder, criteria sections, weight sliders, live preview | |
| **Payments** | ✅ Done | Transactions table, filters, invoice generation, refund | No Stripe/PayPal integration |
| **Courses Governance** | ✅ Done | Course cards, pending/approved/reported tabs | |
| **Categories** | ✅ Done | Hierarchical tree view, drag-to-reorder | |
| **Content Manager (CMS)** | ✅ Done | Rich text editor (Quill.js), page management | |
| **Announcements** | ✅ Done | Create form, scheduled publish, target audience | |
| **Invoicing** | ✅ Done | Invoice table, status, download PDF, mark paid | |
| **Marketing** | ✅ Done | Campaign table, email templates, promo codes | |
| **Prompt Management** | ✅ Done | AI prompt templates management | |
| **A/B Testing** | ✅ Done | Experiment management for platform features | |
| **AI Sales** | ✅ Done | AI sales agent configuration | Premature feature |
| **Technical Settings** | ✅ Done | System technical configuration | |

### 2.4 AI / INTELLIGENCE LAYER

| Component | Status | Details |
|---|---|---|
| **CV Analysis** | ✅ Done | Skill extraction, embedding generation, role detection |
| **Candidate Summary** | ✅ Done | AI-generated summary from CV + interview |
| **Match Scoring** | ✅ Done | Rubric-based scoring against job requirements |
| **Explainable Scores** | ✅ Done | Score breakdown by criterion, evidence quotes |
| **Interview Analysis** | ✅ Done | Per-turn scoring, feedback, reasoning |
| **Skill Detection** | ✅ Done | From CV text, with evidence sentences |
| **Candidate Ranking** | ✅ Done | Multi-dimensional with configurable weights |
| **Calibration** | ✅ Done | Pre-interview calibration questions |
| **Drift Monitoring** | ✅ Done | Score drift detection over time |
| **A/B Testing** | ✅ Done | Scoring variant experiments |
| **JD Bias Detection** | ✅ Done | Bias analysis in job descriptions |
| **AI Sales Bot** | ✅ Done | Automated sales lead generation |
| **Career Chatbot** | ✅ Done | Conversational career guidance |
| **Re-engagement Engine** | ✅ Done | Dormant candidate re-activation |
| **Entity Enrichment** | ✅ Done | Entity extraction from text |
| **Prompt Testing** | ✅ Done | Prompt variant testing framework |
| **Proctoring** | ✅ Done | Proctoring violation detection |

### 2.5 MENTOR / LMS MODULE (12 pages)

| Feature | Status | Notes |
|---|---|---|
| Dashboard | ✅ Done | Stats, analytics, sidebar |
| Course Management | ✅ Done | CRUD, status, student count |
| Course Creator | ✅ Done | Module/lesson builder |
| Student Management | ✅ Done | Progress tracking, messaging |
| Wallet & Earnings | ✅ Done | Balance, payout history |
| Community Forum | ✅ Done | Discussion threads, Q&A |

---

## 3. Duplicate / Unnecessary Features

| Feature | Issue | Recommendation |
|---|---|---|
| **LMS / Mentor Platform** | Complete course marketplace with lessons, quizzes, certificates — a separate product (Candway Academy) embedded in the hiring platform. 12+ pages, 20+ DB models, significant maintenance burden. | **Spin off** as a separate product. Keep only "skill assessments" and "learning recommendations" within core hiring. |
| **AI Sales Bot** | Premature. Generates sales leads from web scraping. No paying customers to automate sales for. | **Remove** until 50+ paying recruiters exist. |
| **A/B Testing System** | 7+ DB models, complex experiment management UI. Useful but over-engineered for MVP. | **Simplify** to basic score comparison view. Remove experiment management UI. |
| **Prompt Management UI** | Admin UI for editing AI prompts. Admin concern, not product feature. | **Keep backend** but remove dedicated admin page. Use env vars/config files. |
| **Career Roadmap** | AI generates learning roadmaps for candidates. Nice-to-have, not core hiring value prop. | **Defer** to Phase 3. |
| **Bot Integrations (Slack/Teams)** | Slack + Teams bot with custom slash commands. Premature when platform hasn't launched. | **Defer** to Phase 2 or 3. |
| **Custom Report Builder** | Drag-and-drop report builder with scheduling. Over-engineered for MVP. | **Replace** with 5-10 pre-built reports in Phase 1. Add custom builder in Phase 2. |
| **Ghost Report / Comparison** | Professional evaluation report with print layout. Advanced feature. | **Defer** to Phase 2. |
| **Multiple AI Provider Cascade** | Groq → Gemini → DeepSeek → Ollama. PII sent to all three without DPAs. | **Single provider** (Groq) for MVP with clear DPA. Add fallback in Phase 2. |
| **Duplicate Score Fields** | `Application.analysis_json`, `Application.cv_text_anonymized`, `Application.declared_role` exist alongside `CvDocument` equivalents. | **Migrate** to CvDocument canonical source. Drop deprecated columns. |

---

## 4. MVP Scope (Phase 1 — Ship in 8-12 weeks)

### Core Principle: Ship the smallest hiring loop that demonstrates value.

**Candidate:** Auth → Profile → CV Upload → AI Analysis → Job Apply → AI Interview → Results  
**Recruiter:** Signup → Company Profile → Post Job → Review Candidates → AI Scoring → Interview → Hiring Decision  
**Admin:** User Management → Job Moderation → Basic Analytics  
**AI:** CV Analysis → Match Scoring → Interview Analysis → Candidate Ranking

### Phase 1 Features (KEEP)

| Module | Features | Pages | API Routes |
|---|---|---|---|
| **Auth** | Email/password login, signup, password reset, role-based (candidate/recruiter/admin) | 8 | ~10 |
| **Candidate Profile** | Personal info, skills (manual entry), CV upload (PDF parse), basic profile view | 3 | ~8 |
| **Candidate Dashboard** | Stats, recent applications, AI score summary, saved jobs | 1 | ~5 |
| **Job Board** | Search, filter, view, apply (with CV) | 3 | ~6 |
| **AI Interview** | 5-7 questions (text/audio), 30-min timer, basic scoring, results view | 3 | ~8 |
| **Applications** | Track status (pending/screening/interview/offer/hired/rejected) | 1 | ~5 |
| **Recruiter Signup** | Company profile setup, invite team members | 2 | ~5 |
| **Post Job** | Title, description, skills, requirements, activate/deactivate | 2 | ~6 |
| **Candidate List** | View applicants, filter by job/stage/score, basic profile view | 2 | ~8 |
| **AI Match Scores** | CV-job match percentage, skill gap analysis, candidate ranking | 1 | ~4 |
| **Pipeline (Simple)** | List view (not kanban) with stage assignment | 1 | ~4 |
| **Recruiter Dashboard** | Active jobs, candidate count, recent activity | 1 | ~4 |
| **Hiring Decision** | Approve/reject, move pipeline stage, add notes | 1 | ~4 |
| **Admin Users** | List users, toggle roles, activate/deactivate | 1 | ~4 |
| **Admin Jobs** | View all jobs, moderate content | 1 | ~3 |

**Total Phase 1: ~25 pages, ~84 API endpoints, ~20 DB models**

### Phase 1 Features to EXCLUDE

| Feature | Reason |
|---|---|
| LMS/Courses/Mentor | Spin off as separate product |
| AI Sales Bot | Premature |
| Bot Integrations (Slack/Teams) | Premature |
| Custom Report Builder | Pre-built reports only |
| Career Roadmap | Nice-to-have |
| A/B Testing full system | Minimal A/B only |
| Prompt Management UI | Config files |
| E-Signature | Defer |
| Background Checks | Defer |
| EEO/Diversity Analytics | Defer |
| Re-engagement campaigns | Defer |
| Calendar sync | Defer |
| Certificate generation | Part of LMS (deferred) |
| Ghost Reports | Defer |
| Candidate Comparison | Defer |
| Recruiter Copilot | Defer |
| Multiple AI providers | Single provider (Groq) |

---

## 5. Development Roadmap

### Phase 1: MVP — "Hiring Loop" (Weeks 1-12)

**Goal:** Functional end-to-end hiring with core AI value proposition.

**Sprint 1-2: Foundation**
- Set up production infra (AWS/GCP, RDS MySQL, ElastiCache Redis, S3)
- Single AI provider (Groq) with signed DPA
- Fix P0 security issues (encryption key, Alembic, CSRF, IDOR)
- Auth system (candidate + recruiter + admin)
- Database migrations cleanup

**Sprint 3-4: Candidate Core**
- Profile management (manual skill entry, CV upload, PDF parsing)
- Job board (search, filter, view, apply)
- AI CV analysis (skill extraction, role detection, embedding)
- AI Match scoring (CV vs JD rubric)

**Sprint 5-6: AI Interview Core**
- AI Interview (5-7 questions, text/audio, timer, basic scoring)
- Interview analysis (per-question score, feedback)
- Results view for both candidate and recruiter
- Application pipeline (basic stage tracking)

**Sprint 7-8: Recruiter Core**
- Job posting (AI-assisted JD generation)
- Candidate management (list, filter, sort, profile view)
- Candidate ranking by AI score
- Pipeline management (stage assignment)
- Recruiter dashboard

**Sprint 9-10: Admin + Polish**
- User management
- Job moderation
- Basic analytics
- i18n (EN/FR/AR)
- Performance optimization
- Security audit pass

**Sprint 11-12: Beta Launch**
- Integration testing
- Load testing (100 concurrent users)
- Documentation
- Beta program with 10 companies

### Phase 2: Growth — "Deep Hiring" (Weeks 13-24)

**Goal:** Expand hiring intelligence, add recruiter power tools, monetize.

- Full kanban pipeline with drag-and-drop
- AI interview improvement (adaptive questions, calibration)
- Skills assessments (integrated, not separate LMS)
- Talent pool
- AI sourcing
- Offer management with e-sign
- Campaigns (bulk invite)
- Email templates
- Team collaboration
- Billing integration (Stripe)
- Advanced analytics
- Candidate comparison
- Recruiter copilot (AI chat)
- Re-engagement campaigns
- EEO forms
- JD bias detection
- Additional AI providers with DPA
- Mobile-responsive sidebar
- 100+ unit/integration tests

### Phase 3: Scale — "Platform" (Weeks 25-52)

**Goal:** Enterprise readiness, ecosystem, advanced AI.

- Background checks
- Bot integrations (Slack, Teams)
- Custom report builder
- A/B testing system
- LMS spin-off (Candway Academy as separate product)
- Career roadmap
- AI Sales bot
- Enterprise SSO (SAML/OIDC)
- API marketplace for third-party integrations
- Advanced proctoring
- Video interview recording storage optimization
- Multi-region deployment
- SOC 2 compliance
- 500+ tests with CI/CD pipeline
- Mobile app (React Native)

---

## 6. Database Architecture (Recommended)

### Phase 1 Models (~20 tables)

```sql
-- Core
users (id, email, hashed_password, role, name, phone, avatar_url, created_at, 
       email_verified, is_locked, deleted_at)
companies (id, name, slug, logo_url, is_active, created_at)
company_members (id, company_id, user_id, role, is_active)

-- Jobs
jobs (id, recruiter_id, company_id, category_id, title, location, type, 
      description, required_skills, is_active, created_at, deleted_at)
saved_jobs (id, user_id, job_id)

-- Applications
applications (id, user_id, job_id, company_id, full_name, email, phone, 
              cv_file_path, status, pipeline_stage, analysis_score, 
              assigned_to, created_at, deleted_at)
cv_documents (id, application_id, cv_text, cv_file_path, extracted_skills, 
              analysis_json, created_at)

-- AI Evaluation
evaluation_sessions (id, application_id, company_id, candidate_id, status, 
                     language, interview_state, interview_log, created_at)
evaluation_results (id, evaluation_session_id, cv_score, rubric_score, 
                    final_score, scoring_status, score_breakdown, verdict, 
                    computed_at)
interview_turns (id, evaluation_session_id, turn_number, question, answer, 
                 score, feedback, created_at)
rubrics (id, job_id, title, passing_score, criteria_json, created_at)
rubric_scoring_details (id, evaluation_result_id, criterion_name, score, 
                        weight, feedback)

-- Pipeline
pipeline_stages (id, recruiter_id, name, slug, sort_order, color)
application_stage_history (id, application_id, stage_slug, entered_at, exited_at)

-- Notifications
notifications (id, user_id, type, title, message, is_read, created_at)

-- Audit & Security
audit_logs (id, user_id, action, target_id, details, ip_address, timestamp)
login_attempts (id, email, success, timestamp, ip_address)
token_blacklist (id, token_hash, user_id, expires_at)
```

### Key Design Decisions

1. **Soft delete** on users, jobs, applications (deleted_at column)
2. **JSON columns** for flexible data (score_breakdown, extracted_skills, interview_log)
3. **Encrypted columns** for PII (cv_text, interview answers) using application-level encryption
4. **Indexes** on all foreign keys and frequently queried columns (role, status, stage, score)
5. **Composite unique constraints** on (user_id, job_id) for applications
6. **Separate cv_documents table** to normalize CV data from applications
7. **evaluation_sessions/evaluation_results** as canonical scoring source
8. **application_stage_history** for full pipeline audit trail

---

## 7. API Architecture (Recommended)

### Phase 1 API Structure

```
/api/v1/
├── auth/
│   ├── POST /register
│   ├── POST /login
│   ├── POST /logout
│   ├── POST /forgot-password
│   ├── POST /reset-password
│   ├── POST /verify-email
│   └── GET /me
├── profile/
│   ├── GET /
│   ├── PUT /
│   ├── POST /cv
│   └── GET /cv/{id}
├── jobs/
│   ├── GET / (public, search/filter)
│   ├── GET /{id}
│   ├── POST / (recruiter)
│   ├── PUT /{id} (recruiter)
│   ├── DELETE /{id} (recruiter)
│   └── GET /{id}/applications (recruiter)
├── applications/
│   ├── POST / (candidate apply)
│   ├── GET /mine (candidate)
│   ├── GET /{id} (recruiter)
│   ├── PUT /{id}/stage (recruiter)
│   └── PUT /{id}/decision (recruiter)
├── interviews/
│   ├── POST /{application_id}/start
│   ├── POST /{session_id}/answer
│   ├── POST /{session_id}/submit
│   ├── GET /{session_id}/results
│   └── GET /{application_id}/analysis (recruiter)
├── analysis/
│   ├── POST /cv (analyze CV)
│   ├── GET /match/{application_id}
│   └── GET /ranking/{job_id}
├── recruiter/
│   ├── GET /dashboard
│   ├── GET /candidates
│   ├── GET /candidates/{id}
│   ├── GET /pipeline
│   └── PUT /pipeline/{application_id}
├── admin/
│   ├── GET /users
│   ├── PUT /users/{id}/role
│   ├── GET /jobs
│   ├── PUT /jobs/{id}/status
│   └── GET /analytics
└── companies/
    ├── GET /
    ├── PUT /
    └── POST /members
```

### API Design Principles

1. **Versioned** (/api/v1/) from day one
2. **RESTful** with clear resource hierarchy
3. **JWT auth** in Authorization header + CSRF cookie for browser
4. **Consistent response format**: `{data, meta?, error?}`
5. **Pagination** via cursor-based for lists (`?cursor=...&limit=20`)
6. **Filtering** via query params (`?status=active&stage=screening`)
7. **Rate limiting**: 60 req/min per user, 600 req/hr
8. **Idempotency key** support for mutations
9. **Request IDs** for tracing
10. **WebSocket** for real-time interview + notifications

---

## 8. AI Architecture (Recommended)

### Phase 1 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │ CV Analysis  │  │ Match Score │  │ Interview Analysis   │  │
│  │ Service      │  │ Service     │  │ Service              │  │
│  └──────┬───────┘  └──────┬──────┘  └─────────┬────────────┘  │
│         │                 │                   │               │
├─────────┼─────────────────┼───────────────────┼──────────────┤
│         ▼                 ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              AI Orchestrator Layer                        │ │
│  │  - Prompt management (template-based)                     │ │
│  │  - Provider routing (Groq primary)                       │ │
│  │  - Response parsing (structured output)                   │ │
│  │  - Caching (Redis, TTL by endpoint)                      │ │
│  │  - Rate limiting (per-endpoint, per-user)                 │ │
│  └───────────────────────┬─────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Single AI Provider (Groq)                    │ │
│  │  - Model: Llama 3.1 70B (low latency)                    │ │
│  │  - Max tokens: 4096 (CV), 2048 (scoring), 1024 (chat)   │ │
│  │  - Temperature: 0.2 (scoring), 0.7 (interview)           │ │
│  │  - DPA signed before production                          │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### AI Pipeline Design

```
CV Upload → Text Extraction (PyPDF) → Skill Extraction (AI) → 
  → Embedding Generation → Store in CvDocument

Job Post → JD Analysis → Skill Requirements → Create Rubric

Application → CV Analysis → Match Score → Score Breakdown → 
  → Candidate Ranking (per job)

Interview Start → Generate Questions (from job requirements) → 
  → Calibration (optional) → Adaptive questions → 
  → Per-turn scoring → Final evaluation → Verdict
```

### Prompt Architecture

```
system_prompts table (key → content):
  cv_analysis: "Analyze this CV text and extract: skills, experience, education..."
  job_match: "Score this candidate against job requirements on scale 0-100..."
  interview_question: "Generate 5 interview questions for role {title}..."
  interview_scoring: "Score this interview answer for criterion {criterion}..."
  candidate_summary: "Generate a 3-sentence candidate summary..."
```

### Key AI Decisions

1. **Single provider (Groq)** for MVP — lowest latency, good quality, US-based
2. **Structured JSON output** via prompt engineering + Pydantic validation
3. **Prompt templates** stored in DB for A/B testing without code deploy
4. **Score caching** — computed once, stored in evaluation_results
5. **Async processing** for CV analysis (background task + notification)
6. **Explainable scores** — always return criterion-level breakdown
7. **No PII in prompts** — anonymize CV text before sending to LLM
8. **Fallback strategy** — if AI fails, return partial results with `needs_review` flag

---

## 9. UX Improvements (Critical)

### P0 — Must Fix Before MVP Launch

1. **Mobile responsiveness** — Sidebar, dashboard, job board, interview — all must work on mobile
2. **Loading states** — Every async operation needs skeleton/spinner (currently many have none)
3. **Empty states** — Every list/dashboard needs empty state illustration + CTA
4. **Error states** — Every API failure needs user-friendly error display (not silent fail)
5. **Form validation** — Inline validation with clear error messages (currently server-side only in many cases)
6. **Navigation consistency** — Same sidebar across all roles, highlight active page, breadcrumbs
7. **Dark mode** — Implement fully (currently partial)
8. **RTL support** — Arabic layout must flip sidebar, text alignment, reading order

### P1 — High Impact

9. **Keyboard navigation** — Full tab order, enter/submit, escape to close
10. **Focus indicators** — Visible focus ring for accessibility
11. **Screen reader support** — ARIA labels on all interactive elements
12. **Confirmation dialogs** — On destructive actions (delete, withdraw, reject)
13. **Toast notifications** — Success/error/info toasts (not inline messages)
14. **Optimistic UI** — Update UI immediately, rollback on error
15. **Infinite scroll** — For job lists, candidate lists (replace pagination)
16. **Real-time updates** — WebSocket for interview status, notifications

### P2 — Quality of Life

17. **Drag-and-drop CV upload** — With preview, progress bar
18. **Rich text editor** — For job descriptions (replace textarea)
19. **Auto-save** — For long forms (job posting, profile edit)
20. **Undo** — For pipeline stage changes, status changes
21. **Bulk actions** — Select multiple candidates for batch operations
22. **Export** — CSV/PDF export from all lists
23. **Search with debounce** — For candidate/job search inputs
24. **Filter persistence** — Remember filter state across page reloads

---

## 10. Technical Risks

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| **PII leaves jurisdiction** without DPA | CRITICAL | HIGH | Single Groq provider with signed DPA; anonymize before sending |
| **No automated tests** — regressions guaranteed | CRITICAL | HIGH | Sprint 1: Add pytest for all endpoints; 70% coverage by Phase 1 end |
| **Alembic disabled** at startup — schema drift | CRITICAL | HIGH | Wire `alembic upgrade head` in startup_event |
| **Encryption key** static + dev fallback | CRITICAL | MEDIUM | Env-var-only key, KMS integration, rotation support |
| **Scoring inconsistency** — 4 competing score sources | HIGH | MEDIUM | ADR-001 implemented: single canonical score source |
| **CSRF bypass** — missing on some routes | HIGH | MEDIUM | Audit all mutation endpoints, add CSRF middleware |
| **XSS via innerHTML** — 75 instances, 3 pages missing DOMPurify | HIGH | MEDIUM | Fix all instances, add CSP headers, use DOMPurify everywhere |
| **Prompt injection** — regex-based guard is weak | HIGH | LOW | Input validation + output sanitization + rate limiting |
| **No rate limiting** on interview/API — DoS vector | HIGH | MEDIUM | RateLimitMiddleware with per-user/per-endpoint limits |
| **Vanilla JS maintenance burden** — 67 files, no framework | MEDIUM | HIGH | Phase 2: Evaluate React/Vue migration for candidate/recruiter portals |
| **No CI/CD pipeline** — manual deploy errors | MEDIUM | HIGH | GitHub Actions with lint + test + deploy by Sprint 3 |
| **SQLite in dev, MySQL in prod** — divergence bugs | MEDIUM | MEDIUM | MySQL in dev via Docker Compose from day 1 |
| **105 DB models, many deprecated** — confusion | MEDIUM | HIGH | Drop deprecated columns, consolidate duplicate models |
| **Load capacity unknown** — no performance testing | MEDIUM | MEDIUM | Locust/k6 test with 100 concurrent users before Phase 1 launch |
| **Multi-tenancy at app layer** — leak risk | MEDIUM | LOW | Row-level security via JWT company_id; audit all queries |

---

## 11. Priority Matrix

```
                    HIGH IMPACT                    LOW IMPACT
                ┌─────────────────┬────────────────────────┐
                │                  │                         │
   HIGH URGENCY │  P0: DO NOW      │  P1: DO NEXT            │
                │  • Fix Alembic   │  • Career roadmap       │
                │  • Encryption key │  • Certificate gen     │
                │  • Tests (P0)    │  • LMS polish           │
                │  • CSRF audit    │  • Bot integrations     │
                │  • XSS fix       │  • AI Sales bot         │
                │  • PII/DPA       │  • Prompt mgmt UI       │
                │  • Rate limiting  │  • Ghost reports        │
                │  • Mobile layout  │                         │
                │  • Loading states │                         │
                │  • Single AI prov │                         │
                ├─────────────────┼────────────────────────┤
                │                  │                         │
  LOW URGENCY   │  P2: PLAN       │  P3: DEFER              │
                │  • Mv candidate  │  • SSO/SAML            │
                │  • Stripe integ  │  • Mobile app          │
                │  • Kanban pipeln │  • Multi-region        │
                │  • Re-engagement  │  • SOC 2               │
                │  • EEO dashboard  │  • API marketplace     │
                │  • JD bias detect │  • Video storage opt   │
                │  • Candidate comp │  • Custom report bldr  │
                │  • Rec copilot   │  • A/B testing UI      │
                │  • Dark mode     │  • Background checks   │
                │  • Accessibility  │                         │
                └─────────────────┴────────────────────────┘
```

---

## 12. Monetization Strategy

### Phase 1 (MVP — Free to build traction)
- **Free for candidates** — always free
- **Free for recruiters** — up to 3 active jobs, 50 candidates
- **Revenue**: None (focus on adoption)

### Phase 2 (Growth — Introduce paid plans)
- **Recruiter Pro ($99/mo)**: 10 active jobs, 500 candidates, AI interviews, analytics
- **Recruiter Enterprise ($299/mo)**: Unlimited jobs, background checks, API access, team seats
- **Featured Jobs ($50/job)**: Promote to top of search results
- **Hot Badge ($25/job)**: Highlight job with "hot" tag

### Phase 3 (Scale — Full monetization)
- **Per-interview pricing**: $2/interview over plan limit
- **Premium AI Analysis**: $5/CV for deep analysis + career roadmap
- **White-label**: Custom domain + branding for enterprise ($999/mo)
- **API Access**: $0.10/API call for third-party integrations
- **Candway Academy**: Revenue share (20%) on course sales
- **Talent Marketplace**: 10% fee on successful hires

### Recommended Pricing Model
```
Freemium → Usage-based → Enterprise
- Free tier: 3 jobs, 50 candidates, basic AI scores
- Usage alerts when approaching limits
- No hard cuts — graceful degradation
- Enterprise: flat annual fee + custom limits
```

---

## 13. Summary Verdict

### Candway Platform Assessment

| Dimension | Score | Verdict |
|---|---|---|
| **Feature Completeness** | 85/100 | Surprisingly comprehensive for pre-launch |
| **Code Quality** | 55/100 | Functional but fragile; needs hardening |
| **Security** | 50/100 | Several critical issues must be fixed |
| **AI Capability** | 75/100 | Strong foundation, over-engineered |
| **UX/Design** | 45/100 | Vanilla JS limits; needs mobile and polish |
| **Test Coverage** | 10/100 | Near-zero; critical risk |
| **Infrastructure** | 60/100 | Docker/Prometheus/Sentry good but no CI/CD |
| **Scalability** | 50/100 | Architecture is fine but untested |
| **Monetization Readiness** | 30/100 | No payment gateway, manual approvals |
| **Investment Readiness** | 40/100 | Interesting but too risky for institutional check |

### Immediate Actions (Next 7 Days)

1. Wire Alembic at startup
2. Replace dev-fallback encryption key with mandatory env key
3. Sign DPA with single AI provider (Groq); anonymize PII
4. Add pytest for all auth endpoints
5. Fix CSRF + XSS critical issues
6. Enable rate limiting
7. Ship mobile-responsive sidebar

### MVP Scope Reduction

**Current codebase:** ~130 pages, ~300 endpoints, ~105 models, ~7 AI providers  
**Recommended MVP:** ~25 pages, ~84 endpoints, ~20 models, 1 AI provider

**Cut 80% of surface area. Ship the hiring loop. Validate. Iterate.**
