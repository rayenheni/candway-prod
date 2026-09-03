# CI/CD Audit — Candway

**Date:** 2026-08-06
**Scope:** `.github/workflows/`, `scripts/deploy.sh`, `Dockerfile`, `docker-compose.yml`, `Procfile`, `.dockerignore`, `pytest.ini`, `pyproject.toml`, `.gitignore`
**Repo remote:** `https://github.com/rayenheni/candwayv.git` (branch `main`)

---

## 1. Current Pipeline Summary

There are **TWO GitHub Actions workflows** that overlap and run in parallel:

| File | Name | Jobs | Notes |
|------|------|------|-------|
| `.github/workflows/ci.yml` | `CI/CD Pipeline` | `lint`, `test`, `security` | Runs **only** `pytest backend/tests/`. No frontend, no docker, no migration, no deploy. |
| `.github/workflows/ci-cd.yml` | `Candway CI/CD Pipeline` | `lint`, `security`, `frontend-lint`, `test`, `migration-check`, `docker-build`, `performance-tests`, `deploy` | Runs **only** `pytest tests/` (root tests). Full stack incl. deploy. |

There is **no GitLab CI**, no `.circleci`, no Jenkinsfile, no Azure/Travis/woodpecker config. Docker/nginx/Procfile are present but only used by the two GitHub workflows above.

### Job → artifact mapping

| CI step | Where defined | What it actually does |
|---------|---------------|-----------------------|
| `lint` (both) | `ci.yml`, `ci-cd.yml` | `ruff check backend/ --select E,F,W,I --ignore E501`, `ruff format backend/ --check`, and (ci-cd only) `mypy backend/ --ignore-missing-imports` |
| `security` (both) | `ci.yml`, `ci-cd.yml` | `bandit -r backend/ -ll -ii`, `safety check -r requirements.txt --ignore 70612`; ci-cd also runs **Trivy** on `candway/platform:ci-test` |
| `frontend-lint` | `ci-cd.yml` | `npm ci` → `npx tsc --noEmit` → `npm run build` (Vite) |
| `test` | `ci.yml` | `pytest backend/tests/` (SQLite in-memory, no coverage) |
| `test` | `ci-cd.yml` | `pytest tests/` + `--cov=backend --cov-fail-under=70` + Codecov upload (`fail_ci_if_error: true`) |
| `migration-check` | `ci-cd.yml` | `alembic check` (needs a live DB → fails, falls back via `||`), then Python assert of **single migration head** |
| `docker-build` | `ci-cd.yml` | `docker/build-push-action` on root `context: .`, `load: true`, **no `target:`** → builds only the Dockerfile **default target (runtime)**; `nginx` target never built in CI |
| `performance-tests` | `ci-cd.yml` | main-branch only: `uvicorn backend.main:app` + `locust -f backend/tests/load_test.py` |
| `deploy` | `ci-cd.yml` | main-branch push only: Docker Hub login/push → SSH to host → `git reset --hard origin/main` → `bash scripts/deploy.sh` |

---

## 2. Triggers

Both workflows trigger on **the same events**:

```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
```

- `ci.yml` and `ci-cd.yml` therefore **both fire on every push to main/develop and every PR to main** → duplicate runs, doubled compute, and two parallel pipelines with the same job names.
- `ci-cd.yml` has `concurrency: { group: workflow-ref, cancel-in-progress: true }`; `ci.yml` has **no concurrency control**.
- `deploy` and `performance-tests` are additionally gated with `if: github.ref == 'refs/heads/main'` (deploy also requires `event_name == 'push'`).

---

## 3. Secrets Required in GitHub

| Secret | Used by | Required for beta? |
|--------|---------|--------------------|
| `DOCKER_USERNAME` | ci-cd `deploy` (docker login) | Only if you enable deploy |
| `DOCKER_PASSWORD` | ci-cd `deploy` (docker login) | Only if you enable deploy |
| `DEPLOY_HOST` | ci-cd `deploy` (SSH) | Only if you enable deploy |
| `DEPLOY_USER` | ci-cd `deploy` (SSH) | Only if you enable deploy |
| `DEPLOY_KEY` | ci-cd `deploy` (SSH private key) | Only if you enable deploy |
| `CODECOV_TOKEN` | ci-cd `test` → `codecov-action@v5` with `fail_ci_if_error: true` | **Yes** — on a public repo it may auto-upload, but on a private repo the step fails without a token, and `fail_ci_if_error: true` will fail the whole `test` job. |

Note: Trivy SARIF upload uses `github/codeql-action/upload-sarif` with the default `GITHUB_TOKEN` — works if GitHub code scanning is enabled on the repo.

`.env` files (`.env`, `.env.staging`, `frontend/.env.production`, `frontend/.env.local`) are **correctly gitignored** and **not tracked** (verified with `git ls-files`). Only template/example files are committed. No secrets are currently in the repo.

---

## 4. What Passes / Fails (empirically verified)

### ❌ FAILS — blocks the pipeline

| Check | Result | Evidence |
|-------|--------|----------|
| `ruff check backend/ --select E,F,W,I --ignore E501` | **FAILS** | **942 errors** (803 outside `backend/tests`). Top rules: `I001` (278, unsorted imports), `F401` (268, unused imports), `E712` (115), `F841` (67), `E402` (56), `F821` (34). |
| `ruff format backend/ --check` | **FAILS** | **311 files would be reformatted**, 106 already formatted. |
| `npx tsc --noEmit` (frontend) | **FAILS** | **8 errors** — e.g. `analytics-dashboard.tsx:25` TS2345, `candidate-esign-view.tsx:10` TS6133 unused `Briefcase`/`MapPin`, `calendar-settings.tsx:3` TS6133 unused Card imports, `ghost-report.tsx:2,7` TS6133 unused `motion`/`Download`. |
| `mypy backend/ --ignore-missing-imports` (ci-cd only) | **Likely FAILS** | Not executed here, but given the ruff error volume and dynamic patterns (monkey-patched relationships), mypy over 371 files will almost certainly emit errors. Unverified. |

### ⚠️ HIGH RISK — structural problems

| Item | Issue |
|------|-------|
| **Trivy job is broken by design** | ci-cd `security` job has `needs: [docker-build]`, but `docker-build` uses `load: true` (image stays in that runner's local daemon, never pushed to a registry). Each GitHub Actions job runs on a **fresh runner**, so `candway/platform:ci-test` does **not exist** in the `security` runner → Trivy cannot pull it → the step fails. |
| **Tests are split, not unified** | `ci.yml` runs `pytest backend/tests/` only; `ci-cd.yml` runs `pytest tests/` only. **Neither runs both.** The `--cov-fail-under=70` in ci-cd applies to root `tests/` alone (26 files, mostly integration/security) — backend coverage from those is very likely < 70%. |
| **`pytest.ini` is self-contradictory** | `testpaths` includes `backend/tests`, but `norecursedirs` also lists `backend/tests`. Empirically bare `pytest` still collects both (1526 tests), so it works, but the config is confusing and a `pytest` run from a subdirectory changes behavior. Also `timeout_modfunc` triggers a `PytestConfigWarning` (unknown option in the installed pytest-timeout). |
| **`docker-build` never builds the nginx stage** | No `target:` is passed, so only the Dockerfile default (`runtime`) is built. The `nginx` stage (React SPA) is never compiled/verified in CI. |
| **`migration-check` is weak** | `alembic check` requires a live DATABASE_URL (none set in the job) → always fails → the `|| echo` fallback runs, then only asserts a **single head**. It never actually applies migrations against a schema. Head is currently `m54` (single) — chain is intact per AGENTS.md, but nothing in CI validates that `alembic upgrade head` succeeds on a clean DB. |
| **Deploy `docker compose pull` will fail** | `docker-compose.yml` defines `backend` and `nginx` with `build:` but **no `image:` tag** (verified: only mysql/redis/prometheus/grafana have `image:`). `scripts/deploy.sh` step 2 runs `docker compose pull`, which errors for build-only services ("no image to pull"). Meanwhile CI pushes `candway/platform:latest` that compose never references — the pushed image is **not used** by the compose stack. |
| **`docker compose up -d` rebuilds from source** | Because `backend`/`nginx` have no `image:`, the host would rebuild from the checked-out source rather than the CI-pushed image — defeating the CI push entirely. |

### ✅ PASSES (verified)

| Check | Result | Evidence |
|-------|--------|----------|
| Alembic single head | **PASSES** | `python -m alembic heads` → `m54 (head)` single head. |
| `pytest backend/tests/` collection | **PASSES** | 732 tests collected. Per AGENTS.md, 150+ targeted tests pass locally. |
| `pytest tests/` + `backend/tests` (bare) | **PASSES (collection)** | 1526 tests collected in ~1s. |
| `npm run build` (Vite) | **PASSES** | AGENTS.md confirms `npm run build` succeeds; Vite build does not run `tsc`, so it passes despite the 8 TS errors. |
| Secrets in git | **CLEAN** | No `.env*`/secrets tracked. |

---

## 5. What Is Safe for Beta

**Good news — nothing deploys automatically today.** The `deploy` job depends on `test`, `frontend-lint`, `migration-check`, `docker-build`, `performance-tests`, all of which transitively depend on `lint`. Since `lint` fails, **every downstream job is skipped** and `deploy` never runs. So:

- ✅ **No risk of accidental auto-deploy to production.**
- ✅ Secrets are not committed.
- ✅ Migration chain is a single head (`m54`).
- ✅ Test suites exist and pass locally (150+ backend, 75+ AI security).

**But CI is not green**, so it cannot act as a quality gate:

- ❌ `lint` red (ruff 942 / format 311 / tsc 8 errors).
- ❌ `frontend-lint` red (8 TS errors).
- ❌ Trivy step cannot work as written.
- ❌ Coverage threshold is applied to a too-small test subset.
- ❌ Deploy script would fail at `docker compose pull` even if the gate were green.

**Beta verdict:** Safe from *accidental deployment*, but **not usable as a CI gate** until lint/typecheck are green and the structural bugs above are fixed. Treat it as "manual deploy only" for now.

---

## 6. What Must Be Improved Later (priority order)

1. **Fix or suppress `lint`** — make `ruff check` + `ruff format` green (or split into an auto-fix job and a warn-only check), and fix the 8 TS6133/TS2345 errors in the frontend. Without this, every job downstream is skipped and CI is a no-op.
2. **Decide the two-workflow overlap** — merge `ci.yml` + `ci-cd.yml` into one, or disable one (BLOCKER-6 from `FINAL_PRE_LAUNCH_AUDIT.md`). Right now they run in parallel on the same triggers with duplicated work.
3. **Fix Trivy** — either push `candway/platform:ci-test` to a registry first (and tag it), or build+scan in the same job, or scan `alembic/`/requirements with `trivy fs` instead of an image.
4. **Unify the test run** — run `pytest` over both `tests/` and `backend/tests/` in one job, and set a **realistic** coverage threshold (or set `fail_under` to the current actual value).
5. **Make `migration-check` real** — spin up a throwaway DB (e.g. MySQL container or `pytest` with `alembic upgrade head`) and verify the migration chain applies; keep the single-head assert as a fast pre-check.
6. **Fix the deploy path** — either add `image: candway/platform:<tag>` to `backend`/`nginx` in compose so `docker compose pull` works and the pushed image is actually used, **or** change `deploy.sh` to `docker compose build` (and drop the pointless image push). Current state is a broken/unsed deploy.
7. **Add `concurrency` to `ci.yml`** and consider `dependabot` + a `CODEOWNERS` file (both currently absent).
8. **Add a staging environment** before promoting to prod deploy — today `deploy` targets production only.
9. **GitHub Settings:** create `CODECOV_TOKEN` if the repo is private; enable code scanning for Trivy SARIF upload.
10. **CI uses SQLite only** — no Redis/MySQL services in any job. Any test that depends on Redis (rate limiting, AI worker, token blacklist) or MySQL-specific behavior is silently not covered. Add service containers.

---

## 7. Files Reviewed

- `.github/workflows/ci.yml` (89 lines) — lint/test/security, `pytest backend/tests/` only
- `.github/workflows/ci-cd.yml` (303 lines) — full pipeline incl. deploy
- `scripts/deploy.sh` — backup → pull → migrate → up → health poll
- `Dockerfile` — 4 stages (frontend-builder, builder, nginx, runtime)
- `docker-compose.yml` — backend/nginx/mysql/redis/prometheus/grafana
- `Procfile`, `.dockerignore`, `nginx.conf`, `prometheus.yml`
- `pytest.ini`, `pyproject.toml` (ruff/mypy/coverage config)
- `.gitignore`, `.env.example`, `.env.production.example`, `backend/.env.production.template`
- `backend/main.py`, `backend/tests/` (57 test files), `tests/` (26 test files), `alembic/` (head m54)

**No CI/CD files were created or modified during this audit.**
