/**
 * Platform auth gate.
 *
 * The platform boots in dev mode whenever VITE_CLERK_PUBLISHABLE_KEY is
 * unset. When dev-mode is on, useCurrentUser() returns a stable fake user
 * and RequireAuth lets `/` through. When Clerk IS configured the guard
 * bounces to /signin and renders the Clerk widget.
 *
 * Detection happens at runtime via isPlatformDevMode().
 */
import { test, expect } from "@playwright/test";
import { isPlatformDevMode, PLATFORM_URL } from "../helpers";

test("dev mode: root renders the org picker without sign-in", async ({ page }) => {
  test.skip(!(await isPlatformDevMode(page)), "Platform is in Clerk mode; dev shim bypassed.");
  await page.goto(`${PLATFORM_URL}/`);
  await expect(page).toHaveURL(new RegExp(`${PLATFORM_URL}/?$`));
  await expect(
    page.locator("h1").filter({ hasText: /Pick an org|No orgs yet|Loading/ }),
  ).toBeVisible({ timeout: 10_000 });
});

test("clerk mode: root redirects to /signin and renders sign-in copy", async ({ page }) => {
  test.skip(await isPlatformDevMode(page), "Platform is in dev mode; no Clerk widget to assert.");
  await page.goto(`${PLATFORM_URL}/`);
  await expect(page).toHaveURL(/\/signin/, { timeout: 10_000 });
  await expect(page.locator("text=/Sign in/i").first()).toBeVisible({ timeout: 15_000 });
});

test("onboarding loads outside the auth guard in any mode", async ({ page }) => {
  await page.goto(`${PLATFORM_URL}/onboarding`);
  await expect(page.locator("text=Let's hire your company.")).toBeVisible({ timeout: 10_000 });
});
