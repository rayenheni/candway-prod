import { test, expect } from '@playwright/test';
import { login, USERS } from './helpers/auth';

test.describe('Recruiter campaign flow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, USERS.recruiter);
  });

  test('dashboard loads with pipeline overview', async ({ page }) => {
    await expect(page.getByText(/recruitment pipeline/i)).toBeVisible();
  });

  test('campaigns list page loads', async ({ page }) => {
    await page.goto('/campaigns');
    await expect(page.getByRole('heading', { name: /email campaigns/i })).toBeVisible({ timeout: 15000 });
  });

  test('new campaign wizard loads', async ({ page }) => {
    await page.goto('/campaigns/new');
    await expect(page.getByText(/job info/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/rubric/i)).toBeVisible();
    await expect(page.getByText(/candidates/i)).toBeVisible();
  });

  test('email templates page loads and supports creation', async ({ page }) => {
    await page.goto('/email-templates');
    await expect(page.getByRole('heading', { name: /email templates/i })).toBeVisible({ timeout: 15000 });

    const created = `E2E Template ${Date.now()}`;
    await page.getByRole('button', { name: /create template/i }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel(/template name/i).fill(created);
    await dialog.getByLabel(/subject line/i).fill(`E2E Subject ${Date.now()}`);
    await dialog.getByRole('button', { name: /^create$/i }).click();
    await expect(page.getByText(created)).toBeVisible({ timeout: 15000 });
  });

  test('settings page shows SMTP section', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: /^settings$/i })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('tab', { name: /profile/i })).toBeVisible();
  });

  test('skill tree / rubric library loads', async ({ page }) => {
    await page.goto('/skill-trees');
    await expect(page.getByRole('heading', { name: /rubric library/i })).toBeVisible({ timeout: 15000 });
  });
});
