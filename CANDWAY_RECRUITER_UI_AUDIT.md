# Candway Recruiter Platform — UI & Design System Discovery Audit

**Date**: 2026-07-01
**Audit Type**: Static repository analysis (no runtime)
**Tech Stack**: MPA (Multi-Page Application), Vanilla JS, Tailwind CSS v4, Font Awesome 6, AOS, Chart.js, Quill.js, FastAPI backend
**Verification Status**: All claims verified from repository files unless marked `[Not verified]`

---

## 1. Recruiter Sitemap (46 Pages)

### 1.1 Dashboard & Overview
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 1 | **Dashboard** | `/recruiter/dashboard` | `pages/recruiter/dashboard.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js, translations.js |
| 2 | **Analytics Dashboard** | `/recruiter/analytics` | `pages/recruiter/analytics-dashboard.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js, Chart.js |
| 3 | **Analytics (Advanced)** | `/recruiter/analytics-advanced` | `pages/recruiter/analytics.html` | config.js, auth-guard.js, security.js, components.js, localization.js |

### 1.2 Jobs
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 4 | **Jobs Manager** | `/recruiter/jobs` | `pages/recruiter/jobs.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js, translations.js |
| 5 | **JD Editor** | `/recruiter/jd-editor` | `pages/recruiter/jd-editor.html` | config.js, auth-guard.js, security.js, components.js, toast.js, jd-editor.js |
| 6 | **Auto Job Creator** | `/recruiter/auto-job` | `pages/recruiter/auto-job.html` | config.js, auth-guard.js, security.js, components.js, toast.js, auto-job.js |

### 1.3 Candidates
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 7 | **Candidates (List)** | `/recruiter/candidates` | `pages/recruiter/candidates.html` | config.js, auth-guard.js, security.js, entity-bridge.js, components.js, recruiter-enhancements.js, cross-page-sync.js, Chart.js |
| 8 | **Candidate Profile** | `/recruiter/candidate` | `pages/recruiter/candidate.html` | config.js, auth-guard.js, security.js, components.js, toast.js, rubric-builder.js, Chart.js |
| 9 | **Candidate Ranking** | `/recruiter/candidate-ranking` | `pages/recruiter/candidate-ranking.html` | config.js, auth-guard.js, security.js, components.js |
| 10 | **Compare Candidates** | `/recruiter/compare` | `pages/recruiter/compare.html` | config.js, auth-guard.js, security.js, components.js, Chart.js |
| 11 | **Comparison View** | `/recruiter/comparison` | `pages/recruiter/comparison.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js |
| 12 | **Talent Pool** | `/recruiter/talent-pool` | `pages/recruiter/talent-pool.html` | config.js, auth-guard.js, security.js, components.js, toast.js, talent-pool.js |
| 13 | **Scoring Preview** | `/recruiter/scoring-preview` | `pages/recruiter/scoring-preview.html` | config.js, auth-guard.js, security.js, components.js, scoring-preview.js |

### 1.4 Pipeline
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 14 | **Talent Pipeline** | `/recruiter/pipeline` | `pages/recruiter/pipeline.html` | config.js, auth-guard.js, security.js, entity-bridge.js, components.js, toast.js, localization.js, recruiter-pipeline.js (1342 lines inline) |

### 1.5 Campaigns & Outreach
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 15 | **Campaign Manager** | `/recruiter/campaigns` | `pages/recruiter/campaigns.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js, translations.js |
| 16 | **Create Campaign** | `/recruiter/campaigns/new` | `pages/recruiter/campaign-create.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 17 | **Campaign View** | `/recruiter/campaigns/view` | `pages/recruiter/campaigns-view.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 18 | **Bulk Invite** | `/recruiter/bulk-invite` | `pages/recruiter/bulk-invite.html` | config.js, auth-guard.js, security.js, components.js |
| 19 | **Re-engagement** | `/recruiter/reengagement` | `pages/recruiter/reengagement.html` | config.js, auth-guard.js, security.js, components.js, toast.js, reengagement.js |
| 20 | **Chatbot Leads** | `/recruiter/chatbot-leads` | `pages/recruiter/chatbot-leads.html` | config.js, auth-guard.js, security.js, components.js, chatbot-leads.js |
| 21 | **Email Templates** | `/recruiter/templates` | `pages/recruiter/email-templates.html` | config.js, auth-guard.js, security.js, components.js, toast.js |

### 1.6 Interviews & Assessments
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 22 | **Interviews** | `/recruiter/interviews` | `pages/recruiter/interviews.html` | config.js, auth-guard.js, security.js, entity-bridge.js, components.js, toast.js, localization.js |
| 23 | **Interview Analysis** | `/recruiter/interview-analysis` | `pages/recruiter/interview-analysis-recruiter.html` | config.js, auth-guard.js, security.js, components.js, Chart.js |
| 24 | **Skill Tree List** | `/recruiter/skill-tree-list` | `pages/recruiter/skill-tree-list.html` | config.js, auth-guard.js, security.js, components.js |
| 25 | **Skill Tree Create** | `/recruiter/skill-tree/create` | `pages/recruiter/skill-tree-create.html` | config.js, auth-guard.js, security.js, components.js |
| 26 | **Skill Tree Library** | `/recruiter/skill-tree-library` | `pages/recruiter/skill-tree-library.html` | config.js, auth-guard.js, security.js, components.js, skill-tree-modal.js |
| 27 | **Skill Tree Detail** | `/recruiter/skill-tree` | `pages/recruiter/skill-tree.html` | config.js, auth-guard.js, security.js, components.js |

### 1.7 Offers & Background Checks
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 28 | **Offers** | `/recruiter/offers` | `pages/recruiter/offers.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 29 | **E-Sign Offer** | `/recruiter/esign-offer` | `pages/recruiter/esign-offer.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 30 | **Background Checks** | `/recruiter/background-checks` | `pages/recruiter/background-checks.html` | config.js, auth-guard.js, security.js, components.js, background-checks.js |
| 31 | **Background Check Detail** | `/recruiter/background-check-detail` | `pages/recruiter/background-check-detail.html` | config.js, auth-guard.js, security.js, components.js |

### 1.8 Reports & Ghost Reports
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 32 | **Reports** | `/recruiter/reports` | `pages/recruiter/reports.html` | config.js, auth-guard.js, security.js, components.js |
| 33 | **Reports List** | `/recruiter/reports-list` | `pages/recruiter/reports-list.html` | config.js, auth-guard.js, security.js, components.js, reports-list.js |
| 34 | **Report Builder** | `/recruiter/report-builder` | `pages/recruiter/report-builder.html` | config.js, auth-guard.js, security.js, components.js, report-builder.js, Chart.js |
| 35 | **Ghost Report** | `/recruiter/candidate/{app_id}/report` | `pages/recruiter/ghost-report.html` | config.js, auth-guard.js, security.js, components.js |

### 1.9 EEO & Compliance
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 36 | **EEO Dashboard** | `/recruiter/eeo-dashboard` | `pages/recruiter/eeo-dashboard.html` | config.js, auth-guard.js, security.js, components.js, eeo-dashboard.js, Chart.js |
| 37 | **EEO Coverage** | `/recruiter/eeo-coverage` | `pages/recruiter/eeo-coverage.html` | config.js, auth-guard.js, security.js, components.js, eeo-coverage.js |
| 38 | **Bias Analytics** | `/recruiter/bias-analytics` | `pages/recruiter/bias-analytics.html` | config.js, auth-guard.js, security.js, components.js |

### 1.10 Settings & Administration
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 39 | **Settings** | `/recruiter/settings` | `pages/recruiter/settings.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js |
| 40 | **Billing** | `/recruiter/billing` | `pages/recruiter/billing.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js |
| 41 | **Team** | `/recruiter/team` | `pages/recruiter/team.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 42 | **Calendar Settings** | `/recruiter/calendar` | `pages/recruiter/calendar-settings.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 43 | **Bot Settings** | `/recruiter/bot-settings` | `pages/recruiter/bot-settings.html` | config.js, auth-guard.js, security.js, components.js, bot-settings.js |

### 1.11 Communication & AI
| # | Page | Route | HTML File | JS Dependencies |
|---|------|-------|-----------|-----------------|
| 44 | **Messages** | `/recruiter/messages` | `pages/recruiter/messages.html` | config.js, auth-guard.js, security.js, components.js, toast.js, localization.js |
| 45 | **Copilot (AI)** | `/recruiter/copilot-full` | `pages/recruiter/copilot-full.html` | config.js, auth-guard.js, security.js, components.js, toast.js |
| 46 | **Recruiter Landing** | `/recruiter/landing` | `pages/recruiter/landing.html` | config.js, security.js, landing.js |

### CSS Dependencies (Shared Across All Pages)
| File | Purpose | Verified |
|------|---------|----------|
| `/css/tailwind-landing.css` | Compiled Tailwind CSS output | Yes |
| `/css/recruiter-glass.css` | Glassmorphism design system for recruiter portal (271 lines) | Yes |
| `/css/custom.css` | Premium components, buttons, glass cards, admin sidebar (1025 lines) | Yes |
| `/css/design-tokens.css` | CSS custom properties bridge (43 lines) | Yes |
| `/css/mobile.css` | Mobile responsive overrides (241 lines) | Yes |
| `/css/tooltips.css` | CSS-only tooltip system + Help Center + Tour (476 lines) | Yes |
| `/css/admin-tables.css` | Enterprise table design system (800 lines) | Yes |
| `/css/rubric-builder.css` | Rubric builder specific styles | Yes |

### Shared JS Dependencies (Loaded on MOST recruiter pages)
| File | Purpose | Lines |
|------|---------|-------|
| `js/config.js` | API config, fetchAPI helper | 176 |
| `js/auth-guard.js` | Auth redirect logic | - |
| `js/security.js` | XSS sanitization, CSRF | - |
| `js/components.js` | Sidebar, header, search, modals, notifications, messages | 2479 |
| `js/toast.js` | Toast notification system | 88 |
| `js/localization.js` | i18n engine | - |
| `js/translations.js` | Translation loader hub | - |

---

## 2. Page Inventory (Detailed)

### 2.1 Dashboard (`/recruiter/dashboard`)

**Sections & Widgets:**
- Stats bar: 4 KPI cards (Active Jobs, Filled Roles, New Matches, Time Saved)
- Priority AI Matches: scrollable candidate recommendation cards
- AI Talent Scout: semantic search input + results panel
- Live Talent Feed / Activity Feed: timeline of recent applications
- Broadcast container: dismissible admin announcements (type: critical/warning/info)

**Forms:** Semantic search input (single field, debounced 300ms)

**Tables:** None on this page

**Buttons:**
- "Post Job" header CTA → links to `/recruiter/jobs`
- "Import Data" / "Import CVs"
- "View All" AI matches
- "Scout" / "Scout Talent" semantic search trigger
- Candidate card click → `/recruiter/candidate?id=X`

**API Calls:**
- `GET /recruiter/stats` — dashboard KPIs
- `GET /recruiter/recommendations?page=X` — AI matches
- `GET /search/talent-scout?query=...` — semantic search
- `GET /recruiter/announcements/active` — broadcast banners
- `GET /notifications/unread-count` — bell badge

**Entry Points:** Sidebar nav, login redirect, any page header
**Exit Points:** Candidate card clicks, Post Job CTA, sidebar navigation

---

### 2.2 Jobs Manager (`/recruiter/jobs`)

**Sections & Widgets:**
- Stats bar: Total Active, Total Applicants, Avg Time, Recommendations
- Job cards grid (3-column) with hover lift effect
- Create Job Modal (2-step wizard)

**Create Job Modal (Step 1):**
- Fields: Job Title, Location, Employment Type (select: Full-time/Part-time/Contract/Freelance/Internship), Category, Required Skills (comma-separated), Salary Range, Description (textarea), Skill Tree selector (optional, searchable dropdown)
- Skill Tree search + list with loading state

**Create Job Modal (Step 2):**
- AI Interview Customization section
- 6 quick-tag buttons (Must: Cloud, Must: System Design, Must: Leadership, Every 3: Culture Fit, Technical Only, Problem-Solving Focus)
- Custom Instructions textarea
- Auto-Generate button

**Buttons:**
- "Post Job" / "Post New Job" (opens modal)
- "Cancel", "Next", "Publish", "Save as Draft"
- Quick-tag chips (6 predefined)
- Skill tree quick search
- Job card: click → expand details, hover actions

**Tables:** Job cards grid (not a traditional table)

**Filters:** Status tabs (All Roles / Online / Dormant / Signals), Location filter, Type filter

**API Calls:**
- `GET /recruiter/jobs/list` — job listings
- `POST /recruiter/jobs/create` — create job
- `PUT /recruiter/jobs/{id}` — update job
- `DELETE /recruiter/jobs/{id}` — delete job with confirmation
- `GET /skill-trees/list` — skill tree options
- `POST /jobs/{id}/auto-generate` — AI auto-generate

---

### 2.3 Talent Pipeline (`/recruiter/pipeline`)

**Sections & Widgets:**
- Stats bar: 6 stage counts (applied, invited, interviewing, offer, hired, rejected)
- View toggle: Board / List (Kanban board vs table)
- Kanban board: 6+ stage columns with draggable candidate cards
- Candidate cards: avatar, name, score, skills, match reason, quick action buttons
- Hover preview: floating card with score breakdown when hovering candidate

**Candidate Card Components:**
- Avatar (initials SVG fallback or photo)
- Name, role, score badge
- Skills tags (up to 6)
- Strengths tags (up to 3)
- Summary text
- Quick action buttons: Invite, Shortlist, Reject
- Notes/comments count
- Progress indicator (interview stage)

**Modals:**
- Schedule Interview Modal: datetime-local picker, duration, type (phone/video/onsite/technical/behavioral/panel), meeting link, location, agenda/notes
- Delete Candidate confirmation
- Assign to Recruiter modal
- Bulk invite modal
- Compare talents modal
- Ghost Report export modal

**Forms:** None inline (modals contain forms)

**Tables:** List view has a table with columns

**Filters:**
- Job filter (populated from API)
- Campaign filter (populated from API)
- Search input (by name/role)
- Min Score slider/input
- Stage tabs

**Bulk Actions:** Bulk Invite, Compare, Export Ghost Reports

**API Calls:**
- `GET /recruiter/jobs/my` — jobs for filter
- `GET /recruiter/campaigns` — campaigns for filter
- `GET /recruiter/applications/list?page=X&...` — paginated applications
- `POST /recruiter/enhancements/quick-action` — invite/shortlist/reject
- `POST /recruiter/enhancements/undo/{undo_id}` — undo action
- `GET /recruiter/enhancements/hover-preview/{app_id}` — hover card data
- `POST /recruiter/interviews/schedule` — schedule interview
- `PUT /recruiter/interviews/{id}` — update interview
- `POST /recruiter/interviews/{id}/feedback` — submit interview feedback
- `DELETE /recruiter/applications/{id}` — delete application

---

### 2.4 Candidates List (`/recruiter/candidates`)

**Sections & Widgets:**
- Stats cards: 6 KPIs
- Tab bar: All / Shortlisted / Interviewing / Offer / Hired / Rejected
- Filter bar row: Job, Recruiter, Location, Experience, Min Score
- Data table: candidates with sorting

**Table Columns:**
1. Checkbox (selection)
2. Candidate (avatar + name)
3. Job Title
4. Stage (colored pill)
5. Score (colored badge)
6. Status
7. Activity (relative time + icon)
8. Assigned To
9. Actions (3-dot menu)

**Stage Pills:** `stage-applied` (gray), `stage-screening` (blue), `stage-interview` (indigo), `stage-offer` (violet), `stage-shortlisted` (amber), `stage-rejected` (red)

**Modals:**
- Move Stage: stage selector + reason textarea
- Assign Recruiter: user select dropdown
- Add Note: textarea

**Filters:**
- Tab filter (stage-based)
- Job title dropdown (populated dynamically)
- Recruiter dropdown
- Location dropdown
- Experience (years) dropdown
- Min Score

**Pagination:** Page numbers with prev/next, 10 per page

**Bulk Actions:** Select checkbox → bulk stage move, bulk assign

**API Calls:**
- `GET /recruiter/candidates/list?page=X&per_page=Y&status=Z&job_id=W&min_score=V`
- `POST /recruiter/candidates/bulk-move`
- `POST /recruiter/candidates/{id}/assign`

---

### 2.5 Candidate Profile (`/recruiter/candidate`)

**Sections & Widgets:**
- Profile header: avatar, name, email, phone, location, status badge
- Score card: overall score with color coding
- AI Evaluation section: trust score, interview progress, strengths, weaknesses
- Skills tags
- Interview transcript: chat bubble UI (AI in green, user in violet)
- Chat widget (floating): AI copilot for candidate Q&A
- Tabbed sections: Profile, Interview, Assessment, Notes, Documents

**Sections (id-based):**
- `#candidate-header`
- `#score-card`
- `#ai-evaluation`
- `#skills-section`
- `#interview-transcript`
- `#notes-section`
- `#documents-section`

**Buttons:**
- Schedule Interview
- Send Message
- Add Note
- Move Stage
- Download CV
- View Ghost Report
- Chat widget toggle

**API Calls:**
- `GET /recruiter/candidates/{id}` — full profile
- `GET /recruiter/candidates/{id}/scores` — AI scores
- `GET /recruiter/candidates/{id}/interview` — interview data
- `POST /recruiter/candidates/{id}/notes` — add note

---

### 2.6 Campaign Manager (`/recruiter/campaigns`)

**Sections & Widgets:**
- Campaign cards grid
- Campaign detail view with candidate list table
- Create Campaign Modal

**Create Campaign Modal:**
- Fields: Campaign Name, Target Role, Interview Language (select), Job Description (textarea), CV Upload (drag-drop)

**Table:** Candidate, Status, Engagement, CV Score, Interview Score, Change, Actions

**Buttons:**
- "New Campaign" (opens modal)
- "Create & Import"
- "Audit" (per candidate)
- "Invite" (per candidate)
- "Archive" (per candidate)
- Medal badges (1st, 2nd, 3rd) for top scorers

**API Calls:**
- `GET /recruiter/campaigns` — list
- `POST /recruiter/campaigns` — create
- `DELETE /recruiter/campaigns/{id}` — delete
- `POST /recruiter/campaigns/{id}/upload` — upload CVs
- `GET /recruiter/campaigns/{id}/candidates` — campaign candidates

---

### 2.7 Settings (`/recruiter/settings`)

**Sections:**
- Branding: Company Name, Company Description, Upload Logo
- Email Configuration (SMTP): SMTP Host, Port, Username, Password, Test Connection
- Notification Preferences
- API Keys section

**Buttons:** Save Changes, Test Connection, Upload Logo

**API Calls:**
- `GET /recruiter/settings`
- `PUT /recruiter/settings`
- `POST /recruiter/settings/test-smtp`

---

### 2.8 Team (`/recruiter/team`)

**Sections:**
- Stats: Total Members count
- Team members list with avatars
- Add Member Modal

**Add Member Modal:**
- Fields: Name, Email, Role (select: Team Member/Admin)
- Buttons: Cancel, Add Member

**Empty State:** "No team members yet" with CTA "Add Your First Member"

**API Calls:**
- `GET /recruiter/team` — list members
- `POST /recruiter/team` — add member
- `DELETE /recruiter/team/{id}` — remove member

---

### 2.9 Billing (`/recruiter/billing`)

**Sections:**
- Current Plan / Active Tier display
- Plan selector (Free / Pro)
- Usage stats: Active Jobs, AI Interviews, CV Analysis
- Payment History table
- Upload Proof of Payment (JPG/PDF)

**Payment History Table:** Date, Amount, Status, Receipt

**Buttons:** Change Plan, Select Plan, Upload Proof, Confirm & Submit

**API Calls:**
- `GET /recruiter/billing/plan`
- `GET /recruiter/billing/history`
- `POST /recruiter/billing/upgrade`
- `POST /recruiter/billing/upload-proof`

---

### 2.10 Interviews (`/recruiter/interviews`)

**Sections:**
- Upcoming interviews list/timeline
- Past interviews archive
- Calendar sync options

**Buttons:** Schedule Interview, Reschedule, Cancel, Provide Feedback, Join Meeting

**API Calls:**
- `GET /recruiter/interviews` — list
- `POST /recruiter/interviews/schedule`
- `PUT /recruiter/interviews/{id}`
- `DELETE /recruiter/interviews/{id}`
- `POST /recruiter/interviews/{id}/feedback`

---

### 2.11 Reports (`/recruiter/reports`, `/recruiter/report-builder`, `/recruiter/reports-list`)

**Reports Sections:**
- Pre-built reports list
- Report builder: metric selection, date range, chart type, export format
- Reports list with delete/edit

**Chart Types (Chart.js):** Bar, Line, Pie, Doughnut, Radar

**Buttons:** Create Report, Export (PDF/CSV), Delete, Duplicate

**API Calls:**
- `GET /recruiter/reports` — list
- `POST /recruiter/reports` — create
- `PUT /recruiter/reports/{id}` — update
- `DELETE /recruiter/reports/{id}` — delete
- `GET /recruiter/reports/{id}/export` — export

---

### 2.12 Ghost Report (`/recruiter/candidate/{app_id}/report`)

**Sections (PDF-style report):**
- Confidential watermark
- Executive Summary
- AI Audit Score
- Competency Matrix
- Career Trajectory
- CV Integrity
- Technical Evidence
- Technical Verdict
- Strengths & Areas for Improvement
- Auditor Endorsement
- Digital Signature
- Generated date, Prepared by, Official stamp

**Buttons:** Export Report (PDF), Exit Report, Retry (on error)

**API Calls:**
- `GET /recruiter/enhancements/ghost-report/{app_id}`

---

### 2.13 Interview Analysis (`/recruiter/interview-analysis`)

**Sections:**
- Overall score gauge
- Per-question breakdown
- Transcript with AI analysis
- Skill gap analysis
- Recommendation

**Charts:** Radar chart for competency scores, bar chart for per-question scores

**API Calls:**
- `GET /recruiter/interviews/{id}/analysis`
- `GET /recruiter/interviews/{id}/transcript`

---

### 2.14 Skill Trees (`/recruiter/skill-tree*`)

**Pages:** Library (grid of skill trees), List, Create, Detail/Editor

**Skill Tree Editor:**
- Category Weights (sliders)
- Skill importance toggles
- Reset to Default button
- Preview Impact button

**API Calls:**
- `GET /skill-trees` — list
- `GET /skill-trees/{id}` — detail
- `POST /skill-trees` — create
- `PUT /skill-trees/{id}` — update
- `DELETE /skill-trees/{id}` — delete

---

### 2.15 Other Pages

**Messages** (`/recruiter/messages`): Conversation list, chat view, send message form. API: `GET/POST /messages/conversations`

**Offers** (`/recruiter/offers`): Offers list, create offer form, status tracking. API: `GET/POST/PUT /recruiter/offers`

**Background Checks** (`/recruiter/background-checks`, `/recruiter/background-check-detail`): List + detail view, verification status badges

**EEO Dashboard** (`/recruiter/eeo-dashboard`): Diversity metrics, charts, compliance status. Uses eeo-dashboard.js

**EEO Coverage** (`/recruiter/eeo-coverage`): Coverage map, demographic breakdown. Uses eeo-coverage.js

**Bias Analytics** (`/recruiter/bias-analytics`): Bias detection metrics, fairness indicators

**Copilot** (`/recruiter/copilot-full`): Full-page AI chat assistant

**Bot Settings** (`/recruiter/bot-settings`): Career chat widget configuration

---

## 3. Design System Audit

### 3.1 Colors

#### Primary Palette
| Token | Value | Usage |
|-------|-------|-------|
| `--primary` / `--candway-primary` | `#6366f1` (Indigo-500) | Primary buttons, links, active states |
| `--primary-dark` / `--candway-primary-dark` | `#4f46e5` (Indigo-600) | Button hover, gradient dark end |
| `--primary-light` / `--candway-primary-light` | `#818cf8` (Indigo-400) | Light accents, hover borders |
| `--secondary` / `--candway-secondary` | `#8b5cf6` / `#7c3aed` (Violet) | Secondary accents, gradients |
| `--accent` / `--candway-accent` | `#06b6d4` (Cyan-500) | Accent highlights |

#### Semantic Colors
| Token | Value | Usage |
|-------|-------|-------|
| `--candway-success` | `#10b981` (Emerald-500) | Success states, hired badges |
| `--candway-warning` | `#f59e0b` (Amber-500) | Warnings, pending states |
| `--candway-danger` | `#ef4444` (Red-500) | Errors, delete actions, rejected |

#### Neutral Scale
| Token | Value | Usage |
|-------|-------|-------|
| `--candway-bg` / `--bg-body` | `#f8fafc` (Slate-50) | Page background |
| `--candway-surface` | `#ffffff` | Card backgrounds |
| `--candway-border` | `#e2e8f0` (Slate-200) | Borders, dividers |
| `--candway-text` | `#1e293b` (Slate-800) | Primary text |
| `--candway-text-muted` | `#64748b` (Slate-500) | Muted text, labels |
| `--text-light` | `#94a3b8` (Slate-400) | Placeholder, disabled |

#### Glassmorphism
| Token | Value |
|-------|-------|
| `--glass-bg` | `rgba(255, 255, 255, 0.65)` |
| `--glass-border` | `rgba(255, 255, 255, 0.8)` |
| `--glass-shadow` | `0 8px 32px 0 rgba(31, 38, 135, 0.07)` |
| `--glass-blur` | `blur(20px)` |

#### Dark Mode
| Token | Light | Dark |
|-------|-------|------|
| `--glass-bg` | `rgba(255,255,255,0.65)` | `rgba(15,23,42,0.6)` |
| `--glass-border` | `rgba(255,255,255,0.8)` | `rgba(255,255,255,0.05)` |
| `--text-main` | `#0f172a` | `#f8fafc` |
| `--text-muted` | `#64748b` | `#94a3b8` |
| `--surface` | `#ffffff` | `#1e293b` |
| `--bg-body` | `#f0f2f8` | `#0f172a` |

#### CSS Variable Inconsistencies
- `design-tokens.css` defines `--candway-*` tokens
- `custom.css` redefines `--primary`, `--secondary` independently
- `recruiter-glass.css` redefines same tokens again
- `dashboard.html`, `jobs.html`, `pipeline.html`, `candidates.html` each define their own `:root { --primary: #6366f1; ... }` inline
- **~5+ competing sources** for the same color tokens

---

### 3.2 Typography

#### Font Families
| Font | Usage | Source |
|------|-------|--------|
| **Outfit** | Primary UI font (headings, body) | Google Fonts |
| **Inter** | Secondary UI font (some recruiter pages) | Google Fonts |
| **Plus Jakarta Sans** | Sidebar + header font | Google Fonts (loaded via components.js) |
| **JetBrains Mono** | Monospace / code | Google Fonts |
| **Instrument Sans** | Public pages | Google Fonts |
| **Cabinet Grotesk** | Public pages | Google Fonts |

#### Font Inconsistencies
- `components.js` loads **Plus Jakarta Sans** as primary (`body { font-family: 'Plus Jakarta Sans' }`)
- `recruiter-glass.css` uses **Inter** (`body { font-family: 'Inter', sans-serif }`)
- `custom.css` uses **Outfit** (`body { font-family: 'Outfit', sans-serif }`)
- `candidates.html` uses **Outfit** (`body { font-family: 'Outfit', sans-serif }`)
- **3 competing body fonts across pages** — no single system font

#### Text Sizes (from public-glass.css — pg-* scale)
| Class | Size | Weight | Usage |
|-------|------|--------|-------|
| `.pg-display` | `clamp(2.2rem, 4.5vw, 4rem)` | 900 | Hero headings |
| `.pg-h2` | `clamp(1.8rem, 3.5vw, 3rem)` | 800 | Section headings |
| `.pg-h3` | `clamp(1.15rem, 1.8vw, 1.5rem)` | 700 | Card headings |
| `.pg-h4` | `1.15rem` | 700 | Sub-headings |
| `.pg-lead` | `1.125rem` | 400 | Lead paragraph |
| `.pg-small` | `0.875rem` | 400 | Body text |
| `.pg-tiny` | `0.75rem` | 400 | Caption, metadata |

*(Recruiter pages use Tailwind classes directly, not pg-* classes)*

#### Letter Spacing
- Section headers: `0.12em` to `0.2em` uppercase
- Navigation labels: `0.02em`
- Badges/pills: `0.04em` to `0.1em`
- Button text: `-0.01em`

---

### 3.3 Spacing & Layout

#### Sidebar
| Variant | Width |
|---------|-------|
| Desktop expanded | 280px |
| Desktop collapsed | 88px |
| Tablet (icons-only) | 72px |
| Mobile (hidden) | 0, slides in from left at 280px |

#### Header
- Height: 76px (desktop), 72px (mobile <680px)
- Padding: `0 32px` (desktop), `12px 14px` (mobile)
- Background: `rgba(255,255,255,0.48)` with `backdrop-filter: blur(24px)`

#### Main Content
- Padding: `24px` left, `80px` top (below header)
- Sidebar offset: `margin-left: var(--sidebar-width)` in desktop

#### Card Padding (inconsistent)
| Source | Value |
|--------|-------|
| `mobile.css` | `1.75rem` |
| `mobile.css` mobile | `1rem` |
| `dashboard.html` inline | `1.25rem` / `1.5rem` |
| `recruiter-glass.css` `.stat-card` | `1rem 1.25rem` |

#### Spacing Scale (Tailwind defaults used throughout)
| Name | Value |
|------|-------|
| `gap-1` | `0.25rem` |
| `gap-2` | `0.5rem` |
| `gap-3` | `0.75rem` |
| `gap-4` | `1rem` |
| `gap-6` | `1.5rem` |
| `gap-8` | `2rem` |

---

### 3.4 Border Radius

| Element | Radius | Page Source |
|---------|--------|-------------|
| Glass cards | `22px` / `1.5rem` | dashboard.html, custom.css |
| Stat cards | `1rem` | recruiter-glass.css |
| Buttons (primary) | `1rem` / `14px` / `12px` | varies across pages |
| Inputs | `12px` / `0.625rem` | recruiter-glass.css |
| Modals | `20px` / `1.25rem` / `3xl` | varies |
| Candidate cards | `12px` | pipeline.html |
| Table container | `22px` / `1.5rem` / `xl` | varies |
| Avatars | `12px` (sidebar), `50%` (header) | |
| Badges/pills | `9999px` / `999px` | |
| Search input | `12px` | components.js |
| Toggle/collapse button | `999px` | components.js |

**Radius inconsistency**: Buttons use different radii across pages (`14px` in dashboard, `12px` in settings, `1rem` in jobs)

---

### 3.5 Shadows

| Element | Shadow |
|---------|--------|
| Glass cards | `0 24px 70px -32px rgba(88,28,135,0.38), inset 0 1px 0 rgba(255,255,255,0.72)` |
| Glass cards (hover) | `0 30px 80px -34px rgba(88,28,135,0.48)` |
| Dropdowns | `0 24px 50px -12px rgba(88,28,135,0.25)` |
| Primary buttons | `0 10px 20px -5px rgba(99,102,241,0.4)` (hover: `0 20px 30px -10px`) |
| Modals | `0 25px 50px -12px rgba(0,0,0,0.15)` |
| Sidebar | `12px 0 50px rgba(46,16,101,0.3)` |
| Toast | `0 10px 25px rgba(0,0,0,0.15)` |

---

### 3.6 Icons

| Property | Value |
|----------|-------|
| Library | **Font Awesome 6** (Free) — loaded via CDN |
| Versions used | `6.4.0`, `6.0.0`, `6.5.1` (inconsistent!) |
| Loading | `media="print" onload="this.media='all'"` with noscript fallback |
| Icon sizes | `14px` (nav), `16px` (buttons), `18px` (sidebar collapsed), `1rem` (card icons) |
| Common icons | `fa-gauge-high`, `fa-briefcase`, `fa-users`, `fa-chart-pie`, `fa-bullhorn`, `fa-video`, `fa-search`, `fa-bell`, `fa-globe`, `fa-cog` |

---

### 3.7 Button Styles

The platform has **no single button system** — styles are duplicated across:

| Style | CSS Class | Defined In | Used On |
|-------|-----------|------------|---------|
| **Primary gradient** | `.btn-premium` | `custom.css` | Jobs, Campaigns |
| **Secondary outline** | `.btn-secondary` | `custom.css` | Jobs, Settings |
| **Glass primary** | `.pg-btn-primary` | `public-glass.css` | Public pages only |
| **Glass secondary** | `.pg-btn-secondary` | `public-glass.css` | Public pages only |
| **Header CTA** | `.topbar-primary-action` | `components.js` | All pages header |
| **Icon button** | `.topbar-icon-btn` | `components.js` | Header actions |
| **Filter button** | (Tailwind classes) | Inline `style` | Pipeline, Candidates |
| **Action button** | `.cw-action-btn--*` | `admin-tables.css` | Admin tables |
| **Quick action** | (Tailwind classes) | Inline `style` | Pipeline cards |

**Button size variants found:**
- `py-4 px-6` (modal primary)
- `py-2.5 px-5` (modal secondary)
- `py-1.5 px-4` (tag/chip button)
- `py-1 px-2 text-[9px]` (quick action on cards)
- `padding: 14px 32px` (pg-btn-lg)
- `padding: 11px 24px` (pg-btn-md)
- `padding: 8px 18px` (pg-btn-sm)

---

### 3.8 Input Styles

| Input Type | Styling | Defined In |
|------------|---------|------------|
| Text input | `bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5` | Inline (Tailwind) |
| Search input | `pl-10 pr-4 py-2.5 rounded-xl bg-slate-50 border` | Inline |
| Select | `px-4 py-2.5 bg-slate-50 border rounded-xl` | Inline |
| Textarea | `rounded-2xl px-5 py-4 border border-slate-200` | Inline |
| Date/time picker | `datetime-local` with input styling | Inline |
| File upload | Drag-and-drop zone with border-dashed | Inline |
| Header search | `padding: 12px 20px 12px 52px border-radius: 12px` | components.js |
| Filter select | `height: 38px border-radius: 0.625rem` | recruiter-glass.css |

**No consistent input component** — every page reinvents input styling with Tailwind utility classes.

---

### 3.9 Navigation

#### Sidebar (components.js)
- Fixed left, 280px wide
- Gradient dark background with violet/indigo radial accents
- Glass blur effect (`backdrop-filter: blur(28px)`)
- Collapsible (desktop): 88px icon-only mode
- Mobile: hidden behind hamburger, slides in from left
- Sections: Overview, Candidates, Operations, Skills, Administration
- Each section: header label + nav links with icons
- Active item: gradient background + glow + active indicator bar (left side)
- User section: avatar, name, role, usage strength bar, sign out
- Upgrade strip: upgrade CTA with icon

#### Top Header (components.js)
- Fixed top, left-aligned to sidebar edge
- Glass background (`backdrop-filter: blur(24px)`)
- Left: hamburger (mobile), search input (`⌘K` shortcut)
- Right: Language switcher, Notifications dropdown, Messages dropdown, User avatar

#### Breadcrumbs
- **Not used** in recruiter pages — no breadcrumb component found

#### Tabs
- Pattern: button row with `.active` class toggle
- Used on: Candidates (All/Shortlisted/Interviewing/Offer/Hired/Rejected)
- Also on: Jobs (All Roles/Online/Dormant/Signals)
- Also: Pipeline (Board/List view toggle)

#### Pagination
- Pattern: `prev 1 2 3 ... next` with page numbers
- Defined in: `admin-tables.css` (`.cw-pagination`)
- Default page size: 20 (constants.js)
- Show threshold: 10 pages

---

### 3.10 Data Display

#### Cards
- `.glass-card`, `.glass-panel`, `.premium-card`, `.job-card`, `.candidate-card`, `.stat-card`
- No single card component — 5+ competing card patterns

#### Tables
- `.admin-table` (custom.css) — force table layout, sticky headers
- `.cw-table-*` (admin-tables.css) — enterprise table design system (800 lines)
- `.candidate-table` (candidates.html) — inline styles
- Pipeline list view table — inline styles
- **~4 different table implementations** doing the same thing

#### Badges
- `.cw-badge--*` (admin-tables.css) — success, warning, danger, neutral, accent + dot indicator
- `.stage-*` pills (candidates.html) — applied, screening, interview, offer, shortlisted, rejected
- `.status-pill` (candidates.html) — active, interviewing, shortlisted, rejected, hired, archived
- `.role-badge` (custom.css) — candidate, recruiter, mentor, admin
- `.nav-badge` (components.js) — new, count, alert
- `.pg-badge-*` (public-glass.css) — primary, success, amber, rose, dark, glass

#### Progress Bars
- `.cw-progress` (admin-tables.css) — 4px height, colored fills
- `#sidebar-strength-bar` (components.js) — strength bar in sidebar
- Interview progress indicator (pipeline cards)

#### Empty States
- Pattern: icon + title + description + optional CTA button
- `.cw-empty` (admin-tables.css): icon + text
- `.pg-empty-state` (public-glass.css): icon + h3 + p
- Pipeline: "No candidates found"

#### Loading States
- Spinner icon (`fa-spinner fa-spin`) + text
- `.cw-loading` (admin-tables.css): spinner + uppercase label
- `.pg-spinner` (public-glass.css): ring + text
- Search: "Searching..." with spinner
- Table: spinner in empty row

---

### 3.11 Feedback Systems

#### Toast (js/toast.js)
- Fixed top-right, `z-[10000]`
- Types: success (green border), error (red), warning (amber), info (blue)
- Icon per type: check, exclamation-circle, exclamation-triangle, info-circle
- Auto-dismiss: 3000ms
- Animation: fade-in-down
- Dismissible via close button (X)

#### Confirmation Dialogs (Components.showConfirm)
- Full-screen overlay with backdrop blur
- White card: icon (question or warning) + title + message + Cancel/Confirm buttons
- Type variants: primary (indigo) and danger (red)
- Returns Promise<boolean>

#### Interview Modal (Components.showInterviewModal)
- Full-screen overlay
- Form: datetime, duration, type select, meeting link, location, agenda
- Submit → API call → toast on success

#### Feedback Modal (Components.showFeedbackModal)
- Star rating (1-5)
- Technical, Communication, Culture Fit, Problem Solving selects (1-5)
- Recommendation select (Strong Yes/Yes/Maybe/No/Strong No)
- Strengths + Areas for Improvement textareas

#### Undo Notifications (recruiter-enhancements.js)
- Fixed bottom-center toast
- "Undid [action]" message + Undo button + countdown timer

---

### 3.12 Responsive System

| Breakpoint | Behavior |
|------------|----------|
| >1024px (Desktop) | Full sidebar (280px), full header, multi-column grids |
| 1024px (Tablet) | Icons-only sidebar (72px), header shrinks, grids go 2-col |
| 768px (Mobile) | Sidebar hidden (slides in via hamburger), full-width content, 1-col grids |
| 680px (Small mobile) | Header wraps, inline labels hidden |
| 480px (Very small) | Button text hidden (icon-only), tighter padding |

**Responsive patterns found:**
- `.mobile-menu-toggle` — visible below 1025px
- `.mobile-overlay` — backdrop for mobile sidebar
- `body.mobile-menu-open` — sidebar visible state
- Tables: overflow-x auto with horizontal scroll on mobile
- Grid columns: collapse to 1fr at 768px

---

## 4. Component Reuse Analysis

### 4.1 Duplicated UI Components

| Component | Files Found | Current Count | Reusable Estimate |
|-----------|-------------|---------------|-------------------|
| **Glass Card** | custom.css, recruiter-glass.css, public-glass.css, dashboard.html, candidates.html, pipeline.html, jobs.html, campaigns.html | ~8+ implementations | 1 |
| **Primary Button** | custom.css, public-glass.css, recruiter-glass.css, components.js, inline in every page | ~20+ implementations | 3-4 variants |
| **Secondary Button** | custom.css, public-glass.css, inline in every page | ~15+ implementations | 2-3 variants |
| **Input** | Inline in every page (Tailwind classes) | ~46 pages, ~50+ instances | 5-6 variants |
| **Select** | Inline in every page | ~46 pages, ~30+ instances | 1-2 variants |
| **Badge/Pill** | admin-tables.css, custom.css, public-glass.css, recruiter-glass.css, inline | ~5+ implementations | 2-3 variants |
| **Modal** | Components.showInterviewModal, Components.showFeedbackModal, Components.showConfirm, inline per page | ~20+ instances | 3-4 variants |
| **Table** | admin-tables.css, custom.css, candidates.html, pipeline.html, billing.html | ~5+ implementations | 1-2 variants |
| **Card Header** | Every page rebuilds the header section | ~46 pages | 1 |
| **Filter Bar** | recruiter-glass.css + inline per page | ~6+ implementations | 1 |
| **Stat Card** | recruiter-glass.css + inline per page | ~10+ implementations | 1 |
| **Empty State** | admin-tables.css, public-glass.css, inline per page | ~15+ instances | 1 |
| **Loading State** | admin-tables.css, public-glass.css, inline per page | ~20+ instances | 1 |
| **Dropdown** | components.js `.candway-dropdown` + inline per page | ~10+ instances | 1 |
| **Pagination** | admin-tables.css + inline per page | ~5+ implementations | 1 |

### 4.2 Total Reusable Component Estimate

**~15-20 reusable React components** could replace the current ~150+ manual HTML/JS duplications.

Core reusable components needed:
1. `Button` (primary/secondary/ghost/danger/icon with loading state)
2. `Input` (text/email/password/number with label, error, helper text)
3. `Select` (with options, label, error)
4. `Textarea` (with label, character count)
5. `Modal` (with header, body, footer slots)
6. `Table` (sortable, filterable, paginated, selectable rows)
7. `Card` (with header, body, footer slots)
8. `StatCard` (icon, value, label, trend)
9. `FilterBar` (search + multiple selects + chips)
10. `Badge` (status variant, color variant, with dot)
11. `Avatar` (image with initials fallback)
12. `Toast` (success/error/warning/info)
13. `Dropdown` (with trigger, content, animations)
14. `Pagination` (page numbers + prev/next)
15. `EmptyState` (icon + title + description + action)
16. `LoadingState` (spinner + text)
17. `ProgressBar` (percentage fill, color variant)
18. `Tabs` (horizontal tab bar with active state)
19. `ConfirmDialog` (title + message + confirm/cancel)

---

## 5. React Mapping

### 5.1 Sitemap → Route → Components → API → Reusables

```
Dashboard
├── /recruiter/dashboard
├── DashboardPage
│   ├── StatCard (×4)           [Reusable: StatCard]
│   ├── AiMatchList             [Reusable: Card]
│   │   └── AiMatchCard (×N)    [Reusable: Card, Badge]
│   ├── TalentScoutSearch       [Reusable: Input, Button]
│   └── ActivityFeed            [Reusable: Timeline]
├── GET /recruiter/stats
├── GET /recruiter/recommendations
├── GET /search/talent-scout?query=
└── GET /recruiter/announcements/active

Jobs Manager
├── /recruiter/jobs
├── JobsPage
│   ├── StatsBar (×4)           [Reusable: StatCard]
│   ├── JobFilters              [Reusable: FilterBar]
│   ├── JobCardGrid             [Reusable: Card]
│   │   └── JobCard (×N)        [Reusable: Card, Badge, Avatar]
│   └── CreateJobModal (2-step) [Reusable: Modal, Input, Select, Textarea]
├── GET /recruiter/jobs/list
├── POST /recruiter/jobs/create
├── PUT /recruiter/jobs/{id}
├── DELETE /recruiter/jobs/{id}
└── GET /skill-trees/list

Talent Pipeline
├── /recruiter/pipeline
├── PipelinePage
│   ├── PipelineStats           [Reusable: StatCard]
│   ├── PipelineFilters         [Reusable: FilterBar]
│   ├── ViewToggle              [Reusable: SegmentedControl]
│   ├── KanbanBoard
│   │   ├── StageColumn (×6)    [Reusable: Card]
│   │   │   └── CandidateCard   [Reusable: Card, Badge, Avatar, ProgressBar]
│   │   │       ├── QuickActions [Reusable: Button]
│   │   │       └── HoverPreview
│   └── ListView
│       └── CandidatesTable     [Reusable: Table, Badge]
├── Modals
│   ├── ScheduleInterviewModal  [Reusable: Modal, DateTime, Select]
│   ├── ConfirmDeleteModal      [Reusable: ConfirmDialog]
│   ├── AssignRecruiterModal    [Reusable: Modal, Select]
│   └── BulkInviteModal         [Reusable: Modal]
├── GET /recruiter/applications/list
├── POST /recruiter/enhancements/quick-action
├── POST /recruiter/enhancements/undo/{id}
├── GET /recruiter/enhancements/hover-preview/{id}
├── POST /recruiter/interviews/schedule
└── POST /recruiter/interviews/{id}/feedback

Candidates List
├── /recruiter/candidates
├── CandidatesPage
│   ├── StatsCards (×6)         [Reusable: StatCard]
│   ├── TabBar                  [Reusable: Tabs]
│   ├── FilterRow               [Reusable: FilterBar]
│   ├── CandidatesTable         [Reusable: Table, Badge, Avatar, Pagination]
│   └── BulkActions             [Reusable: Button]
├── Modals
│   └── MoveStageModal          [Reusable: Modal, Select, Textarea]
├── GET /recruiter/candidates/list
├── POST /recruiter/candidates/bulk-move
└── POST /recruiter/candidates/{id}/assign

Candidate Profile
├── /recruiter/candidate?id=X
├── CandidateProfilePage
│   ├── ProfileHeader           [Reusable: Avatar, Badge]
│   ├── ScoreCard               [Reusable: Card, Badge]
│   ├── AiEvaluation           [Reusable: Card, ProgressBar]
│   ├── SkillsSection           [Reusable: Badge (skill tag)]
│   ├── InterviewTranscript     [Reusable: ChatBubble]
│   ├── NotesSection            [Reusable: Card, Textarea]
│   └── DocumentsSection        [Reusable: Card, Link]
├── GET /recruiter/candidates/{id}
├── GET /recruiter/candidates/{id}/scores
└── POST /recruiter/candidates/{id}/notes

Campaign Manager
├── /recruiter/campaigns
├── CampaignsPage
│   ├── CampaignCardGrid        [Reusable: Card]
│   │   └── CampaignCard (×N)
│   └── CreateCampaignModal     [Reusable: Modal, Input, Select, Textarea, Upload]
├── GET /recruiter/campaigns
├── POST /recruiter/campaigns
├── DELETE /recruiter/campaigns/{id}
└── POST /recruiter/campaigns/{id}/upload

Reports
├── /recruiter/reports, /report-builder, /reports-list
├── ReportsPage / ReportBuilderPage
│   ├── ReportList              [Reusable: Table, Card]
│   ├── ReportBuilder
│   │   ├── MetricSelector      [Reusable: Select, Checkbox]
│   │   ├── DateRangePicker     [Reusable: DatePicker]
│   │   ├── ChartTypeSelector   [Reusable: SegmentedControl]
│   │   └── ChartPreview        (Chart.js)
│   └── ExportButton            [Reusable: Button]
├── GET /recruiter/reports
├── POST /recruiter/reports
├── PUT /recruiter/reports/{id}
├── DELETE /recruiter/reports/{id}
└── GET /recruiter/reports/{id}/export

Settings & Admin
├── /recruiter/settings, /billing, /team, /calendar
├── SettingsPage
│   ├── BrandingSection         [Reusable: Input, Upload]
│   ├── SmtpSection             [Reusable: Input, Button]
│   ├── TeamSection             [Reusable: Table, Avatar, Modal]
│   ├── BillingSection          [Reusable: Card, StatCard, Table, Upload]
│   └── CalendarSection         [Reusable: Card, Button]
├── GET/PUT /recruiter/settings
├── GET/POST/PUT /recruiter/billing/*
└── GET/POST/DELETE /recruiter/team/*
```

---

## 6. UX Observations

### 6.1 Strengths

1. **Glassmorphism design language** is visually distinctive and consistent across card components
2. **Animated background blobs** create a premium, modern feel
3. **Hover preview on pipeline cards** provides glanceable candidate data without navigation
4. **Undo system for quick actions** reduces anxiety around one-click reject/archive
5. **Keyboard shortcuts** (⌘K for search, `/` for filter focus, Escape) improve power-user efficiency
6. **Cross-tab sync** of sidebar state and pipeline changes via localStorage events
7. **Step-based modals** (Create Job wizard) reduce cognitive load
8. **URL-based toast messages** (`?msg=...&type=...`) allow server redirects to show feedback
9. **Color-coded scores** (excellent=emerald, good=blue, average=amber, poor=gray) at-a-glance parsing
10. **Drag-and-drop Kanban** board for pipeline management

### 6.2 Issues

1. **Font inconsistency**: 3 different fonts used as `body` font across recruiter pages (Plus Jakarta Sans, Inter, Outfit)
2. **CSS token duplication**: `--primary` defined in 5+ separate places (design-tokens.css, custom.css, recruiter-glass.css, inline per page)
3. **No loading skeleton on page transitions**: Spinner-only loading, no skeleton placeholders
4. **Fixed header + sidebar**: No `content-visibility` or `contain` optimization for large lists
5. **No breadcrumb navigation**: Users cannot see hierarchical path or go back to parent pages
6. **Inline Tailwind classes**: Every page reinvents styling with utility classes instead of using shared component classes
7. **Font Awesome version inconsistency**: 6.4.0, 6.0.0, 6.5.1 all referenced across pages — potential CSS conflicts
8. **No touch-optimized interactions**: Quick action buttons are `9px` font — too small for mobile
9. **No persistent state**: Page refresh loses filter/sort/pagination state (except URL params on pipeline)
10. **No batch action confirmation count**: Bulk operations don't show selected count before confirming

---

## 7. Design Inconsistencies

### 7.1 Color Token Fragmentation

| Source | `--primary` value | Pages Using |
|--------|-------------------|-------------|
| `design-tokens.css` | `#6366f1` | (attempted canonical) |
| `custom.css` (line 8) | `#6366f1` | Jobs, Candidates |
| `recruiter-glass.css` (line 5) | `#6366f1` | Pipeline, Campaigns |
| `dashboard.html` (line 50) | `#6366f1` | Dashboard |
| `jobs.html` (line 29) | `#6366f1` | Jobs |
| `pipeline.html` (line 34) | `#6366f1` | Pipeline |
| `candidates.html` (inline style) | (not explicitly set) | Candidates |
| `components.js` (line 124) | `#7C3AED` (violet!) | Sidebar (different from palette!) |

**Impact**: The sidebar uses `#7C3AED` as primary, while recruiter pages use `#6366f1` — subtle but noticeable inconsistency.

### 7.2 Card Radius Fragmentation

| Context | Radius Value |
|---------|-------------|
| `.glass-card` (custom.css) | `1.5rem` (24px) |
| `.glass-panel` (recruiter-glass.css) | `1rem` (16px) |
| `.glass-card` (dashboard.html inline) | `22px` |
| `.premium-card` (campaigns.html) | `24px` |
| `.card` (candidate.html) | `16px` |

### 7.3 Button System Fragmentation

- Dashboard buttons: inline Tailwind classes
- Jobs page: `btn-premium`, `btn-secondary` CSS classes
- Pipeline buttons: inline Tailwind classes
- Candidates table buttons: `.cw-action-btn--*`
- Modals: inline Tailwind classes
- Header: `.topbar-primary-action`, `.topbar-icon-btn`
- Quick actions: inline `text-[9px]` Tailwind classes

### 7.4 Table System Fragmentation

- `.admin-table` (custom.css) — used in admin pages
- `.cw-table-*` (admin-tables.css) — used in some recruiter tables
- `.candidate-table` (candidates.html inline) — candidate list
- Pipeline list view — inline table
- Billing history — inline table

### 7.5 Dark Mode Fragmentation

- `components.js` defines `[data-theme="dark"]` styles for sidebar + header
- `recruiter-glass.css` has its own `[data-theme="dark"]`
- `public-glass.css` uses `.dark-mode` class instead of `[data-theme="dark"]`
- `custom.css` defines `--dark-*` variables but no dark mode implementation
- Some recruiter pages have `<style>` blocks with `[data-theme="dark"]` overrides
- **3 competing dark mode mechanisms**

---

## 8. Opportunities for Simplification

| Opportunity | Effort | Impact | Description |
|-------------|--------|--------|-------------|
| **1. CSS Token Consolidation** | Low | High | Move all `--primary` definitions to a single source (`design-tokens.css`), remove inline `<style>` overrides |
| **2. Font Unification** | Low | Medium | Choose one body font (Outfit or Inter) for all recruiter pages |
| **3. Component Extraction** | High | Very High | Extract 15-20 reusable components from 150+ manual implementations |
| **4. Tailwind Component Classes** | Medium | High | Define `@apply` component classes in `custom.css` to replace inline utility class clusters |
| **5. Sass/PostCSS Variables** | Medium | Medium | Use PostCSS nesting and variables to reduce CSS repetition |
| **6. Dark Mode Unification** | Medium | High | Single dark mode strategy (`data-theme` attribute + CSS custom properties) |
| **7. Font Awesome Version Lock** | Low | Medium | Pin to single version across all pages |
| **8. Loading Skeleton System** | Medium | Medium | Replace all spinner loaders with skeleton screens |
| **9. Breadcrumb Component** | Low | Medium | Add breadcrumb component for better navigation context |
| **10. State Persistence** | Medium | High | Save filter/pagination state in URL params across all pages |

---

## 9. Final Recommendation

The Candway Recruiter Platform at 46 pages contains a **complete, functional MPA** with a visually distinctive glassmorphism design language. However, it exhibits **significant architectural debt** typical of fast-growth products:

### Primary Concern: CSS & Component Fragmentation
There are **~4 competing color token systems**, **~3 body fonts**, **~5 card patterns**, **~4 table implementations**, and **~20+ button styles** — all doing the same thing differently. Every HTML page re-decares its own `<style>` block with duplicate CSS.

### Secondary Concern: No Component System
The entire 46-page recruiter platform is built without a single shared UI component. Every page manually duplicates:
- Card structures
- Button styling (Tailwind utility classes repeated)
- Form inputs (same 10+ Tailwind classes on every input)
- Table markup
- Modal markup
- Loading/empty states

### Recommended Approach (Not Redesign, But Consolidation)

1. **Phase 0 — CSS Token Lock**: Centralize all CSS variables into `design-tokens.css`, remove inline `:root` blocks
2. **Phase 1 — Font Lock**: Pick one body font, remove other font loads from recruiter pages
3. **Phase 2 — Button System**: Define 3 button classes in `custom.css` (primary/secondary/ghost) with sm/md/lg sizes
4. **Phase 3 — Card System**: Define `.cw-card` with header/body/footer slots
5. **Phase 4 — Table System**: Adopt `.cw-table-*` (admin-tables.css already has this) across all recruiter tables
6. **Phase 5 — Form System**: Define reusable `.cw-input`, `.cw-select`, `.cw-textarea` classes
7. **Phase 6 — Modal System**: Extract modal pattern from `Components` class into reusable markup
8. **Phase 7 — React Migration (Future)**: When ready, the consolidated CSS and documented patterns will map directly to React components as outlined in Section 5.

The good news: **all the UI patterns already exist** in the codebase. The work is extraction and consolidation, not invention.

---

*End of Audit — All content verified from `C:\Users\rayen\projects\candway_landing_page (2)\masar_landing_page\masar_landing_page\` repository files.*
