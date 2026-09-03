import { test, expect } from '@playwright/test';
import { login, USERS } from './helpers/auth';

test.describe('Authentication', () => {
  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/auth\/login/);
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  });

  test('login page shows form and validation', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByText(/please enter a valid email/i)).toBeVisible();
  });

  test('recruiter can log in and see recruiter dashboard', async ({ page }) => {
    await login(page, USERS.recruiter);
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/recruitment pipeline/i)).toBeVisible();
  });

  test('candidate can log in and see candidate dashboard', async ({ page }) => {
    await login(page, USERS.candidate);
    await expect(page.getByRole('heading', { name: /^hey /i })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/find jobs/i)).toBeVisible();
  });
});
