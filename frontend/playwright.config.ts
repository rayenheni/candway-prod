import { defineConfig, devices } from '@playwright/test';

// E2E base URL. The SPA is served by the FastAPI backend (it mounts the built
// React app from ../static/app). Set E2E_BASE_URL to point at your backend.
const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:8003';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
