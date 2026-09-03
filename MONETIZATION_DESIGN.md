# Candway Monetization System — Production-Grade Design (Manual Payments Only)

**Date:** 2026-08-01 · **Author:** Lead Architect / SaaS Billing / FinTech · **Supersedes:** `MONETIZATION_AUDIT.md` (audit findings remain valid; this document is the implementation blueprint)

## Design rules (locked for V1)
- **Only payment method: Manual Bank Transfer** → admin verification → manual invoice → manual activation.
- **No Stripe. No Konnect. No webhooks.** All payment lifecycle is human-in-the-loop via the Admin Panel.
- Reuse existing real backend (admin routers, `Transaction`, `Invoice`, `AuditLog`, `SystemConfig`, `FeatureFlag`, `paginate()`) instead of inventing parallel systems.
- The admin frontend (20 static mock pages) is **greenfield** — we wire real UI to the real backend APIs.
- Every new table is `TenantMixin` (company_id) unless global, matching the multi-tenant architecture.

---

# PART 1 — SUBSCRIPTION SYSTEM

## 1.1 Model: the subscription lifecycle core

Add a real `subscriptions` table (today there is **no lifecycle record** — only `RecruiterProfile.tier/subscription_status/subscription_end` and `CandidateProfile.subscription_status`). The new `Subscription` row is the single source of truth; profile columns become cached denormalized mirrors.

```
subscriptions
  id PK
  company_id (TenantMixin, indexed)
  user_id FK users.id
  plan_id FK subscription_plans.id
  target_audience ENUM('candidate','recruiter')          -- derived from plan
  status ENUM('trialing','active','pending','past_due','expired','canceled') DEFAULT 'pending'
  billing_cycle ENUM('monthly','yearly') DEFAULT 'monthly'
  started_at DATETIME
  current_period_start DATETIME
  current_period_end DATETIME                            -- manual expiry driver
  grace_end DATETIME NULL                                -- grace period expiry
  cancel_at_period_end BOOL DEFAULT False                -- soft cancel
  canceled_at DATETIME NULL
  reason_canceled VARCHAR(255) NULL
  last_payment_transaction_id FK transactions.id NULL
  renewal_reminder_sent BOOL DEFAULT False               -- idempotent dunning
  notes TEXT NULL                                        -- admin internal note
  created_at / updated_at
```

**Manual activation flow (no webhooks):**
1. User uploads bank proof → `Transaction(status='pending')` (reuse existing `POST /candidate/upgrade/manual` + `POST /recruiter/subscription/upgrade`).
2. Admin verifies bank receipt in Admin Panel → `POST /admin/subscriptions/{tx_id}/approve` (exists) → now also:
   - `Transaction.status='succeeded'` (exists)
   - `_create_invoice_internal(...)` (exists, auto-generates `INV-YYYY-NNNN` PDF + TEIF XML)
   - **NEW:** create/update `Subscription` row: `status='active'`, `current_period_start=now`, `current_period_end = now + 30/365d` (from `billing_cycle` + plan)
   - **NEW:** write `SubscriptionHistory` entry `(action='activated', actor=admin)`
   - profile mirror update (exists)
3. Grace period: at `current_period_end`, a daily cron flips `active→past_due`, sets `grace_end = end + 3 days`, sends renewal-reminder email, grants **read-only/downgrade** to free plan limits after grace.

## 1.2 Plan upgrades / downgrades / cancel / renewal — all manual, admin-driven

| Operation | Admin action | Effect |
|---|---|---|
| **Upgrade (proactive)** | `POST /admin/subscriptions/{user}/change-plan?plan_id=X` (NEW) | Pro-rate: `current_period_end` unchanged, `SubscriptionHistory(action='upgraded')`, credits for new plan granted pro-rata |
| **Downgrade (reactive, at renewal)** | same endpoint with lower plan | Effective at period end (soft) or immediately (admin "force") |
| **Cancel** | `POST /admin/subscriptions/{user}/cancel` (exists → extend) | `cancel_at_period_end=True` → on cron at period end: `status='canceled'`, `SubscriptionHistory(action='canceled', reason)`, profile→free |
| **Extend / renew** | `POST /admin/subscriptions/{user}/extend` (exists) | extends `current_period_end`, resets `renewal_reminder_sent=False` |
| **Expire** | `POST /admin/subscriptions/{user}/expire` (NEW) | immediate `status='expired'`, profile→free, history entry |
| **Reinstate** | `POST /admin/subscriptions/{user}/reinstate` (NEW) | revive past_due/canceled before period end |
| **Renewal reminder** | daily cron (`scheduler.py`) | at period_end−3d and period_end−1d: `send_subscription_status_email` (exists `email_service.py:287`) |

## 1.3 Plan versions
Add `plan_versions` so price changes don't break active subscribers:
```
plan_versions
  id PK, plan_id FK subscription_plans.id
  version INT
  price_monthly DECIMAL, price_yearly DECIMAL, currency VARCHAR(10)
  credits_monthly INT, job_limit INT, cv_limit INT, ai_interview_limit INT, team_seat_limit INT
  features_json TEXT, permissions_json TEXT
  valid_from DATETIME, valid_to DATETIME NULL
```
`Subscription` stores `plan_version_id` at activation → grandfathering is free. `SubscriptionPlan.price_*` = "current published price"; admin edits always snapshot a new `plan_versions` row.

## 1.4 Subscription history (audit of lifecycle)
```
subscription_history
  id PK, subscription_id FK, company_id, user_id
  action ENUM('created','activated','extended','renewed','upgraded','downgraded','canceled','expired','reinstate','payment_received','trial_started')
  from_plan_id / to_plan_id (nullable)
  amount_paid DECIMAL NULL, transaction_id FK NULL
  admin_user_id FK NULL (null = system cron)
  notes TEXT NULL
  created_at
```
Every lifecycle event = one immutable history row + one `AuditLog` row (existing pattern).

## 1.5 Trial (manual-friendly, admin-activated)
- Reuse existing **inert** `free_trial` SystemConfig flag (`admin/settings.py:56`).
- New: `POST /admin/subscriptions/{user}/start-trial?plan_id=X&days=14` → `Subscription(status='trialing')`, plan applied, `trial` history row. No card, no webhook — admin grants it (or candidate requests via support ticket).
- Cron converts `trialing`→`expired` at `current_period_end`.

---

# PART 2 — AI CREDIT SYSTEM

## 2.1 The wallet + ledger (replace 7 scattered counters)

Replace `RecruiterProfile.usage_jobs/cvs/ai_interviews` + `CandidateProfile.candidate_*_this_month` with a universal credit wallet. Legacy counters stay for read-compat during migration, then retire.

```
credit_wallets
  id PK, company_id, user_id UNIQUE
  balance DECIMAL(18,4) NOT NULL DEFAULT 0
  currency VARCHAR(10) DEFAULT 'CRED'
  version INT NOT NULL DEFAULT 0            -- optimistic locking
  created_at / updated_at

credit_transactions  (the immutable ledger)
  id PK, wallet_id FK, company_id, user_id
  amount DECIMAL(18,4)   -- signed: + grant/purchase/topup/refund, - consume
  type ENUM('grant','purchase','topup','consume','refund','adjustment','promo','expire','rollback')
  resource VARCHAR(64)   -- e.g. 'ai_interview_turn','cv_analysis','ai_search','copilot_turn'
  reference_type VARCHAR(64) / reference_id BIGINT  -- application/session/job id
  actor_type ENUM('user','system','admin','promo') / actor_id
  provider ENUM('manual','promo','admin','system') DEFAULT 'system'
  provider_ref VARCHAR(128)  -- invoice number / promo code
  idempotency_key VARCHAR(128) UNIQUE     -- prevents double-charge on retries
  status ENUM('pending','succeeded','failed','reversed')
  created_at
```
**No webhooks, no provider SDKs:** every credit movement is an internal SQL transaction. `idempotency_key` = e.g. `consume:{resource}:{reference_id}` so a retried HTTP request can't double-debit.

## 2.2 Credit cost matrix (per AI feature)

| Feature | Call site (existing) | Credits/unit | Est. AI cost/unit | Enforcement point |
|---|---|---|---|---|
| AI Interview — question gen | `ai_interview/questions.py:88` | 5 | ~$0.002 | `require_credits` dep on `POST /generate-interview` |
| AI Interview — per turn eval | `ai_interview/chat.py:761` | 1 | ~$0.001 | `require_credits` on chat |
| AI Interview — final eval | `evaluation.py:255,530` | 3 | ~$0.006 | `require_credits` on `evaluate-final` |
| CV analysis (candidate) | `candidate/cv.py:326,463,521` | 3 | ~$0.002 | `require_credits` on `/analyze`, `/cv-review` |
| Resume parse (apply/onboarding) | `applications.py:107`, `onboarding.py:745` | 2 | ~$0.002 | inside `_run_background_analysis` |
| AI candidate search / rerank | `recruiter_candidates/search.py:454` | 2 | ~$0.001 | `require_credits` on `/search/advanced` |
| Copilot chat turn | `copilot.py:42`, `copilot_engine.py:46,155` | 1 | ~$0.002 | `require_credits` on `/hiring/chat` |
| Career roadmap | `career.py:22` | 4 | ~$0.003 | `require_credits` on `/career/plan` |
| JD writer | `recruiter_jobs.py:89` | 2 | ~$0.001 | `require_credits` on `/generate-job` |
| Wizard AI suggestions | `recruiter_job_wizard.py:588–861` | 1 each | ~$0.001 | `require_credits` on 8 suggest endpoints |
| Ghost reports | `scoring.py:1498,1621` | 5 | ~$0.002 | `has_feature('ghost_report')` + credits |
| Re-engagement (per candidate) | `reengagement_engine.py:82` | 1 | ~$0.002 | metered inside loop (hard cap 200) |
| AI sourcing (per candidate) | `sourcing_agent.py:379` | 1 | ~$0.002 | metered inside loop |
| AI invitations | `invitations.py:334` | 1 | ~$0.001 | `require_credits` |
| Score comparison | `scoring.py:922,943` | 1 | ~$0.001 | `require_credits` |
| Debrief summary | `actions.py:292` | 1 | ~$0.001 | `require_credits` |
| Translation | `ai_utils.py:125` | 1 | ~$0.001 | `require_credits` |
| PDF report download | `candidate/applications.py:1558` | 1 | ~$0.001 | `require_credits` |
| Career chatbot turn | `career_chatbot.py:98,190` | 1 | ~$0.002 | `require_credits` |

## 2.3 Monthly allocations (replaces plan limit columns)

| Plan | Credits/mo | Notes |
|---|---|---|
| Free recruiter (`free_recruiter`) | 25 | throttle only — no paid value |
| Starter (49 TND) | 150 | |
| Professional (149 TND) | 750 | |
| Enterprise (499 TND) | 5,000 | |
| Free candidate (`free-candidate`) | 10 | 1 interview (5+1+3) + 1 CV analysis |
| Candidate Pro (29 TND) | 150 | ~30 interviews |
| Candidate Premium (49 TND) | 600 | |

Allocation mechanics: at subscription activation + on `current_period_start` cron, `credit_transactions(type='grant', amount=+plan.credits_monthly)`. **Credits expire** at next period start (matching current monthly-reset semantics) — no rollover in V1 (simpler, matches `reset_usage_if_needed` behavior).

## 2.4 Top-ups / promo / enterprise / admin override

| Source | Table path | Notes |
|---|---|---|
| **Manual top-up** | `Transaction(status='pending')` → admin approve → `credit_transactions(type='topup', provider='manual', provider_ref=<invoice_number>)` | Buyer buys a credit pack via bank transfer; admin approves like any payment |
| **Promotional** | `credit_transactions(type='promo', actor_type='promo', provider_ref=<promo_code>)` | admin grants with coupon code |
| **Enterprise contract** | `credit_transactions(type='grant', actor_type='admin', provider='admin')` | covered by contract value, no per-topup invoice |
| **Admin adjust** | `POST /admin/credits/{user}/adjust` → `credit_transactions(type='adjustment', actor_type='admin')` | + or − (removal = negative signed amount, never NULL) |
| **Temporary/permanent unlock** | `FeatureFlag` per-user override + credit grant | see Part 3 |

## 2.5 The `require_credits` dependency (server-side enforcement, single choke point)

```python
# backend/dependencies.py — NEW
def require_credits(resource: str, credits: int = 1, ref_resolver=None):
    async def dep(current_user=Depends(get_current_user), db=Depends(get_db)):
        wallet = get_or_create_wallet(db, current_user.id)
        if wallet.balance < credits:
            raise HTTPException(402, detail={"error":"insufficient_credits", ...})
        # reserve atomically via UPDATE ... WHERE balance >= credits (row-lock)
        row = db.execute(update(CreditWallet).where(
            CreditWallet.user_id==current_user.id,
            CreditWallet.balance >= credits,
            CreditWallet.version==wallet.version).values(
            balance=CreditWallet.balance - credits, version=CreditWallet.version+1))
        if row.rowcount == 0: raise HTTPException(402, ...)
        tx = CreditTransaction(amount=-credits, type='consume', resource=resource,
              idempotency_key=f"consume:{resource}:{ref}")   # idempotent
        db.add(tx); db.commit()
        yield credits
    return dep
```
`idempotency_key` dedupes retries. On downstream failure, a compensating `rollback` transaction restores credits (callers catch the AI error and call `rollback_credits(key)`).

---

# PART 3 — FEATURE MANAGEMENT

## 3.1 Extend the existing `FeatureFlag` model (`backend/models/foundation/user.py:248`)
Today: `flag_key, user_id(null=global), enabled, rollout_percentage, description`. Add:
```
feature_flags (+ add columns)
  visibility ENUM('public','beta','internal','hidden','experimental') DEFAULT 'public'
  audiences VARCHAR(100) DEFAULT 'all'      -- 'recruiter'|'candidate'|'admin'|'enterprise'|'all'
  maintenance_mode BOOL DEFAULT False       -- kill switch
  kill_switch BOOL DEFAULT False
  depends_on VARCHAR(100) NULL              -- feature dependency key
  plan_restrictions VARCHAR(255) NULL       -- CSV of allowed plan slugs
  company_override_key VARCHAR(100) NULL    -- per-company override value key
  temp_unlock_user_id INT NULL / temp_unlock_until DATETIME NULL
  permanent_unlock_user_id INT NULL
```
Backfill current `DEFAULT_FLAGS` from `backend/routers/feature_flags.py:22-63` into this table.

## 3.2 The feature-eval helper
```python
# backend/services/feature_service.py — NEW
def feature_enabled(feature_key, user, company_id) -> (bool, str):
    f = get_feature_flag(feature_key)                       # global definition
    if f.kill_switch or f.maintenance_mode: return (False, 'maintenance')
    if f.visibility == 'internal': return (is_admin(user), 'admin_only')
    if f.audiences not in ('all', user.role): return (False, 'audience')
    if f.plan_restrictions and user.plan.slug not in f.plan_restrictions: return (False, 'plan')
    if f.rollout_percentage and hash(user.id) % 100 > f.rollout_percentage: return (False, 'rollout')
    if per_user override (temp/permanent unlock) set: return (True, 'override')
    if company override set in company_flags table: return (company_value, 'company_override')
    return (f.enabled, 'flag')
```
**Zero code changes** to enable/disable any feature — admin toggles rows in the Admin Panel.

## 3.3 Reuse + wire existing flag routers
- `backend/routers/feature_flags.py` already has admin CRUD (`:171-287`, `require_admin`) — extend with the new columns, keep the routes.
- Wire legacy `permissions_json` plan matrix (`has_feature()` in `subscription_service.py:69`) to ALSO consult `feature_flags` so both systems coexist during migration.

---

# PART 4 — ADMIN SUBSCRIPTION PANEL

**Backend endpoints (new/extended, all `manage_finance`):**

| Endpoint | Action | Status |
|---|---|---|
| `GET /admin/subscriptions` | list all Subscriptions (filter: status, audience, plan) | NEW |
| `GET /admin/subscriptions/{id}` | detail + history + wallet | NEW |
| `POST /admin/subscriptions/{id}/change-plan` | upgrade/downgrade (+force flag) | NEW |
| `POST /admin/subscriptions/{id}/cancel` / `expire` / `reinstate` / `extend` / `start-trial` | lifecycle | cancel/extend exist, rest NEW |
| `POST /admin/plans` / `PUT` / `DELETE` | plan CRUD (exists) + **duplicate** + **archive** (`is_active=False`) | extend |
| `POST /admin/plans/{id}/duplicate` | copy plan + bump slug `-copy` | NEW |
| `POST /admin/users/{user}/assign-plan/{plan}` | force assign (exists `admin/users.py:276`) | reuse |
| `GET /admin/users/usage` + `POST /admin/users/{user}/usage` | usage reset/bonus (exists `admin/users.py:184,231`) | reuse → migrate to credits |
| `POST /admin/subscriptions/{tx}/approve|reject` | payment verdict (exists `admin/subscriptions.py:56,192`) | reuse |
| `POST /admin/credits/{user}/adjust` | grant/remove credits | NEW |
| `GET /admin/invoices` + `/download` + `/xml` | invoices (exists `admin/invoices.py`) | reuse |

**Frontend:** rewrite `frontend/src/features/admin/pages/subscriptions-manager.tsx` (currently static mock, `subscriptions-manager.tsx:15-21`) to call real endpoints via extended `admin.service.ts` (currently only `getSubscriptions` at `admin.service.ts:32`). Add methods: `getSubscriptionDetail`, `changePlan`, `startTrial`, `extendSubscription`, `expireSubscription`, `reinstate`, `adjustCredits`, `duplicatePlan`, `listUsageEvents`.

**Panel layout (tabs):**
```
Subscriptions Manager
  ├─ Overview  (counts by status, MRR snapshot, renewal calendar)
  ├─ All Subs  (table: user, company, plan, cycle, status, period, credits, actions)
  │    └─ row action menu: Approve Payment · Extend · Change Plan · Cancel · Expire · Reinstate · Grant Credits · View History
  ├─ Pending  (payment queue — see Part 6)
  ├─ Trials
  ├─ Plans    (CRUD + duplicate + archive + price history / plan_versions)
  ├─ Credits  (wallet balances, top-up queue, adjust)
  ├─ History  (subscription_history stream)
  └─ Export   (CSV)
```

---

# PART 5 — FINANCIAL DASHBOARD

**Backend:** new `admin_financial_service.py` (mirrors `backend/admin_analytics_service.py` pattern) + `GET /admin/finance/overview|revenue|customers|credits|forecast|export`. All computed from `transactions` (status='succeeded'), `invoices`, `subscriptions`, `credit_transactions`, `usage_events`, `users` — no new infra.

| KPI | Source query |
|---|---|
| Today's / Month / Annual revenue | `SUM(transactions.amount_ttc) WHERE status='succeeded'` grouped by date |
| MRR / ARR | active subscriptions × plan price (monthly) / ×12 |
| Revenue growth | compare month-over-month |
| Total customers / recruiters / candidates | `users.role` counts |
| Active / expired subscriptions | `subscriptions.status` counts |
| Pending / approved / rejected payments | `transactions.status` counts |
| Revenue by plan | `transactions.plan_id → subscription_plans.name` |
| Revenue by month | group by `created_at` |
| Revenue by country/company/recruiter | join `users`, `companies` |
| ARPU / ARPCompany | revenue ÷ active users / companies |
| LTV | ARPU × (1 ÷ monthly churn) |
| Monthly churn | expired+canceled ÷ active (period) |
| Renewal / upgrade / downgrade rate | `subscription_history` action counts |
| Credits sold / consumed | `credit_transactions` SUM by type |
| AI cost / profit / gross margin | `usage_events.cost_usd` vs revenue; margin = 1 − cost/revenue |
| Top paying companies / recruiters | revenue desc |
| Most used / expensive / profitable feature | `usage_events` group by resource (count, cost, credits) |
| DAU / MAU | distinct users by day / month |
| Conversion / subscription / payment funnels | stages: signup → activated plan → approved payment |

**Export:** CSV (`paginate()`-style streaming), Excel (openpyxl — add dependency or reuse CSV), PDF (reuse `pdf_generator.py` `PDFReport`).

**Frontend:** rewrite `frontend/src/features/admin/pages/payments.tsx` + add `finance-dashboard.tsx` using `recharts` (already in `package.json`). Wire the 4 stat cards + charts (revenue trend, plan mix pie, churn line, credits bar) to real API.

---

# PART 6 — PAYMENT MANAGEMENT (Manual Bank Transfer)

Reuse the **existing, working** `Transaction` + `Invoice` flow and extend it with a queue:

## 6.1 New table
```
payment_proofs
  id PK, transaction_id FK transactions.id, company_id
  file_path VARCHAR(255), original_filename VARCHAR(255), file_size INT
  uploaded_by INT FK, uploaded_at DATETIME
  mime_type VARCHAR(100), checksum_sha256 VARCHAR(64)   -- duplicate/fraud detection
```
(Keep `Transaction.proof_url` for back-compat; `payment_proofs` adds structured metadata.)

## 6.2 Payment queue lifecycle (all admin-driven, no webhooks)
```
pending → [admin review] → approved  (tx.succeeded + invoice + subscription active)
                          └─ rejected (reason required, tx.Failed + email)
                          └─ expired  (cron: pending > 7d → 'Failed', reason "expired")
```
- **Duplicate detection:** before approve, hash uploaded proof (`checksum_sha256`) and reject if it matches an already-`succeeded` transaction for the same user/amount → blocks reusing the same receipt.
- **Fraud signals:** same proof reused across users; amount mismatch vs plan price; same IBAN mismatch; proof upload IP ≠ account IP (logged to `AuditLog`).
- **Payment timeline:** `subscription_history` rows (`payment_received`, `approved`, `rejected`) render a timeline in the panel.
- **Notes/internal comments:** extend `Transaction` with `admin_note` (or reuse `subscription_history.notes`).

## 6.3 Invoice generation (fully manual, exists)
`admin/invoices.py` `_create_invoice_internal` already: TVA 19% + stamp 1.000 TND, `INV-YYYY-NNNN`, client MF from KYB, PDF + TEIF XML. Approve endpoint already calls it (`admin/subscriptions.py:183`). Only change: link `invoice → subscription.plan_id` and write `plan_versions` snapshot.

**Payment config for users:** `GET /candidate/payment-config` (`candidate/subscriptions.py:119`) and bank fields in `SystemConfig` (`bank_name`, `bank_iban`, `payment_instructions` — already editable in Admin Settings). Recruiter side mirrors.

---

# PART 7 — USAGE ANALYTICS

**Backend:** `usage_events` table (Part 8) + `GET /admin/usage/ai|credits|features|users|storage|interviews|cv|search` + `GET /admin/usage/export`.

| Dashboard | Aggregations |
|---|---|
| AI usage | requests/day & /month, cost/day, cost per feature, credits per feature, model breakdown |
| Credits usage | consumed/allocated/remaining per plan, top-up volume, burn rate |
| Feature usage | top features by calls/users |
| Recruiter / candidate / company usage | per-entity totals |
| Most / least active users | by `usage_events` + login activity |
| API usage | request counts per router prefix (from a light middleware counter or `audit_logs`) |
| Storage usage | sum of file fields (proofs, avatars, uploads) |
| Interviews / CV / search stats | counts + avg credits + avg cost |

**Frontend:** rewrite `frontend/src/features/admin/pages/recruiter-usage.tsx` + `ai-monitoring.tsx` to real data. `recharts` charts.

---

# PART 8 — DATABASE (All new tables, normalized, TenantMixin unless noted)

| Table | File (new) | Purpose |
|---|---|---|
| `subscriptions` | `backend/models/finance/subscription.py` | lifecycle core (Part 1) |
| `subscription_history` | same | immutable lifecycle events |
| `plan_versions` | same | price/limit snapshots for grandfathering |
| `credit_wallets` | `backend/models/finance/credits.py` | balance + optimistic lock |
| `credit_transactions` | same | immutable credit ledger (idempotency) |
| `usage_events` | same | metering stream (Part 7) |
| `payment_proofs` | `backend/models/finance/finance.py` (extend) | structured receipt metadata + fraud hash |
| `coupons` | `backend/models/finance/coupon.py` | future-ready (code, type, value, max_uses, expires) |
| `tax_rates` | `backend/models/finance/finance.py` (extend) | TVA/stamp by country (default 19% / 1.000 TND) |
| `feature_flags` | extend existing (`user.py:248`) | Part 3 |

**Column additions to existing models:**
- `SubscriptionPlan`: `credits_monthly INT DEFAULT 0`, `plan_group VARCHAR(20)`.
- `Transaction`: `plan_id FK` (nullable), `admin_note TEXT`, `expires_at DATETIME`.
- `Invoice`: `plan_version_id FK` (nullable).
- `RecruiterProfile` / `CandidateProfile`: keep current columns as read-compat mirrors (write-through during transition, retire after).

## 8.1 Migration files (Alembic, follow `m{NN}_*.py` convention)
- `m47_create_subscriptions_and_history.py`
- `m48_create_credit_wallet_ledger.py`
- `m49_create_usage_events.py`
- `m50_extend_feature_flags.py`
- `m51_add_payment_proofs_and_tax_rates.py`
- `m52_add_plan_credits_and_coupons.py`
- Merge with production chain (`p1prod202606300`) via `alembic merge` if needed (two heads exist).

---

# PART 9 — SECURITY

| Threat | Mitigation |
|---|---|
| **Credit fraud** | immutable ledger; balance via `UPDATE ... WHERE balance >= n AND version = v` (row-lock); negative balance impossible; `idempotency_key` unique on every debit |
| **Double-charge on retry** | `credit_transactions.idempotency_key` UNIQUE → retried consume returns 200 without second debit |
| **Subscription bypass** | `require_credits` dependency on every AI/paid endpoint (Part 4.2 of audit lists the ~40 ungated sites); **fix `require_pro_tier` exact-match bug** (`dependencies.py:716`, `search.py:115`) so `pro_plus`/`enterprise` aren't locked out |
| **Tier read inconsistency** | `ai_quota_service.py:454` reads deprecated `User.tier` → switch to plan/subscription-derived tier (single source = `subscriptions.plan_id`) |
| **Usage manipulation** | usage only writable by system (`actor_type='system'`) or admin (audit-logged); client cannot post usage events |
| **Race conditions** | `FOR UPDATE` on wallet + subscription rows; optimistic `version` column; idempotency keys everywhere |
| **Duplicate payments** | proof checksum dedupe (Part 6.2) |
| **Admin abuse** | every admin mutation writes `AuditLog` (pattern exists); `manage_finance` is `SUPER_ADMIN_ONLY` (`admin/users.py:335`) — restrict billing panel to super-admins in V1 |
| **Replay of approve/reject** | existing `Idempotency-Key` header + terminal-state guards (`admin/subscriptions.py:89,125-132`) — keep |
| **Audit trails** | `AuditLog` (every mutation) + `subscription_history` + `credit_transactions` = triple audit |
| **Insufficient credits UX** | 402 with `upgrade_url`, `balance`, `cost` — consistent with `check_ai_quota_dependency` response shape (`ai_quota_service.py:439-472`) |

---

# PART 10 — IMPLEMENTATION ROADMAP

## 10.1 Architecture diagram
```
CANDIDATE/RECRUITER ──▶ POST /upgrade (manual bank proof) ──▶ Transaction(pending)
                                                                │
ADMIN PANEL ─────────────────────────────────────────────────────┤
  ├─ Payments queue ─▶ approve ─▶ tx.succeeded + Invoice(PDF/TEIF) + Subscription(active) + Credits(grant)
  ├─ Subscriptions ─▶ extend/cancel/change-plan/trial ─▶ subscription_history + AuditLog
  ├─ Credits ─▶ adjust/top-up/promo ─▶ credit_transactions (ledger) ─▶ wallet.balance
  ├─ Feature flags ─▶ feature_flags rows ─▶ feature_service.evaluate()
  └─ Finance/Usage dashboards ─▶ transactions+invoices+usage_events ─▶ KPI/CSV/PDF

DAILY CRON (scheduler.py)
  ├─ renewals: period_end → past_due(grace 3d) → expired; renewal reminder emails
  ├─ credit grants at period_start
  ├─ expire pending payments (>7d)
  └─ trial expiry
```

## 10.2 Implementation order (dependency-sorted)

| Step | Deliverable | Reuses | Est. |
|---|---|---|---|
| **S1** | Seed paid plans (Alembic) + `plan_versions` | `admin/plans.py` | 0.5 d |
| **S2** | `subscriptions` + `subscription_history` models + migration | profile write-through pattern | 1 d |
| **S3** | Lifecycle endpoints (change-plan/cancel/expire/reinstate/trial) + cron | `admin/subscriptions.py` | 1.5 d |
| **S4** | `credit_wallets` + `credit_transactions` + `usage_events` + migrations | ledger pattern | 1.5 d |
| **S5** | `require_credits` dependency + wire to ~25 AI endpoints (Part 2.2) | `dependencies.py` | 2 d |
| **S6** | Credit admin endpoints (adjust/top-up/promo) + approval hook | `admin/users.py` | 1 d |
| **S7** | Feature flags extension + `feature_service` + wire `has_feature` | `feature_flags.py` | 1 d |
| **S8** | Financial dashboard backend + frontend | `admin_analytics_service.py`, recharts | 2 d |
| **S9** | Admin subscriptions/credits/features frontend (rewrite mock pages) | `admin.service.ts`, `billing.tsx` | 3 d |
| **S10** | Payment queue (proofs, dedupe, fraud signals, expiry) | `payments.py`, `subscriptions.py` | 1.5 d |
| **S11** | Export (CSV/Excel/PDF), coupons, tax_rates | `pdf_generator.py` | 1 d |
| **S12** | Hardening: fix `require_pro_tier`, tier SSOT, idempotency sweep | audit list | 1 d |

**Total: ~18–19 engineer-days** (backend ~10d, frontend ~8d) + 1–2 days QA/migrations.

## 10.3 Priority list
- **P0 (must ship first):** S1, S5 (enforcement), S6 (credits admin), S12 (security). Without enforcement the system monetizes nothing.
- **P1:** S2, S3, S4 (lifecycle + ledger), S9 (admin UI).
- **P2:** S7, S8, S10, S11 (analytics + queue + exports).

## 10.4 Quick wins (first week)
1. Fix `require_pro_tier` exact-match bug (`dependencies.py:716`, `search.py:115`).
2. Enforce existing-but-dead candidate paywalls: `check_pdf_download_limit` on `applications.py:1558`, `check_ai_analysis_limit` on `cv.py:521`.
3. Add per-turn credit check to `ai_interview/chat.py:761`.
4. Seed the 6 paid plans in DB so `GET /admin/plans` matches `pricing.html`.
5. Wire `free_trial` SystemConfig flag to the trial cron.

## 10.5 Critical issues (must fix)
1. 40+ ungated AI endpoints (audit Part 4.2) — abuse + cost exposure until S5.
2. `require_pro_tier` exact-match → blocks paying higher tiers.
3. Tier read from deprecated `User.tier` in `ai_quota_service.py:454`.
4. Konnect/Stripe code paths — **leave dormant** (V1 manual-only). Do not delete; hide behind `CANDWAY_PAYMENTS_ENABLED=0` (already gated `payments.py:48`).
5. Dead-code candidate limits (`candidate_subscription_service.py:100-191`) — wire, don't rewrite.

## 10.6 Feature flag default set (V1)
`ai_interview`, `ghost_report`, `talent_scout`, `ai_copilot`, `ai_search_rerank`, `career_roadmap`, `cv_enriched_review`, `recruiter_desktop`, `translation`, `bulk_import`, `maintenance_mode`, `payments_enabled` — all as DB rows, admin-toggleable with zero deploys.

---

### How this satisfies the manual-payment-only rule
Every revenue path ends in the same manual loop: **user uploads bank proof → `Transaction(pending)` → admin verifies → invoice generated (PDF/TEIF) → `Subscription(active)` → credits granted.** No payment provider SDK, no webhook, no cron that touches money — only the admin approves or rejects. Stripe/Konnect code stays behind the existing `CANDWAY_PAYMENTS_ENABLED` flag and is inert by default.

*File/line references verified against the codebase. Admin frontend pages referenced are currently static mocks and are the primary greenfield build.*
