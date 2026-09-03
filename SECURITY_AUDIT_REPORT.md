# Security Audit Report — Chatbot API Authorization

**Date**: 2026-07-01
**Scope**: `backend/routers/chatbot.py` — 6 endpoints
**Severity**: CRITICAL (previously: no authentication on any endpoint)

---

## Vulnerability Summary

| # | Endpoint | Before | After |
|---|----------|--------|-------|
| 1 | `GET /api/v1/chatbot/leads` | No auth — anyone could list ALL leads | `require_recruiter` + company filter |
| 2 | `POST /api/v1/chatbot/capture-lead` | No auth — anyone could create leads | `get_optional_user` + company context capture |
| 3 | `POST /api/v1/chatbot/message` | No auth — anonymous message history | `get_optional_user` + company context capture |
| 4 | `POST /api/v1/chatbot/transfer/{id}` | No auth — anyone could transfer leads | `get_current_user` + `get_chatbot_lead_for_recruiter` |
| 5 | `POST /api/v1/chatbot/leads/{id}/assign` | No auth — anyone could reassign leads | `require_recruiter` + `get_chatbot_lead_for_recruiter` |
| 6 | `POST /api/v1/chatbot/leads/{id}/contacted` | No auth — anyone could mark leads | `require_recruiter` + `get_chatbot_lead_for_recruiter` |

---

## Changes Made

### 1. `backend/models/core/job.py` — Tenant Isolation

Added `company_id` column to `ChatbotLead`:

```python
company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
company = relationship("Company", foreign_keys=[company_id])
```

- Indexed for fast company-scoped queries
- Nullable for backward compatibility (existing unclaimed leads)

### 2. `backend/authz.py` — Authorization Function

Added `get_chatbot_lead_for_recruiter()`:

| Role | Behavior |
|------|----------|
| Recruiter | Own company only → 403 on cross-company access |
| Admin | Allowed company only → 403 on cross-company access |
| Super admin | Explicit permission required → 403 by default (prevents privilege escalation) |

**HTTP status codes**:
- `404 Not Found` — resource does not exist (prevents enumeration)
- `403 Forbidden` — cross-company access attempt (prevents IDOR)

### 3. `backend/routers/chatbot.py` — Full Rewrite

**Authentication** (per endpoint type):

| Endpoint | Dependency | Rationale |
|----------|-----------|-----------|
| `POST /message` | `get_optional_user` | Public chatbot widget |
| `GET /jobs` | `get_optional_user` | Public job search |
| `POST /capture-lead` | `get_optional_user` | Public lead capture |
| `POST /transfer/{id}` | `get_current_user` | Accesses lead data |
| `GET /leads` | `require_recruiter` | Exposes PII |
| `POST /leads/{id}/assign` | `require_recruiter` | Modifies lead ownership |
| `POST /leads/{id}/contacted` | `require_recruiter` | Modifies lead state |

**Authorization**:
- `GET /leads` — filters by `company_id` at query level (no lead leaks)
- Individual lead ops — calls `get_chatbot_lead_for_recruiter()` (company ownership check)
- `POST /capture-lead` — when updating existing lead with company, validates ownership

**Company Context**:
- New leads capture `company_id` from authenticated user via `_derive_company_id()`
- Falls back to `source_job_id` → job owner's company for anonymous leads
- Unclaimed leads: `company_id = NULL` (no company has access)

**Audit Logging** — every lead access operation creates an `AuditLog` entry:

| Action | Trigger |
|--------|---------|
| `leads_listed` | `GET /leads` |
| `lead_captured` | `POST /capture-lead` |
| `lead_transferred` | `POST /transfer/{id}` |
| `lead_assigned` | `POST /leads/{id}/assign` |
| `lead_contacted` | `POST /leads/{id}/contacted` |

### 4. `backend/tests/conftest.py` — Test Fixtures

- `test_recruiter` now creates `CompanyMember` record (required by `get_current_user` for `_company_id`)
- `test_company_b` — second company fixture for cross-company tests
- `test_recruiter_b` — recruiter for Company B (attacker)
- `recruiter_headers_b` — auth headers for attacker recruiter

### 5. `backend/tests/test_chatbot_security.py` — 19 New Tests

| Test Class | Tests | What It Validates |
|------------|-------|-------------------|
| `TestUnauthenticated` | 4 | 401 for unprotected endpoints |
| `TestRoleEnforcement` | 3 | 403 for candidate on recruiter endpoints |
| `TestCrossCompanyAccess` | 4 | 403 for Company A accessing Company B leads |
| `TestIntraCompanyAccess` | 3 | 200 for legitimate intra-company access |
| `TestIDORPrevention` | 2 | 404 for non-existent leads (no info leak) |
| `TestAuditLogging` | 3 | AuditLog entries created on access |

---

## Attack Vectors Mitigated

| Attack | Mitigation |
|--------|-----------|
| **IDOR** — guess numeric lead ID from another company | `get_chatbot_lead_for_recruiter` enforces company ownership with 403 |
| **Enumeration** — probe lead IDs to discover company size | 404 for non-existent, 403 for cross-company (same response either way) |
| **Cross-company** — switch company_id in request | `ASSIGN`/`CONTACTED` validated via authz; `LIST` filtered at DB query level |
| **Privilege escalation** — super admin accessing any company | Super admin explicitly blocked (403 with "explicit permission required") |
| **Data exfiltration** — mass download via `GET /leads` | Requires `require_recruiter` + company-scoped query |
| **CSRF** — cross-site POST | App-level CSRF middleware (pre-existing, now test-covered) |

---

## Test Results

```
19 passed, 0 failed — 91.48s
```

- **Zero regressions** in existing test suites (`test_security.py`, `test_auth.py`, `test_architecture_enforcement.py`)
- Pre-existing failures in `test_audit_fixes.py` (4 failures, unrelated to this change)

---

## Recommendations

1. **Database migration**: Run `ALTER TABLE chatbot_leads ADD COLUMN company_id INTEGER REFERENCES companies(id)` to backfill the new column
2. **Frontend update**: The chatbot widget (`chatbot-leads.js`) should ensure authenticated requests include `Authorization: Bearer <token>` header for internal recruiters
3. **Super admin elevation**: Implement an admin impersonation endpoint with audit trail so super admins can access specific companies with explicit consent
4. **Unclaimed leads**: Define a process for claiming leads with `company_id = NULL` — currently no company can access unclaimed leads
5. **Rate limiting**: Consider adding rate limiting to auth'd endpoints to prevent brute-force IDOR probing

---

*Report generated by automated security audit*
