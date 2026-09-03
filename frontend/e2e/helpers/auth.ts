import { expect, type Page } from '@playwright/test';

export const E2E_BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:8003';

export const USERS = {
  recruiter: {
    email: process.env.E2E_RECRUITER_EMAIL || 'recruiter@candway.dev',
    password: process.env.E2E_RECRUITER_PASSWORD || 'Test@2026!',
  },
  candidate: {
    email: process.env.E2E_CANDIDATE_EMAIL || 'test@candway.tn',
    password: process.env.E2E_CANDIDATE_PASSWORD || 'Test@2026!',
  },
};

export async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto('/auth/login');
  await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible({ timeout: 15000 });
  await page.getByLabel('Email address').fill(credentials.email);
  await page.getByLabel('Password').fill(credentials.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/\/dashboard|\/admin\/dashboard|\/org\b/, { timeout: 20000 });
}

export async function logout(page: Page) {
  await page.request.post('/api/v1/auth/logout');
}
