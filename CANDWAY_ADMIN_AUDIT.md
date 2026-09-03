# Candway Admin Platform — Full Audit

> **Scope**: Server-side admin API routes (15 files, 30+ endpoints), 19 admin HTML pages (~5,500 LOC), shared admin JS (sidebar, RBAC, CSRF), permissions/RBAC model, admin-specific DB models.
> **Date**: 2026-06-03
> **Method**: Static code review against the on-disk tree at `backend/`, `pages/admin/`, `js/`. Every claim is anchored to `file:line` evidence. Claims labelled **UNVERIFIED** could not be substantiated from code. Optimism is not a feature.
> **Prerequisite reading**: `CANDWAY_DUE_DILIGENCE_AUDIT.md` (main platform audit).

---

## 0. Executive Summary

The admin platform is a **comprehensive, functional back-office** with 15 API modules, 19 served pages, and a 9-permission RBAC model. It handles finance (payments, subscriptions, invoices, plans), content (CMS, courses, jobs, announcements), compliance (KYB verification), system management (settings, prompts, AI sales, technical health), and user administration (CRUD, impersonation, RBAC assignment). This is **unusually thorough** for a startup at this stage — most comparable platforms have a far thinner admin surface.

**The good:**
- CSRF protection is present and correctly wired (middleware + JS helper + cookie-to-header extraction)
- Every mutation endpoint has a granular permission check (no endpoint is unprotected)
- Audit logging covers all sensitive actions (impersonation, payment approval, deletions)
- Sensitive operations (impersonation, soft-delete) are rate-limited
- Idempotency-Key support for payment/subscription approve/reject (P0-05 fix)
- Soft-delete for user records (not hard-delete)
- Redis-backed caching on dashboard stats (2-min TTL)
- All mutation endpoints require `X-CSRF-Token` header extracted from httponly cookie — no JWT-in-localStorage anti-pattern

**The critical gaps:**
1. **Client-side RBAC hiding is a stub** — `window.applyRBACUI()` is called at `js/admin-components.js:135` but **never defined anywhere in the codebase**. Sidebar nav links all have `data-permission` attributes, but no JavaScript enforces visibility. Low-permission admins see links to features they cannot access (they get a 403 when they click, but the UX is broken).
2. **`manage_marketing` permission cannot be assigned** — `backend/routers/admin/marketing.py:37` (for bulk email sending) checks for `"manage_marketing"`, but this string is absent from `ALLOWED_PERMISSIONS` in `backend/routers/admin/users.py:247-257`. The only way to assign it is to set `is_super_admin=true`, which grants every permission — defeating least-privilege.
3. **75 `innerHTML` assignments across 18 pages** — with DOMPurify missing in 3 of them. This is the single largest XSS surface in the application.
4. **121 inline event handlers** (`onclick`, `onmouseover`, `onchange`, etc.) across all 19 pages — Content Security Policy cannot be meaningfully enforced.
5. **4 pages with zero i18n** — `prompt-management.html`, `ai_sales.html`, `categories.html`, `courses.html` have no `data-i18n` attributes. Arabic/FR users see English-only labels on those pages.

### 0.1 Admin platform scores (0–100)

| Dimension | Score | Verdict |
|---|---|---|
| **Backend completeness** | 85 | All expected admin functions present; no missing CRUD for core entities |
| **Backend security** | 72 | Good CSRF, reasonable RBAC, audit logging; `manage_marketing` gap and no RBAC middleware |
| **Frontend security** | 35 | 75 innerHTML, 121 inline handlers, 3 pages sans DOMPurify — dangerously high XSS surface |
| **UX & consistency** | 45 | Mixed patterns, 4 pages untranslated, stub RBAC hiding, no loading/error states |
| **Internationalisation** | 50 | 15/19 pages have `data-i18n`; 4 have none; Arabic/FR incomplete |
| **Maintainability** | 40 | Inline JS in every HTML file, no SPA, no component framework, duplication of patterns |
| **RBAC model** | 55 | Flat CSV, no hierarchy, no middleware, `manage_marketing` unassignable, `manage_settings` dead |
| **Overall Admin** | **52** | Functional but fragile. The backend is solid; the frontend is the risk. |

> A <60 score is "needs work before onboarding enterprise admins". A 65+ is "reasonably mature for a startup".

---

## 1. Architecture Overview

```
Browser                                    Backend (FastAPI)
│                                          │
├─ /admin/dashboard  ── SSR HTML ────────► GET /admin/dashboard       pages.py:511
├─ /admin/users      ── SSR HTML ────────► GET /admin/users           pages.py:525
├─ ... (19 pages)                                                      pages.py:500-665
│                                          │
│  (each page loads JS inline)             │
│  ├─ /js/config.js            fetchAPI    │
│  ├─ /js/admin-components.js  sidebar     │
│  ├─ /js/csrf.js              CSRF helper │
│  └─ /js/translations.js      i18n        │
│                                          │
├─ fetchAPI(/api/v1/admin/...) ── JSON ──► │
│    │   │   │   │                        │
│    │   │   │   │                        ├─ admin.router (prefix=/admin)
│    │   │   │   │                        │   ├─ analytics.py  (6 GET + 1 POST)
│    │   │   │   │                        │   ├─ users.py      (7 endpoints)
│    │   │   │   │                        │   ├─ payments.py   (5 endpoints)
│    │   │   │   │                        │   ├─ subscriptions.py (6 endpoints)
│    │   │   │   │                        │   ├─ ... (11 more sub-routers)
│    │   │   │   │                        │   └─ system.py    (7 endpoints)
│    │   │   │   │                        │
│    │   │   │   │                        └─ Each route:
│    │   │   │   │                           Depends(get_current_user)
│    │   │   │   │                           └─ check_permission(current_user, "<perm>")
│    │   │   │   │                              ├─ check_admin()          → 403 if role≠"admin"
│    │   │   │   │                              ├─ is_super_admin?        → bypass
│    │   │   │   │                              └─ CSV permission match   → 403 if missing
│    │   │   │   │
│    │   │   │   └─ CSRFMiddleware validates X-CSRF-Token header
│    │   │   │      against Redis-stored single-use HMAC token
│    │   │   │      (backend/security.py:158-300)
│    │   │   │
│    │   │   └─ fetchAPI auto-attaches X-CSRF-Token from httponly cookie
│    │   │      (js/config.js:57-63 + js/csrf.js:49-65)
│    │   │
│    │   └─ HTTP-only cookie carries JWT (no localStorage token)
│    │
│    └─ Authorization: Bearer <token> in localStorage (legacy fallback)
│       Only used for a few direct fetch() calls that bypass fetchAPI
```

---

## 2. Server-Side Findings

### 2.1 Backend completeness ✅ (Score: 85)

All 15 admin sub-routers are mounted in `backend/routers/admin/__init__.py` and activated via `app.include_router()` at `backend/app.py:282,326`. Coverage:

| Domain | Endpoints | Permission |
|---|---|---|
| Analytics | 6 GET + 1 POST | `view_analytics` |
| CMS | 8 endpoints | `manage_content` |
| Courses | 4 endpoints | `manage_content` |
| Invoices | 5 endpoints + internal helper | `manage_finance` |
| Jobs | 3 endpoints | `manage_content` |
| Marketing | 5 endpoints | `view_analytics` / `manage_marketing` / `manage_finance` |
| Payments | 5 endpoints | `manage_finance` |
| Plans | 4 endpoints | `manage_finance` |
| Settings | 8 endpoints | `manage_admins` + super_admin for write |
| Subscriptions | 6 endpoints | `manage_finance` |
| System | 7 endpoints | admin-only + `view_logs` |
| Tickets | 5 endpoints | `manage_admins` / `view_users` |
| Users | 7 endpoints | `view_users` / `edit_users` / `delete_users` / `manage_finance` / `manage_admins` |
| Verifications | 4 endpoints | `manage_admins` / `manage_content` |

**Verdict**: No obvious missing CRUD endpoints. The module boundaries are well-chosen.

---

### 2.2 Backend security (Score: 72)

**What's good:**
- CSRFMiddleware is active for all mutation endpoints (`backend/security.py:158-300`). Token is HMAC-signed, single-use (Redis-backed replay protection), extracted from httponly cookie.
- Every mutation endpoint calls `check_permission()` before acting.
- Audit logging on all sensitive actions via `AuditLog` model (`backend/database.py:284`).
- Impersonation rate-limited to 5/hr per admin (`backend/routers/admin/users.py:84-130`).
- Soft-delete rate-limited to 10/hr per admin (`backend/routers/admin/users.py:140-175`).
- Payment/subscription approve/reject are idempotent (`Idempotency-Key` header) with `SELECT FOR UPDATE` row locking.
- Verified-email gate on admin page routes via `get_current_admin` dependency.

**What's wrong:**

| # | Finding | File:Line | Severity | Detail |
|---|---|---|---|---|
| H-01 | **`manage_marketing` cannot be assigned** | `users.py:247-257`, `marketing.py:37` | **Critical** | `marketing.py:37` calls `check_permission(current_user, "manage_marketing")` but `ALLOWED_PERMISSIONS` in `users.py:247` doesn't include `"manage_marketing"`. The `PUT /users/{id}/permissions` endpoint at `users.py:262` validates against `ALLOWED_PERMISSIONS` and would reject any attempt to set this permission. A non-super-admin admin can NEVER be granted the right to send bulk email. This forces a binary choice: either give them `is_super_admin=true` (grants all permissions) or not at all. |
| H-02 | **No RBAC middleware — manual checks only** | All admin route files | **High** | Every route handler must independently call `check_permission()`. There is no permission-checking decorator and no middleware that enforces permissions based on the request path. A route added in a future refactor could easily omit the check. |  
| H-03 | **Some system routes lack granular permissions** | `system.py:20,87,96` | **High** | `GET /drift-summary`, `GET /drift-history`, and `GET /experiments` use `Depends(get_current_admin)` (which checks `role == "admin"` only) — no granular permission check. Any admin can access drift analysis and experiment configs regardless of their assigned permissions. |
| H-04 | **Settings POST uses hard `is_super_admin` check** | `settings.py:25` | **Medium** | `POST /settings` gates on `if not current_user.is_super_admin: raise HTTPException(403)`. This is inconsistent with the rest of the codebase which uses `check_permission()`. If `manage_settings` was ever meant to control settings write, this check bypasses it. |
| H-05 | **No IP allow-listing for admin endpoints** | N/A | **Low (env-specific)** | Any authenticated admin can access admin routes from any IP. For high-security deployments (SOC 2, PCI), admin UI should be restrictable to a VPN or allow-listed CIDR. |

---

### 2.3 RBAC / Permissions model (Score: 55)

**Current model:**
```
User
├── role: str = "admin"          # The only role with admin access
├── is_super_admin: bool         # Bypasses all permission checks
└── admin_permissions: Text      # CSV: "view_users,manage_finance,manage_content,..."
```

**Defined permissions (users.py:247-257):**
```
view_users, edit_users, delete_users,
view_analytics, manage_content, manage_finance,
view_logs, manage_admins, manage_settings
```

**Super-admin-only subset (users.py:259):**
```
manage_admins, manage_settings, manage_finance
```

| # | Finding | File:Line | Severity | Detail |
|---|---|---|---|---|
| R-01 | **Flat CSV model — no role hierarchy** | `database.py:210-216` | **Medium** | Permissions are stored as a comma-separated string on the `User` model. There is no `Role` table, no `Permission` table, no hierarchical role (e.g., "super-admin > admin > support > read-only"). Adding a new permission requires: (1) add it to Python `ALLOWED_PERMISSIONS`, (2) add it to route handlers, (3) ensure the CSV is comma-separated correctly. |
| R-02 | **`manage_settings` is defined but unused** | `users.py:254` | **Low** | `manage_settings` is in both `ALLOWED_PERMISSIONS` and `SUPER_ADMIN_ONLY` but is never checked by any route handler. Settings POST uses hard `is_super_admin` check (see H-04). Settings GET uses `manage_admins`. This is dead weight. |
| R-03 | **No audit trail for permission changes** | `users.py:262-280` | **Medium** | `PUT /users/{id}/permissions` updates the CSV string but does NOT create an `AuditLog` entry. There is no record of who granted/revoked which permission to whom, or when. |
| R-04 | **Permission CSV is case-sensitive** | `common.py:64-78` | **Low** | `check_permission()` does `required_perm not in perms` (no `.lower()` normalization). `"Manage_Content"` would be rejected. |
| R-05 | **`applyRBACUI` is never defined** | `admin-components.js:135` | **Critical** | The sidebar renders `data-permission` attributes on every nav link and calls `window.applyRBACUI()` after injection — but this function is **never defined anywhere in the codebase**. Low-permission admins see ALL sidebar links, including ones they don't have access to. They get a 403 when they click, but the UX is broken and confusing. See F-01 for full detail. |

---

### 2.4 Audit logging (Score: 80)

**What's logged:**
`AuditLog` captures: `impersonate`, `delete_user`, `change_settings`, `approve_course`, `reject_course`, `approve_payment`, `reject_payment`, `approve_subscription`, `reject_subscription`, `create_plan`, `update_plan`, `delete_plan`, `approve_verification`, `reject_verification`, `create_category`, `EMAIL_SENT`, `EMAIL_FAILED`, `SYSTEM_ERROR`

**What's NOT logged:**
- `PUT /users/{id}/permissions` — permission changes (R-03)
- `POST /admin/login-admin` — admin login attempts (separate from regular auth login logging)
- Coupon create/delete (`marketing.py`)
- Bulk email send (`marketing.py`)
- Job deletion (`jobs.py`)

---

## 3. Frontend Findings

### 3.1 Page inventory

19 admin HTML pages, all served via SSR routes in `pages.py:500-665`. Every page uses the same skeleton:

```html
<!-- ADMIN GUARD BYPASSED -->       (now clean after 2026-06-03 fix)
<meta robots="noindex">
<link tailwind-landing.css, font-awesome, custom.css, aos>
<script src="/js/config.js">
<script src="/js/admin-components.js">
<!-- ... page-specific JS inline in <script> blocks ... -->
<script src="/js/csrf.js">
```

The sidebar is injected dynamically by `admin-components.js:renderAdminSidebar()` into `<div id="admin-sidebar-container">`.

---

### 3.2 Critical frontend findings

| # | Finding | File:Line | Severity | Detail |
|---|---|---|---|---|
| F-01 | **`applyRBACUI` — client-side RBAC is a stub** | `admin-components.js:135-136` | **Critical** | After injecting the sidebar nav, the code calls `if (window.applyRBACUI) { window.applyRBACUI(); }`. `applyRBACUI` is NEVER defined anywhere in any file in the codebase. All nav links have `data-permission` attributes (e.g., `data-permission="manage_finance"`), but no JS reads them to hide links. An admin with only `view_users` permission sees ALL sidebar links — Settings, AI Sales, Payments, etc. — and gets a 403 when clicking on unauthorised ones. The `if (window.applyRBACUI)` guard prevents a crash, but the feature is functionally dead. |
| F-02 | **75 `innerHTML` usages — XSS surface** | 18/19 pages | **Critical** | All admin pages dynamically build table rows and cards by concatenating strings into `element.innerHTML = ...`. Values from the API (user names, job titles, course names, etc.) are interpolated directly into HTML. 15 pages include DOMPurify and use `DOMPurify.sanitize(...)`. **3 pages do NOT include DOMPurify at all:** `dashboard.html`, `prompt-management.html`, `recruiter-usage.html`. These pages also use innerHTML to render API data. If any API response contains malicious HTML (e.g., a user with `email=<img onerror=alert(1)>`), the XSS fires. |
| F-03 | **121 inline event handlers — CSP cannot be enforced** | All 19 pages | **High** | Every admin page uses `onclick="..."`, `onmouseover="..."`, `onchange="..."`, `onsubmit="..."` inline handlers. This is the natural pattern for PHP-style server-rendered pages, but it means: (a) CSP with `script-src 'strict-dynamic'` cannot be applied without breaking every button, (b) event handler code cannot be minified or tree-shaken, (c) any XSS can trivially execute arbitrary JavaScript without bypassing CSP `unsafe-inline` restrictions. |
| F-04 | **4 pages with zero i18n coverage** | All pages | **High** | `prompt-management.html`, `ai_sales.html`, `categories.html`, `courses.html` have zero `data-i18n` attributes. `technical.html` has exactly one (the page title). When the language switcher is set to FR or AR, these pages display English-only labels and titles. |

---

### 3.3 Medium-severity frontend findings

| # | Finding | File:Line | Severity | Detail |
|---|---|---|---|---|
| M-01 | **DOMPurify included inconsistently** | 15/19 pages | **Medium** | 3 pages missing: `dashboard.html` (renders activity feed + backup UI), `prompt-management.html` (renders AI prompts + test results), `recruiter-usage.html` (renders usage stats). The other 16 pages include `purify.min.js` and mostly use `DOMPurify.sanitize(...)`, but a spot-check of `verifications.html:147,159` and `users.html:146,150,198` shows that innerHTML values are NOT consistently passed through `DOMPurify.sanitize()` — some are, some aren't. A systematic audit of all 75 innerHTML uses is needed. |
| M-02 | **Hardcoded dev URLs in settings.html** | `settings.html:80,190` | **Medium** | Line 80: `http://localhost:8002/auth/linkedin/callback` — LinkedIn OAuth redirect URL hardcoded. Line 190: `http://127.0.0.1:11434` — Ollama local LLM endpoint. These will not work in production deployments. |
| M-03 | **Inconsistent redundant `is_super_admin` checks** | `pages.py:511-528` vs `pages.py:555-662` | **Low** | Older admin page routes (`/admin/dashboard`, `/admin/jobs`, `/admin/users`) have a redundant check: `if user.role != "admin" and not getattr(user, "is_super_admin", False): raise 403`. Newer routes (`/admin/payments`, `/admin/ai-sales`, `/admin/analytics`, etc.) do NOT have this check — they rely solely on `get_current_admin`. This creates an inconsistent behaviour: a user with `is_super_admin=true` but `role!="admin"` (a theoretical edge case) could access old pages but not new ones. |
| M-04 | **No loading/error states** | All pages | **Medium** | Every admin page's JS follows the pattern `try { data = await fetchAPI(...); renderTable(data); } catch (e) { Toast.show("...", "error"); }`. There are no skeleton loaders, no retry buttons, no inline error messages, and no "retry after N seconds" fallback. On network failure, the page shows a blank table with a brief toast. |
| M-05 | **`data-permission` only on sidebar, not on page content** | `admin-components.js:79` | **Medium** | Even if `applyRBACUI` were implemented, it would only hide sidebar nav links. Action buttons on the page (e.g., "Approve Payment", "Delete User") are hardcoded in each page's HTML with no `data-permission` attribute. A user who navigates to a page they shouldn't be on would see the full UI, then get a 403 when clicking an action. |
| M-06 | **No SRI hashes on CDN resources** | All pages | **Medium** | All 5 CDN scripts/stylesheets (Font Awesome 6.4.0, Chart.js 4.4.1, Quill 1.3.6, DOMPurify 3.0.8, AOS 2.3.1) are loaded without `integrity=...` attributes. A compromised CDN could serve malicious JavaScript to every admin session. |

### 3.4 Minor findings

| # | Finding | File:Line | Severity | Detail |
|---|---|---|---|---|
| L-01 | **`settings.html` missing `</script>` on csrf.js include** | `settings.html:344` | **Low** | `<script src="/js/csrf.js">` is missing `</script>`. The browser may implicitly close it, but this is malformed HTML. |
| L-02 | **`admin-root` redirect is unauthenticated** | `pages.py:503` | **Low** | `GET /admin` redirects to `/login/admin` regardless of whether the user is already authenticated. An admin who visits `/admin` when already logged in gets redirected to login unnecessarily. |
| L-03 | **No pagination on many list endpoints** | Various | **Low** | `GET /jobs`, `GET /blogs`, `GET /opportunities`, `GET /coupons`, `GET /payments`, `GET /subscriptions` return all results at once without pagination. As data grows, these will become slow and memory-heavy. |

---

## 4. Specific Findings by Page

### 4.1 `dashboard.html` (415 lines)
| Finding | Line | Detail |
|---|---|---|
| No DOMPurify | — | The only admin page with `innerHTML` that lacks DOMPurify entirely |
| Hardcoded backup endpoint | 404 | `fetch(\`${window.CONFIG ? window.CONFIG.API_BASE_URL : ''}/api/v1/admin/backup/db\`)` — this endpoint doesn't appear in any admin route file (UNVERIFIED: may exist elsewhere) |
| 4 inline event handlers | 81, 84, 165, 301 | Tab switches, date range |

### 4.2 `analytics.html` (354 lines)
| Finding | Line | Detail |
|---|---|---|
| All innerHTML uses DOMPurify | 353 | Good |
| Chart.js CDN without SRI | 11 | Supply chain risk |
| 2 inline event handlers | 85, 89 | Tab switches |

### 4.3 `users.html` (228 lines)
| Finding | Line | Detail |
|---|---|---|
| innerHTML at 146, 150, 198 | 146, 150, 198 | User data injected — confirmed NOT passed through DOMPurify |
| 8 inline event handlers | 43, 46, 111, 182, 185, 188, 213 | Impersonate, delete, filter |
| CSRF included | 119 | ✅ |

### 4.4 `settings.html` (347 lines)
| Finding | Line | Detail |
|---|---|---|
| Hardcoded LinkedIn OAuth URL | 80 | `http://localhost:8002` |
| Hardcoded Ollama URL | 190 | `http://127.0.0.1:11434` |
| Missing `</script>` on csrf.js | 344 | `<script src="/js/csrf.js">` not closed |
| 50+ i18n keys | All | Best-covered admin page ✅ |

### 4.5 `prompt-management.html` (232 lines)
| Finding | Line | Detail |
|---|---|---|
| **Zero i18n coverage** | — | No `data-i18n` attributes |
| **No DOMPurify** | — | innerHTML used at 201, 204, 208, 228 without sanitization |
| 13 inline event handlers | 78, 81, 89, 90, 91, 92, 153, 157, 177, 201, 204, 208, 228 | Heavy inline JS |

### 4.6 `ai_sales.html` (317 lines)
| Finding | Line | Detail |
|---|---|---|
| **Zero i18n coverage** | — | No `data-i18n` attributes |
| 11 inline event handlers | 47, 98, 103, 145, 151, 155, 159, 163, 175, 243 | Heavy inline JS |

### 4.7 `categories.html` (201 lines)
| Finding | Line | Detail |
|---|---|---|
| **Zero i18n coverage** | — | No `data-i18n` attributes |
| DOMPurify present | 112 | ✅ |
| 0 inline event handlers | — | Best-behaved page for event handling ✅ |

### 4.8 `courses.html` (263 lines)
| Finding | Line | Detail |
|---|---|---|
| **Zero i18n coverage** | — | No `data-i18n` attributes |
| DOMPurify present | 135 | ✅ |
| 6 inline event handlers | 52, 56, 57, 58, 81, 85, 90, 183, 184 | |

### 4.9 `recruiter-usage.html` (222 lines)
| Finding | Line | Detail |
|---|---|---|
| **No DOMPurify** | — | innerHTML at 132 without sanitization |
| 5 inline event handlers | 41, 79, 105, 183 | |
| No guard comment | — | `ADMIN GUARD` instead of `ADMIN GUARD BYPASSED` |

---

## 5. JS Files Analysis

### 5.1 `js/config.js` (145 lines)
- Defines `window.fetchAPI()` — the canonical API helper used across all pages
- Automatically attaches `X-CSRF-Token` from cookie for state-changing requests (line 58-63)
- Implements retry, timeout, in-memory GET caching (30s TTL)
- Auth via httponly cookie (`credentials: 'same-origin'`) — no localStorage JWT
- Falls back to `http://127.0.0.1:8001` when `protocol === 'file:'` (line 5) — this is for local dev
- ✅ Well-designed, no security issues

### 5.2 `js/admin-components.js` (156 lines)
- Renders fixed 280px sidebar with 7 nav groups and 19 links
- Injects `data-permission` attributes on nav links (line 79)
- **Calls `window.applyRBACUI()` which is never defined (line 135)** — see F-01
- Language switcher (EN/FR) stores preference in localStorage (line 112)
- Logout clears localStorage and redirects (line 140-143) — does NOT clear the httponly auth cookie
- Uses inline `onclick`/`onmouseover` handlers in template (lines 127-130) — CSP issue

### 5.3 `js/csrf.js` (90 lines)
- `getCSRFToken()` — reads `csrf_token` cookie or meta tag (line 7-26)
- Enhances `fetchAPI` to attach `X-CSRF-Token` for POST/PUT/DELETE (lines 49-65)
- Enhances native `fetch` similarly (lines 69-85)
- Injects hidden `csrf_token` input into all `<form>` elements (lines 29-46)
- ✅ Well-designed. The only concern: `csrf.js` wraps `fetchAPI` only if `window.fetchAPI` is already defined. Script loading order matters — `csrf.js` must be loaded AFTER `config.js`. All admin pages load `config.js` first, so this is correct.

---

## 6. CSRF Protection Analysis

The CSRF chain is **correctly implemented**:

| Step | Component | File:Line |
|---|---|---|
| 1. Token generation | `_set_csrf_cookie()` on login | `auth.py:289-299` |
| 2. Token validation | `CSRFMiddleware.dispatch()` | `security.py:158-300` |
| 3. Token transport | httponly cookie `csrf_token` + `X-CSRF-Token` header | HTTP |
| 4. Replay protection | Redis `setex csrf_used:{hash} 86400 1` | `security.py:211` |
| 5. Client-side injection | `config.js:57-63` + `csrf.js:49-65` | JS |

**Finding**: The `CSRFMiddleware` uses `request.method in {"POST", "PUT", "DELETE", "PATCH"}` (line 276). It skips `GET`, `HEAD`, `OPTIONS` — correct.

**One concern**: The middleware also checks for `multipart/form-data` content type and tries `form_data.get("csrf_token")` (line 281). None of the admin pages use form-based CSRF submission (they all use `fetchAPI` with `X-CSRF-Token` header), so this path is dead code in admin context. It doesn't hurt, but it's unnecessary complexity.

---

## 7. API Endpoint — Permission Matrix

```
ENDPOINT                                    PERMISSION              FILE:LINE
─────────────────────────────────────────────────────────────────────────────────
GET    /admin/stats                         view_analytics          analytics.py:29
GET    /admin/activity                      view_analytics          analytics.py:42
GET    /admin/analytics/overview            view_analytics          analytics.py:52
GET    /admin/analytics/growth              view_analytics          analytics.py:83
GET    /admin/analytics/revenue             view_analytics          analytics.py:103
GET    /admin/analytics/ai                  view_analytics          analytics.py:124
GET    /admin/analytics/efficiency          view_analytics          analytics.py:138
POST   /admin/analytics/daily-report/refresh  view_analytics        analytics.py:152
POST   /admin/blogs                         manage_content          cms.py:39
DELETE /admin/blogs/{post_id}               manage_content          cms.py:77
GET    /admin/blogs                         manage_content          cms.py:121
POST   /admin/opportunities                 manage_content          cms.py:148
DELETE /admin/opportunities/{opp_id}        manage_content          (likely cms)
GET    /admin/opportunities                 manage_content          (likely cms)
GET    /admin/pages/{page_slug}             manage_content          cms.py
POST   /admin/pages/{page_slug}/{section}   manage_content          cms.py
GET    /admin/courses                       manage_content          courses.py:22
POST   /admin/courses/{id}/approve          manage_content          courses.py:50
POST   /admin/courses/{id}/reject           manage_content          courses.py:80
POST   /admin/courses/external              manage_content          courses.py:100
POST   /admin/invoices/generate             manage_finance          invoices.py:111
GET    /admin/invoices                      manage_finance          invoices.py:176
GET    /admin/invoices/{id}/download        manage_finance          invoices.py:187
GET    /admin/invoices/{id}/xml             manage_finance          invoices.py:237
PUT    /admin/invoices/{id}                 manage_finance          invoices.py:274
GET    /admin/jobs                          manage_content          jobs.py:22
DELETE /admin/jobs/{job_id}                 manage_content          jobs.py:60
POST   /admin/categories                    manage_content          jobs.py:76
GET    /admin/marketing/leads               view_analytics          marketing.py:20
POST   /admin/marketing/send                manage_marketing        marketing.py:37
GET    /admin/coupons                       manage_finance          marketing.py:51
POST   /admin/coupons                       manage_finance          marketing.py:61
DELETE /admin/coupons/{coupon_id}           manage_finance          marketing.py:81
GET    /admin/payments                      manage_finance          payments.py:20
POST   /admin/payments/{id}/approve         manage_finance          payments.py:56
POST   /admin/payments/{id}/reject          manage_finance          payments.py:139
GET    /admin/payouts                       manage_finance          payments.py:190
POST   /admin/payouts/{id}/pay              manage_finance          payments.py:203
GET    /admin/plans                         manage_finance          plans.py:26
POST   /admin/plans                         manage_finance          plans.py:48
PUT    /admin/plans/{plan_id}               manage_finance          plans.py:98
DELETE /admin/plans/{plan_id}               manage_finance          plans.py:126
GET    /admin/settings                      manage_admins           settings.py:25
POST   /admin/settings                      super_admin ONLY        settings.py:25
POST   /admin/email/test                    manage_admins           settings.py:195
GET    /admin/ab-testing/config             manage_content          settings.py:235
POST   /admin/ab-testing/config             manage_content          settings.py:274
GET    /admin/ab-testing/stats              view_analytics          settings.py:296
POST   /admin/ab-testing/reset-stats        manage_admins           settings.py:350
GET    /admin/prompts                       manage_content          settings.py:359
POST   /admin/prompts                       manage_content          settings.py:369
GET    /admin/subscriptions                 manage_finance          subscriptions.py:20
POST   /admin/subscriptions/{tx}/approve    manage_finance          subscriptions.py:59
POST   /admin/subscriptions/{tx}/reject     manage_finance          subscriptions.py:181
GET    /admin/subscriptions/active          manage_finance          subscriptions.py:238
POST   /admin/subscriptions/{uid}/cancel    manage_finance          subscriptions.py:260
POST   /admin/subscriptions/{uid}/extend    manage_finance          subscriptions.py:279
GET    /admin/health                        admin-only              system.py:20
GET    /admin/logs                          view_logs               system.py:38
GET    /admin/background-jobs               view_logs               system.py:56
GET    /admin/audit-trail                   view_logs               system.py:84
GET    /admin/drift-summary                 admin-only (no perm!)   system.py:87
GET    /admin/drift-history                 admin-only (no perm!)   system.py:96
GET    /admin/experiments                   admin-only (no perm!)   system.py:105
GET    /admin/tickets                       manage_admins           tickets.py:23
GET    /admin/upgrade-requests              manage_admins           tickets.py:48
POST   /admin/upgrade-requests/{id}/approve manage_admins           tickets.py:77
POST   /admin/upgrade-requests/{id}/reject  manage_admins           tickets.py:125
POST   /admin/tickets/{id}/reply            view_users              tickets.py:147
GET    /admin/users                         view_users              users.py:32
POST   /admin/users/{id}/impersonate        edit_users              users.py:84
DELETE /admin/users/{id}                    delete_users            users.py:140
GET    /admin/users/usage                   manage_finance          users.py:184
POST   /admin/users/{id}/usage              manage_finance          users.py:209
POST   /admin/users/{id}/assign-plan/{pid}  manage_finance          users.py:231
PUT    /admin/users/{id}/permissions        manage_admins           users.py:269
GET    /admin/verifications                 manage_admins           verifications.py:19
POST   /admin/verifications/{id}/approve    manage_admins           verifications.py:33
POST   /admin/verifications/{id}/reject     manage_admins           verifications.py:90
POST   /admin/announcements                 manage_content          verifications.py:137
GET    /admin/announcements/active          (none)                  verifications.py:157
```

---

## 8. Scoring Summary

| Dimension | Score | Why |
|---|---|---|
| Backend completeness | 85 | All CRUD present; admin covers every platform domain |
| Backend security | 72 | CSRF good, RBAC reasonable, but `manage_marketing` gap + no middleware |
| Frontend security | 35 | 75 innerHTML, 121 inline handlers, 3 pages without DOMPurify |
| UX & consistency | 45 | Stub RBAC hiding, no loading states, inconsistent redundant checks |
| Internationalisation | 50 | 15/19 pages translated; 4 have zero i18n (prompts, AI sales, categories, courses) |
| Maintainability | 40 | Inline JS in every page, no component framework, duplication |
| RBAC model | 55 | Flat CSV, no hierarchy, `manage_marketing` unassignable, `applyRBACUI` dead |
| **Overall Admin** | **52** | Functional but fragile. The backend is solid; the frontend is the risk. |

---

## 9. Prioritised Roadmap (Admin-Specific)

### P0 (Immediate — security blocking)
| ID | Finding | Fix |
|---|---|---|
| A-P0-01 | `manage_marketing` not in `ALLOWED_PERMISSIONS` | Add `"manage_marketing"` to `ALLOWED_PERMISSIONS` in `users.py:247` |
| A-P0-02 | 3 pages missing DOMPurify | Add `<script src="...DOMPurify...">` to `dashboard.html`, `prompt-management.html`, `recruiter-usage.html`; wrap all innerHTML assignments |

### P1 (High — security hardening)
| ID | Finding | Fix |
|---|---|---|
| A-P1-01 | `applyRBACUI` never defined | Implement `window.applyRBACUI` JS function that reads user's `admin_permissions` from `/auth/me` and hides sidebar links with mismatched `data-permission` |
| A-P1-02 | 4 pages with zero i18n | Add `data-i18n` attributes to `prompt-management.html`, `ai_sales.html`, `categories.html`, `courses.html` (min 10 keys each) |
| A-P1-03 | No permission-change audit trail | Add `AuditLog` entry in `PUT /users/{id}/permissions` |
| A-P1-04 | Inline event handlers | Move to JS event delegation pattern — remove `onclick`, `onmouseover`, etc. from HTML |

### P2 (Medium — quality)
| ID | Finding | Fix |
|---|---|---|
| A-P2-01 | `manage_settings` dead code | Either wire it to `POST /settings` or remove from `ALLOWED_PERMISSIONS` |
| A-P2-02 | 3 system routes without granular permissions | Add `check_permission(current_user, "view_logs")` to `/drift-summary`, `/drift-history`, `/experiments` |
| A-P2-03 | No pagination on list endpoints | Add `limit`/`offset` parameters to `GET /jobs`, `/blogs`, `/opportunities`, `/coupons`, `/payments`, `/subscriptions` |
| A-P2-04 | Inconsistent `is_super_admin` checks | Remove redundant checks from old page routes; let `get_current_admin` handle it |

### P3 (Low — polish)
| ID | Finding | Fix |
|---|---|---|
| A-P3-01 | No SRI hashes on CDN resources | Add `integrity="..."` attributes to all 5 CDN script/link tags |
| A-P3-02 | Hardcoded dev URLs in settings.html | Move LinkedIn OAuth URL and Ollama URL to server-side settings |
| A-P3-03 | `settings.html` missing `</script>` | Add closing tag |
| A-P3-04 | `/admin` redirect unauthenticated | Check auth status before redirecting; route to dashboard if already authenticated |

---

## 10. Key Files Reference

| File | Lines | What it does |
|---|---|---|
| `backend/routers/admin/__init__.py` | 33 | Mounts all 15 admin sub-routers |
| `backend/routers/admin/common.py` | 78 | `check_permission()`, `SystemSettings` model |
| `backend/routers/admin/users.py` | 305 | User CRUD, impersonation, RBAC assignment, `ALLOWED_PERMISSIONS` |
| `backend/routers/admin/marketing.py` | 86 | Marketing leads, bulk email, coupons |
| `backend/routers/admin/system.py` | 143 | Health, logs, background jobs, drift, experiments |
| `backend/routers/admin/payments.py` | 210 | Payment approve/reject (idempotent) |
| `backend/routers/admin/subscriptions.py` | 295 | Subscription approve/reject/cancel/extend |
| `backend/routers/pages.py:500-665` | 165 | SSR routes for all 19 admin pages |
| `backend/dependencies.py:638-700` | 62 | `check_admin`, `require_admin`, role guards |
| `backend/security.py:158-300` | 142 | `CSRFMiddleware` |
| `js/admin-components.js` | 156 | Dynamic sidebar with RBAC stub |
| `js/config.js` | 145 | `fetchAPI` helper with CSRF, caching, timeout |
| `js/csrf.js` | 90 | CSRF token extraction + `fetch`/`fetchAPI` enhancement |
| `pages/admin/*.html` (19 files) | ~5,500 | Admin HTML pages — all SSR, all inline JS |
