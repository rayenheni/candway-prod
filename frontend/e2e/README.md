# E2E Tests (Playwright)

End-to-end tests that drive a real browser against the **live Candway app**
(React SPA + FastAPI backend) and verify the real business flows:

- **landing.spec.ts** — public pages: landing, pricing, careers job board, privacy/terms
- **auth.spec.ts** — login redirect, form validation, recruiter + candidate login
- **recruiter-flow.spec.ts** — recruiter: dashboard, campaigns list, new-campaign wizard, email templates (incl. create), settings, rubric library
- **candidate-flow.spec.ts** — candidate: dashboard, applications, job board, profile

## Prerequisites

1. **Backend running** — the SPA is served by FastAPI from `static/app`.
   Start it (default `127.0.0.1:8003`):
   ```
   cd backend && uvicorn backend.app:app --host 127.0.0.1 --port 8003
   ```
   Point Playwright elsewhere with `E2E_BASE_URL`.
2. **Frontend built** — `npm run build` (backend serves the built SPA).
3. **Test accounts** — default credentials in `e2e/helpers/auth.ts`:
   - Recruiter: `recruiter@candway.dev` / `Test@2026!`
   - Candidate: `test@candway.tn` / `Test@2026!`
   Override via `E2E_RECRUITER_EMAIL`, `E2E_RECRUITER_PASSWORD`,
   `E2E_CANDIDATE_EMAIL`, `E2E_CANDIDATE_PASSWORD`.

## Run

From `frontend/`:

```
npm run test:e2e          # headless
npm run test:e2e:headed   # watch in a visible browser
npm run test:e2e:ui       # Playwright UI runner
npx playwright test auth.spec.ts          # single file
npx playwright test --project=chromium    # single browser
```

## Config

`playwright.config.ts` — chromium only, HTML report saved to
`playwright-report/`, traces on first retry. Set `E2E_BASE_URL` to target a
different environment (e.g. staging).
