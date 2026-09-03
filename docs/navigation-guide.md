# Navigation Guide & Page Inventory — Candway

> **Complete reference:** Every page, every navigation element, every button, every sidebar.  
> **135 pages total** | 15 public + 12 auth + 108 authenticated role pages

---

## Table of Contents

1. [Global Navigation Infrastructure](#1-global-navigation-infrastructure)
   - [AuthGuard: Page Protection System](#11-authguard-page-protection-system)
   - [Top Header (Every Authenticated Page)](#12-top-header-every-authenticated-page)
   - [Page Loading Pattern](#13-page-loading-pattern)
2. [Recruiter Sidebar & Navigation](#2-recruiter-sidebar--navigation)
3. [Candidate & Mentor Sidebar](#3-candidate--mentor-sidebar)
4. [Admin Sidebar & Navigation](#4-admin-sidebar--navigation)
5. [Public Pages (No Auth)](#5-public-pages-no-auth)
6. [Auth Pages (Pre-Auth)](#6-auth-pages-pre-auth)
7. [Candidate Pages (26 pages)](#7-candidate-pages-26-pages)
8. [Recruiter Pages (47 pages)](#8-recruiter-pages-47-pages)
9. [Admin Pages (23 pages)](#9-admin-pages-23-pages)
10. [Mentor Pages (11 pages)](#10-mentor-pages-11-pages)
11. [Cross-Page Navigation Map](#11-cross-page-navigation-map)
12. [All Buttons & Interactive Elements Reference](#12-all-buttons--interactive-elements-reference)

---

## 1. Global Navigation Infrastructure

### 1.1 AuthGuard: Page Protection System

**How pages protect themselves:** Every authenticated page under `/pages/{role}/` auto-initializes auth protection on `DOMContentLoaded`. The system works identically through `app-auth.js` (modern) and the backward-compatible `auth-guard.js` wrapper.

```javascript
isAuthPage = path startsWith '/candidate/' OR '/recruiter/' OR '/mentor/' OR '/admin/'
if (isAuthPage):
    1. requireAuth()               → redirects to login if no valid session
    2. checkSession()              → async /auth/me validation
    3. refreshUser() / refreshUserCache() → fetches fresh user data
    4. Role guard based on path:
       '/candidate/' → allow candidate, admin
       '/recruiter/' → allow recruiter, admin
       '/mentor/'    → allow mentor, admin
       '/admin/'     → allow admin ONLY
```

**Login URL mappings by role:**

| Path prefix | Required role | Login page URL |
|-------------|--------------|----------------|
| `/candidate/...` | candidate or admin | `pages/auth/login-candidate.html` → `/login` |
| `/recruiter/...` | recruiter or admin | `pages/auth/login-recruiter.html` → `/login/recruiter` |
| `/admin/...` | admin only | `pages/auth/login-admin.html` → `/login/admin` |
| `/mentor/...` | mentor or admin | `pages/auth/login-mentor.html` → `/login/mentor` |

**Session timeout:** 24 hours (stored in `localStorage.loggedInAt`). On expiry, clears auth keys, redirects to login with `?session=expired`.

---

### 1.2 Top Header (Every Authenticated Page)

**Rendered by:** `Components.renderTopHeader()` in `js/components.js:1803-1893`  
**Rendered into:** First found of: `#top-header-container`, `#header-container`, `#top-bar-extra`, `#topbar-container`

**Layout (left to right):**

```
┌─────────────────────────────────────────────────────────────────────┐
│ [☰]  [🔍 Search... (⌘K)]     [+ New]  [🌐]  [🔔]  [💬]  [👤 JD] │
└─────────────────────────────────────────────────────────────────────┘
```

| # | Element | Icon | Action | Details |
|---|---------|------|--------|---------|
| 1 | **Mobile menu toggle** | ☰ (hamburger SVG) | `Components.toggleMobileMenu()` | Visible only on mobile <1024px. Opens sidebar as overlay. |
| 2 | **Global search** | 🔍 magnifier icon | `POST /api/v1/search` | Placeholder: Recruiter → "Search candidates, jobs...", Candidate → "Search jobs, companies...". Shortcut: `⌘K` / `Ctrl+K`. 300ms debounce. Results dropdown with glass styling. |
| 3 | **Primary CTA button** | ➕ (recruiter) / ✅ (candidate) | Recruiter → `/recruiter/jobs` ("Post Job"), Candidate → `/onboarding` ("New audit") | Indigo primary button, Font Awesome icon + label |
| 4 | **Language switcher** | 🌐 globe | `Components.toggleLangDropdown()` | Dropdown: 🇬🇧 EN, 🇫🇷 FR, 🇹🇳 AR. Calls `window.setLanguage(lang)`. |
| 5 | **Notifications bell** | 🔔 bell | `Components.toggleNotifications()` | Fetches `GET /notifications/latest?limit=5`. Red dot badge for unread. "Mark all read" button. "View all notifications" link → `/notifications`. |
| 6 | **Messages dropdown** | 💬 comment dots | `Components.toggleMessages()` | Fetches `GET /messages/conversations`. Shows 5 latest. Unread count badge. Footer → `/recruiter/messages` or `/candidate/messages`. |
| 7 | **User profile chip** | Avatar image + name + role | None (display only) | Shows name + uppercase role label. Rounded pill with primary-light bg. |

---

### 1.3 Page Loading Pattern

Every authenticated page loads JS in this order:

```html
<!-- CORE BUNDLE — loaded on every page (139 KB) -->
<script src="/js/dist/core.js?v=2026072618"></script>

<!-- SHARED FEATURES (33 KB) — candidate + recruiter pages -->
<script src="/js/dist/shared.js?v=2026072618"></script>

<!-- ROLE-SPECIFIC BUNDLE (one of): -->
<script src="/js/dist/candidate.js?v=2026072618"></script>   <!-- 160 KB -->
<script src="/js/dist/recruiter.js?v=2026072618"></script>    <!-- 275 KB -->
<script src="/js/dist/admin.js?v=2026072618"></script>       <!-- 41 KB -->
<script src="/js/dist/mentor.js?v=2026072618"></script>      <!-- 8 KB -->

<!-- Inline page-specific script -->
<script>
    document.addEventListener('DOMContentLoaded', () => {
        Components.init('active_page_id');
        loadPageData();
    });
</script>
```

**CSS files loaded** (varies by page — see section 4 of `frontend-structure-design-system.md`):
- `tailwind-landing.css` — Tailwind v4 output (pre-built)
- `custom.css` — Base app styles (sidebar, glass, admin)
- `public-glass.css` — Candidate/public glass system
- `recruiter-glass.css` — Recruiter-specific glass
- `admin-tables.css` — Enterprise table system
- `tooltips.css` — CSS tooltip system
- CDN Tailwind (`cdn.tailwindcss.com`) — some pages load this dynamically
- Inline `<style>` blocks — page-specific CSS

---

## 2. Recruiter Sidebar & Navigation

**Rendered by:** `Components.renderSidebar()` in `js/components.js:1317-1495`  
**Target container:** `<div id="sidebar-container">`

### 2.1 Sidebar Sections & Items

```
┌──────────────────────────────────────────────────────────────┐
│                     [CANDWAY LOGO]                           │
│                                                              │
│  ── OVERVIEW ──────────────────────────────────────────────  │
│  📊 Dashboard             → /recruiter/dashboard            │
│  💼 Jobs                  → /recruiter/jobs                  │
│  ✨ Create Job (Skill-First)  → /recruiter/job-wizard        │
│  📈 Analytics             → /recruiter/analytics             │
│  📄 Reports               → /recruiter/reports               │
│                                                              │
│  ── CANDIDATES ────────────────────────────────────────────  │
│  👥 Candidates Management → /recruiter/candidates            │
│                                                              │
│  ── OPERATIONS ────────────────────────────────────────────  │
│  🗃️ Talent Pipeline       → /recruiter/pipeline              │
│  📣 Campaign Manager      → /recruiter/campaigns             │
│  🎥 Interviews            → /recruiter/interviews            │
│                                                              │
│  ── SKILLS ───────────────────────────────────────────────  │
│  🌳 Skills Library        → /recruiter/skill-tree-library    │
│                                                              │
│  ── ADMINISTRATION ───────────────────────────────────────  │
│  👥 Team                  → /recruiter/team                  │
│  ⚙️ Settings              → /recruiter/settings              │
│  ❓ Help & Guide          → # (opens HelpCenter modal)       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 📈 Talent Accelerator                                 │   │
│  │ AI Sourcing, priority matching                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Avatar] John Doe                                           │
│           RECRUITER                                    ›    │
│  Usage Balance          72%                                  │
│  [████████░░░░░░░░░░░░░░░░]                                  │
│                                                              │
│  🚪 Sign Out                                                │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Recruiter Sidebar Interactive Elements

| Element | Type | Action | Details |
|---------|------|--------|---------|
| **Logo** | Link (image) | `/recruiter/dashboard` | Candway logo image, max 140px width |
| **Collapse button** | `◀` chevron button | `Components.toggleSidebar()` | Toggles `sidebar-collapsed` class. Persisted in `localStorage.candway_sidebar_collapsed`. Collapsed width = 88px. In RTL, chevron direction reverses. |
| **All nav links** | `<a>` links | Navigate to href | Active detection: `pathname === href` OR `pathname.startsWith(href + '/')`. Active item gets `.active-item` class (indigo highlight + light-sweep animation). |
| **Help & Guide** | Nav link with onclick | `HelpCenter.openModal()` | Opens help center modal instead of navigating. No page navigation. |
| **Upgrade strip** | Link | Recruiter → `/recruiter/subscription` | "Talent Accelerator" CTA. Shows "AI Sourcing, priority matching" subtitle. |
| **User card** | Link | `/recruiter/settings` | Shows avatar (generated via `ui-avatars.com` API with fallback SVG), name, "Recruiter" role label, chevron-right icon. |
| **Usage balance** | Display only | — | Green percentage bar. Shows current usage against plan limits. |
| **Sign Out** | Link | `/logout` | Red hover effect. Font Awesome arrow-right-from-bracket icon. |

### 2.3 Collapse Behavior

| State | Width | Visible Elements | Hidden Elements |
|-------|-------|-----------------|-----------------|
| **Expanded** | 280px | All | — |
| **Collapsed** | 88px | Icons only | Labels, section headers, upgrade strip, user info, badge text |
| **Mobile (<1024px)** | Full width overlay | All (slide in from left) | — |
| **Tablet (768-1024px)** | 240px | All (reduced) | — |

---

## 3. Candidate & Mentor Sidebar

**Note:** Mentors use the **same sidebar** as candidates. There is no dedicated mentor sidebar.

### 3.1 Sidebar Structure

```
┌──────────────────────────────────────────────────────────────┐
│                     [CANDWAY LOGO]                           │
│                                                              │
│  ── INTELLIGENCE ──────────────────────────────────────────  │
│  🏠 Dashboard            → /candidate/dashboard              │
│  👤 Profile              → /candidate/profile                │
│  🎓 Learning             → /candidate/learning               │
│                                                              │
│  ── PIPELINE ──────────────────────────────────────────────  │
│  💼 Jobs                 → /candidate/jobs                   │
│                                                              │
│  ── TRACKING ▼ ────────────────────────────────────────────  │
│  📂 Applications         → /candidate/applications           │
│  📅 Interviews           → /candidate/interviews             │
│                                                              │
│  ── ACCOUNT ───────────────────────────────────────────────  │
│  ⚙️ Settings             → /candidate/settings               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🚀 Career Accelerator                                │   │
│  │ Coaching, insights, priority matching                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Avatar] Jane Doe                                           │
│           CANDIDATE                                    ›    │
│  Profile Strength        65%                                 │
│  [████████████░░░░░░░░░░░░]                                  │
│                                                              │
│  🚪 Sign Out                                                │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Candidate Sidebar Interactive Elements

| Element | Type | Action | Details |
|---------|------|--------|---------|
| **Logo** | Image link | `/candidate/dashboard` | Candway logo |
| **Collapse button** | `◀` chevron | `Components.toggleSidebar()` | Same as recruiter |
| **Tracking group** | Collapsible section | `Components.toggleNavGroup()` | Click section header to expand/collapse "Tracking" items. State persisted in localStorage. Cheveron rotates -90deg when collapsed. |
| **Upgrade strip** | Link | `/subscription` | "Career Accelerator" CTA. "Coaching, insights, priority matching" subtitle. |
| **User card** | Link | `/candidate/profile` | Avatar, name, "Candidate" role |
| **Profile strength** | Display only | — | Indigo percentage bar. Shows profile completion. |
| **Sign Out** | Link | `/logout` | Same as recruiter |

---

## 4. Admin Sidebar & Navigation

**Rendered by:** `renderAdminSidebar()` in `js/admin-components.js:91-153`  
**Target container:** `<div id="admin-sidebar-container">`  
**Note:** This is a **completely different** sidebar from the recruiter/candidate one. It has its own rendering logic, RBAC, and styling.

### 4.1 Admin Sidebar Structure

```
┌──────────────────────────────────────────────────────────────┐
│  [☰]                                                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ [Candway Logo]                                         │  │
│  │ CandwayAdmin                                           │  │
│  │ Control Panel                                          │  │
│  │                                                        │  │
│  │ ── OVERVIEW ─────────────────────────────────────────  │  │
│  │ 🖥️ Dashboard              → /admin/dashboard           │  │
│  │ 🧠 Intelligence & Stats   → /admin/analytics ☐        │  │
│  │ 👥 Users & Roles          → /admin/users ☐            │  │
│  │                                                        │  │
│  │ ── COMMERCIAL ───────────────────────────────────────  │  │
│  │ 👑 Subscriptions          → /admin/subscriptions ☐    │  │
│  │ 📈 Usage Monitor          → /admin/recruiter-usage ☐  │  │
│  │ 🪙 Transactions           → /admin/payments ☐         │  │
│  │ 🧾 Invoices (TND)         → /admin/invoices ☐         │  │
│  │ 📣 Marketing              → /admin/marketing ☐        │  │
│  │                                                        │  │
│  │ ── CONTENT & CMS ────────────────────────────────────  │  │
│  │ ✍️ Blog Manager           → /admin/content ☐          │  │
│  │ 🌍 Opportunities          → /admin/opportunities ☐    │  │
│  │                                                        │  │
│  │ ── LMS & TRAINING ───────────────────────────────────  │  │
│  │ 🧑‍🏫 Courses               → /admin/courses ☐           │  │
│  │ 💼 Job Board              → /admin/jobs ☐             │  │
│  │ 🗂️ Categories             → /admin/categories ☐       │  │
│  │                                                        │  │
│  │ ── SYSTEM ───────────────────────────────────────────  │  │
│  │ 🎫 Support                → /admin/support ☐          │  │
│  │ ⚙️ Settings               → /admin/settings ☐         │  │
│  │ 🧠 Prompt Management      → /admin/prompt-management ☐│  │
│  │ 🤖 AI Sales Engine        → /admin/ai-sales ☐         │  │
│  │ 📡 Broadcasts             → /admin/announcements ☐    │  │
│  │ 🖥️ System Health          → /admin/technical ☐        │  │
│  │                                                        │  │
│  │ ── SCORING ──────────────────────────────────────────  │  │
│  │ 🗂️ Rubric Builder         → /admin/rubric-builder      │  │
│  │ 🧪 A/B Testing            → /admin/ab-testing ☐       │  │
│  │                                                        │  │
│  │ ── COMPLIANCE (TN) ──────────────────────────────────  │  │
│  │ ✅ KYB Verification       → /admin/verifications ☐    │  │
│  │                                                        │  │
│  │ ── LINKS ────────────────────────────────────────────  │  │
│  │ 🔗 Live Site (Candidate)  → /dashboard                 │  │
│  │ 💼 Live Site (Recruiter)  → /recruiter/dashboard       │  │
│  │                                                        │  │
│  │ ── FOOTER ───────────────────────────────────────────  │  │
│  │ [EN] [FR] [AR]                                         │  │
│  │ 🚪 Logout                                              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

☐ = RBAC-protected (requires specific admin_permission)
```

### 4.2 Admin Sidebar Interactive Elements

| Element | Type | Action | Details |
|---------|------|--------|---------|
| **Toggle button** | Hamburger SVG | `window.toggleAdminSidebar(true)` | Opens mobile sidebar overlay |
| **Close button** | `×` | `window.toggleAdminSidebar(false)` | Closes mobile sidebar overlay |
| **Overlay** | Click backdrop | `window.toggleAdminSidebar(false)` | Mobile backdrop click-to-close |
| **Logo + brand** | Display | — | "CandwayAdmin" brand name + "Control Panel" tagline |
| **All nav links** | `<a>` links | Navigate to href | Active detection via `normalizePath()`. Links with `data-permission` attribute are RBAC-filtered. |
| **Language switcher** | 3 buttons | `setLanguage(lang)` | EN / FR / AR toggle. Active state highlighted. |
| **Logout** | Button | `logout()` | `POST /api/v1/logout` → clears auth → redirect to landing. |

### 4.3 Admin RBAC (Permission-Based Filtering)

```javascript
// applyRBACUI() fetches user's admin_permissions from /auth/me
// Then hides sidebar links whose data-permission doesn't match
// Super admins (is_super_admin) bypass all filtering
```

| Permission | Protected Links |
|------------|----------------|
| `view_analytics` | Analytics |
| `view_users` | Users, Support |
| `manage_finance` | Subscriptions, Usage Monitor, Transactions, Invoices |
| `manage_content` | Marketing, Blog, Opportunities, Courses, Jobs, Categories, Prompt Management, AI Sales, Broadcasts, A/B Testing |
| `manage_admins` | Settings, Verifications |
| `view_logs` | System Health |

---

## 5. Public Pages (No Auth)

These pages are at the root (`*.html`). They require no authentication and use the **Custom Public** design system (Cabinet Grotesk + Instrument Sans fonts, indigo/violet palette, glassmorphism).

| # | Page File | URL | Description | Key Elements / Buttons |
|---|-----------|-----|-------------|----------------------|
| 1 | **index.html** | `/` or `/index.html` | **Landing page** — Hero with animated gradient blobs, floating elements, "AI révèle ton vrai potentiel" headline | • **CTA buttons:** "Get Started" → redirects to signup, "Learn More" → scroll to features<br>• **Nav bar:** Logo, features, pricing, blog, login button<br>• **Sections:** Features carousel, testimonials, stats counter, FAQ accordion<br>• **Footer:** Links to privacy, terms, social media |
| 2 | **blogs.html** | `/blogs` | **Blog listing** — Card grid of articles with categories | • **Filter tabs:** Category pills (All, AI, Career, etc.)<br>• **Blog cards:** Title, excerpt, author, date, read time badge<br>• **Pagination:** Page numbers<br>• **Search:** Blog search input |
| 3 | **blog-details.html** | `/blog/{slug}` | **Blog article** — Full article layout | • **Scroll progress bar:** Top fixed progress indicator<br>• **Share buttons:** Social media share (LinkedIn, Twitter, Facebook)<br>• **Related articles:** Bottom card grid<br>• **Back to blog:** Link → `/blogs` |
| 4 | **jobs.html** | `/jobs` | **Public job board** — Job listings | • **Search bar:** Full-text job search<br>• **Category pills:** Filter by job category<br>• **Job cards:** Title, company, location, type badge, apply button<br>• **Pagination** |
| 5 | **job-details.html** | `/job/{id}` | **Public job detail** | • **Apply CTA:** "Postuler" button → login/signup or application form<br>• **Company info:** Logo, description, website link<br>• **Job info:** Description, requirements, benefits<br>• **Share button** |
| 6 | **courses.html** | `/courses` | **Public course catalog** | • **Category tabs:** Course categories filter<br>• **Course cards:** Title, instructor, rating stars, price, enrollment count<br>• **Search:** Course search |
| 7 | **pricing.html** | `/pricing` | **Pricing plans** | • **Toggle:** Monthly / Yearly billing toggle<br>• **Pricing cards:** 3 tiers (Free, Pro, Enterprise) with feature list<br>• **CTA buttons:** "Get Started" / "Contact Sales"<br>• **Feature comparison:** Full table |
| 8 | **privacy.html** | `/privacy` | **Privacy policy** | • Clean prose layout. No interactive elements. |
| 9 | **terms.html** | `/terms` | **Terms of service** | • Clean prose layout. No interactive elements. |
| 10 | **opportunities.html** | `/opportunities` | **Public opportunities** | • **Opportunity cards:** Title, description, apply modal trigger<br>• **Apply modal:** Form with name, email, message |
| 11 | **404.html** | `/404` | **Not found page** | • **Button:** "Back to Home" → `/`<br>• Animated illustration |
| 12 | **500.html** | `/500` | **Server error page** | • **Button:** "Try Again" → reload<br>• **Button:** "Contact Support" |
| 13 | **setup-wizard.html** | `/setup-wizard` | **Initial setup** | • **Step indicator:** Multi-step progress dots<br>• **Form panels:** Glass-styled sections<br>• **Navigation:** Next/Previous buttons |

---

## 6. Auth Pages (Pre-Auth)

These pages are in `pages/auth/`. They load before authentication and share the **Dark Glass** design system (slate-950 background, blur containers, indigo/violet accents).

### 6.1 Login Pages

| # | Page | URL | Role | Key Elements / Buttons |
|---|------|-----|------|----------------------|
| 1 | **login.html** | `/login` | All roles | • **Role tabs:** Candidate / Recruiter / Mentor / Admin pills to switch login variant<br>• **Email input:** Premium glass input with focus glow<br>• **Password input:** With show/hide toggle<br>• **"Sign In" button:** Primary gradient CTA<br>• **"Forgot Password?" link:** → `/forgot-password`<br>• **"Don't have an account? Sign up" link:** → `/signup`<br>• **Social login:** Google OAuth button<br>• **Background:** Animated gradient (indigo + emerald) |
| 2 | **login-candidate.html** | `/login/candidate` | candidate | • Violet-accented glass (`--primary: #7C3AED`)<br>• Same form as login.html with candidate branding<br>• **"Candidate Portal" badge** |
| 3 | **login-recruiter.html** | `/login/recruiter` | recruiter | • Indigo-accented glass (`--primary: #6366F1`)<br>• **"Recruiter Portal" badge**<br>• "Create company account" link → signup-recruiter |
| 4 | **login-admin.html** | `/login/admin` | admin | • Dark enterprise glass, no frills<br>• Minimal form: email + password only |
| 5 | **login-mentor.html** | `/login/mentor` | mentor | • Purple-accented glass<br>• **"Mentor Portal" badge** |

### 6.2 Signup Pages

| # | Page | URL | Key Elements / Buttons |
|---|------|-----|----------------------|
| 6 | **signup.html** | `/signup` | • **Role selector:** Candidate / Recruiter / Mentor tabs<br>• **Form:** Name, email, password, confirm password<br>• **"Create Account" button**<br>• **Google signup button**<br>• **"Already have an account? Sign in" link** |
| 7 | **signup-recruiter.html** | `/signup/recruiter` | • **Company fields:** Company name, website, size<br>• Same form base |
| 8 | **signup-mentor.html** | `/signup/mentor` | • **Mentor fields:** Expertise areas, bio |

### 6.3 Password & Verification Pages

| # | Page | URL | Key Elements / Buttons |
|---|------|-----|----------------------|
| 9 | **forgot-password.html** | `/forgot-password` | • **Email input:** Single field form<br>• **"Send Reset Link" button**<br>• **"Back to Sign In" link** |
| 10 | **reset-password.html** | `/reset-password` | • **Token from URL:** Hidden/embedded<br>• **New password + confirm inputs**<br>• **"Reset Password" button** |
| 11 | **verify-email.html** | `/verify-email` | • **Message:** "Check your email for verification link"<br>• **"Resend email" button** (with cooldown timer) |
| 12 | **verify-otp.html** | `/verify-otp` | • **6-digit OTP inputs:** Individual digit boxes with auto-advance<br>• **"Verify" button**<br>• **Resend timer:** Countdown + resend link |
| 13 | **google-callback.html** | `/google-callback` | • **Processing spinner:** Auto-redirects after OAuth callback<br>• No user input |

---

## 7. Candidate Pages (26 pages)

**Base URL:** `/candidate/...`  
**Sidebar:** Candidate sidebar (see section 3)  
**JS Bundle:** `core.js` + `shared.js` + `candidate.js`  
**Design System:** Violet (`#7C3AED`) — Public Glass (`public-glass.css`)

---

### 7.1 Candidate Dashboard

**File:** `pages/candidate/dashboard.html`  
**URL:** `/candidate/dashboard`  
**Sidebar active:** `nav_overview`

```
┌──────────────────────────────────────────────────────────────┐
│                    TOP HEADER                                 │
│  [☰] [🔍 Search...]    [📋 New Audit] [🌐] [🔔] [💬] [👤] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Ambient Background (radial violet gradient + grid pattern)  │
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 📊      │ │ 📋      │ │ 📈      │ │ 🏆      │           │
│  │ 85%     │ │ 12      │ │ 4       │ │ 3       │           │
│  │ Profile │ │ Apps    │ │ Skills  │ │ Badges  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  ┌────────────────────────┐ ┌─────────────────────────┐     │
│  │ 📈 Profile Views       │ │ 🎯 AI Match Score        │     │
│  │ [Line chart]           │ │ [Gauge chart]            │     │
│  │                        │ │                          │     │
│  │ +24% this week         │ │ 92% Match with top job  │     │
│  └────────────────────────┘ └─────────────────────────┘     │
│                                                              │
│  ┌────────────────────────┐ ┌─────────────────────────┐     │
│  │ 📋 Recent Applications │ │ 🏆 Achievements          │     │
│  │ • Sr. Dev @ Acme   ✅ │ │ ★ Profile Complete      │     │
│  │ • Jr. Dev @ Beta   ⏳ │ │ ★ First Interview       │     │
│  │ • Intern @ Gamma   📋 │ │ ★ CV Uploaded           │     │
│  │                        │ │                          │     │
│  │ [View All →]           │ │ [View All →]             │     │
│  └────────────────────────┘ └─────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

**Interactive Elements:**

| Element | Action | Details |
|---------|--------|---------|
| **Stat cards** (4) | Display only | Profile Strength (%), Total Applications, Skills Assessed, Achievements Badges |
| **Profile Views chart** | Display (Chart.js) | Line chart showing profile view trends over time |
| **AI Match Score gauge** | Display (Chart.js) | Doughnut gauge showing match % with top job |
| **Recent Applications** | Links | Each application row → `/candidate/applications` (opens detail). "View All" → `/candidate/applications` |
| **Achievements** | Display | Badge list with completion checkmarks |
| **Quick actions** | Links | "Complete Profile" → `/candidate/profile`, "Take Interview" → `/candidate/interview`, "Browse Jobs" → `/candidate/jobs` |

---

### 7.2 Candidate Profile

**File:** `pages/candidate/profile.html` | **URL:** `/candidate/profile` | **Sidebar:** `nav_profile`

| Element | Action | Details |
|---------|--------|---------|
| **Avatar upload** | Click to upload | Opens file picker. Crops to square. Auto-uploads. |
| **Banner image** | Click to upload | Cover photo (16:9 ratio) |
| **Edit buttons** (pencil icons) | Inline edit | Each section (name, headline, bio, skills) becomes editable |
| **Skills tags** | Add/Remove | Pill-shaped tags. "Add skill" input with autocomplete. Click X to remove. |
| **"Save Profile"** | Button | `PUT /candidate/profile` — saves all changes |
| **"View Public Profile"** | Link | → `/candidate/profile-view` |
| **Profile Visitors** | Link | → `/candidate/profile-visitors` |
| **Skill assessment** | Button | → `/candidate/interview` (start AI interview to assess skills) |
| **LinkedIn sync** | Button | OAuth to import profile data |
| **CV upload** | File input | Upload CV PDF/DOCX → `/candidate/cv-builder` |

**Sections:** Avatar + banner, Name + Headline, Bio, Skills (tags), Experience timeline, Education, Certifications, Languages, Social links (LinkedIn, GitHub, Portfolio, Website).

---

### 7.3 Candidate Profile View (Public)

**File:** `pages/candidate/profile-view.html` | **URL:** `/candidate/profile-view`

| Element | Action | Details |
|---------|--------|---------|
| **Share profile** | Button | Copies profile URL to clipboard |
| **Download as PDF** | Button | Generates PDF resume |
| **Back to edit** | Link | → `/candidate/profile` |
| All other elements | Display only | Read-only view of profile sections |

---

### 7.4 Candidate Applications

**File:** `pages/candidate/applications.html` | **URL:** `/candidate/applications` | **Sidebar:** `nav_applications`

| Element | Action | Details |
|---------|--------|---------|
| **Status filter pills** | Filter | All / In Review / Interview / Offer / Rejected. Each pill shows count. |
| **Application cards** | Click → detail | Each card shows: company logo, job title, company name, status badge (colored pill), date applied, stage progress bar. |
| **"View Details"** | Button per card | Opens slide panel or → detail view |
| **"Withdraw"** | Button per card | Confirmation modal → `DELETE /api/v1/candidate/applications/{id}` |
| **Empty state** | Display | Illustration + "No applications yet" + "Browse Jobs" CTA |
| **Stage indicator** | Visual bar | Shows current pipeline stage (Applied → Screening → Interview → Offer) |

---

### 7.5 Candidate Saved Jobs

**File:** `pages/candidate/saved-jobs.html` | **URL:** `/candidate/saved-jobs`

| Element | Action | Details |
|---------|--------|---------|
| **Saved job cards** | Display | Similar to job cards with bookmark icon filled |
| **"Remove"** | Button per card | Unsaves job (toggles bookmark) |
| **"Apply Now"** | Button per card | → application flow for that job |
| **Empty state** | Display | "No saved jobs" + "Browse Jobs" CTA |

---

### 7.6 Candidate Jobs (Job Board)

**File:** `pages/candidate/jobs.html` | **URL:** `/candidate/jobs` | **Sidebar:** `nav_jobs`

```
┌──────────────────────────────────────────────────────────────┐
│                    TOP HEADER                                 │
├──────────────────────────────────────────────────────────────┤
│  [🔍 Search jobs, companies...]       [Filters ▼]            │
│                                                              │
│  ┌──────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐          │
│  │ All Jobs │ │Remote  │ │ Full-Time│ │ Contract │          │
│  └──────────┘ └────────┘ └─────────┘ └──────────┘          │
│                                                              │
│  ┌──────────────────────────────────┐                        │
│  │ [Logo] Sr. Software Engineer     │ 92%  ★★★★★           │
│  │        Acme Corp · Remote        │ [Apply] [Save]         │
│  │        $120k-150k · Full-Time    │                        │
│  │        🏷️ Python, React, AWS     │                        │
│  ├──────────────────────────────────┤                        │
│  │ [Logo] Jr. Developer             │ 85%  ★★★★☆           │
│  │        Beta Inc · Tunis          │ [Apply] [Save]         │
│  │        $40k-60k · Full-Time      │                        │
│  │        🏷️ JavaScript, Node.js    │                        │
│  └──────────────────────────────────┘                        │
│                                                              │
│  [Pagination: < 1 2 3 ... 12 >]                              │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Search bar** | Input | Full-text job search with autocomplete |
| **Category pills** | Filter | All / Remote / Full-Time / Contract / Internship |
| **Sort dropdown** | Select | Relevance / Date / Salary / Match Score |
| **Job cards** | Click → detail | Each card: company logo, title, company, location, salary, skills tags, match score badge, star rating (AI-predicted fit) |
| **"Apply"** | Button per card | Starts application flow (submits CV) → `POST /api/v1/candidate/applications` |
| **"Save"** (bookmark) | Icon toggle | Saves/unsaves job → `POST /api/v1/candidate/saved-jobs` |
| **Match score** | Badge | Percentage: green (80%+), amber (60-80%), red (<60%) |
| **Pagination** | Nav | Page numbers + prev/next |
| **Empty state** | Display | "No jobs match your filters" + suggestion |

---

### 7.7 Candidate Interview

**File:** `pages/candidate/interview.html` | **URL:** `/candidate/interview` (or `/candidate/interview?application_id=X`)

```
┌──────────────────────────────────────────────────────────────┐
│  🎥 AI Interview                              ⏱️ 12:34       │
│                                                              │
│  ┌─────────────────────────────────────────────┐             │
│  │                                             │             │
│  │         AI Avatar / Voice Interface          │             │
│  │                                             │             │
│  │     "Tell me about a challenge you faced"   │             │
│  │                                             │             │
│  │              [🎤 Recording...]               │             │
│  │                                             │             │
│  │         [Pause]  [Stop]  [Skip]             │             │
│  └─────────────────────────────────────────────┘             │
│                                                              │
│  ┌── Transcript Sidebar ──────────────────────────┐          │
│  │ Question 1/8                                   │          │
│  │ AI: Tell me about yourself                      │          │
│  │ You: I'm a software engineer with...           │          │
│  │                                                │          │
│  │ Question 2/8                                   │          │
│  │ AI: Why do you want this role?                 │          │
│  └────────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Record button** | 🎤 Toggle | Start/stop recording. Changes to red when recording. |
| **Pause button** | ⏸️ Toggle | Pause/resume interview |
| **Stop button** | ⏹️ | End interview → submit for analysis |
| **Skip button** | ⏭️ | Skip current question, go to next |
| **Timer** | Display | Elapsed time (MM:SS) |
| **Question counter** | Display | "Question 3/8" |
| **AI avatar** | Animated visual | Flowing waveform/orb animation when AI speaks |
| **Transcript sidebar** | Scrollable | Running conversation log. AI messages (left, violet) / User messages (right, indigo). |
| **"Exit interview"** | Link | → confirmation modal → back to dashboard |

---

### 7.8 Candidate Interviews List

**File:** `pages/candidate/interviews.html` | **URL:** `/candidate/interviews` | **Sidebar:** `nav_interviews`

| Element | Action | Details |
|---------|--------|---------|
| **Interview cards** | Click → detail | Each card: job title, company, date, duration, score badge |
| **"Start New Interview"** | Button | → `/candidate/interview` |
| **Score badge** | Display | Green (80%+), amber, red. Click → `/candidate/interview-analysis` |
| **Filter** | Tabs | All / Completed / Pending / In Progress |
| **Empty state** | Display | "No interviews yet" + "Take your first interview" CTA |

---

### 7.9 Candidate Interview Analysis

**File:** `pages/candidate/interview-analysis.html` | **URL:** `/candidate/interview-analysis?id=X`

| Element | Action | Details |
|---------|--------|---------|
| **Radar chart** | Display (Chart.js) | 5-axis skill assessment (Technical, Communication, Problem-solving, etc.) |
| **Overall score** | Large gauge | Percentage with letter grade |
| **Skill breakdown** | Horizontal bar chart | Per-skill scores with labels |
| **Strengths** | List | Top 3-5 strengths identified by AI |
| **Weaknesses** | List | Areas for improvement |
| **AI summary** | Text panel | Paragraph analysis from AI |
| **"Download Report"** | Button | PDF export |
| **"Share"** | Button | Share link to recruiter (if applicable) |
| **"Retake Interview"** | Button | → `/candidate/interview` |
| **Transcript viewer** | Accordion | Full interview transcript with timestamps |

---

### 7.10 Candidate CV Builder

**File:** `pages/candidate/cv-builder.html` | **URL:** `/candidate/cv-builder`

| Element | Action | Details |
|---------|--------|---------|
| **Template selector** | Card grid | Choose CV template design |
| **Drag-and-drop sections** | Reorder | Drag sections (Experience, Education, Skills, etc.) to reorder |
| **Add section** | Button | Dropdown: Add Experience / Education / Skill / Language / Project |
| **Edit section** | Inline form | Click to edit each entry |
| **Delete section** | Trash icon | Remove section with confirmation |
| **Live preview** | Panel | Real-time CV preview on the right |
| **"Save Draft"** | Button | Save progress |
| **"Export PDF"** | Button | Generate and download PDF |
| **"AI Optimize"** | Button | AI suggests improvements to content |

---

### 7.11 Candidate CV Review

**File:** `pages/candidate/cv-review.html` | **URL:** `/candidate/cv-review`

| Element | Action | Details |
|---------|--------|---------|
| **AI Score** | Gauge | CV quality score (0-100) |
| **Improvement suggestions** | List | AI-generated tips: "Add more quantifiable achievements", "Improve summary" |
| **Section scores** | Bars | Individual scores for each CV section |
| **Keyword analysis** | Tags | Missing keywords for target roles |
| **"Apply Suggestions"** | Button | Auto-applies AI improvements |
| **"Edit CV"** | Button | → `/candidate/cv-builder` |

---

### 7.12 Candidate CV Selection

**File:** `pages/candidate/cv-selection.html` | **URL:** `/candidate/cv-selection`

| Element | Action | Details |
|---------|--------|---------|
| **CV version cards** | Click to select | Multiple CV versions with preview thumbnails |
| **"Set as Default"** | Button per card | Marks CV as primary for applications |
| **"Delete"** | Button per card | Removes version |
| **"Upload New"** | Button | New CV upload → `/candidate/cv-builder` |

---

### 7.13 Candidate Documents

**File:** `pages/candidate/documents.html` | **URL:** `/candidate/documents`

| Element | Action | Details |
|---------|--------|---------|
| **Document cards** | Display | Uploaded documents with file type badges (PDF, DOCX, etc.) |
| **"Upload"** | Button | File picker → upload document |
| **"Download"** | Button per card | Download file |
| **"Delete"** | Button per card | Remove document with confirmation |
| **Categories** | Tabs | All / CV / Cover Letter / Certificate / Other |

---

### 7.14 Candidate EEO Form

**File:** `pages/candidate/eeo-form.html` | **URL:** `/candidate/eeo-form`

| Element | Action | Details |
|---------|--------|---------|
| **Radio groups** | Select | Equal Employment Opportunity questions (gender, ethnicity, veteran status, disability) |
| **"Prefer not to say"** | Option per group | Opt-out choice |
| **"Submit EEO"** | Button | `POST /api/v1/candidate/eeo` |
| **Privacy note** | Text | "This information is anonymous and doesn't affect your application" |

---

### 7.15 Candidate E-Sign View

**File:** `pages/candidate/esign-view.html` | **URL:** `/candidate/esign-view`

| Element | Action | Details |
|---------|--------|---------|
| **Document viewer** | Embedded | PDF/HTML document to sign |
| **Signature pad** | Canvas | Draw signature with mouse/touch |
| **"Accept & Sign"** | Button | Submit signed document |
| **"Decline"** | Button | Reject with confirmation modal |

---

### 7.16 Candidate Settings

**File:** `pages/candidate/settings.html` | **URL:** `/candidate/settings` | **Sidebar:** `nav_settings`

| Element | Action | Details |
|---------|--------|---------|
| **Tab navigation** | Tabs | Profile / Account / Notifications / Privacy / Security |
| **Name/Email/Phone** | Editable inputs | Update personal info |
| **Password change** | Form | Current password + new + confirm |
| **Notification toggles** | Switches | Email push / SMS preferences per event type |
| **Language selector** | Dropdown | EN / FR / AR |
| **Theme toggle** | Switch | Light / Dark mode |
| **"Save Changes"** | Button | `PUT /api/v1/candidate/settings` |
| **"Delete Account"** | Button | Danger zone — confirmation modal → `DELETE /api/v1/account` |

---

### 7.17 Candidate Subscription

**File:** `pages/candidate/subscription.html` | **URL:** `/subscription` (or `/candidate/subscription`)

| Element | Action | Details |
|---------|--------|---------|
| **Plan cards** | Select | Current plan highlighted. Free / Pro / Premium tiers. |
| **Feature comparison** | Table | Per-plan feature list |
| **"Upgrade" / "Downgrade"** | Button | Plan change → `POST /api/v1/candidate/subscription` |
| **"Cancel Subscription"** | Button | Confirmation modal |
| **Usage meters** | Progress bars | CV uploads used, AI analyses used, interviews used |

---

### 7.18 Candidate Onboarding

**File:** `pages/candidate/onboarding.html` | **URL:** `/candidate/onboarding`

| Element | Action | Details |
|---------|--------|---------|
| **Step wizard** | Dots indicator | 4-5 step onboarding flow |
| **Step panels** | Glass cards | Each step: Personal Info → Skills → Experience → CV Upload → Preferences |
| **"Next" / "Previous"** | Buttons | Navigate steps with fadeSlideIn animation |
| **"Skip"** | Button | Skip current step |
| **"Complete Setup"** | Button | Final step → `POST /api/v1/candidate/onboarding` |
| **Progress bar** | Visual | Shows overall completion |

---

### 7.19 Candidate Messages

**File:** `pages/candidate/messages.html` | **URL:** `/candidate/messages`

```
┌──────────────────────────────────────────────────────────────┐
│  💬 Messages                                                 │
│                                                              │
│  ┌────────── Conversation List ────┐ ┌── Chat Area ────────┐ │
│  │ [Avatar] Acme Corp Recruiter    │ │                      │ │
│  │ "We'd like to schedule..."  2🔴 │ │ Hey John!           │ │
│  │                                  │ │                      │ │
│  │ [Avatar] Beta Inc HR            │ │ We reviewed your     │ │
│  │ "Your application is moving..."  │ │ application and...  │ │
│  │                                  │ │                      │ │
│  │ [Avatar] Candway AI Assistant   │ │ ┌──────────────┐    │ │
│  │ "New job matches for you"       │ │ │ Type a message│    │ │
│  │                                  │ │ └──────────────┘    │ │
│  └──────────────────────────────────┘ │ [Send ➤]            │ │
│                                       └──────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Conversation list** | Click → select | Shows avatar, name, last message preview, unread badge |
| **Message input** | Text field | Type message |
| **"Send" button** | ➤ | `POST /api/v1/messages` |
| **Message bubbles** | Display | Sent (right, indigo) / Received (left, gray) |
| **Attachment icon** | 📎 | File picker for image/document attachment |
| **"New Message"** | Button | Compose new → recipient selector modal |

---

### 7.20 Candidate Marketplace

**File:** `pages/candidate/marketplace.html` | **URL:** `/candidate/marketplace`

| Element | Action | Details |
|---------|--------|---------|
| **Category grid** | Icons | Course categories (Programming, Design, Business, etc.) |
| **Marketplace cards** | Click → detail | Course/service cards with price, rating |
| **Search** | Input | Search marketplace items |
| **Filters** | Sidebar | Price range, category, rating |

---

### 7.21 Candidate Learning

**File:** `pages/candidate/learning.html` | **URL:** `/candidate/learning` | **Sidebar:** `nav_learning`

| Element | Action | Details |
|---------|--------|---------|
| **Course cards** | Click → `/candidate/course-details` | Thumbnail, title, instructor, progress bar, rating |
| **Category tabs** | All / In Progress / Completed / Recommended |
| **Learning path** | Timeline | Suggested course sequence with milestones |
| **Progress rings** | Circular SVG | Per-course completion percentage |
| **"Continue Learning"** | Button per course | → `/candidate/course-player` (resumes) |
| **Certificate count** | Badge | Number of earned certificates |

---

### 7.22 Candidate Course Details

**File:** `pages/candidate/course-details.html` | **URL:** `/candidate/course-details?id=X`

| Element | Action | Details |
|---------|--------|---------|
| **Course hero** | Video/image banner | Title, instructor, rating, price |
| **"Enroll Now" / "Start Course"** | Button | → enrollment or → course player |
| **Syllabus accordion** | Expandable sections | Module list with lesson count + duration |
| **Instructor card** | Avatar + name + bio | Click → instructor profile |
| **Reviews** | Star ratings + text | User reviews with pagination |

---

### 7.23 Candidate Course Player

**File:** `pages/candidate/course-player.html` | **URL:** `/candidate/course-player?id=X&lesson=Y`

| Element | Action | Details |
|---------|--------|---------|
| **Video player** | Embedded | Course video with controls |
| **Lesson sidebar** | Scrollable list | All lessons with completion checkmarks |
| **"Mark Complete"** | Button | Marks lesson as complete, advances to next |
| **Notes panel** | Text area | Take notes synced to video timestamp |
| **Resources** | Download links | Attached files for current lesson |
| **Progress bar** | Top bar | Course-wide progress |

---

### 7.24 Candidate Certificate

**File:** `pages/candidate/certificate.html` | **URL:** `/candidate/certificate?id=X`

| Element | Action | Details |
|---------|--------|---------|
| **Certificate display** | Styled card | User name, course name, date, completion seal |
| **"Download PDF"** | Button | Print/save as PDF |
| **"Share on LinkedIn"** | Button | Opens LinkedIn share intent |
| **"View Course"** | Button | Back to course page |
| **Confetti animation** | Visual | CSS celebration effect |

---

### 7.25 Candidate Profile Visitors

**File:** `pages/candidate/profile-visitors.html` | **URL:** `/candidate/profile-visitors`

| Element | Action | Details |
|---------|--------|---------|
| **Visitor cards** | Display | Company name (from RecruiterProfile), logo, visit date |
| **Anonymous count** | Stat | Number of anonymous (non-logged-in) visitors |
| **Timeline** | Chronological | Visitor history sorted by date |
| **Total views stat** | Number | Lifetime profile view count |

---

## 8. Recruiter Pages (47 pages)

**Base URL:** `/recruiter/...`  
**Sidebar:** Recruiter sidebar (see section 2)  
**JS Bundle:** `core.js` + `shared.js` + `recruiter.js`  
**Design System:** Indigo (`#6366F1`) — Recruiter Glass (`recruiter-glass.css`) + Custom (`custom.css`)

---

### 8.1 Recruiter Dashboard

**File:** `pages/recruiter/dashboard.html`  
**URL:** `/recruiter/dashboard`  
**Sidebar active:** `nav_dashboard`

```
┌──────────────────────────────────────────────────────────────┐
│                    TOP HEADER                                 │
├──────────────────────────────────────────────────────────────┤
│  Ambient Background (animated indigo blobs + grid)           │
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Active  │ │ Total   │ │ New     │ │ Avg     │           │
│  │ Jobs    │ │ Cand.   │ │ Apps    │ │ Score   │           │
│  │  12     │ │  234    │ │  28     │ │  76%    │           │
│  │ +3 this │ │ +12     │ │ +8 this │ │ +2%     │           │
│  │  month  │ │  week   │ │  week   │ │  vs     │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  ┌────────────────────────┐ ┌─────────────────────────┐     │
│  │ 📈 Applications Over   │ │ 🏆 Top Candidates        │     │
│  │    Time                │ │                          │     │
│  │ [Chart.js line chart]  │ │ 1. John Doe   98% 🟢    │     │
│  │                        │ │ 2. Jane Smith 94% 🟢    │     │
│  │                        │ │ 3. Bob Wilson 89% 🟡    │     │
│  └────────────────────────┘ │ [View All →]             │     │
│                              └─────────────────────────┘     │
│  ┌────────────────────────┐ ┌─────────────────────────┐     │
│  │ 📋 Recent Activity     │ │ 🎯 AI Matches            │     │
│  │ • New application      │ │                          │     │
│  │ • Interview completed  │ │ 5 new high-match         │     │
│  │ • Offer sent           │ │ candidates found         │     │
│  │ • Candidate stage      │ │ [View Matches →]         │     │
│  │   changed              │ │                          │     │
│  │ [View All →]           │ │                          │     │
│  └────────────────────────┘ └─────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Stat cards** (4) | Display | Active Jobs, Total Candidates, New Applications, Avg Match Score |
| **Applications chart** | Chart.js | Line/bar chart with time range selector (7d/30d/90d) |
| **Top candidates** | Links | Ranked list → `/recruiter/candidate?id=X` |
| **Recent activity** | List | Latest events with timestamps. "View All" → activity log |
| **AI matches** | Card | AI-discovered high-match candidates. "View Matches" → `/recruiter/candidates` filtered |
| **"Post a Job"** | CTA | → `/recruiter/job-wizard` |
| **"View Pipeline"** | CTA | → `/recruiter/pipeline` |

---

### 8.2 Recruiter Analytics

**File:** `pages/recruiter/analytics.html` | **URL:** `/recruiter/analytics` | **Sidebar:** `nav_analytics`

| Element | Action | Details |
|---------|--------|---------|
| **Date range picker** | Dropdown | 7d / 30d / 90d / Custom |
| **KPI cards** | Display | Applications, Hires, Conversion Rate, Time-to-Hire, Cost-per-Hire |
| **Source breakdown** | Pie/doughnut chart | Where candidates come from (LinkedIn, Indeed, Direct, etc.) |
| **Conversion funnel** | Funnel chart | Stages: Applied → Screening → Interview → Offer → Hire |
| **Trend lines** | Line charts | Time-series metrics |
| **"Export Report"** | Button | Download analytics as CSV/PDF |
| **Demographic breakdown** | Charts | EEO stats, diversity metrics |

---

### 8.3 Recruiter Analytics Dashboard

**File:** `pages/recruiter/analytics-dashboard.html` | **URL:** `/recruiter/analytics-dashboard`

| Element | Action | Details |
|---------|--------|---------|
| **Combined metrics** | Display | Aggregated view of analytics + dashboard stats |
| **Source + funnel** | Charts | Same as Analytics but consolidated |
| **Unique candidates** | Stat | `total_unique_candidates` count (distinct by email) |

---

### 8.4 Recruiter Candidates (Management)

**File:** `pages/recruiter/candidates.html` | **URL:** `/recruiter/candidates` | **Sidebar:** `nav_candidates`

```
┌──────────────────────────────────────────────────────────────┐
│                    TOP HEADER                                 │
├──────────────────────────────────────────────────────────────┤
│  [🔍 Search candidates...]    [Filters ▼]  [Sort ▼]         │
│                                                              │
│  [📊 All ] [📋 Screening] [🎥 Interview] [📩 Offer] [✅ Hired]│
│                                                              │
│  ┌─── Table ─────────────────────────────────────────────┐  │
│  │ NAME          │ STAGE      │ SCORE │ APPLIED  │ ACTION │  │
│  │───────────────┼────────────┼───────┼──────────┼────────│  │
│  │ John Doe      │ 🟢 Review  │ 92%   │ 2d ago   │ [👁️]   │  │
│  │ Jane Smith    │ 🎥 Interv. │ 88%   │ 5d ago   │ [👁️]   │  │
│  │ Bob Wilson    │ 📩 Offer   │ 76%   │ 1w ago   │ [👁️]   │  │
│  │ Alice Brown   │ ✅ Hired   │ 94%   │ 2w ago   │ [👁️]   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [< 1 2 3 ... 12 >]   [Selected: 0] [Bulk Actions ▼]       │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Search bar** | Input | Full-text candidate search (name, email, skills) |
| **Stage filter pills** | Filter | All / Screening / Interview / Offer / Hired / Rejected |
| **Sort dropdown** | Select | Relevance / Score / Date / Name |
| **Candidates table** | Click row → detail | Sticky header, sortable columns |
| **"View" button** | 👁️ per row | → `/recruiter/candidate?id=X` |
| **Checkbox selection** | Per row | Select for bulk actions |
| **Bulk actions** | Dropdown | "Move to Stage", "Send Email", "Delete" |
| **Pagination** | Nav | Pages + items per page selector |
| **Action buttons** | Top bar | "Invite Candidates" → `/recruiter/bulk-invite`, "Export CSV" |

---

### 8.5 Recruiter Candidate Detail

**File:** `pages/recruiter/candidate.html` | **URL:** `/recruiter/candidate?id=X`

```
┌──────────────────────────────────────────────────────────────┐
│                    TOP HEADER                                 │
├──────────────────────────────────────────────────────────────┤
│  ← Back to Candidates                                        │
│                                                              │
│  [Avatar] John Doe                  Stage: In Review 🟢      │
│  Sr. Software Engineer              Score: 92% 🟢            │
│                                                              │
│  [Change Stage ▼]  [Send Email]  [Schedule Interview]  [Offer]│
│                                                              │
│  ┌─ Tabs ───────────────────────────────────────────────────┐│
│  │ [Profile] [CV] [Interview] [Notes] [Activity] [Docs]   ││
│  │                                                         ││
│  │ Profile Content:                                        ││
│  │ - Email: john@email.com                                 ││
│  │ - Phone: +216 XX XXX XXX                                ││
│  │ - Location: Tunis                                       ││
│  │ - Skills: Python, React, AWS, Docker                    ││
│  │ - LinkedIn: /in/johndoe                                 ││
│  │ - Experience: 5 years                                   ││
│  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **"Back to Candidates"** | Link | → `/recruiter/candidates` |
| **"Change Stage"** | Dropdown | Move candidate through pipeline stages |
| **"Send Email"** | Button | → email composer modal or → invites |
| **"Schedule Interview"** | Button | → scheduling modal with calendar |
| **"Make Offer"** | Button | → `/recruiter/offers` (create offer for this candidate) |
| **Tabs** | Navigation | Profile / CV / Interview / Notes / Activity / Docs |
| **Profile tab** | Display | Personal info, skills tags, experience timeline, education |
| **CV tab** | Embedded viewer | PDF/HTML CV preview, download button |
| **Interview tab** | Results | Interview scores, transcript, analysis link |
| **Notes tab** | Text area + list | Internal notes with add/delete |
| **Activity tab** | Timeline | All actions taken on this candidate |
| **Docs tab** | Files | Uploaded documents with download |
| **"Add Note"** | Button | Quick note input |
| **"Compare"** | Button | → `/recruiter/compare?ids=X,Y` |

---

### 8.6 Recruiter Candidate Ranking

**File:** `pages/recruiter/candidate-ranking.html` | **URL:** `/recruiter/candidate-ranking`

| Element | Action | Details |
|---------|--------|---------|
| **Ranked list** | Score-sorted | Candidates ordered by AI match score |
| **Score bars** | Visual bars | Horizontal bars with percentage |
| **Skill breakdown** | Per-candidate | Radar or bar charts for individual scores |
| **"Compare selected"** | Button | → `/recruiter/compare?ids=X,Y,Z` |
| **Filters** | Sidebar | Filter by skills, experience, location |

---

### 8.7 Recruiter Compare / Comparison

**File:** `pages/recruiter/compare.html` + `pages/recruiter/comparison.html` | **URL:** `/recruiter/compare?ids=X,Y`

| Element | Action | Details |
|---------|--------|---------|
| **Side-by-side cards** | Display | 2-4 candidates compared |
| **Score matrix** | Table | Scores across dimensions (Technical, Soft Skills, Culture) |
| **Radar chart overlay** | Chart.js | Multiple candidates on same radar |
| **"Add Candidate"** | Button | Search to add another |
| **"Remove"** | Button per card | Remove from comparison |
| **"Shortlist"** | Button | Add to talent pool |

---

### 8.8 Recruiter Jobs

**File:** `pages/recruiter/jobs.html` | **URL:** `/recruiter/jobs` | **Sidebar:** `nav_jobs`

| Element | Action | Details |
|---------|--------|---------|
| **"Create Job"** | Button | → `/recruiter/job-wizard` |
| **Job list** | Cards/table | Job title, department, status, applicant count, date |
| **Status badges** | Draft / Published / Closed / Archived |
| **"Edit"** | Button per job | → `/recruiter/job-wizard?edit=X` |
| **"View Applicants"** | Button per job | → `/recruiter/candidates?job_id=X` |
| **"Clone"** | Button per job | Duplicate job posting |
| **"Close"** | Button per job | Stop accepting applications |
| **"Delete"** | Button per job | Confirmation modal → `DELETE` |
| **Search/filter** | Input + dropdowns | Search by title, filter by status, department |

---

### 8.9 Recruiter Job Wizard (Create Job)

**File:** `pages/recruiter/job-wizard.html` | **URL:** `/recruiter/job-wizard` | **Sidebar:** `nav_job_wizard`

```
┌──────────────────────────────────────────────────────────────┐
│  ✨ Create Job (Skill-First)                                  │
│                                                              │
│  ● Step 1: Basic Info  ○ Step 2: Skills  ○ Step 3: Details  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Step 1: Basic Information                              │  │
│  │                                                        │  │
│  │ Job Title: [________________________]                  │  │
│  │ Category:  [Software Engineering ▼]                    │  │
│  │ Location:  [________________________]                  │  │
│  │ Type:      [Full-Time ▼]                               │  │
│  │ Recruiter: [John Doe (you) ▼]                          │  │
│  │                                                        │  │
│  │ Salary Range: [$_____] - [$_____]  [🤖 AI Suggest]     │  │
│  │                                                        │  │
│  │ ┌─ Tips ─────────────────────────────────────────┐    │  │
│  │ │ 💡 Use specific job titles for better matches   │    │  │
│  │ │ 💡 Include salary range to attract more apps    │    │  │
│  │ └────────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │ [Back]                    [Next: Skills →]             │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Step indicators** | Dots | Step 1: Basic Info / Step 2: Skills / Step 3: Description |
| **"AI Suggest"** | Button 🤖 | Calls AI to suggest salary range based on job title |
| **Tips sidebar** | Glass panel | Contextual tips for current step |
| **"Next"** | Button | Advances to next step with animation (fadeSlideIn) |
| **"Previous"** | Button | Goes back to previous step |
| **"Save Draft"** | Button | Saves incomplete job |
| **Categories** | Dropdown | Fetched from /recruiter/jobs/wizard/categories |
| **Recruiters** | Multi-select | Select team members for this job |
| **Skill tags** | Add/remove | Step 2: Search + add required skills |
| **Rich text editor** | Text area | Step 3: Job description with formatting |

---

### 8.10 Recruiter JD Editor

**File:** `pages/recruiter/jd-editor.html` | **URL:** `/recruiter/jd-editor`

| Element | Action | Details |
|---------|--------|---------|
| **Rich text editor** | ContentEditable | Full job description editor |
| **"AI Rewrite"** | Button | AI suggests improved phrasing |
| **"Analyze"** | Button | AI bias detection on job description |
| **Word lists** | Side panel | Suggested keywords, forbidden words |
| **Character count** | Display | Live count |
| **"Save"** | Button | Save JD |
| **"Preview"** | Button | See how it looks to candidates |

---

### 8.11 Recruiter Pipeline (Kanban)

**File:** `pages/recruiter/pipeline.html` | **URL:** `/recruiter/pipeline` | **Sidebar:** `nav_pipeline`

```
┌──────────────────────────────────────────────────────────────┐
│  🔄 Talent Pipeline                  [Kanban] [List] [Table] │
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ APPLIED │ │SCREENING│ │INTERVIEW│ │  OFFER  │           │
│  │   12    │ │    8    │ │    5    │ │    2    │           │
│  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤           │
│  │ Card 1  │ │ Card 1  │ │ Card 1  │ │ Card 1  │           │
│  │ Card 2  │ │ Card 2  │ │ Card 2  │ │ Card 2  │           │
│  │ Card 3  │ │ Card 3  │ │         │ │         │           │
│  │ ...     │ │ ...     │ │         │ │         │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **View toggles** | Segmented buttons | Kanban / List / Table views |
| **Kanban columns** | 4+ columns | Applied → Screening → Interview → Offer → Hired |
| **Candidate cards** | Draggable | Avatar, name, score, skills. Drag to change stage. |
| **Column count** | Badge | Number of candidates in each column |
| **"Add" button per column** | Quick-add | Add candidate to column manually |
| **Search** | Input | Filter cards within pipeline |

---

### 8.12 Recruiter Offers

**File:** `pages/recruiter/offers.html` | **URL:** `/recruiter/offers`

| Element | Action | Details |
|---------|--------|---------|
| **Offer cards** | List | Candidate name, position, amount, status |
| **Status pills** | Draft / Sent / Accepted / Rejected / Withdrawn |
| **"Create Offer"** | Button | → offer composer modal |
| **"Send"** | Button per draft | Send offer to candidate via email + e-sign |
| **"Withdraw"** | Button per sent | Withdraw with confirmation |
| **"View"** | Button per card | Offer detail view |

---

### 8.13 Recruiter E-Sign Offer

**File:** `pages/recruiter/esign-offer.html` | **URL:** `/recruiter/esign-offer`

| Element | Action | Details |
|---------|--------|---------|
| **Offer builder** | Form | Compensation, benefits, start date, contingencies |
| **Template selector** | Dropdown | Use saved offer template |
| **Signature fields** | Drag-and-drop | Place signature/date/initial fields on document |
| **"Send for Signature"** | Button | Dispatch to candidate via DocuSign/email |
| **Preview** | Panel | Live offer document preview |

---

### 8.14 Recruiter Interviews

**File:** `pages/recruiter/interviews.html` | **URL:** `/recruiter/interviews` | **Sidebar:** `nav_interviews`

| Element | Action | Details |
|---------|--------|---------|
| **Calendar view** | Month/week/day | Interview schedule |
| **Interview cards** | List | Candidate, job, date/time, interviewer, status |
| **"Schedule Interview"** | Button | → scheduling modal |
| **Feedback status** | Badge | Pending / Submitted for each interviewer |
| **"Join"** | Button | → video call link |
| **"View Analysis"** | Button | → `/recruiter/interview-analysis-recruiter` |

---

### 8.15 Recruiter Interview Analysis

**File:** `pages/recruiter/interview-analysis-recruiter.html` | **URL:** `/recruiter/interview-analysis-recruiter`

| Element | Action | Details |
|---------|--------|---------|
| **AI scores** | Charts | Same as candidate analysis but recruiter-facing |
| **Transcript viewer** | Full transcript | With highlights on key moments |
| **AI notes** | Summary panel | AI-generated interview summary |
| **Recording** | Video/audio | Playback if recorded |
| **"Add Feedback"** | Form | Recruiter's own evaluation |
| **"Share with Team"** | Button | Share analysis with other recruiters |

---

### 8.16 Recruiter EEO Dashboard

**File:** `pages/recruiter/eeo-dashboard.html` | **URL:** `/recruiter/eeo-dashboard`

| Element | Action | Details |
|---------|--------|---------|
| **Diversity metrics** | Charts | Demographics breakdown (gender, ethnicity, etc.) |
| **Compliance status** | Indicators | EEO reporting status per job |
| **Coverage percentage** | Gauge | % of candidates who submitted EEO data |
| **"View EEO Coverage"** | Link | → `/recruiter/eeo-coverage` |
| **"Generate Report"** | Button | Export EEO compliance report |

---

### 8.17 Recruiter EEO Coverage

**File:** `pages/recruiter/eeo-coverage.html` | **URL:** `/recruiter/eeo-coverage`

| Element | Action | Details |
|---------|--------|---------|
| **Coverage table** | Per job | EEO submission rate per job posting |
| **Progress bars** | Visual | % coverage per demographic category |
| **Department breakdown** | Grouped | EEO stats by department |
| **"Download Report"** | Button | CSV export |

---

### 8.18 Recruiter Background Checks

**File:** `pages/recruiter/background-checks.html` | **URL:** `/recruiter/background-checks`

| Element | Action | Details |
|---------|--------|---------|
| **Background check cards** | List | Candidate name, status, vendor, date requested |
| **Status pills** | Pending / In Progress / Completed / Failed |
| **"Initiate Check"** | Button | → select candidate + vendor |
| **"View Detail"** | Button | → `/recruiter/background-check-detail` |
| **Vendor info** | Badge | Checkr / GoodHire / Other |

---

### 8.19 Recruiter Background Check Detail

**File:** `pages/recruiter/background-check-detail.html` | **URL:** `/recruiter/background-check-detail`

| Element | Action | Details |
|---------|--------|---------|
| **Report sections** | Accordion | Criminal, Employment, Education, Reference, etc. |
| **Status per section** | Clear / Flagged / Pending |
| **"Download Report"** | Button | PDF download |
| **"Dispute"** | Button | Flag incorrect result |
| **"Share"** | Button | Share with hiring team |

---

### 8.20 Recruiter Campaigns

**File:** `pages/recruiter/campaigns.html` | **URL:** `/recruiter/campaigns` | **Sidebar:** `nav_campaigns`

| Element | Action | Details |
|---------|--------|---------|
| **Campaign cards** | Grid | Campaign name, status, sent count, open rate, reply rate |
| **Status badges** | Draft / Active / Paused / Completed |
| **"Create Campaign"** | Button | → `/recruiter/campaign-create` |
| **"View"** | Button per card | → `/recruiter/campaigns-view` |
| **"Duplicate"** | Button per card | Clone campaign |
| **"Pause/Resume"** | Toggle per card | Control active state |

---

### 8.21 Recruiter Campaign View

**File:** `pages/recruiter/campaigns-view.html` | **URL:** `/recruiter/campaigns-view`

| Element | Action | Details |
|---------|--------|---------|
| **Campaign detail** | Header | Name, dates, status, audience size |
| **Performance metrics** | Stats | Sent, Opened, Clicked, Replied, Unsubscribed |
| **Charts** | Line/bar | Engagement over time |
| **Audience breakdown** | Pie chart | Demographic/role breakdown |
| **"Edit Campaign"** | Button | → edit mode |

---

### 8.22 Recruiter Campaign Create

**File:** `pages/recruiter/campaign-create.html` | **URL:** `/recruiter/campaign-create`

| Element | Action | Details |
|---------|--------|---------|
| **Campaign name** | Input | Name your campaign |
| **Audience selector** | Filter builder | Skills, location, experience, saved search |
| **Email template** | Dropdown + editor | Choose template, customize |
| **Schedule** | Date/Time picker | Send now or schedule |
| **"Save as Draft"** | Button | |
| **"Launch Campaign"** | Button | Send or schedule |

---

### 8.23 Recruiter Email Templates

**File:** `pages/recruiter/email-templates.html` | **URL:** `/recruiter/email-templates`

| Element | Action | Details |
|---------|--------|---------|
| **Template list** | Cards | Template name, category, last used |
| **"Create Template"** | Button | New blank template |
| **"Edit"** | Button per card | Open template editor |
| **"Duplicate"** | Button per card | Clone template |
| **"Delete"** | Button per card | Remove with confirmation |
| **Template editor** | Rich text | Subject, body, variable insertion ({{name}}, {{job}}) |

---

### 8.24 Recruiter Chatbot Leads

**File:** `pages/recruiter/chatbot-leads.html` | **URL:** `/recruiter/chatbot-leads`

| Element | Action | Details |
|---------|--------|---------|
| **Lead list** | Table/Cards | Name, email, source, score, status, date |
| **Chat transcript** | Viewer | Full conversation with lead |
| **Lead score** | Badge | AI-calculated interest score |
| **"Convert to Candidate"** | Button | Add lead as candidate in system |
| **"Send Email"** | Button | → email composer |
| **Status selector** | Dropdown | New / Contacted / Qualified / Converted / Closed |

---

### 8.25 Recruiter Copilot (Full)

**File:** `pages/recruiter/copilot-full.html` | **URL:** `/recruiter/copilot-full`

| Element | Action | Details |
|---------|--------|---------|
| **AI chat interface** | Full page | Conversational AI assistant for recruiting |
| **Context sidebar** | Panel | Current candidate/job context |
| **Action suggestions** | Chips | "Compare candidates", "Find similar", "Draft email" |
| **Chat history** | Scrollable | Previous conversations |
| **"New Chat"** | Button | Clear and start fresh |
| **Query input** | Text area | Type question or command |

---

### 8.26 Recruiter Reports

**File:** `pages/recruiter/reports.html` | **URL:** `/recruiter/reports` | **Sidebar:** `nav_reports`

| Element | Action | Details |
|---------|--------|---------|
| **Report cards** | Grid with preview | Report name, type, last run, schedule indicator |
| **"Create Report"** | Button | → `/recruiter/report-builder` |
| **"Run Now"** | Button per card | Generate fresh report |
| **"Schedule"** | Button per card | Set recurring schedule |
| **"Download"** | Button per card | CSV/PDF export |
| **Report types** | Tags | Pipeline / Source / Diversity / Time-to-Hire / Custom |

---

### 8.27 Recruiter Reports List

**File:** `pages/recruiter/reports-list.html` | **URL:** `/recruiter/reports-list`

| Element | Action | Details |
|---------|--------|---------|
| **Sorted/filtered list** | Table | All reports with date range, type filters |
| **"View"** | Button per row | Open report detail |
| **"Delete"** | Button per row | Remove report |

---

### 8.28 Recruiter Report Builder

**File:** `pages/recruiter/report-builder.html` | **URL:** `/recruiter/report-builder`

| Element | Action | Details |
|---------|--------|---------|
| **Metric selector** | Drag items | Drag metrics from list to canvas |
| **Chart picker** | Choose type | Bar / Line / Pie / Table / Funnel |
| **Preview canvas** | Live preview | Real-time report preview |
| **Filters** | Side panel | Date range, job, department |
| **"Save Report"** | Button | Name + save |
| **"Export"** | Button | PDF/CSV/Schedule |

---

### 8.29 Recruiter Scoring Preview

**File:** `pages/recruiter/scoring-preview.html` | **URL:** `/recruiter/scoring-preview`

| Element | Action | Details |
|---------|--------|---------|
| **Score breakdown** | Cards | Score per dimension (Skills, Experience, Culture, etc.) |
| **Criterion bars** | Horizontal bars | Score per individual criterion |
| **AI explanation** | Text panel | Why this score was assigned |
| **Bias indicators** | Flags | Any detected bias in scoring |
| **Weight sliders** | Adjustable | Adjust criterion weights (tier-dependent) |

---

### 8.30 Recruiter Bias Analytics

**File:** `pages/recruiter/bias-analytics.html` | **URL:** `/recruiter/bias-analytics`

| Element | Action | Details |
|---------|--------|---------|
| **Bias detection dashboard** | Overview | Overall fairness score |
| **Demographic comparison** | Charts | Score distribution by gender, age, ethnicity |
| **Fairness metrics** | KPIs | Disparate impact, 4/5ths rule, statistical significance |
| **"Run Audit"** | Button | Trigger full bias audit |
| **Recommendations** | List | AI-suggested improvements |

---

### 8.31 Recruiter Ghost Report

**File:** `pages/recruiter/ghost-report.html` | **URL:** `/recruiter/ghost-report`

| Element | Action | Details |
|---------|--------|---------|
| **Ghost candidates** | List | Candidates who started but didn't complete application |
| **Abandonment rate** | Stat | % of incomplete applications |
| **Stage breakdown** | Chart | At which stage do candidates abandon |
| **"Send Reminder"** | Button per candidate | Re-engagement email |

---

### 8.32 Recruiter Settings

**File:** `pages/recruiter/settings.html` | **URL:** `/recruiter/settings` | **Sidebar:** `nav_settings`

| Element | Action | Details |
|---------|--------|---------|
| **Tab navigation** | Tabs | Profile / Company / Notifications / Security / Integrations |
| **Profile tab** | Form | Name, email, phone, avatar upload |
| **Company tab** | Form | Company name, description, logo, website, social links |
| **SMTP settings** | Form | Email server config (custom SMTP) |
| **Notifications tab** | Toggles | Email/SMS preferences |
| **Security tab** | Password change | Current + new password |
| **Integrations tab** | API keys | Webhooks, API tokens |
| **"Save Changes"** | Button | `PUT /api/v1/recruiter/settings` |

---

### 8.33 Recruiter Billing/Subscription

**File:** `pages/recruiter/billing.html` | **URL:** `/recruiter/subscription` or `/recruiter/billing`

| Element | Action | Details |
|---------|--------|---------|
| **Current plan card** | Highlighted | Plan name, price, renewal date |
| **Usage meters** | Progress bars | Jobs used, AI interviews used, CV storage |
| **Invoices table** | List | Past invoices with download |
| **Payment method** | Card info | Stored card with update option |
| **"Change Plan"** | Button | Plan selector modal |
| **"Cancel Subscription"** | Button | Confirmation flow |

---

### 8.34 Recruiter Calendar Settings

**File:** `pages/recruiter/calendar-settings.html` | **URL:** `/recruiter/calendar-settings`

| Element | Action | Details |
|---------|--------|---------|
| **Calendar sync** | Buttons | "Connect Google Calendar", "Connect Outlook" |
| **Availability slots** | Time picker | Define available interview times |
| **Timezone selector** | Dropdown | Your timezone |
| **"Save"** | Button | `PUT /api/v1/recruiter/calendar-settings` |

---

### 8.35 Recruiter Team

**File:** `pages/recruiter/team.html` | **URL:** `/recruiter/team` | **Sidebar:** `nav_team`

| Element | Action | Details |
|---------|--------|---------|
| **Team member cards** | Grid | Avatar, name, email, role badge, status |
| **Role badges** | Admin / Recruiter / Viewer |
| **"Invite Member"** | Button | → invite form modal (email + role) |
| **"Remove"** | Button per card | Confirmation modal |
| **"Edit Permissions"** | Button per card | Role change dropdown |

---

### 8.36 Recruiter Messages

**File:** `pages/recruiter/messages.html` | **URL:** `/recruiter/messages`

| Element | Action | Details |
|---------|--------|---------|
| **Conversation list** | Left panel | Contact name, last message, unread badge |
| **Chat area** | Right panel | Message bubbles, timestamp dividers |
| **Message input** | Text field + Send button |
| **"New Message"** | Button | → recipient selector modal |
| **Attachment** | 📎 | File upload |
| **Templates** | Button | Insert saved email template |

---

### 8.37 Recruiter Talent Pool

**File:** `pages/recruiter/talent-pool.html` | **URL:** `/recruiter/talent-pool`

| Element | Action | Details |
|---------|--------|---------|
| **Pool cards** | Grid | Talent pool name, description, candidate count |
| **"Create Pool"** | Button | New pool with name + description |
| **Pool detail** | Click → view | List of candidates in pool |
| **"Add Candidate"** | Button | Search + add candidate |
| **"Remove from Pool"** | Button per candidate |
| **"Export Pool"** | Button | CSV export |

---

### 8.38 Recruiter Auto Job

**File:** `pages/recruiter/auto-job.html` | **URL:** `/recruiter/auto-job`

| Element | Action | Details |
|---------|--------|---------|
| **AI job generation config** | Form | Source description, industry, level |
| **"Generate Jobs"** | Button | AI creates job descriptions |
| **Generated preview** | Cards | AI-suggested jobs with edit/accept |
| **Schedule** | Recurrence | Auto-generate on schedule |

---

### 8.39 Recruiter Reengagement

**File:** `pages/recruiter/reengagement.html` | **URL:** `/recruiter/reengagement`

| Element | Action | Details |
|---------|--------|---------|
| **Audience filters** | Selectors | Skills, last contact date, previous stage |
| **Email template** | Dropdown + preview | Choose reengagement message |
| **"Preview Audience"** | Button | Show matching candidates count |
| **"Send Campaign"** | Button | Launch reengagement |

---

### 8.40 Recruiter Bulk Invite

**File:** `pages/recruiter/bulk-invite.html` | **URL:** `/recruiter/bulk-invite`

| Element | Action | Details |
|---------|--------|---------|
| **CSV upload** | Drag-and-drop | Upload CSV with candidate emails |
| **Manual input** | Text area | Paste email list (one per line) |
| **Review list** | Table | Preview parsed emails before sending |
| **"Send Invites"** | Button | Dispatch invitations |
| **Progress bar** | During send | Shows send progress |

---

### 8.41 Recruiter Skill Tree

**File:** `pages/recruiter/skill-tree.html` | **URL:** `/recruiter/skill-tree`

| Element | Action | Details |
|---------|--------|---------|
| **Interactive skill tree** | Canvas/SVG | Visual tree of skills and their relationships |
| **Node click** | → detail | Shows skill name, description, related skills |
| **Zoom controls** | +/- | Zoom in/out of tree |
| **"Edit"** | Button | → `/recruiter/skill-tree-create` |

---

### 8.42 Recruiter Skill Tree Create

**File:** `pages/recruiter/skill-tree-create.html` | **URL:** `/recruiter/skill-tree-create`

| Element | Action | Details |
|---------|--------|---------|
| **Node editor** | Forms | Add/edit skill nodes (name, description, parent) |
| **Drag connections** | Interactive | Connect skills with drag lines |
| **"Add Root Skill"** | Button | Create top-level skill |
| **"Add Child Skill"** | Button per node | Create sub-skill |
| **"Save Tree"** | Button | `POST /api/v1/recruiter/skill-trees` |
| **"Preview"** | Button | See full tree view |

---

### 8.43 Recruiter Skill Tree Library

**File:** `pages/recruiter/skill-tree-library.html` | **URL:** `/recruiter/skill-tree-library` | **Sidebar:** `nav_skill_tree_library`

| Element | Action | Details |
|---------|--------|---------|
| **Library cards** | Grid | Pre-built skill trees with name, skill count, industry |
| **"Import"** | Button per card | Import to your account |
| **"Preview"** | Button per card | See tree structure before importing |
| **Search** | Input | Search library by name or industry |

---

### 8.44 Recruiter Skill Tree List

**File:** `pages/recruiter/skill-tree-list.html` | **URL:** `/recruiter/skill-tree-list`

| Element | Action | Details |
|---------|--------|---------|
| **My skill trees** | List/table | Name, skill count, last modified, status |
| **"Edit"** | Button per tree | → `/recruiter/skill-tree-create` |
| **"View"** | Button per tree | → `/recruiter/skill-tree` |
| **"Delete"** | Button per tree | Confirmation modal |

---

### 8.45 Recruiter Landing (Marketing)

**File:** `pages/recruiter/landing.html` | **URL:** `/recruiter/landing`

| Element | Action | Details |
|---------|--------|---------|
| **Marketing page** | Hero + features | Recruiter-specific value proposition |
| **"Get Started"** | CTA | → signup |
| **Feature sections** | Scrollable | Product highlights |

---

### 8.46 Recruiter Bot Settings

**File:** `pages/recruiter/bot-settings.html` | **URL:** `/recruiter/bot-settings`

| Element | Action | Details |
|---------|--------|---------|
| **Chatbot config** | Form | Enable/disable, name, greeting message |
| **Personality** | Selector | Professional / Friendly / Formal |
| **Response templates** | Editor | Default responses for common queries |
| **"Save Settings"** | Button | `PUT /api/v1/recruiter/bot-settings` |

---

## 9. Admin Pages (23 pages)

**Base URL:** `/admin/...`  
**Sidebar:** Admin sidebar (see section 4) with RBAC  
**JS Bundle:** `core.js` + `admin.js`  
**Design System:** Custom (`custom.css`) + Admin Tables (`admin-tables.css`)

---

### 9.1 Admin Dashboard

**File:** `pages/admin/dashboard.html` | **URL:** `/admin/dashboard` | **Sidebar:** `nav_dashboard`

```
┌──────────────────────────────────────────────────────────────┐
│  System Overview                [Global Status: 🟢 Operational]
│  Monitoring platform health     [💾 Backup] [🔄 Refresh]     │
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ 👥 Users│ │ 💰 Rev  │ │ 💼 Jobs │ │ 🎥 Int. │           │
│  │  1,234  │ │ $12.5K  │ │   56    │ │  189    │           │
│  │ +0%     │ │ +8%     │ │ +3 this │ │ +12 this│           │
│  │         │ │         │ │ month   │ │  month  │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  ┌────────────────────────┐ ┌─────────────────────────┐     │
│  │ 📈 Signups (30d)       │ │ 💰 Revenue (30d)        │     │
│  │ [Chart.js line chart]  │ │ [Chart.js bar chart]    │     │
│  │                        │ │                          │     │
│  └────────────────────────┘ └─────────────────────────┘     │
│                                                              │
│  ┌────────────────────────┐ ┌─────────────────────────┐     │
│  │ Recent Activity         │ │ Quick Actions            │     │
│  │ • User joined           │ │ [Send Announcement]     │     │
│  │ • Subscription upgraded │ │ [View Support Tickets]  │     │
│  │ • New job posted        │ │ [Backup Database]       │     │
│  │ • Payment received      │ │ [System Health]         │     │
│  └────────────────────────┘ └─────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Stat cards** (4) | Display | Users, Revenue, Jobs, Interviews — with trend indicators |
| **Signups chart** | Chart.js | Line chart with 30-day signup trend |
| **Revenue chart** | Chart.js | Bar chart with 30-day revenue |
| **Activity list** | Scrollable | Latest platform activity events |
| **"Backup"** | Button 💾 | `downloadBackup()` — triggers database backup download |
| **"Refresh"** | Button 🔄 | `loadDashboard()` — reloads all dashboard data |
| **"Deep Analytics"** | Button | → `/admin/analytics` |
| **Quick action buttons** | Various | Send announcement, support tickets, backup, system health |

---

### 9.2 Admin Analytics

**File:** `pages/admin/analytics.html` | **URL:** `/admin/analytics` | **Sidebar:** `nav_analytics` (RBAC: `view_analytics`)

| Element | Action | Details |
|---------|--------|---------|
| **Comprehensive stats** | Multiple charts | Signups, revenue, jobs posted, interviews, subscription conversions |
| **User growth** | Line chart | Cumulative and daily new users |
| **Revenue metrics** | Bar + line | MRR, ARR, one-time payments |
| **Geographic distribution** | Map/chart | User locations |
| **"Export"** | Button | CSV/PDF export |
| **Date range** | Selector | Custom date ranges |

---

### 9.3 Admin Users

**File:** `pages/admin/users.html` | **URL:** `/admin/users` | **Sidebar:** `nav_users` (RBAC: `view_users`)

| Element | Action | Details |
|---------|--------|---------|
| **Users table** | `cw-table` | Name, email, role, status, signup date, last login |
| **Search** | Input | Search by name, email, ID |
| **Role filter** | Dropdown | All / Candidate / Recruiter / Admin / Mentor |
| **Status filter** | Dropdown | Active / Suspended / Banned |
| **"Edit"** | Button per row | → user edit modal (change role, status, add credits) |
| **"Suspend"** | Button per row | Confirmation → suspend user |
| **"Delete"** | Button per row | Confirmation → delete user |
| **Bulk actions** | Checkbox + dropdown | Suspend / Activate / Delete selected |
| **Pagination** | Controls | Page navigation + per-page selector |

---

### 9.4 Admin Subscriptions

**File:** `pages/admin/subscriptions.html` | **URL:** `/admin/subscriptions` | **Sidebar:** `nav_subscriptions` (RBAC: `manage_finance`)

| Element | Action | Details |
|---------|--------|---------|
| **Subscriptions table** | `cw-table` | User/company, plan, status, start/end date, amount |
| **Plan badges** | Free / Pro / Enterprise / Premium |
| **Status badges** | Active / Past Due / Cancelled / Expired |
| **"Edit"** | Button per row | Change plan, adjust credits |
| **"Cancel"** | Button per row | Force cancel subscription |
| **"Refund"** | Button per row | Issue refund |
| **Filters** | Plan / Status / Date range |

---

### 9.5 Admin Payments

**File:** `pages/admin/payments.html` | **URL:** `/admin/payments` | **Sidebar:** `nav_payments` (RBAC: `manage_finance`)

| Element | Action | Details |
|---------|--------|---------|
| **Transactions table** | `cw-table` | ID, user, amount, method, status, date |
| **Status badges** | Completed / Pending / Failed / Refunded |
| **"View Receipt"** | Button per row | Receipt detail modal |
| **"Refund"** | Button per row | Issue refund with reason |
| **Search** | Input | Search by transaction ID or user |

---

### 9.6 Admin Invoices

**File:** `pages/admin/invoices.html` | **URL:** `/admin/invoices` | **Sidebar:** `nav_invoices` (RBAC: `manage_finance`)

| Element | Action | Details |
|---------|--------|---------|
| **Invoices table** | `cw-table` | Invoice #, user, amount, status, date, due date |
| **Status badges** | Paid / Unpaid / Overdue / Cancelled |
| **"Download PDF"** | Button per row | Download invoice PDF |
| **"Mark as Paid"** | Button per unpaid | Manual mark |
| **"Send Reminder"** | Button per unpaid | Email payment reminder |
| **"Generate Invoice"** | Button | Create manual invoice |

---

### 9.7 Admin Categories

**File:** `pages/admin/categories.html` | **URL:** `/admin/categories` | **Sidebar:** `nav_categories` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Category tree/table** | Hierarchical | Job categories with parent/child |
| **"Add Category"** | Button | New category form |
| **"Edit"** | Button per row | Rename, reorder |
| **"Delete"** | Button per row | Confirmation, reassign jobs |
| **Drag to reorder** | Interactive | Change display order |

---

### 9.8 Admin Content (Blog)

**File:** `pages/admin/content.html` | **URL:** `/admin/content` | **Sidebar:** `nav_content` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Blog posts table** | `cw-table` | Title, author, status, publish date, views |
| **Status badges** | Draft / Published / Archived |
| **"New Post"** | Button | → rich text editor |
| **"Edit"** | Button per row | Open post editor |
| **"Publish/Unpublish"** | Toggle per row | Change status |
| **"Delete"** | Button per row | Confirmation |

---

### 9.9 Admin Courses

**File:** `pages/admin/courses.html` | **URL:** `/admin/courses` | **Sidebar:** `nav_courses` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Courses table** | `cw-table` | Title, instructor, category, enrollment, status |
| **"Approve/Reject"** | Buttons per pending | Course approval workflow |
| **"Featured"** | Toggle per row | Mark as featured on course page |
| **"Edit"** | Button per row | Course details editor |

---

### 9.10 Admin Jobs (Job Board)

**File:** `pages/admin/jobs.html` | **URL:** `/admin/jobs` | **Sidebar:** `nav_jobs` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Jobs table** | `cw-table` | Title, company, category, status, applications, date |
| **Status badges** | Active / Filled / Draft / Expired |
| **"Edit"** | Button per row | Job detail editor |
| **"Feature"** | Toggle per row | Promote on job board |
| **"Remove"** | Button per row | Take down job |

---

### 9.11 Admin Settings

**File:** `pages/admin/settings.html` | **URL:** `/admin/settings` | **Sidebar:** `nav_settings` (RBAC: `manage_admins`)

| Element | Action | Details |
|---------|--------|---------|
| **Platform settings** | Form | Site name, description, logo, favicon |
| **Feature toggles** | Switches | Enable/disable features globally |
| **Defaults** | Form | Default subscription tier, credit limits |
| **"Save"** | Button | `PUT /api/v1/admin/settings` |

---

### 9.12 Admin Technical (System Health)

**File:** `pages/admin/technical.html` | **URL:** `/admin/technical` | **Sidebar:** `nav_technical` (RBAC: `view_logs`)

| Element | Action | Details |
|---------|--------|---------|
| **System status indicators** | Green/Red | API, Database, Redis, AI providers, Webhooks |
| **Cache management** | Buttons | "Clear Cache", "Clear PII Mapping Cache" |
| **Log viewer** | Filterable | Application logs with level filter |
| **"Run Health Check"** | Button | Trigger full system diagnostic |
| **"View Prometheus Metrics"** | Link | → `/api/v1/monitoring/metrics/prometheus` |

---

### 9.13 Admin Support

**File:** `pages/admin/support.html` | **URL:** `/admin/support` | **Sidebar:** `nav_support` (RBAC: `view_users`)

| Element | Action | Details |
|---------|--------|---------|
| **Tickets table** | `cw-table` | ID, user, subject, status, priority, date |
| **Status badges** | Open / In Progress / Resolved / Closed |
| **Priority badges** | Low / Medium / High / Critical |
| **"View"** | Button per row | Ticket detail with conversation |
| **"Assign"** | Dropdown per row | Assign to admin |
| **"Close"** | Button per row | Resolve ticket |

---

### 9.14 Admin Verifications (KYB)

**File:** `pages/admin/verifications.html` | **URL:** `/admin/verifications` | **Sidebar:** `nav_verifications` (RBAC: `manage_admins`)

| Element | Action | Details |
|---------|--------|---------|
| **Verification table** | `cw-table` | Company, documents submitted, status, date |
| **Status badges** | Pending / Verified / Rejected |
| **"View Documents"** | Button per row | Document viewer modal |
| **"Approve"** | Button per row | Mark as verified |
| **"Reject"** | Button per row | Reject with reason |

---

### 9.15 Admin Announcements

**File:** `pages/admin/announcements.html` | **URL:** `/admin/announcements` | **Sidebar:** `nav_announcements` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **"New Announcement"** | Button | → compose form |
| **Announcement list** | Table | Title, audience, status, scheduled date, sent count |
| **Target audience** | Multi-select | All / Candidates / Recruiters / Mentors |
| **"Send Now"** | Button | Immediate broadcast |
| **"Schedule"** | Button | Set future send date |

---

### 9.16 Admin Marketing

**File:** `pages/admin/marketing.html` | **URL:** `/admin/marketing` | **Sidebar:** `nav_marketing` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Campaign list** | Table | Campaign name, channels, budget, ROI |
| **"Create Campaign"** | Button | New marketing campaign |
| **Performance metrics** | Charts | Impressions, clicks, conversions |
| **A/B test results** | Stats | Variant comparison |

---

### 9.17 Admin Opportunities

**File:** `pages/admin/opportunities.html` | **URL:** `/admin/opportunities` | **Sidebar:** `nav_opportunities` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Opportunity cards/table** | List | Title, type, status, applicant count |
| **"Create"** | Button | New opportunity |
| **"Edit"** | Button per item | |
| **"Close"** | Button per item | Mark as filled |

---

### 9.18 Admin Recruiter Usage

**File:** `pages/admin/recruiter-usage.html` | **URL:** `/admin/recruiter-usage` | **Sidebar:** `nav_recruiter-usage` (RBAC: `manage_finance`)

| Element | Action | Details |
|---------|--------|---------|
| **Usage table** | `cw-table` | Recruiter/company, jobs used, AI interviews used, CV storage, limit |
| **Progress bars** | Visual | Usage vs limit per metric |
| **"Reset Usage"** | Button per row | Reset counters |
| **"Add Bonus"** | Button per row | Add extra credits |

---

### 9.19 Admin Rubric Builder

**File:** `pages/admin/rubric-builder.html` | **URL:** `/admin/rubric-builder` | **Sidebar:** `nav_rubric-builder`

```
┌──────────────────────────────────────────────────────────────┐
│  🗂️ Rubric Builder                                            │
│                                                              │
│  Rubric Name: [________________________]                     │
│                                                              │
│  ┌── Criteria ─────────────────────────────────────────────┐ │
│  │ [+] Add Criterion                                       │ │
│  │                                                         │ │
│  │ ┌─ Technical Skills ──────────────────────────────────┐ │ │
│  │ │ Weight: [40%]                                        │ │ │
│  │ │ Levels:                                              │ │ │
│  │ │   1 - Beginner    [✏️] [❌]                           │ │ │
│  │ │   2 - Intermediate [✏️] [❌]                          │ │ │
│  │ │   3 - Advanced    [✏️] [❌]                           │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  │                                                         │ │
│  │ ┌─ Communication ─────────────────────────────────────┐ │ │
│  │ │ Weight: [25%]                                        │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  [Save Rubric]  [Preview]  [Test with Candidate]             │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **Rubric name** | Input | Name for the rubric |
| **"Add Criterion"** | Button | Add new scoring dimension |
| **Criterion editor** | Inline form | Name, weight slider, level descriptions |
| **Level rows** | 1-5 levels | Per criterion: name, description, score |
| **Weight** | Input (%) | Must sum to 100% across criteria |
| **✏️ Edit** | Button per item | Edit criterion/level inline |
| **❌ Delete** | Button per item | Remove with confirmation |
| **"Save Rubric"** | Button | `POST /api/v1/admin/rubrics` |
| **"Preview"** | Button | See rubric as scoring interface |
| **"Test with Candidate"** | Button | Apply rubric to sample candidate |

---

### 9.20 Admin A/B Testing

**File:** `pages/admin/ab-testing.html` | **URL:** `/admin/ab-testing` | **Sidebar:** `nav_ab-testing` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Experiments table** | `cw-table` | Name, variant count, status, start date, confidence |
| **Status badges** | Draft / Running / Paused / Completed |
| **"New Experiment"** | Button | Create A/B test |
| **"View Results"** | Button per row | Metrics, statistical significance |
| **"Stop"** | Button per row | End experiment early |

---

### 9.21 Admin Prompt Management

**File:** `pages/admin/prompt-management.html` | **URL:** `/admin/prompt-management` | **Sidebar:** `nav_prompt-management` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Prompt list** | Table | Prompt name, model, version, last modified |
| **"New Prompt"** | Button | Create blank prompt |
| **"Edit"** | Button per row | → prompt editor with syntax highlighting |
| **Version history** | Dropdown | Switch between versions |
| **"Test"** | Button | Run prompt with sample input |
| **A/B comparison** | Side by side | Compare two prompt versions |

---

### 9.22 Admin AI Sales

**File:** `pages/admin/ai-sales.html` | **URL:** `/admin/ai-sales` | **Sidebar:** `nav_ai-sales` (RBAC: `manage_content`)

| Element | Action | Details |
|---------|--------|---------|
| **Sales leads** | Table | Company, contact, score, status, value |
| **Pipeline value** | Stat | Total potential revenue |
| **Conversion metrics** | Charts | Lead → Customer conversion funnel |
| **"View Lead"** | Button per row | Lead detail |

---

## 10. Mentor Pages (11 pages)

**Base URL:** `/mentor/...`  
**Sidebar:** Candidate sidebar (shared — see section 3)  
**JS Bundle:** `core.js` + `mentor.js`  
**Design System:** Custom Vivid (purple gradient cards, dark background)

---

### 10.1 Mentor Dashboard

**File:** `pages/mentor/mentor-dashboard.html` | **URL:** `/mentor/dashboard`

```
┌──────────────────────────────────────────────────────────────┐
│  Creator Studio               [🏆 Instructor Portal] [🟢 Live]
│  Manage your content and track your growth.                  │
│                                                              │
│  [➕ New Course]                                              │
│                                                              │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐ │
│  │ 💰 Total Revenue │ │ 📚 Active Courses│ │ 👥 Students  │ │
│  │    $0.00         │ │       0          │ │     0        │ │
│  │    +12%           │ │                  │ │              │ │
│  └──────────────────┘ └──────────────────┘ └──────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 📈 Earnings (30d)                                       │ │
│  │ [Chart.js line chart]                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  │
│  │ 📋 Recent Courses       │  │ 🎯 Tasks                 │  │
│  │                         │  │                          │  │
│  │ No courses yet          │  │ • Complete your profile  │  │
│  │ [Create your first →]   │  │ • Create your first c.. │  │
│  └─────────────────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

| Element | Action | Details |
|---------|--------|---------|
| **"Instructor Portal" badge** | Display | Purple badge |
| **"Live" badge** | Display | Green badge |
| **"New Course"** | Button | → `/mentor/mentor-create-course` |
| **Stat cards** (3) | Display | Total Revenue, Active Courses, Students |
| **Earnings chart** | Chart.js | Line chart |
| **Recent Courses** | List | → course detail |
| **Tasks** | Checklist | Onboarding to-do items |

---

### 10.2 Mentor Profile

**File:** `pages/mentor/mentor.html` | **URL:** `/mentor/mentor`

| Element | Action | Details |
|---------|--------|---------|
| **Profile display** | View | Mentor profile with bio, expertise, courses |
| **"Edit Profile"** | Button | → `/mentor/profile` |

---

### 10.3 Mentor Profile Edit

**File:** `pages/mentor/profile.html` | **URL:** `/mentor/profile`

| Element | Action | Details |
|---------|--------|---------|
| **Avatar upload** | File input | Profile photo |
| **Bio editor** | Text area | About me |
| **Expertise tags** | Add/remove | Skills/areas of expertise |
| **Social links** | Inputs | Website, LinkedIn, Twitter |
| **"Save"** | Button | `PUT /api/v1/mentor/profile` |

---

### 10.4 Mentor Landing

**File:** `pages/mentor/mentor-landing.html` | **URL:** `/mentor/mentor-landing`

| Element | Action | Details |
|---------|--------|---------|
| **Marketing page** | Hero + CTA | Mentor program promotion |
| **"Become a Mentor"** | Button | → `/signup/mentor` |

---

### 10.5 Mentor Courses

**File:** `pages/mentor/mentor-courses.html` | **URL:** `/mentor/mentor-courses`

| Element | Action | Details |
|---------|--------|---------|
| **Course list** | Cards/table | Title, status, enrollment, rating |
| **Status badges** | Draft / Published / Archived |
| **"Create Course"** | Button | → `/mentor/mentor-create-course` |
| **"Edit"** | Button per card | → `/mentor/mentor-course-editor` |
| **"Preview"** | Button per card | → public course view |

---

### 10.6 Mentor Create Course

**File:** `pages/mentor/mentor-create-course.html` | **URL:** `/mentor/mentor-create-course`

| Element | Action | Details |
|---------|--------|---------|
| **Course form** | Inputs | Title, description, category, price, thumbnail |
| **"Save Draft"** | Button | |
| **"Publish"** | Button | Submit for approval |

---

### 10.7 Mentor Course Editor

**File:** `pages/mentor/mentor-course-editor.html` | **URL:** `/mentor/mentor-course-editor`

| Element | Action | Details |
|---------|--------|---------|
| **Section list** | Accordion | Course modules with lessons |
| **"Add Section"** | Button | New module |
| **"Add Lesson"** | Button per section | New lesson within module |
| **Drag reorder** | Drag handle | Reorder sections/lessons |
| **Lesson editor** | Form | Title, video URL, content, duration |
| **"Save"** | Button | |

---

### 10.8 Mentor Students

**File:** `pages/mentor/mentor-students.html` | **URL:** `/mentor/mentor-students`

| Element | Action | Details |
|---------|--------|---------|
| **Students table** | `cw-table` | Name, email, course, progress, last active |
| **Progress bars** | Per student | Course completion % |
| **"Message"** | Button per student | Open chat |
| **"View Progress"** | Button per student | Detailed progress report |

---

### 10.9 Mentor Settings

**File:** `pages/mentor/mentor-settings.html` | **URL:** `/mentor/mentor-settings`

| Element | Action | Details |
|---------|--------|---------|
| **Profile settings** | Form | Name, bio, expertise, avatar |
| **Notification prefs** | Toggles | Email alerts for new enrollments, questions |
| **Payout settings** | Form | Payment method, minimum payout threshold |
| **"Save"** | Button | |

---

### 10.10 Mentor Wallet

**File:** `pages/mentor/mentor-wallet.html` | **URL:** `/mentor/mentor-wallet`

| Element | Action | Details |
|---------|--------|---------|
| **Balance** | Stat display | Current earnings balance |
| **Payout history** | Table | Date, amount, status (Paid/Pending) |
| **"Withdraw"** | Button | Request payout (if above threshold) |
| **Earnings chart** | Line chart | Earnings over time |

---

### 10.11 Mentor Community

**File:** `pages/mentor/community.html` | **URL:** `/mentor/community`

| Element | Action | Details |
|---------|--------|---------|
| **Discussion threads** | List | Topic, replies, last activity |
| **"New Thread"** | Button | Create discussion |
| **Q&A section** | Questions | Students asking questions |
| **"Answer"** | Button per question | Respond |

---

## 11. Cross-Page Navigation Map

This section shows how pages link to each other — the complete user flow graph.

### 11.1 Public → Auth Flow

```
index.html (landing)
  ├── "Get Started" → signup.html
  ├── "Sign In" → login.html
  ├── "View Jobs" → jobs.html
  └── "Pricing" → pricing.html

login.html (any role)
  ├── "Sign In" (success) → [role]/dashboard
  ├── "Forgot Password?" → forgot-password.html
  ├── "Sign Up" → signup.html
  └── Role tab switch → login-[role].html

signup.html
  ├── "Create Account" (success) → onboarding or dashboard
  └── Switch role → signup-[role].html

forgot-password.html
  ├── "Send Reset Link" (success) → verify-email.html
  └── "Back to Sign In" → login.html

reset-password.html
  └── "Reset Password" (success) → login.html
```

### 11.2 Candidate Flow

```
/candidate/dashboard
  ├── "Complete Profile" → /candidate/profile
  ├── "Take Interview" → /candidate/interview
  ├── "Browse Jobs" → /candidate/jobs
  └── Stat cards → /candidate/applications, /candidate/interviews

/candidate/profile
  ├── "Edit" → inline edit mode
  ├── "View Public" → /candidate/profile-view
  ├── "Visitors" → /candidate/profile-visitors
  └── "CV" → /candidate/cv-builder

/candidate/jobs
  ├── Job card → /candidate/jobs (detail → apply flow)
  ├── "Apply" → application submission
  └── "Save" → saves to /candidate/saved-jobs

/candidate/interview
  ├── "Start" → AI interview flow
  ├── "Complete" → /candidate/interview-analysis
  └── "Exit" → /candidate/dashboard

/candidate/applications
  └── Row click → application detail (stage, timeline)

/candidate/learning
  └── Course card → /candidate/course-details → /candidate/course-player

Sidebar links:
  /candidate/dashboard, /candidate/profile, /candidate/learning,
  /candidate/jobs, /candidate/applications, /candidate/interviews,
  /candidate/settings

Header:
  "New audit" → /candidate/onboarding
  Messages → /candidate/messages
```

### 11.3 Recruiter Flow

```
/recruiter/dashboard
  ├── "Post a Job" → /recruiter/job-wizard
  ├── "View Pipeline" → /recruiter/pipeline
  ├── Top candidate → /recruiter/candidate?id=X
  └── "View Matches" → /recruiter/candidates (filtered)

/recruiter/candidates
  ├── Row click → /recruiter/candidate?id=X
  ├── "Invite" → /recruiter/bulk-invite
  └── "Compare" → /recruiter/compare?ids=X,Y

/recruiter/candidate?id=X
  ├── "Change Stage" → inline
  ├── "Send Email" → email modal
  ├── "Schedule Interview" → calendar modal
  ├── "Make Offer" → /recruiter/offers
  ├── "Compare" → /recruiter/compare?ids=X,Y
  └── Tabs: Profile / CV / Interview / Notes / Activity / Docs

/recruiter/job-wizard
  └── "Complete" → /recruiter/jobs (new job listed)

/recruiter/pipeline
  ├── Kanban card → /recruiter/candidate?id=X
  └── View toggle → List / Table views

/recruiter/campaigns
  ├── "Create" → /recruiter/campaign-create
  └── "View" → /recruiter/campaigns-view

Sidebar links (all recruiter):
  Dashboard, Jobs, Create Job, Analytics, Reports,
  Candidates, Pipeline, Campaigns, Interviews,
  Skills Library, Team, Settings, Help

Header:
  "Post Job" → /recruiter/jobs
  Messages → /recruiter/messages
```

### 11.4 Admin Flow

```
/admin/dashboard
  ├── "Deep Analytics" → /admin/analytics
  ├── "Send Announcement" → /admin/announcements
  ├── "Support Tickets" → /admin/support
  ├── "Backup" → triggers backup
  └── "System Health" → /admin/technical

/admin/users
  ├── "Edit" → user edit modal (can manipulate subscription, credits, role)
  └── "Suspend" / "Delete" → confirmation

/admin/subscriptions
  └── "Edit" → change plan, adjust credits

Admin sidebar links → all /admin/* pages
  Links section → /dashboard, /recruiter/dashboard (live site previews)
```

---

## 12. All Buttons & Interactive Elements Reference

### 12.1 Global Elements (Present on Most Authenticated Pages)

| Element | Location | Icon | Action | API Endpoint |
|---------|----------|------|--------|-------------|
| **Mobile menu toggle** | Top header (mobile) | ☰ SVG | `Components.toggleMobileMenu()` | — |
| **Global search** | Top header | 🔍 | `POST /api/v1/search` | `/api/v1/search` |
| **Primary CTA** | Top header | ➕ / ✅ | Navigate to create/audit | — |
| **Language switcher** | Top header | 🌐 | `window.setLanguage(lang)` | — |
| **Notifications bell** | Top header | 🔔 | `Components.toggleNotifications()` | `GET /api/v1/notifications/latest?limit=5` |
| **Mark all read** | Notif dropdown | — | `Components.markAllNotifRead()` | `POST /api/v1/notifications/mark-all-read` |
| **Messages dropdown** | Top header | 💬 | `Components.toggleMessages()` | `GET /api/v1/messages/conversations` |
| **Sidebar collapse** | Sidebar | ◀ | `Components.toggleSidebar()` | — |
| **Sidebar nav items** | Sidebar | Various | Navigate to href | — |
| **Upgrade strip** | Sidebar bottom | 📈 | Navigate to subscription | — |
| **User card** | Sidebar bottom | Avatar | Navigate to settings/profile | — |
| **Sign Out** | Sidebar bottom | 🚪 | `POST /api/v1/logout` | `/api/v1/logout` |

### 12.2 Button Reference by Role

```
CANDIDATE BUTTONS:
  "New Audit" (header)          → /onboarding
  "Save Profile"                PUT /candidate/profile
  "Apply" (per job)             POST /candidate/applications
  "Save" (bookmark per job)     POST /candidate/saved-jobs
  "Withdraw" (per application)  DELETE /candidate/applications/{id}
  "Start Interview"             → /candidate/interview
  "Record/Pause/Stop/Skip"      Interview controls
  "Download Report"             PDF export
  "Share"                       Share link
  "Enroll Now" / "Start Course" → course enrollment
  "Mark Complete" (lesson)      PUT /learning/{courseId}/progress
  "Download Certificate"        PDF export
  "Save Changes" (settings)     PUT /candidate/settings
  "Delete Account"              DELETE /account
  "Submit EEO"                  POST /candidate/eeo
  "Accept & Sign" (esign)       POST /esign/{id}/sign
  "Upgrade" / "Downgrade"       POST /candidate/subscription
  "Cancel Subscription"         DELETE /candidate/subscription
  "Send Message"                POST /messages

RECRUITER BUTTONS:
  "Post Job" (header)           → /recruiter/jobs
  "Create Job"                  → /recruiter/job-wizard
  "AI Suggest" (salary)         AI suggestion call
  "Next" / "Previous" (wizard)  Step navigation
  "Save Draft" (job)            POST /recruiter/jobs (draft)
  "AI Rewrite" (JD)             AI processing
  "Analyze" (JD bias)           POST /jd/analyze
  "View" (per candidate)        → /recruiter/candidate?id=X
  "Change Stage"                PUT /recruiter/applications/{id}/stage
  "Send Email" (per candidate)  → email modal
  "Schedule Interview"          POST /recruiter/interviews
  "Make Offer"                  POST /recruiter/offers
  "Compare"                     → /recruiter/compare?ids=X,Y
  "Invite Candidate"            → /recruiter/bulk-invite
  "Create Campaign"             → /recruiter/campaign-create
  "Send Campaign"               POST /recruiter/campaigns/{id}/send
  "Initiate Background Check"   POST /background-checks
  "Save Settings"               PUT /recruiter/settings
  "Invite Member" (team)        POST /recruiter/team
  "Remove" (team member)        DELETE /recruiter/team/{id}
  "Create Pool" (talent pool)   POST /recruiter/talent-pools
  "Export CSV"                  CSV download
  "Run Audit" (bias)            POST /bias/audit
  "Generate Report"             POST /recruiter/reports/generate

ADMIN BUTTONS:
  "Deep Analytics"              → /admin/analytics
  "Backup"                      GET /admin/backup
  "Refresh"                     Reload dashboard data
  "Edit" (per user)             User edit modal
  "Suspend" / "Delete" (user)   PUT/DELETE /admin/users/{id}
  "Edit" (per subscription)     Plan change modal
  "Refund" (per payment)        POST /admin/payments/{id}/refund
  "Approve" / "Reject" (KYB)    POST /admin/verifications/{id}/{action}
  "Send Announcement"           POST /admin/announcements
  "Clear Cache"                 POST /admin/cache/clear
  "Save Rubric"                 POST /admin/rubrics
  "Save Settings"               PUT /admin/settings
  "New Prompt" (AI)             POST /admin/prompts
  "Test" (prompt)               POST /admin/prompts/{id}/test
  "New Experiment" (A/B)        POST /admin/ab-experiments
  "Create Course"               POST /admin/courses
  "Approve Course"              POST /admin/courses/{id}/approve

MENTOR BUTTONS:
  "New Course"                  → /mentor/mentor-create-course
  "Save Draft" (course)         POST /mentor/courses (draft)
  "Publish" (course)            POST /mentor/courses/{id}/publish
  "Add Section" / "Add Lesson"  Course structure builder
  "Save" (settings)             PUT /mentor/settings
  "Withdraw" (wallet)           POST /mentor/wallet/withdraw
  "Answer" (community)          POST /mentor/community/{id}/answer
```

---

## Legend

| Icon | Meaning |
|------|---------|
| → | Page navigation (URL change) |
| `POST/GET/PUT/DELETE` | API call |
| 🔒 | RBAC-protected (admin only with specific permission) |
| 🟢 / 🟡 / 🔴 | Status indicators |
| `{id}` | URL parameter (dynamic) |
| `[Button]` | Clickable button/link |
