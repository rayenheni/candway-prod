# Frontend Structure & Design System — Candway

> **Platform:** AI-Powered Recruitment & Learning Ecosystem  
> **Pages:** 15 public + 120 authenticated = **135 HTML files**  
> **Stack:** Static HTML + Tailwind CSS v4 + Custom CSS + esbuild JS bundling  
> **Server:** FastAPI/Starlette (serves static HTML)

---

## Table of Contents

1. [Directory Structure](#1-directory-structure)
2. [Build System](#2-build-system)
3. [Design System Overview](#3-design-system-overview)
4. [Page-by-Page Design System](#4-page-by-page-design-system)
   - [4.1 Public Pages](#41-public-pages)
   - [4.2 Auth Pages](#42-auth-pages)
   - [4.3 Candidate Pages](#43-candidate-pages)
   - [4.4 Recruiter Pages](#44-recruiter-pages)
   - [4.5 Admin Pages](#45-admin-pages)
   - [4.6 Mentor Pages](#46-mentor-pages)
5. [Core CSS Files Reference](#5-core-css-files-reference)
6. [JavaScript Architecture](#6-javascript-architecture)
7. [Common UI Components & Patterns](#7-common-ui-components--patterns)
8. [RTL & Dark Mode](#8-rtl--dark-mode)
9. [Internationalization](#9-internationalization)

---

## 1. Directory Structure

```
masar_landing_page/
│
├── *.html                              # 15 root-level public pages
│   index.html, blogs.html, blog-details.html
│   jobs.html, job-details.html
│   courses.html, opportunities.html
│   pricing.html, privacy.html, terms.html
│   404.html, 500.html, setup-wizard.html
│
├── pages/
│   ├── auth/                           # 13 pre-auth pages
│   │   login.html, login-admin.html, login-candidate.html
│   │   login-mentor.html, login-recruiter.html
│   │   signup.html, signup-recruiter.html, signup-mentor.html
│   │   forgot-password.html, reset-password.html
│   │   verify-email.html, verify-otp.html
│   │   google-callback.html
│   │
│   ├── candidate/                      # 26 pages
│   │   dashboard.html, profile.html, profile-view.html
│   │   applications.html, saved-jobs.html, jobs.html
│   │   interview.html, interviews.html, interview-analysis.html
│   │   cv-builder.html, cv-review.html, cv-selection.html
│   │   documents.html, eeo-form.html, esign-view.html
│   │   settings.html, subscription.html, onboarding.html
│   │   messages.html, marketplace.html
│   │   learning.html, course-details.html, course-landing.html
│   │   course-player.html, certificate.html
│   │   profile-visitors.html
│   │
│   ├── recruiter/                      # 47 pages
│   │   dashboard.html, analytics.html, analytics-dashboard.html
│   │   candidates.html, candidate.html, candidate-ranking.html
│   │   compare.html, comparison.html
│   │   jobs.html, job-wizard.html, jd-editor.html
│   │   pipeline.html, offers.html, interviews.html
│   │   interview-analysis-recruiter.html
│   │   eeo-dashboard.html, eeo-coverage.html
│   │   background-checks.html, background-check-detail.html
│   │   campaigns.html, campaigns-view.html, campaign-create.html
│   │   email-templates.html, esign-offer.html
│   │   chatbot-leads.html, copilot-full.html
│   │   reports.html, reports-list.html, report-builder.html
│   │   scoring-preview.html, bias-analytics.html, ghost-report.html
│   │   settings.html, billing.html, calendar-settings.html
│   │   team.html, messages.html, talent-pool.html
│   │   auto-job.html, reengagement.html, bulk-invite.html
│   │   skill-tree.html, skill-tree-create.html
│   │   skill-tree-library.html, skill-tree-list.html
│   │   landing.html, bot-settings.html
│   │
│   ├── admin/                          # 23 pages
│   │   dashboard.html, analytics.html, jobs.html
│   │   users.html, subscriptions.html, payments.html
│   │   invoices.html, categories.html, content.html
│   │   courses.html, settings.html, technical.html
│   │   support.html, verifications.html, announcements.html
│   │   marketing.html, opportunities.html, recruiter-usage.html
│   │   rubric-builder.html, rubrics.html, prompt-management.html
│   │   ab-testing.html, ai_sales.html
│   │
│   └── mentor/                         # 11 pages
│       mentor.html, mentor-dashboard.html, mentor-landing.html
│       mentor-courses.html, mentor-course-editor.html
│       mentor-create-course.html, mentor-students.html
│       mentor-settings.html, mentor-wallet.html
│       community.html, profile.html
│
├── css/
│   ├── design-tokens.css               # Centralized CSS custom properties (bridge layer)
│   ├── custom.css                      # Main app styles (1154 lines)
│   ├── public-glass.css                # Public-facing glassmorphism (1862 lines)
│   ├── recruiter-glass.css             # Recruiter-specific glass system (327 lines)
│   ├── admin-tables.css                # Enterprise table design system (810 lines)
│   ├── tailwind-landing.css            # Tailwind v4 PostCSS output (minified)
│   ├── mobile.css                      # Responsive breakpoints
│   ├── rubric-builder.css              # Rubric tree UI
│   └── tooltips.css                    # CSS-only [data-tooltip] system
│
├── js/
│   ├── entries/                        # 6 esbuild entry points
│   │   core.js, shared.js, candidate.js
│   │   recruiter.js, admin.js, mentor.js
│   │
│   ├── dist/                           # 12 bundled output files
│   │   core.js/.map, shared.js/.map, candidate.js/.map
│   │   recruiter.js/.map, admin.js/.map, mentor.js/.map
│   │
│   ├── lang/                           # Translation files (4600+ keys each)
│   │   en.js, fr.js, ar.js
│   │
│   ├── Core Layer (loaded on every page)
│   │   app-state.js, app-auth.js, config.js, csrf.js
│   │   constants.js, security.js, xss-protection.js
│   │   components.js, toast.js, error-boundary.js
│   │   translations.js, localization.js, performance.js
│   │   load-assets.js, auth-guard.js, auth-token.js
│   │
│   ├── Shared Features
│   │   feature-flags.js, cross-page-sync.js, notifications.js
│   │   chat-widget.js, gdpr.js, accessibility-enhanced.js
│   │
│   ├── Candidate
│   │   candidate-dashboard.js, candidate-interview.js
│   │   career-chat-widget.js, eeo-form.js, eeo-coverage.js
│   │   profile-visitors.js, courses-premium.js
│   │   jobs-premium.js, cv-builder.js
│   │
│   ├── Recruiter
│   │   recruiter-enhancements.js, recruiter-pipeline.js
│   │   recruiter-onboarding.js, onboarding-wizard.js
│   │   jd-editor.js, job-wizard.js, scoring-preview.js
│   │   rubric-builder.js, rubrics.js, skill-tree-modal.js
│   │   reengagement.js, report-builder.js, reports-list.js
│   │   background-checks.js, chatbot-leads.js, talent-pool.js
│   │
│   ├── Admin
│   │   admin-components.js, eeo-dashboard.js, prompt-management.js
│   │
│   └── Mentor
│       help-center.js
│
├── assets/
│   ├── images/                         # Logo PNGs, favicon, OG image
│   └── receipts/ sounds/              # Misc assets
│
├── scripts/
│   └── build-js.js                     # esbuild bundler script
│
├── package.json                        # Build scripts
├── tailwind.config.js                  # Tailwind theme config
└── postcss.config.js                   # PostCSS: tailwindcss + autoprefixer
```

---

## 2. Build System

### 2.1 JS Bundling (esbuild)

| Bundle | Size | Contents |
|--------|------|----------|
| `core.js` | 139 KB | AppState, AppAuth, config, csrf, constants, security, xss-protection, components, toast, error-boundary, translations, localization, performance, load-assets, auth-guard, auth-token |
| `shared.js` | 33 KB | feature-flags, cross-page-sync, notifications, chat-widget, gdpr, accessibility-enhanced |
| `candidate.js` | 160 KB | candidate-dashboard, candidate-interview, career-chat-widget, eeo-form, eeo-coverage, profile-visitors, courses-premium, jobs-premium, cv-builder |
| `recruiter.js` | 275 KB | recruiter-enhancements, recruiter-pipeline, recruiter-onboarding, onboarding-wizard, jd-editor, job-wizard, scoring-preview, rubric-builder, rubrics, skill-tree-modal, reengagement, report-builder, reports-list, background-checks, chatbot-leads, talent-pool |
| `admin.js` | 41 KB | admin-components, eeo-dashboard, prompt-management |
| `mentor.js` | 8 KB | help-center |

**Build script** (`scripts/build-js.js`):
- Format: IIFE (Immediately Invoked Function Expression)
- Target: ES2020
- Source maps: dev only
- Minification: production only
- Tree-shaking: disabled (IIFEs use `window.*` assignments)

### 2.2 CSS Build (Tailwind v4 + PostCSS)

```json
{
  "build:css": "npx tailwindcss -i ./css/tailwind-landing.input.css -o ./css/tailwind-landing.css --minify",
  "build:js": "node scripts/build-js.js",
  "build": "npm run build:css && npm run build:js"
}
```

### 2.3 Tailwind Config

```js
theme: {
  extend: {
    fontFamily: {
      sans: ["Outfit", "sans-serif"],
      mono: ["JetBrains Mono", "monospace"],
    },
    colors: {
      indigo: { 50: "#eef2ff", 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5", 900: "#312e81" },
      violet: { 50–900 (full scale) },
      slate: { 850: "#1e293b", 900: "#0f172a", 950: "#020617" },
    },
    keyframes: { "gradient-x", float, "infinite-scroll", "fade-in-up", "pulse-slow" },
    animation: { "gradient-x", float, "infinite-scroll", "fade-in-up", "pulse-slow" },
  },
}
```

---

## 3. Design System Overview

### 3.1 Core Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--candway-primary` | `#6366F1` (Indigo-500) | Primary actions, links, recruiter branding |
| `--candway-primary-light` | `#818CF8` (Indigo-400) | Hover states, light accents |
| `--candway-primary-dark` | `#3730A3` (Indigo-800) | Active states, dark backgrounds |
| `--candway-secondary` | `#7C3AED` (Violet-600) | Candidate branding, secondary CTAs |
| `--candway-accent` | `#06B6D4` (Cyan-500) | Highlights, notifications |
| `--candway-success` | `#10B981` (Emerald-500) | Positive indicators, stages passed |
| `--candway-warning` | `#F59E0B` (Amber-500) | Warnings, medium risk |
| `--candway-danger` | `#EF4444` (Red-500) | Errors, rejections, critical |
| `--candway-bg` | `#F8FAFC` (Slate-50) | Page backgrounds |
| `--candway-text` | `#1E293B` (Slate-800) | Body text |
| `--candway-text-muted` | `#64748B` (Slate-500) | Secondary text, placeholders |

### 3.2 Typography

| Role | Font | Weights |
|------|------|---------|
| **Primary (app)** | Outfit | 300, 400, 500, 600, 700, 800, 900 |
| **Public landing** | Cabinet Grotesk (displays) + Instrument Sans (body) | 400–900 / 400–600 |
| **Monospace** | JetBrains Mono | 400, 500 |
| **Icons** | Font Awesome 6 (free) | — |

### 3.3 Glassmorphism (Core Visual Language)

The entire platform uses glassmorphism as its defining visual pattern:

```css
.glass-panel {
    background: rgba(255, 255, 255, 0.65);
    backdrop-filter: blur(20px) saturate(165%);
    -webkit-backdrop-filter: blur(20px) saturate(165%);
    border: 1px solid rgba(255, 255, 255, 0.8);
    border-radius: 22px;
    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
}
```

### 3.4 Three CSS Variable Systems (Migration in Progress)

| System | Prefix | File | Primary |
|--------|--------|------|---------|
| **Legacy custom.css** | `--primary` | `custom.css` | `#6366F1` |
| **Public Glass** | `--pg-*` | `public-glass.css` | `#7C3AED` |
| **Canonical tokens** | `--candway-*` | `design-tokens.css` | `#6366F1` |

New code should use `--candway-*` tokens. Both legacy systems are aliased in `design-tokens.css`.

### 3.5 Key CSS Files

| File | Lines | Purpose |
|------|-------|---------|
| `design-tokens.css` | 43 | Centralized CSS custom properties (bridge layer) |
| `custom.css` | 1154 | Premium components, glass cards, sidebar, RTL, admin styles |
| `public-glass.css` | 1862 | Full public-facing glassmorphism design system |
| `recruiter-glass.css` | 327 | Recruiter-specific glass system, blob backgrounds |
| `admin-tables.css` | 810 | Enterprise table design system with glass aesthetics |
| `mobile.css` | ~200 | Responsive breakpoints, sidebar collapse, mobile overlay |
| `tooltips.css` | ~100 | CSS-only `[data-tooltip]` system |
| `rubric-builder.css` | ~200 | Rubric tree UI components |

---

## 4. Page-by-Page Design System

### 4.1 Public Pages

| Page | CSS Files | Design System | Key Visual Features |
|------|-----------|---------------|-------------------|
| **index.html** | Inline `<style>` + Font Awesome | **Custom public** — Indigo/Violet | Ambient gradient blobs, glass hero section, animated counters, testimonials carousel, Cabinet Grotesk display font, grid pattern overlay, floating elements |
| **blogs.html** | Inline + Font Awesome | Same as index | Blog card grid, glass cards, tag filters, reading time badges |
| **blog-details.html** | Inline + Font Awesome | Same as index | Article prose layout, scroll progress bar, share buttons |
| **jobs.html** (public) | Inline + Font Awesome | Same as index | Job listing cards, search bar, category pills |
| **job-details.html** | Inline + Font Awesome | Same as index | Hero section with apply CTA, company info sidebar |
| **courses.html** | Inline + Font Awesome | Same as index | Course card grid, category tabs, rating stars |
| **pricing.html** | Inline + Font Awesome | Same as index | Pricing tier cards, feature comparison, toggle monthly/yearly |
| **privacy.html / terms.html** | Inline | Minimal | Clean prose layout, no glass, simple typography |
| **404.html / 500.html** | Inline | Minimal | Centered error message, animated illustration |
| **setup-wizard.html** | Inline | Custom setup | Step indicator, glass form panels |
| **opportunities.html** | Inline | Same as index | Opportunity cards with apply modal |

**Page structure (public):**
```html
<html lang="fr">
<head>
    <!-- Cabinet Grotesk + Instrument Sans fonts -->
    <!-- Font Awesome 6 -->
    <!-- Inline <style> with design tokens + all page CSS -->
</head>
<body>
    <!-- Navbar: glass fixed top -->
    <!-- Hero section with gradient blobs -->
    <!-- Content sections with glass cards -->
    <!-- Footer -->
    <!-- Translation JS + localization -->
    <!-- GDPR consent banner -->
</body>
```

**Design tokens (public pages, from index.html):**
```css
--indigo: #6366F1;
--purple: #9333EA;
--rose: #F43F5E;
--green: #10B981;
--amber: #F59E0B;
--ink: #0F172A;
--ink-m: #64748B;
--f-disp: 'Cabinet Grotesk', 'Georgia', sans-serif;
--f-body: 'Instrument Sans', -apple-system, sans-serif;
--grad: linear-gradient(135deg, var(--indigo) 0%, var(--purple) 100%);
```

---

### 4.2 Auth Pages

| Page | CSS Files | Design System | Key Visual Features |
|------|-----------|---------------|-------------------|
| **login.html** | `tailwind-landing.css` + CDN Tailwind + inline | **Dark glass** — Slate-950 bg | Auth-glass container (dark blur), premium-input fields, role tabs (candidate/recruiter), gradient accent borders on focus, social login buttons, animated gradient background (indigo + emerald) |
| **login-candidate.html** | `tailwind-landing.css` + inline | **Violet accent** — `#7C3AED` | Violet-tinted glass, candidate-branded role badge |
| **login-recruiter.html** | `tailwind-landing.css` + inline | **Indigo accent** — `#6366F1` | Indigo-tinted glass, recruiter-branded role badge |
| **login-admin.html** | `tailwind-landing.css` + inline | **Dark enterprise** | Dark glass, admin badge, no-nonsense form |
| **login-mentor.html** | `tailwind-landing.css` + inline | **Purple accent** | Purple glass, mentor badge |
| **signup.html** | `tailwind-landing.css` + inline | Dark glass (same as login) | Multi-role signup tabs, glass form sections |
| **signup-recruiter.html** | `tailwind-landing.css` + inline | Indigo accent | Company info fields, glass card layout |
| **signup-mentor.html** | `tailwind-landing.css` + inline | Purple accent | Mentor registration form |
| **forgot-password.html** | `tailwind-landing.css` + inline | Dark glass minimal | Single email field, glass card centered |
| **reset-password.html** | `tailwind-landing.css` + inline | Dark glass minimal | New password + confirm form |
| **verify-email.html** | `tailwind-landing.css` + inline | Dark glass | OTP input, resend timer |
| **verify-otp.html** | `tailwind-landing.css` + inline | Dark glass | 6-digit OTP input boxes |
| **google-callback.html** | Inline | Minimal | Processing spinner, auto-redirect |

**Auth glass pattern:**
```css
.auth-glass {
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
}
.premium-input {
    background: rgba(2, 6, 23, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: white;
}
.premium-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
}
```

---

### 4.3 Candidate Pages

**Primary palette:** Violet (`#7C3AED`) — distinct from recruiter's Indigo

| Page | CSS Files | Design System | Key Visual Features |
|------|-----------|---------------|-------------------|
| **dashboard.html** | `public-glass.css` (via link) + inline | **Public Glass** — Violet (`--pg-primary: #7C3AED`) | Ambient radial gradient background, bento grid layout (12-col), stat cards with icons, AOS scroll animations, achievement cards, skill tag pills, activity timeline, dark mode support, `data-theme="dark"` |
| **profile.html** | `tailwind-landing.css` + `custom.css` + `public-glass.css` | Public Glass + Custom | Avatar upload, glass card sections, skills tags, experience timeline, education cards |
| **profile-view.html** | `tailwind-landing.css` + `custom.css` + inline | Public Glass | Read-only profile, company info from recruiter profile, badges |
| **applications.html** | `tailwind-landing.css` + `custom.css` + inline | Public Glass + Custom table | Application cards with stage indicator pills, progress bars, status badges, empty states |
| **saved-jobs.html** | `tailwind-landing.css` + `custom.css` + `public-glass.css` | Public Glass | Bookmarked job cards, remove button, apply CTA |
| **jobs.html** | `tailwind-landing.css` + `custom.css` (sidebar) + AOS | **Custom (sidebar)** — Indigo primary | Full sidebar (280px) + top header (76px), search bar, filter bar, job cards grid, match score badges, company logo avatars, dark mode support |
| **interview.html** | `tailwind-landing.css` + `public-glass.css` + inline | Public Glass | AI interview interface, chat bubbles (AI left / user right), timer, recording indicator, waveform animation, transcript side panel |
| **interviews.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Public Glass | Interview history cards, score badges, re-take button, calendar view |
| **interview-analysis.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Public Glass | Radar chart (Chart.js), skill breakdown bars, strengths/weaknesses, AI summary panel |
| **cv-builder.html** | `tailwind-landing.css` + `custom.css` + inline | Custom | Drag-and-drop sections, live preview panel, template selector, rich text editor |
| **cv-review.html** | `tailwind-landing.css` + `custom.css` + inline | Custom | AI review results, improvement suggestions, score gauge |
| **cv-selection.html** | `tailwind-landing.css` + `custom.css` + inline | Custom | CV version comparison, selection cards |
| **documents.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Document upload cards, file type badges, download buttons |
| **eeo-form.html** | `tailwind-landing.css` + inline | Minimal glass | EEO compliance form, radio groups, privacy note |
| **esign-view.html** | `tailwind-landing.css` + inline | Minimal | Document viewer, signature pad, accept/decline |
| **settings.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Tabbed settings sections, toggle switches, language selector |
| **subscription.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Plan comparison cards, features list, upgrade CTA |
| **onboarding.html** | `tailwind-landing.css` + `public-glass.css` + inline | Public Glass | Step wizard, progress dots, glass panels, motivation cards |
| **messages.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Chat list + conversation view, message bubbles, attachment icons |
| **marketplace.html** | Inline | Public Glass | Course/job marketplace cards, category grid |
| **learning.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Violet | Course cards, learning path timeline, progress rings |
| **course-details.html** | `tailwind-landing.css` + inline | Custom | Course hero, syllabus accordion, instructor card, reviews |
| **course-landing.html** | `tailwind-landing.css` + inline | Custom + Violet | Course marketing page, feature highlights, pricing |
| **course-player.html** | `tailwind-landing.css` + inline | Custom | Video player, lesson sidebar, progress tracking, notes panel |
| **certificate.html** | Inline | Minimal print | Certificate display, download/share buttons, confetti animation |
| **profile-visitors.html** | `tailwind-landing.css` + `custom.css` + `public-glass.css` + inline | Public Glass + Custom | Visitor cards with company info, visit timestamps, anonymous visitor count |

**Candidate dashboard GLASS pattern:**
```css
:root {
    --primary: #7C3AED;
    --primary-light: #A78BFA;
    --primary-dark: #5B21B6;
    --success: #10B981;
    --glass-bg: rgba(255, 255, 255, 0.68);
    --glass-border: rgba(255, 255, 255, 0.58);
    --card-shadow: 0 24px 70px -32px rgba(88, 28, 135, 0.38), inset 0 1px 0 rgba(255,255,255,0.72);
}
```

**Bento grid system** (used in candidate dashboard):
```css
.bento-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 1.5rem;
}
.bento-col-3 { grid-column: span 3; }
.bento-col-4 { grid-column: span 4; }
.bento-col-6 { grid-column: span 6; }
.bento-col-8 { grid-column: span 8; }
.bento-col-12 { grid-column: span 12; }
```

**Page structure (candidate dashboard):**
```html
<html lang="en" data-theme="light">
<head>
    <!-- Outfit font, Font Awesome 6, AOS CSS -->
    <!-- public-glass.css -->
    <!-- Inline <style>: tokens, ambient-bg, bento grid, glass cards, skeleton -->
    <!-- Core bundle -->
</head>
<body class="bg-[#F5F3FF] font-['Outfit'] antialiased">
    <!-- Ambient background (radial gradients + grid pattern) -->
    <!-- Sidebar (injected by Components.init()) -->
    <!-- Main content with bento grid layout -->
    <!-- Stats row (4 glass cards) -->
    <!-- Activity + Tasks + Charts + Quick actions (2-column bento) -->
    <!-- Shared bundle + Candidate bundle -->
    <!-- Inline page script -->
</body>
```

---

### 4.4 Recruiter Pages

**Primary palette:** Indigo (`#6366F1`) — distinct from candidate's Violet

| Page | CSS Files | Design System | Key Visual Features |
|------|-----------|---------------|-------------------|
| **dashboard.html** | `tailwind-landing.css` + `tooltips.css` + `recruiter-glass.css` + CDN Tailwind | **Recruiter Glass** — Indigo (`--primary: #6366F1`) | Animated background blobs (`blob-1`, `blob-2`, `blob-3`), glass-panel class system, bento grid, stat cards with gradient overlays, AOS scroll, Chart.js analytics, dark mode, sidebar + top header |
| **analytics.html** | `tailwind-landing.css` + `custom.css` + inline | Recruiter Glass + Custom | Chart.js visualizations, date range picker, KPI cards, funnel chart, export buttons |
| **analytics-dashboard.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Combined analytics, source breakdown, conversion funnel, trend lines |
| **candidates.html** | `tailwind-landing.css` + `tooltips.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Candidate table with sticky header (`candidate-table`), stage pills (`stage-pill`), action buttons, filter bar, sortable columns, selectable rows, search, bulk actions |
| **candidate.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Candidate profile view, CV viewer, interview results, notes timeline, stage changer |
| **candidate-ranking.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Ranked candidate cards, score bars, comparison toggle |
| **compare.html / comparison.html** | `tailwind-landing.css` + `custom.css` + inline | Recruiter Glass | Side-by-side candidate comparison, skill radar charts, score matrix |
| **jobs.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Job list with status badges, draft/published filters, stats per job |
| **job-wizard.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` + Inter font | **Recruiter Wizard** — Indigo + Inter | Multi-step wizard with `step-panel` transitions (fadeSlideIn/Out), step indicator dots, category/recruiter dropdown, AI suggest salary, tips sidebar, glass form panels, animated bg blob |
| **jd-editor.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Rich text editor, AI rewrite panel, token counter, word list analysis |
| **pipeline.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | **Recruiter Glass** | Kanban board (drag-and-drop columns), candidate cards with avatars and score, column counts, view toggle (kanban/list/table) |
| **offers.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Offer cards, status tracking, send/withdraw/respond actions |
| **interviews.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Interview schedule, calendar view, interview cards with feedback status |
| **interview-analysis-recruiter.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Comprehensive analysis, transcript viewer, skill scores, AI notes, recording |
| **eeo-dashboard.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` + inline | **Admin Tables** | EEO compliance dashboard, diversity metrics, charts, demographic breakdowns |
| **eeo-coverage.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Coverage percentage cards, department breakdown, completion status |
| **background-checks.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` + inline | Recruiter Glass + Custom | Background check cards, status pills, initiate button, vendor status |
| **background-check-detail.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Detailed check report, section-by-section results, report download |
| **campaigns.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Campaign list cards, active/draft/completed, stats per campaign |
| **campaigns-view.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Campaign detail, performance metrics, audience breakdown |
| **campaign-create.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Campaign builder, audience selector, template picker, schedule |
| **email-templates.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Template list, preview mode, editor, variable insertion |
| **esign-offer.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Offer document builder, signature fields, send for e-sign |
| **chatbot-leads.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` + inline | Recruiter Glass + Custom | Lead list, chat transcript viewer, lead score, conversion actions |
| **copilot-full.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Full AI copilot interface, chat panel, context sidebar, action suggestions |
| **reports.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Report cards with preview thumbnails, schedule indicators |
| **reports-list.html** | `tailwind-landing.css` + `custom.css` | Recruiter Glass | Sorted/filtered report list, date range, type badges |
| **report-builder.html** | `tailwind-landing.css` + `custom.css` | Recruiter Glass | Drag-and-drop report builder, metric selector, chart picker, preview |
| **scoring-preview.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Score breakdown cards, criteria bars, AI explanation panel, bias indicators |
| **bias-analytics.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Bias detection dashboard, fairness metrics, demographic comparison |
| **ghost-report.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Ghost candidate report, incomplete application tracking |
| **settings.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass + Custom | Tabbed settings (profile, company, notifications, security), glass panels |
| **billing.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Subscription card, usage meters, invoices table, payment method |
| **calendar-settings.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Calendar sync (Google/Outlook), availability slots, timezone selector |
| **team.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Team member cards, role badges, invite member modal, permissions |
| **messages.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Inbox with conversation list, message area, templates, quick replies |
| **talent-pool.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Talent pool cards, candidate count, notes, add/remove actions |
| **auto-job.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Auto-job creation config, AI-generated jobs preview, schedule |
| **reengagement.html** | `tailwind-landing.css` + `custom.css` + `recruiter-glass.css` | Recruiter Glass | Reengagement campaign setup, audience filters, email templates |
| **bulk-invite.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | CSV upload, email input list, review before send, progress bar |
| **skill-tree.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Interactive skill tree visualization, node details |
| **skill-tree-create.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Skill tree editor, add/remove nodes, drag connections |
| **skill-tree-library.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Skill tree template library, import, preview |
| **skill-tree-list.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | List of created skill trees, status, edit/delete |
| **landing.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Public | Recruiter landing/marketing page, feature showcase |
| **bot-settings.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Chatbot configuration, personality settings, response templates |

**Recruiter GLASS pattern:**
```css
:root {
    --primary: #6366f1;
    --primary-dark: #4f46e5;
    --primary-light: #818cf8;
    --primary-glow: rgba(99, 102, 241, 0.15);
    --glass-bg: rgba(255, 255, 255, 0.65);
    --glass-border: rgba(255, 255, 255, 0.8);
    --glass-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
}

.glass-card:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 102, 241, 0.34);
    box-shadow: 0 30px 80px -34px rgba(79, 70, 229, 0.48);
}
```

**Animated background blobs** (recruiter pages):
```css
.bg-blob {
    position: fixed; width: 500px; height: 500px;
    border-radius: 50%; filter: blur(120px); z-index: 0; pointer-events: none;
}
.blob-1 { background: linear-gradient(135deg, #818cf8, #6366f1); top: -10%; left: -5%; }
.blob-2 { background: linear-gradient(135deg, #a78bfa, #8b5cf6); bottom: -10%; right: -5%; }
```

---

### 4.5 Admin Pages

**Primary palette:** Indigo (`#6366F1`) with dark sidebar

| Page | CSS Files | Design System | Key Visual Features |
|------|-----------|---------------|-------------------|
| **dashboard.html** | `tailwind-landing.css` + `custom.css` + CDN Chart.js | **Custom** (dark sidebar + glass panels) | `glass-panel` stat cards (rounded-2xl), stat-icon with group hover color transition, action-chip badges, activity-card list, Chart.js line/bar charts, dark gradient sidebar, backup button, global status pulse indicator, AOS animations, i18n attributes |
| **analytics.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` + Chart.js | **Custom + Admin Tables** | Deep analytics dashboard, multiple Chart.js visualizations, tables, export |
| **jobs.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | Job management table (`cw-table-*` classes), batch actions, status badges |
| **users.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | User management table, role badges, actions dropdown, search + filter |
| **subscriptions.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | Subscription table, plan badges, status indicators, payment history |
| **payments.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | Payment transactions table, receipt download, refund action |
| **invoices.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | Invoice generation, status tracking, download PDF |
| **categories.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | Category management tree + table, reorder, add/edit/delete |
| **content.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Content management, rich text editor, publish/draft toggle |
| **courses.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Tables | Course list, approval workflow, featured toggle |
| **settings.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Platform settings, toggle switches, config fields |
| **technical.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | System status, cache management, log viewer, health checks |
| **support.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Support tickets table, assignee select, status workflow |
| **verifications.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Verification requests, approve/reject actions, ID document viewer |
| **announcements.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Announcement editor, scheduling, target audience, send |
| **marketing.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Campaign management, analytics, A/B test results |
| **opportunities.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Opportunity management, status, application count |
| **recruiter-usage.html** | `tailwind-landing.css` + `custom.css` + `admin-tables.css` | **Admin Tables** | Usage monitoring per recruiter, limits, overage indicators |
| **rubric-builder.html** | `tailwind-landing.css` + `custom.css` + `rubric-builder.css` | **Custom + Rubric** | Interactive rubric tree, criteria editor, scoring weights, preview |
| **rubrics.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | Rubric list, version history, status badges |
| **prompt-management.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | AI prompt editor, versioning, test runner, A/B prompt comparison |
| **ab-testing.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | A/B experiment dashboard, variants, metrics, statistical significance |
| **ai_sales.html** | `tailwind-landing.css` + `custom.css` + inline | Custom + Glass | AI sales lead tracking, conversion metrics, pipeline value |

**Admin table system** (`admin-tables.css`):
```css
:root {
    --cw-accent: #7C3AED;
    --cw-bg-page: #f5f3ff;
    --cw-bg-card: rgba(255, 255, 255, 0.72);
    --cw-radius-xl: 22px;
    --cw-shadow-card: 0 24px 70px -32px rgba(88, 28, 135, 0.38), inset 0 1px 0 rgba(255,255,255,0.72);
}
.cw-table-wrap { background: #fff; border-radius: var(--cw-radius-xl); overflow: hidden; }
.cw-table { width: 100%; border-collapse: collapse; }
.cw-table th { text-align: left; padding: 14px 24px; font-size: 10px; font-weight: 800; text-transform: uppercase; color: #94a3b8; background: rgba(245,243,255,0.85); }
.cw-table td { padding: 14px 24px; border-bottom: 1px solid rgba(167,139,250,0.1); }
.cw-pill { display: inline-flex; align-items: center; padding: 2px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; }
```

**Page structure (admin dashboard):**
```html
<html lang="en">
<head>
    <!-- tailwind-landing.css, custom.css -->
    <!-- Chart.js CDN -->
    <!-- Font Awesome 6 (lazy loaded) -->
    <!-- Outfit font -->
    <!-- Core + Admin bundles -->
</head>
<body class="flex bg-white text-slate-800 font-['Outfit'] antialiased overflow-hidden h-screen">
    <!-- Fixed sidebar (#admin-sidebar-container) — dark gradient, indigo/violet accents -->
    <!-- Main content (overflow-y-auto, scroll-smooth) -->
    <!-- Header with title, global status indicator, backup & refresh buttons, deep analytics link -->
    <!-- Stats grid (4 glass cards: users, revenue, jobs, interviews) -->
    <!-- Charts section (Chart.js: signups + revenue) -->
    <!-- Recent activity + quick actions -->
    <!-- Inline page script -->
</body>
```

**Admin sidebar:**
```css
/* Dark sidebar with radial gradient, light-sweep animation on active link,
   section labels, language switcher, logout button */
```

---

### 4.6 Mentor Pages

**Primary palette:** Purple (`#7C3AED` / violet gradient)

| Page | CSS Files | Design System | Key Visual Features |
|------|-----------|---------------|-------------------|
| **mentor-dashboard.html** | `tailwind-landing.css` + Chart.js | **Custom Vivid** — Purple gradient | Dark bg (slate-900), vivid gradient stat cards (indigo→purple), glass badges with backdrop-blur, Chart.js earnings chart, course performance cards, student list, sidebar injected by components.js, i18n attributes |
| **mentor.html** | `tailwind-landing.css` + inline | Custom Vivid | Mentor profile/landing, stats overview |
| **mentor-landing.html** | Inline | Custom Vivid | Marketing page for mentor program |
| **mentor-courses.html** | `tailwind-landing.css` + inline | Custom Vivid | Course list, status badges, student count, rating |
| **mentor-course-editor.html** | `tailwind-landing.css` + inline | Custom Vivid | Section/lesson editor, drag-and-drop reorder, content blocks |
| **mentor-create-course.html** | `tailwind-landing.css` + inline | Custom Vivid | Course creation form, pricing, categories, thumbnail upload |
| **mentor-students.html** | `tailwind-landing.css` + inline | Custom Vivid | Student table, progress bars, last active, message button |
| **mentor-settings.html** | `tailwind-landing.css` + inline | Custom Vivid | Profile settings, payout info, notification prefs |
| **mentor-wallet.html** | `tailwind-landing.css` + inline | Custom Vivid | Earnings dashboard, payout history, withdrawal form |
| **community.html** | `tailwind-landing.css` + inline | Custom Vivid | Discussion threads, Q&A, mentor badges |
| **profile.html** | `tailwind-landing.css` + inline | Custom Vivid | Mentor public profile, bio, courses, reviews |

**Menter dashboard card pattern:**
```css
/* Vivid gradient cards */
.bg-gradient-to-br.from-indigo-600.to-purple-700 {
    /* Example: Revenue card with white/10 blur overlay */
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    transition: all 0.5s;
}
```

---

## 5. Core CSS Files Reference

### 5.1 `design-tokens.css` (43 lines)

Centralized bridge layer unifying three variable systems:

```css
--candway-primary: #6366f1;
--candway-secondary: #7c3aed;
--candway-accent: #06b6d4;
--candway-success: #10b981;
--candway-warning: #f59e0b;
--candway-danger: #ef4444;
--candway-bg: #f8fafc;
--candway-surface: #ffffff;
--candway-border: #e2e8f0;
--candway-text: #1e293b;
--candway-text-muted: #64748b;
--candway-glass-bg: rgba(255,255,255,0.15);
--candway-glass-border: rgba(255,255,255,0.25);
--candway-glass-shadow: 0 8px 32px rgba(0,0,0,0.1);

/* Legacy aliases */
--primary: var(--candway-primary);
--secondary: var(--candway-secondary);
--pg-primary: var(--candway-primary);
--pg-secondary: var(--candway-secondary);
```

### 5.2 `custom.css` (1154 lines)

**Sections:**
1. Color palette (`--primary: #6366f1`) + neutrals
2. Glassmorphism tokens (`--glass-bg`, `--glass-blur`, etc.)
3. Sidebar variables + responsive breakpoints
4. Kanban board responsive styles
5. Admin sidebar (dark gradient with light-sweep animation)
6. Sidebar nav links with hover effects
7. Top header styles
8. Premium form inputs
9. Button styles (primary, secondary, outline, ghost)
10. Badge and tag styles
11. Card hover effects
12. Scrollbar customization
13. Stats grid patterns
14. Skeleton loader animations
15. RTL overrides (lines 1028–1154)

### 5.3 `public-glass.css` (1862 lines)

The most comprehensive CSS file, designed for candidate/public-facing pages.

**Sections:**
1. Design tokens (`--pg-primary: #7C3AED`)
2. Reset & base styles
3. Typography (headings, body, small, captions)
4. Glass panel system
5. Premium cards (glass, hover, gradient overlay, glow)
6. Buttons (solid, outline, ghost, size variants)
7. Forms (inputs, selects, textareas, checkboxes, toggles)
8. Badges & tags (status, skill, role)
9. Profile components (avatar, banner, stats)
10. Navigation (top nav, breadcrumbs, tabs, pagination)
11. Grid layouts (bento, card grids)
12. Tables
13. Modals & drawers
14. Utility classes

### 5.4 `recruiter-glass.css` (327 lines)

**Sections:**
1. Design tokens (`--primary: #6366f1`)
2. Animated background blobs (`blob-1/2/3` with `floatBlob` keyframe)
3. Glass panel utility (`.glass-panel`)
4. Stat cards (`.stat-card` with icon, value, label)
5. Premium glass cards (`.glass-card` with `::before` gradient overlay)
6. Glass form controls
7. Glass buttons
8. Filter bar
9. Score bar component
10. Responsive breakpoints
11. RTL + dark mode support

### 5.5 `admin-tables.css` (810 lines)

**Sections:**
1. Design tokens (`--cw-*` namespace, violet/indigo palette)
2. Table wrapper (`.cw-table-wrap` — glass, rounded-2xl)
3. Table scroll container
4. Table headers (sticky, uppercase, 10px font)
5. Table cells (padding, borders)
6. Row states (hover, selected, clickable)
7. Component styles: pills, badges, progress bars, action buttons
8. Filter bar integration
9. Pagination
10. Empty states
11. Skeleton loading states
12. Responsive breakpoints
13. RTL overrides

---

## 6. JavaScript Architecture

### 6.1 Bundle Loading Strategy

Every page loads **core.js** + role-specific bundle:

```html
<!-- EVERY page: -->
<script src="/js/dist/core.js?v=2026072618"></script>

<!-- ROLE-SPECIFIC (one of): -->
<script src="/js/dist/shared.js?v=2026072618"></script>
<script src="/js/dist/candidate.js?v=2026072618"></script>
<script src="/js/dist/recruiter.js?v=2026072618"></script>
<script src="/js/dist/admin.js?v=2026072618"></script>
<script src="/js/dist/mentor.js?v=2026072618"></script>
```

### 6.2 Core Modules (139 KB, loaded on every page)

| Module | File | Purpose |
|--------|------|---------|
| **AppState** | `app-state.js` | Centralized state manager (pub/sub, cross-tab BroadcastChannel sync, localStorage persistence) |
| **AppAuth** | `app-auth.js` | Auth state derived from httponly cookie, role detection |
| **config** | `config.js` | API base URL, endpoints, app settings |
| **csrf** | `csrf.js` | CSRF token management, `X-CSRF-Token` header on mutations |
| **constants** | `constants.js` | App-wide constants |
| **security** | `security.js` | DOMPurify-based XSS sanitization, HTML escaping |
| **xss-protection** | `xss-protection.js` | Fallback shim for `sanitizeHTML`/`escapeHTML` |
| **components** | `components.js` | **2496 lines** — UI component system (sidebar, header, modals, tables, stats, pagination, kanban cards, badges, avatars, progress bars, slide panels, wizards, empty states) |
| **toast** | `toast.js` | Toast notification system |
| **error-boundary** | `error-boundary.js` | Global error handling |
| **translations** | `translations.js` | i18n engine, auto-loads en/fr/ar |
| **localization** | `localization.js` | RTL switching, date/number formatting |
| **performance** | `performance.js` | Performance monitoring, lazy loading |
| **load-assets** | `load-assets.js` | Dynamic asset loading |
| **auth-guard** | `auth-guard.js` | Role-based page access control |
| **auth-token** | `auth-token.js` | Legacy auth token (backward compat) |

### 6.3 Components System (`components.js`)

The main UI rendering engine providing:

```js
// XSS-safe HTML rendering
Components.safeHTML(str)

// Notifications
Components.showToast(message, type)

// Layout
Components.init(activePage)  // → renders sidebar + header + injects styles
Components.renderSidebar(activePage)
Components.renderTopHeader()

// Modals
Components.showModal({ title, content, buttons })
Components.showConfirm({ title, message, onConfirm })

// Data display
Components.renderTable({ columns, data, onRowClick, pagination })
Components.renderStats({ stats })
Components.renderFilters({ filters })
Components.renderPagination({ current, total, onChange })

// Advanced
Components.showSlidePanel({ content, direction })
Components.showWizard({ steps, onComplete })
Components.renderKanbanCard({ item })
Components.renderBadge({ text, variant })
Components.renderAvatar({ src, name, size })
Components.renderProgressBar({ value, max, variant })
```

### 6.4 Page Script Pattern

```html
<script>
document.addEventListener('DOMContentLoaded', () => {
    Components.init('dashboard');
    loadDashboardData();
});

async function loadDashboardData() {
    try {
        const data = await fetchAPI('/api/v1/candidate/dashboard');
        renderStats(data.stats);
        renderCharts(data.charts);
    } catch (e) {
        Components.showToast('Failed to load dashboard', 'error');
    }
}
</script>
```

### 6.5 API Communication

```js
// Global fetchAPI wrapper (in config.js)
window.fetchAPI(url, options = {})  // auto CSRF, caching, retry, 401 redirect
```

---

## 7. Common UI Components & Patterns

### 7.1 Glass Card
```html
<div class="glass-card p-6 rounded-[2rem]">
    <div class="stat-icon">...</div>
    <div class="text-4xl font-black">123</div>
    <div class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Label</div>
</div>
```

### 7.2 Stage Pill
```html
<span class="stage-pill bg-amber-100 text-amber-700">
    <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
    In Review
</span>
```

### 7.3 Filter Bar
```html
<div class="glass-panel p-4 rounded-2xl flex gap-4 items-center">
    <select class="glass-select">...</select>
    <input class="glass-input" placeholder="Search...">
    <button class="glass-btn-primary">Apply</button>
</div>
```

### 7.4 Stat Card (Admin)
```html
<div class="glass-panel p-6 rounded-[2rem] border-0 shadow-xl shadow-indigo-100/20 group">
    <div class="flex items-center justify-between mb-6">
        <div class="stat-icon bg-indigo-50 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors duration-500">
            <i class="fas fa-users"></i>
        </div>
        <span class="text-[10px] font-black bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-lg">+12%</span>
    </div>
    <div class="text-4xl font-black text-slate-900">1,234</div>
    <div class="text-[10px] font-black text-slate-400 uppercase tracking-widest mt-1">Managed Users</div>
</div>
```

### 7.5 Status Badge
```html
<span class="cw-pill bg-emerald-50 text-emerald-700 border border-emerald-200">
    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
    Active
</span>
```

### 7.6 Skeleton Loader
```css
.skeleton {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 8px;
}
@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
```

### 7.7 Kanban Card
```html
<div class="kanban-card glass-panel p-4 rounded-xl cursor-grab">
    <div class="flex items-center gap-3 mb-3">
        <img class="w-8 h-8 rounded-full" src="avatar.jpg">
        <div>
            <div class="font-semibold text-sm">Candidate Name</div>
            <div class="text-xs text-slate-400">Software Engineer</div>
        </div>
    </div>
    <div class="flex gap-2">
        <span class="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full">Python</span>
        <span class="bg-violet-100 text-violet-700 text-xs px-2 py-0.5 rounded-full">React</span>
    </div>
    <div class="mt-3 flex justify-between items-center">
        <span class="text-xs font-bold text-emerald-600">Score: 92%</span>
        <i class="fas fa-grip-vertical text-slate-300"></i>
    </div>
</div>
```

### 7.8 Modal
```js
Components.showModal({
    title: 'Confirm Action',
    content: 'Are you sure you want to proceed?',
    buttons: [
        { text: 'Cancel', class: 'glass-btn-secondary', dismiss: true },
        { text: 'Confirm', class: 'glass-btn-primary', action: () => doAction() }
    ]
});
```

### 7.9 User Avatar
```html
<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm">
    JD
</div>
```

### 7.10 Loading Spinner
```html
<div class="flex justify-center py-12">
    <div class="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
</div>
```

---

## 8. RTL & Dark Mode

### 8.1 RTL (Right-to-Left) Support

- **Activation:** `[dir="rtl"]` or `html.rtl-mode` class
- Arabic translation file: `js/lang/ar.js`
- Comprehensive RTL overrides in `custom.css` (lines 1028–1154) and `recruiter-glass.css`
- Flipped elements: sidebar position, nav link hover transforms, light-sweep animations, chat bubble corners, table text alignment, stat trends, button groups, margin/padding flips

### 8.2 Dark Mode

- **Activation:** `[data-theme="dark"]` on `<html>` element
- Override blocks in candidate and recruiter pages:
```css
[data-theme="dark"] {
    --surface: #0F172A;
    --text-primary: #F1F5F9;
    --text-secondary: #94A3B8;
    --border-light: #1E293B;
    --glass-bg: rgba(15, 23, 42, 0.85);
    --glass-border: rgba(51, 65, 85, 0.25);
}
```
- `custom.css` has `.dark-mode .premium-glass` override
- Dark mode is page-specific (each page defines its own dark variables)

---

## 9. Internationalization

### 9.1 Translation Files

| File | Keys | Language |
|------|------|----------|
| `js/lang/en.js` | 4600+ | English (default) |
| `js/lang/fr.js` | 4600+ | French |
| `js/lang/ar.js` | 4600+ | Arabic (RTL) |

### 9.2 Usage

```html
<!-- In HTML: -->
<h1 data-i18n="candidate.dashboard.title">Dashboard</h1>

<!-- In JS: -->
const text = window.t('candidate.dashboard.title');
```

### 9.3 Auto-loading

Translations auto-load based on user preference (localStorage `lang` key) via `translations.js`. Arabic also triggers RTL mode via `localization.js`.
