import { test, expect } from '@playwright/test';

test.describe('Public marketing pages', () => {
  test('landing page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Candway/i);
    await expect(page.getByRole('link', { name: /get started/i }).first()).toBeVisible();
  });

  test('pricing page loads', async ({ page }) => {
    await page.goto('/pricing');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });

  test('careers / public job board loads', async ({ page }) => {
    await page.goto('/careers');
    await expect(page.getByRole('heading', { name: /find your next role/i })).toBeVisible();
    await expect(page.getByPlaceholder(/job title, keyword/i)).toBeVisible();
  });

  test('privacy and terms pages load', async ({ page }) => {
    await page.goto('/privacy');
    await expect(page.getByRole('heading', { name: /privacy policy/i })).toBeVisible();
    await page.goto('/terms');
    await expect(page.getByRole('heading', { name: /terms of service/i })).toBeVisible();
  });
});
