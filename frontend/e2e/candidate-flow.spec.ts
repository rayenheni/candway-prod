import { test, expect } from '@playwright/test';
import { login, USERS } from './helpers/auth';

test.describe('Candidate flow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, USERS.candidate);
  });

  test('candidate dashboard shows applications', async ({ page }) => {
    await expect(page.getByText(/track your applications/i)).toBeVisible({ timeout: 15000 });
  });

  test('applications tracker loads', async ({ page }) => {
    await page.goto('/applications');
    await expect(page.getByRole('heading', { name: /my applications/i })).toBeVisible({ timeout: 15000 });
  });

  test('job board loads for candidates', async ({ page }) => {
    await page.goto('/jobs');
    await expect(page.getByRole('heading', { name: /browse jobs/i })).toBeVisible({ timeout: 15000 });
  });

  test('profile page loads with job preferences', async ({ page }) => {
    await page.goto('/profile');
    await expect(page.getByText(/job preferences/i)).toBeVisible({ timeout: 15000 });
  });
});
