# Frontend Migration Plan: React SPA Completion

## Project Status
- **Legacy Frontend**: 135 HTML pages + 62 JS files (vanilla JS, MPA)
- **New React Frontend**: 52 pages (39% complete), 11 services
- **Backend API**: ~577+ endpoints ready
- **Active Frontend Dir**: `frontend/` (builds to `static/app/`)
- **Archived Copy**: `candway-frontend-architecture-redesign (1)/`

## Guiding Principles

1. **One service per domain** — Create new `.service.ts` files for missing API domains (background checks, EEO, campaigns, etc.)
2. **Lazy-loaded pages** — Every new page must use `lazy(() => import(...))` in router
3. **RoleGuard** — All routes must enforce proper role authorization
4. **Reuse shared components** — Use existing `shared/components/ui/` (Button, Card, Badge, Table, Pagination, Dialog, etc.)
5. **No jQuery or DOM manipulation** — Use React state + TanStack Query
6. **Tailwind CSS v4 + glassmorphism** — Use CSS tokens from `index.css`
7. **Build output** goes to `static/app/` (FastAPI/nginx serve it)

## Implementation Phases

---

## Phase 1: Foundation — Create Missing Services (Week 1)

**Goal**: Create all missing API service files so pages can be built concurrently.

### Task 1.1: Background Check Service
Create `frontend/src/services/background-checks.service.ts`:
- `initiateCheck(appId)`, `getCheck(appId)`, `listChecks(params)`, `initiateAdverseAction(id)`, `getStats()`
- Backend: `/recruiter/background-checks/*` (6 endpoints)

### Task 1.2: Campaign Service
Create `frontend/src/services/campaigns.service.ts`:
- `getCampaigns()`, `getCampaign(id)`, `createCampaign()`, `updateCampaign()`, `deleteCampaign()`
- `uploadCVs()`, `getTracking(id)`, `getTemplates()`, `createTemplate()`
- Backend: `/recruiter/campaigns/*` (8+ endpoints)

### Task 1.3: EEO Service
Create `frontend/src/services/eeo.service.ts`:
- `getDashboard()`, `getPipelineDiversity()`, `getSelectionRates()`, `getTrends()`
- `getEEO1Report()`, `getComplianceSummary()`, `getCoverageRate()`, `getCoverageDetail()`
- `exportEEOReport(format)`
- Backend: `/recruiter/eeo/*` (9 endpoints)

### Task 1.4: Re-engagement Service
Create `frontend/src/services/reengagement.service.ts`:
- `getCandidates()`, `createCampaign()`, `sendCampaign()`
- Backend: `/recruiter/reengagement/*` (3 endpoints)

### Task 1.5: JD/Bias Service
Create `frontend/src/services/jd-bias.service.ts`:
- `analyzeJD(jdText)`, `analyzeExistingJD(jobId)`, `rewriteJD(data)`, `getWordLists()`
- Backend: `/jd/*` (4 endpoints)

### Task 1.6: Reports Service (extend existing)
Extend `analytics.service.ts`:
- `getReports()`, `generateReport(data)`, `getReport(id)`, `exportReport(type)`
- Backend: `/recruiter/reports/*` (4 endpoints)

### Task 1.7: Skill Trees Service
Create `frontend/src/services/skill-trees.service.ts`:
- `listTrees()`, `getTree(id)`, `createTree()`, `updateTree(id)`, `deleteTree(id)`
- `duplicateTree(id)`, `createStandalone(data)`
- Backend: `/recruiter/skill-trees/*` (8+ endpoints)

### Task 1.8: AI Interview Service
Create `frontend/src/services/ai-interview.service.ts`:
- `createSession()`, `getSession(id)`, `startSession(id)`, `endSession(id)`
- `getQuestions(sessionId)`, `evaluateAnswer()`, `finalEvaluation(sessionId)`
- `chatMessage(sessionId)`, `getChatHistory(sessionId)`
- Backend: `/ai-interview/*` (15+ endpoints)

### Task 1.9: AI Sales Service (Admin)
Create `frontend/src/services/ai-sales.service.ts`:
- `getLeads()`, `updateLeadStatus(id)`, `launchAutopilot()`
- `getCampaigns()`, `generateInternalLeads()`, `generateOutreach()`
- Backend: `/admin/ai/sales/*` (6 endpoints)

---

## Phase 2: Recruiter Pages (Weeks 2-4)

### Sprint R1: Core Recruiter Features (Week 2)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Billing/Subscription** | `features/recruiter/pages/billing.tsx` + route `/billing` |
| 2 | **Background Checks (list)** | `features/recruiter/pages/background-checks.tsx` + route `/background-checks` |
| 3 | **Background Check Detail** | `features/recruiter/pages/background-check-detail.tsx` + route `/background-checks/:id` |
| 4-5 | **EEO Dashboard** | `features/recruiter/pages/eeo-dashboard.tsx` + route `/eeo/dashboard` + EEO coverage |

### Sprint R2: Recruiter Analytics & Campaigns (Week 3)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Re-engagement Campaigns** | `features/recruiter/pages/reengagement.tsx` + route `/reengagement` |
| 2 | **Campaign Detail + Create** | `features/recruiter/pages/campaign-detail.tsx` + `campaign-create.tsx` |
| 3 | **Reports List + Builder** | `features/reports/pages/reports-list.tsx` + `report-builder.tsx` |
| 4 | **Candidate Ranking** | `features/candidates/pages/candidate-ranking.tsx` + route `/candidates/ranking/:jobId` |
| 5 | **Chatbot Leads** | `features/recruiter/pages/chatbot-leads.tsx` + route `/chatbot-leads` |

### Sprint R3: Advanced Recruiter Tools (Week 4)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **JD Editor + Auto Job** | `features/recruiter/pages/jd-editor.tsx` + `auto-job.tsx` |
| 2 | **Ghost Report** | `features/recruiter/pages/ghost-report.tsx` + route `/ghost-report` |
| 3 | **Candidate Comparison** | `features/candidates/pages/compare.tsx` + route `/candidates/compare` |
| 4 | **Bias Analytics** | `features/recruiter/pages/bias-analytics.tsx` + route `/bias-analytics` |
| 5 | **eSign Offers + Calendar Settings** | Calendar page + esign components |

---

## Phase 3: Candidate Pages (Weeks 5-6)

### Sprint C1: Core Candidate Features (Week 5)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **CV Upload/History** | Extend candidate profile page with CV section |
| 2 | **EEO Form** | `features/candidate/pages/eeo-form.tsx` + route `/eeo` |
| 3 | **Subscription Management** | `features/candidate/pages/subscription.tsx` + route `/subscription` |
| 4 | **Onboarding Flow** | `features/candidate/pages/onboarding.tsx` + route `/onboarding` |
| 5 | **Qualifications** | Extend profile page with qualifications section |

### Sprint C2: Learning & Marketplace (Week 6)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Course Details Page** | `features/courses/pages/course-details.tsx` + route `/courses/:id` |
| 2 | **Course Player** | `features/courses/pages/course-player.tsx` + route `/courses/:id/player` |
| 3 | **Marketplace** | `features/candidate/pages/marketplace.tsx` + route `/marketplace` |
| 4 | **Profile View (public)** | `features/candidate/pages/public-profile.tsx` + route `/profile/:id` |
| 5 | **eSign View** | `features/candidate/pages/esign-view.tsx` + route `/esign/:id` |

---

## Phase 4: Admin Pages (Weeks 7-8)

### Sprint A1: Admin Finance & Content (Week 7)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Payments/Treasury** | `features/admin/pages/payments.tsx` + route `/admin/payments` |
| 2 | **Invoices** | `features/admin/pages/invoices.tsx` + route `/admin/invoices` |
| 3 | **Marketing Engine** | `features/admin/pages/marketing.tsx` + route `/admin/marketing` |
| 4 | **Announcements** | `features/admin/pages/announcements.tsx` + route `/admin/announcements` |
| 5 | **Job Board Admin** | `features/admin/pages/jobs-board.tsx` + route `/admin/jobs` |

### Sprint A2: Admin Operations (Week 8)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Recruiter Usage** | `features/admin/pages/recruiter-usage.tsx` + route `/admin/recruiter-usage` |
| 2 | **Rubric Builder** | `features/rubrics/pages/rubric-builder.tsx` + route `/rubrics/new` + `/rubrics/:id/edit` |
| 3 | **Support Inbox** | `features/admin/pages/support.tsx` + route `/admin/support` |
| 4 | **Sales Autopilot + AB Testing** | `features/admin/pages/ai-sales.tsx` + `ab-testing.tsx` |
| 5 | **Categories Management** | `features/admin/pages/categories.tsx` + route `/admin/categories` |

---

## Phase 5: Mentor Pages + Public Pages (Weeks 9-10)

### Sprint M1: Mentor Suite (Week 9)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Mentor Dashboard** | `features/mentor/pages/mentor-dashboard.tsx` + route `/mentor/dashboard` |
| 2 | **Create Course** | `features/mentor/pages/mentor-create-course.tsx` + route `/mentor/courses/new` |
| 3-4 | **Course Editor** | `features/mentor/pages/mentor-course-editor.tsx` + sections/lessons CRUD |
| 5 | **Mentor Profile + Community** | Profile + community page stubs |

### Sprint P1: Public Pages (Week 10)

| Day | Task | Files to Create |
|-----|------|-----------------|
| 1 | **Blog List + Detail** | `features/blog/pages/blog-list.tsx` + `blog-detail.tsx` |
| 2 | **Public Jobs + Job Detail** | `features/jobs/pages/public-jobs.tsx` + `public-job-detail.tsx` |
| 3 | **Public Courses + Pricing** | Course list + pricing static page |
| 4 | **Auth Pages** | Verify email, verify OTP, Google callback |
| 5 | **Setup Wizard + Privacy/Terms** | Setup flow + legal pages |

---

## Phase 6: Cleanup & Optimization (Week 11)

| Day | Task |
|-----|------|
| 1 | Verify all 577+ API endpoints have client-side coverage |
| 2 | Remove legacy `.html` pages from FastAPI `pages.router` |
| 3 | Delete archived JS files from `js/` directory |
| 4 | Run full E2E tests on new React SPA |
| 5 | Performance audit + Lighthouse scoring |

---

## Effort Summary

| Phase | Days | Pages | New Services | New Components |
|-------|------|-------|-------------|----------------|
| P1: Services | 5 | 0 | 9 | 0 |
| R1: Core Recruiter | 5 | 5 | 0 | 3 |
| R2: Recruiter Analytics | 5 | 6 | 0 | 4 |
| R3: Advanced Recruiter | 5 | 6 | 0 | 3 |
| C1: Core Candidate | 5 | 5 | 0 | 2 |
| C2: Learning | 5 | 5 | 0 | 3 |
| A1: Admin Finance | 5 | 5 | 0 | 2 |
| A2: Admin Ops | 5 | 6 | 0 | 3 |
| M1: Mentor | 5 | 5 | 0 | 3 |
| P1: Public | 5 | 8 | 0 | 2 |
| Cleanup | 5 | 0 | 0 | 0 |
| **TOTAL** | **55 days** | **51 pages** | **9 services** | **25 components** |

**Total estimated effort: 11 weeks (55 working days)**

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backend API changes during migration | High | Freeze API changes until migration complete |
| Broken legacy pages during transition | Medium | Serve both old and new via `pages.router` fallback |
| Missing API endpoints | Medium | Audit all old frontend `fetchAPI()` calls first |
| Design inconsistency | Low | Use existing glassmorphism tokens + shared components |
| Performance regression | Low | Lazy loading + chunk splitting already configured |
| Arabic/RTL support | Low | i18n context + RTL handling already implemented |

---

## Quick Start for New Pages

```
// 1. Create the feature directory + page
mkdir -p frontend/src/features/feature-name/pages/
touch frontend/src/features/feature-name/pages/my-new-page.tsx

// 2. Register route in frontend/src/app/router.tsx
const MyNewPage = lazy(() => import('@/features/feature-name/pages/my-new-page'));
{ path: 'my-new-route', element: allowed(['recruiter', 'admin'], <S><MyNewPage /></S>) }

// 3. Add API service method if needed
// In frontend/src/services/existing-service.ts or create new service

// 4. Build: npm run build (outputs to static/app/)
```
