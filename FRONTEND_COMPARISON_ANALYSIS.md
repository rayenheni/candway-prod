# Frontend Architecture Comparison: Legacy vs React Migration

## Overview

| Aspect | Legacy (Old) | React (New) | Status |
|--------|-------------|-------------|--------|
| **Framework** | Vanilla JS (no framework) | React 19 + TypeScript | ✅ Migrated |
| **Build Tool** | esbuild (manual bundles) | Vite 7.3.2 | ✅ Migrated |
| **Styling** | Tailwind CSS (inline classes) | Tailwind CSS v4 + glassmorphism design system | ✅ Migrated |
| **Routing** | Multi-page HTML (MPA) | React Router v7 (SPA) | ✅ Migrated |
| **State Mgmt** | DOM-based + localStorage | TanStack Query + React Context | ✅ Migrated |
| **Forms** | Native HTML forms | React Hook Form + Zod validation | ✅ Migrated |
| **API Client** | `window.fetchAPI()` + raw `fetch()` | `lib/api-client.ts` (CSRF, auto-refresh, timeout) | ✅ Migrated |
| **Total Pages** | 135 HTML pages | ~55 routes (47 lazy-loaded) | **41% complete** |
| **UI Components** | Inline HTML/CSS | 20 Radix-based components | ✅ Migrated |
| **Localization** | JS translations object | i18n context + dictionaries | ✅ Migrated |
| **Output Dir** | Root HTML files | `static/app/` (served by FastAPI/nginx) | ✅ Migrated |

---

## 1. PAGES COMPARISON: LEGACY VS REACT

### 1.1 Public Pages

| Legacy Page | React Route | Page Component | Status |
|-------------|-------------|----------------|--------|
| `index.html` | `/`, `/landing` | `LandingPage` | ✅ Done |
| `blog-details.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `blogs.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `jobs.html` (public) | ❌ Missing | — | ❌ **NOT CREATED** |
| `job-details.html` (public) | ❌ Missing | — | ❌ **NOT CREATED** |
| `courses.html` (public) | ❌ Missing | — | ❌ **NOT CREATED** |
| `opportunities.html` | Admin: `/admin/opportunities` | `OpportunitiesManagerPage` | ✅ Done |
| `pricing.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `privacy.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `terms.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `404.html` | Catch-all `*` → `/` redirect | Route Error Page | ⚠️ Partial |
| `500.html` | `AppErrorBoundary` | `RouteErrorPage` | ✅ Done |
| `setup-wizard.html` | ❌ Missing | — | ❌ **NOT CREATED** |

### 1.2 Auth Pages

| Legacy Page | React Route | Page Component | Status |
|-------------|-------------|----------------|--------|
| `login.html` | `/auth/login` | `LoginPage` | ✅ Done |
| `login-recruiter.html` | `/auth/login` (unified) | `LoginPage` | ✅ Done |
| `login-candidate.html` | `/auth/login` (unified) | `LoginPage` | ✅ Done |
| `login-mentor.html` | `/auth/login` (unified) | `LoginPage` | ✅ Done |
| `login-admin.html` | `/auth/login` (unified) | `LoginPage` | ✅ Done |
| `signup.html` | `/auth/register` | `RegisterPage` | ✅ Done |
| `signup-recruiter.html` | `/auth/register` (unified) | `RegisterPage` | ✅ Done |
| `signup-mentor.html` | `/auth/register` (unified) | `RegisterPage` | ✅ Done |
| `forgot-password.html` | `/auth/forgot-password` | `ForgotPasswordPage` | ✅ Done |
| `reset-password.html` | `/auth/reset-password` | `ResetPasswordPage` | ✅ Done |
| `verify-email.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `verify-otp.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `google-callback.html` | ❌ Missing | — | ❌ **NOT CREATED** |

### 1.3 Candidate Pages (Legacy: 26 HTML)

| Legacy Page | React Route | Page Component | Status |
|-------------|-------------|----------------|--------|
| `dashboard.html` | `/dashboard` (role-based) | `RoleBasedDashboard` + `CandidateDashboard` | ✅ Done |
| `jobs.html` | ✅ Via `/jobs` list | `JobsListPage` | ✅ Done |
| `applications.html` | `/applications` | `ApplicationsTrackerPage` | ✅ Done |
| `profile.html` | `/profile`, `/candidate/profile` | `CandidateOwnProfilePage` | ✅ Done |
| `interviews.html` | `/interviews` (role-based) | `RoleBasedInterviews` | ✅ Done |
| `interview.html` | `/interview-room`, `/candidate/interview` | `InterviewRoomPage` | ✅ Done |
| `interview-analysis.html` | `/interviews/:id/analysis`, `/candidate/interview-analysis` | `InterviewAnalysisPage` | ✅ Done |
| `settings.html` | `/settings` | `SettingsPage` | ✅ Done |
| `subscription.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `saved-jobs.html` | `/saved-jobs` | `SavedJobsPage` | ✅ Done |
| `messages.html` | `/messages` | `MessagesPage` | ✅ Done |
| `marketplace.html` | ❌ Missing (`ComingSoonPage`) | — | ❌ **PLACEHOLDER** |
| `learning.html` | `/courses` | `CoursesListPage` | ✅ Done |
| `onboarding.html` | ❌ Missing (`ComingSoonPage`) | — | ❌ **PLACEHOLDER** |
| `cv-builder.html` | `/cv-builder` | `CVBuilderPage` | ✅ Done |
| `cv-review.html` | `/cv-review` | `CVReviewPage` | ✅ Done |
| `cv-selection.html` | ❌ Missing (`ComingSoonPage`) | — | ❌ **PLACEHOLDER** |
| `documents.html` | ❌ Missing (`ComingSoonPage`) | — | ❌ **PLACEHOLDER** |
| `course-details.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `course-player.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `course-landing.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `certificate.html` | `/certificates` | `CertificatesPage` | ✅ Done |
| `profile-view.html` | ❌ Missing (`ComingSoonPage`) | — | ❌ **PLACEHOLDER** |
| `profile-visitors.html` | `/profile-visitors` | `ProfileVisitorsPage` | ✅ Done |
| `eeo-form.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `esign-view.html` | ❌ Missing | — | ❌ **NOT CREATED** |

### 1.4 Recruiter Pages (Legacy: 47 HTML — Most critical gap)

| Legacy Page | React Route | Page Component | Status |
|-------------|-------------|----------------|--------|
| `dashboard.html` | `/dashboard` | `RecruiterDashboard` | ✅ Done |
| `candidates.html` | `/candidates` | `CandidatesListPage` | ✅ Done |
| `candidate.html` | `/candidates/:id` | `CandidateProfilePage` | ✅ Done |
| `candidate-ranking.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `jobs.html` | `/jobs` | `JobsListPage` | ✅ Done |
| `job-wizard.html` | `/jobs/new` | `JobWizardPage` | ✅ Done |
| `analytics.html` | `/analytics` | `AnalyticsDashboard` | ✅ Done |
| `analytics-dashboard.html` | `/analytics` (unified) | `AnalyticsDashboard` | ✅ Done |
| `interviews.html` | `/interviews` | `RoleBasedInterviews` | ✅ Done |
| `interview-analysis-recruiter.html` | `/recruiter/interview-analysis` | `RecruiterInterviewAnalysis` | ✅ Done |
| `offers.html` | `/offers` | `OffersManagementPage` | ✅ Done |
| `pipeline.html` | `/pipeline` | `PipelineBoardPage` | ✅ Done |
| `campaigns.html` | `/email-campaigns` | `CampaignsListPage` | ✅ Done |
| `campaigns-view.html` | ❌ Missing (campaign detail) | — | ❌ **NOT CREATED** |
| `campaign-create.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `team.html` | `/team` | `TeamManagementPage` | ✅ Done |
| `messages.html` | `/messages` | `MessagesPage` | ✅ Done |
| `settings.html` | `/settings` | `SettingsPage` | ✅ Done |
| `billing.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `bulk-invite.html` | `/bulk-invite` | `BulkInvitePage` | ✅ Done |
| `landing.html` (recruiter) | ❌ Missing | — | ❌ **NOT CREATED** |
| `reports.html` | `/reports` | `ReportsDashboard` | ✅ Done |
| `reports-list.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `report-builder.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `reengagement.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `calendar-settings.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `email-templates.html` | `/email-templates` | `EmailTemplatesPage` | ✅ Done |
| `eeo-dashboard.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `eeo-coverage.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `background-checks.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `background-check-detail.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `bias-analytics.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `copilot-full.html` | `/copilot` | `CopilotPage` | ✅ Done |
| `comparison.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `compare.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `chatbot-leads.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `ghost-report.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `auto-job.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `jd-editor.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `esign-offer.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `talent-pool.html` | `/talent-pool` | `TalentPoolPage` | ✅ Done |
| `scoring-preview.html` | `/scoring-preview` | `ScoringPreviewPage` | ✅ Done |
| `skill-tree.html` | `/skill-trees` | `SkillTreesPage` | ✅ Done |
| `skill-tree-list.html` | `/skill-trees` (unified) | `SkillTreesPage` | ✅ Done |
| `skill-tree-library.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `skill-tree-create.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `bot-settings.html` | ❌ Missing | — | ❌ **NOT CREATED** |

### 1.5 Admin Pages (Legacy: 23 HTML)

| Legacy Page | React Route | Page Component | Status |
|-------------|-------------|----------------|--------|
| `dashboard.html` | `/admin` | `AdminDashboard` | ✅ Done |
| `users.html` | `/admin/users` | `UsersManagementPage` | ✅ Done |
| `jobs.html` (admin) | ❌ Missing | — | ❌ **NOT CREATED** |
| `analytics.html` (admin) | `/admin/analytics` | `AnalyticsDashboard` | ✅ Done |
| `subscriptions.html` | `/admin/subscriptions` | `SubscriptionsManagerPage` | ✅ Done |
| `payments.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `invoices.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `courses.html` (admin) | `/admin/courses` | `CoursesManagerPage` | ✅ Done |
| `content.html` | `/admin/content` | `ContentManagerPage` | ✅ Done |
| `categories.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `opportunities.html` | `/admin/opportunities` | `OpportunitiesManagerPage` | ✅ Done |
| `marketing.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `announcements.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `verifications.html` | `/admin/moderation` | `VerificationsManagerPage` | ✅ Done |
| `recruiter-usage.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `rubrics.html` | `/rubrics` | `RubricsPage` | ✅ Done |
| `rubric-builder.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `support.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `ai_sales.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `ab-testing.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `prompt-management.html` | `/admin/prompt-management` | `PromptManagementPage` | ✅ Done |
| `settings.html` (admin) | `/admin/settings` | `SettingsPage` | ✅ Done |
| `technical.html` | `/admin/logs` | `SystemHealthPage` | ✅ Done |

### 1.6 Mentor Pages (Legacy: 11 HTML — Major gap)

| Legacy Page | React Route | Page Component | Status |
|-------------|-------------|----------------|--------|
| `mentor.html` (redirect) | `/mentor` | Redirects to dashboard | ✅ Done |
| `mentor-dashboard.html` | `/mentor` | `MentorDashboard` | ✅ Done |
| `mentor-courses.html` | `/courses` | `CoursesListPage` | ⚠️ Shared page |
| `mentor-create-course.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `mentor-course-editor.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `mentor-students.html` | `/mentor/students` | `MentorStudentsPage` | ✅ Done |
| `mentor-wallet.html` | `/mentor/wallet` | `MentorWalletPage` | ✅ Done |
| `mentor-settings.html` | `/settings` | `SettingsPage` | ✅ Done |
| `mentor-landing.html` | ❌ Missing | — | ❌ **NOT CREATED** |
| `profile.html` (mentor) | `/mentor/profile` | `ComingSoonPage` | ❌ **PLACEHOLDER** |
| `community.html` | `/mentor/community` | `ComingSoonPage` | ❌ **PLACEHOLDER** |

---

## 2. API SERVICE GAP ANALYSIS

### 2.1 Services Created in React

| Service File | API Coverage | Missing Endpoints |
|-------------|-------------|-------------------|
| `auth.service.ts` | Login, register, logout, profile, forgot/reset password, refresh | — |
| `candidate.service.ts` | Profile (comprehensive), dashboard, applications | Missing: CV upload/analyze/history, EEO, qualifications, extras, subscriptions |
| `candidates.service.ts` | List, get, applications, status, upload resume, notes, compare, AI scores | Missing: Bulk assign, interactions, candidate assignment |
| `jobs.service.ts` | CRUD, pipeline, analytics, publish/close/duplicate/clone | Missing: Wizard endpoints (18 AI endpoints) |
| `interviews.service.ts` | List, get, schedule, update, cancel, feedback | Missing: AI interview session create/start/end/evaluate, chat, media |
| `analytics.service.ts` | Dashboard stats, trends, funnel, interviews, offers, team, export | Missing: Insights endpoint |
| `messages.service.ts` | Conversations, send, read, unread, search | — |
| `notifications.service.ts` | List, unread, mark read, mark all | — |
| `courses.service.ts` | Get, enroll, progress, reviews | Missing: Mentor course CRUD, syllabus generation, quiz generation |
| `calendar.service.ts` | ICS, Google, Outlook, connect, disconnect, sync | Missing: Calendar links |
| `admin.service.ts` | Users, health, AI monitoring, verifications/courses/subscriptions | Missing: Payments, invoices, marketing, announcements, categories, rubric builder, support, AI sales, AB testing, prompt management, jobs, recruiter-usage |

### 2.2 Service Files NOT Created (Missing Entirely)

| Missing Service | Legacy JS Files | Backend Endpoints Affected |
|----------------|----------------|---------------------------|
| **Background Check** | `background-checks.js` | 6 endpoints (initiate, get, list, adverse-action, stats, webhook) |
| **Campaign Service** | `reengagement.js` | 8+ endpoints (CRUD campaigns, candidates, tracking, upload) |
| **EEO Service** | `eeo-dashboard.js`, `eeo-form.js`, `eeo-coverage.js` | 9 endpoints (dashboard, pipeline, selection, trends, EE01, compliance, coverage) |
| **JD/Bias Service** | `jd-editor.js`, `bias_detection` | 4 endpoints (analyze, rewrite, word-lists) |
| **Re-engagement** | `reengagement.js` | 3 endpoints (list candidates, campaign, send) |
| **Reports Builder** | `report-builder.js` | 5+ endpoints (list, generate, get, export) |
| **Skill Trees** | `skill-tree-modal.js` | 8+ endpoints (list, CRUD, duplicate, standalone) |
| **GDPR Service** | `gdpr.js` | 2 endpoints (erasure, consent) |
| **LinkedIn Service** | (deleted) | Removed from old frontend too |
| **Assessment Service** | (deleted) | Removed from both |

---

## 3. MIGRATION BACKLOG BY PRIORITY

### Phase 1: HIGH PRIORITY — Missing Recruiter Pages (22 pages)
Pages used daily by recruiters that have existing backend API:

| Page | Backend API Ready | Complexity | Effort |
|------|-------------------|------------|--------|
| Billing/Subscription | `GET /recruiter/subscription/*` | Low | 1 day |
| Background Checks (list) | `GET /recruiter/background-checks` | Medium | 2 days |
| Background Check Detail | `GET /recruiter/background-checks/{id}` | Medium | 1 day |
| Re-engagement | `GET/POST /recruiter/reengagement/*` | Medium | 2 days |
| EEO Dashboard | `GET /recruiter/eeo/dashboard` | Medium | 2 days |
| Candidate Ranking | `GET /recruiter/jobs/{id}/candidates/ranked` | Medium | 1 day |
| Reports List | `GET /recruiter/reports` | Low | 1 day |
| Campaign Detail | `GET /recruiter/campaigns/{id}` | Medium | 2 days |
| Chatbot Leads | `GET /chatbot/leads` | Low | 1 day |
| JD Editor | `POST /jd/analyze` | Medium | 2 days |
| Auto Job | AI endpoint exists | Medium | 2 days |
| eSign Offer | `POST /recruiter/offers/respond` | Low | 1 day |
| Calendar Settings | `GET /calendar/status` | Low | 0.5 day |
| Ghost Report | `GET /recruiter/applications/{id}/ghost-data` | Low | 1 day |
| Candidate Comparison | `POST /recruiter/applications/compare` | Medium | 1 day |
| Bias Analytics | `GET /recruiter/enhancements/analytics/jd-bias` | Low | 1 day |
| Bot Settings | Bot config endpoints | Low | 0.5 day |
| Talent Pool Detail | `GET /recruiter/talent-pools/{id}` (existing) | Low | 1 day |
| Skill Tree Library | `GET /recruiter/skill-trees` | Low | 1 day |
| Skill Tree Create | `POST /recruiter/skill-trees` | Medium | 1 day |
| Report Builder | `POST /recruiter/reports/generate` | High | 3 days |
| Recruiter Landing | Public page | Low | 1 day |

### Phase 2: HIGH PRIORITY — Missing Candidate Pages (10 pages)

| Page | Backend API Ready | Complexity | Effort |
|------|-------------------|------------|--------|
| CV Upload/History | `POST /candidate/cv/upload`, `GET /candidate/cv/history` | Medium | 2 days |
| EEO Form | `GET/POST /candidate/eeo` | Low | 1 day |
| Subscription | `GET /candidate/subscriptions` | Low | 1 day |
| Onboarding | `POST /onboarding/*` | Medium | 2 days |
| Course Details | `GET /courses/{id}/details` | Low | 1 day |
| Course Player | `POST /courses/{id}/lessons/{lid}/progress` | High | 3 days |
| Marketplace | Listings API | Low | 1 day |
| Qualification Upload | `POST /candidate/qualifications/*` | Low | 1 day |
| eSign View | `POST /recruiter/offers/respond/{id}` | Low | 1 day |
| Profile View (public) | Public profile endpoint | Low | 1 day |

### Phase 3: MEDIUM PRIORITY — Missing Admin Pages (8 pages)

| Page | Backend API Ready | Complexity | Effort |
|------|-------------------|------------|--------|
| Payments/Treasury | `GET /admin/payments` | Low | 1 day |
| Invoices | `GET /admin/invoices` | Low | 1 day |
| Marketing | `GET/POST /admin/marketing/*` | Medium | 2 days |
| Announcements | `POST /admin/announcements` | Low | 1 day |
| Recruiter Usage | `GET /admin/recruiter-usage/*` | Low | 1 day |
| Rubric Builder | `POST /admin/rubrics` | High | 3 days |
| Sales Autopilot | `GET /admin/ai/sales/*` | Low | 1 day |
| Support Inbox | `GET /admin/tickets` | Medium | 2 days |
| AB Testing | `GET /admin/ab-testing/*` | Medium | 2 days |
| Categories | `GET/POST /admin/categories` | Low | 1 day |
| Jobs (admin view) | `GET /admin/jobs` | Low | 1 day |

### Phase 4: MEDIUM PRIORITY — Missing Mentor Pages (5 pages)

| Page | Backend API Ready | Complexity | Effort |
|------|-------------------|------------|--------|
| Create Course | `POST /mentor/courses` | High | 3 days |
| Course Editor | `PUT /mentor/courses/{id}` + sections/lessons | High | 4 days |
| Mentor Dashboard | `GET /mentor/stats`, `GET /mentor/earnings-chart` | Medium | 2 days |
| Mentor Profile | `PUT /mentor/profile` | Low | 1 day |
| Mentor Community | Social features | High | 5 days |
| Mentor Landing | Public page | Low | 1 day |

### Phase 5: LOW PRIORITY — Public Pages (8 pages)

| Page | Backend API Ready | Complexity | Effort |
|------|-------------------|------------|--------|
| Blog List | `GET /blogs` | Low | 1 day |
| Blog Detail | `GET /blogs/{slug}` | Low | 1 day |
| Public Jobs | `GET /jobs/public` | Low | 1 day |
| Public Job Detail | `GET /jobs/public/{id}` | Low | 1 day |
| Courses (public) | `GET /courses/public` | Low | 1 day |
| Pricing | Static page, no API | Low | 0.5 day |
| Privacy/Terms | Static pages, no API | Low | 0.5 day |
| Setup Wizard | `GET/POST /setup/*` | Medium | 2 days |

### Phase 6: LOW PRIORITY — Auth Pages (3 pages)

| Page | Backend API Ready | Complexity | Effort |
|------|-------------------|------------|--------|
| Verify Email | `GET /auth/verify-email/{token}` | Low | 1 day |
| Verify OTP | `POST /auth/verify-otp` | Low | 1 day |
| Google Callback | `GET /auth/google/callback` | Medium | 1 day |

---

## 4. LEGACY FRONTEND FILES READY FOR ARCHIVAL

After each page is migrated, these JS files can be retired:

| JS File | Backend Endpoints | Migration Status |
|---------|------------------|------------------|
| `background-checks.js` | 6 Checkr endpoints | ❌ Not started |
| `reengagement.js` | 3 re-engagement endpoints | ❌ Not started |
| `jd-editor.js` | 4 bias/rewrite endpoints | ❌ Not started |
| `eeo-dashboard.js` | 9 EEO endpoints | ❌ Not started |
| `eeo-form.js` | 2 candidate EEO endpoints | ❌ Not started |
| `eeo-coverage.js` | 2 coverage endpoints | ❌ Not started |
| `report-builder.js` | 2 report endpoints | ❌ Not started |
| `scoring-preview.js` | 2 scoring endpoints | ❌ Not started |
| `skill-tree-modal.js` | 4 skill tree endpoints | ❌ Not started |
| `talent-pool.js` | 4 talent pool endpoints | ❌ Not started |
| `cv-builder.js` | 2 CV endpoints | ❌ Not started |
| `auth-guard.js` | Auth checks | ✅ Replaced by React guards |
| `auth-token.js` | Token management | ✅ Replaced by React context |
| `cross-page-sync.js` | Cross-tab sync | ✅ Replaced by React state |
| `config.js` | API base URL | ✅ Replaced by Vite env |
| `csrf.js` | CSRF token | ✅ Replaced by api-client |
| `xss-protection.js` | XSS sanitization | ✅ Replaced by React auto-escape |
| `localization.js` | Translation | ✅ Replaced by i18n context |
| `translations.js` | Language keys | ✅ Replaced by dictionaries |

---

## 5. SUMMARY STATISTICS

| Role | Legacy Pages | React Pages | Completion | Remaining |
|------|-------------|-------------|------------|-----------|
| **Public** | 13 | 3 (includes route error) | 23% | 10 |
| **Auth** | 13 | 5 | 38% | 8 |
| **Candidate** | 26 | 11 | 42% | 15 |
| **Recruiter** | 47 | 17 | 36% | 30 |
| **Admin** | 23 | 10 | 43% | 13 |
| **Mentor** | 11 | 4 | 36% | 7 |
| **TOTAL** | **135** | **52 (+ 7 ComingSoon)** | **39%** | **83** |

## 6. BACKEND API COVERAGE

| Category | Backend Endpoints | Consumed by New Frontend | Coverage |
|----------|------------------|------------------------|----------|
| Auth | 15 | 8 (from `auth.service.ts`) | 53% |
| Admin | ~50+ | 11 (from `admin.service.ts`) | 22% |
| Recruiter | ~250+ | ~40 | 16% |
| Candidate | ~30 | ~10 | 33% |
| Courses | ~12 | 8 | 67% |
| Interviews | ~15 | 8 | 53% |
| Messages | ~10 | 8 | 80% |
| Notifications | 5 | 4 | 80% |
| AI Interview | ~15 | 0 | **0%** |
| Background Check | 6 | 0 | **0%** |
| EEO | 9 | 0 | **0%** |
| Reports | 5 | 0 | **0%** |
| **API TOTAL** | **~577+** | **~85+** | **~15%** |
