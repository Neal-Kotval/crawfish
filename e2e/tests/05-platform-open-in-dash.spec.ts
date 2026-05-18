/**
 * Bridge test: Open-in-Dash from the platform's org canvas opens dash
 * in a new tab with org/user/name query params; dash auto-links and the
 * shell renders.
 *
 * Walks signed-in platform UI, so this skips in Clerk mode.
 */
import { test, expect } from "@playwright/test";
import {
  apiCreateOrg,
  clearDashIdentity,
  DASH_URL,
  isPlatformDevMode,
  PLATFORM_URL,
  rnd,
} from "../helpers";

test("Open-in-Dash opens a tab and the dash shell renders with the linked user", async ({
  page,
  request,
  context,
}) => {
  test.skip(!(await isPlatformDevMode(page)), "Platform in Clerk mode — bridge UI test requires dev shim.");

  const user = `bridge-${rnd()}`;
  const email = `${user}@local`;
  const orgName = `e2e-br-${rnd()}`;
  await apiCreateOrg(request, { name: orgName, userId: user, email });

  await clearDashIdentity(page);

  await page.goto(`${PLATFORM_URL}/onboarding`);
  await page.evaluate((u) => localStorage.setItem("cf_dev_user", u), user);
  await page.goto(`${PLATFORM_URL}/orgs/${orgName}/canvas`);

  const link = page.locator('a:has-text("Open in Dash")');
  await expect(link).toBeVisible({ timeout: 10_000 });

  const [dashPage] = await Promise.all([context.waitForEvent("page"), link.click()]);
  await dashPage.waitForLoadState("domcontentloaded");

  const url = dashPage.url();
  expect(url).toContain(`org=${encodeURIComponent(orgName)}`);
  expect(url).toContain("user=");

  await expect(dashPage.locator(".cfp-shell")).toBeVisible({ timeout: 15_000 });
  await expect(dashPage.locator('[data-testid="signin-gate"]')).toHaveCount(0);

  const initial = user.charAt(0).toUpperCase();
  await expect(dashPage.locator(".cfp-titlebar__avatar")).toContainText(initial, {
    timeout: 10_000,
  });

  expect(dashPage.url().startsWith(DASH_URL)).toBe(true);
});
