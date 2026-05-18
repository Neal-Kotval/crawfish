/**
 * OrgPicker + OrgRoute canvas.
 *
 * These tests walk the signed-in platform UI, which is gated by RequireAuth.
 * In Clerk mode the guard bounces to /signin and we can't proceed without a
 * real Clerk session, so the whole suite skips. Run with
 * VITE_CLERK_PUBLISHABLE_KEY unset to exercise these.
 */
import { test, expect } from "@playwright/test";
import { apiCreateOrg, isPlatformDevMode, PLATFORM_URL, rnd } from "../helpers";

test.describe("platform org picker + canvas", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!(await isPlatformDevMode(page)), "Platform in Clerk mode — UI tests require dev shim.");
  });

  test("empty state appears when the dev user has no orgs", async ({ page }) => {
    const user = `empty-${rnd()}`;
    await page.goto(`${PLATFORM_URL}/onboarding`);
    await page.evaluate((u) => localStorage.setItem("cf_dev_user", u), user);
    await page.goto(`${PLATFORM_URL}/`);
    await expect(page.locator("text=No orgs yet")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=Start onboarding")).toBeVisible();
  });

  test("OrgPicker lists seeded orgs", async ({ page, request }) => {
    const user = `seed-${rnd()}`;
    const a = `e2e-pick-a-${rnd()}`;
    const b = `e2e-pick-b-${rnd()}`;
    await apiCreateOrg(request, { name: a, userId: user, email: `${user}@local` });
    await apiCreateOrg(request, { name: b, userId: user, email: `${user}@local` });

    await page.goto(`${PLATFORM_URL}/onboarding`);
    await page.evaluate((u) => localStorage.setItem("cf_dev_user", u), user);
    await page.goto(`${PLATFORM_URL}/`);
    await expect(page.locator(`text=${a}`).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator(`text=${b}`).first()).toBeVisible();
    await expect(page.locator("text=Pick an org")).toBeVisible();
  });

  test("OrgRoute canvas renders agents read-only and Open-in-Dash href is correct", async ({
    page,
    request,
  }) => {
    const user = `canvas-${rnd()}`;
    const name = `e2e-can-${rnd()}`;
    await apiCreateOrg(request, { name, userId: user, email: `${user}@local` });

    await page.goto(`${PLATFORM_URL}/onboarding`);
    await page.evaluate((u) => localStorage.setItem("cf_dev_user", u), user);
    await page.goto(`${PLATFORM_URL}/orgs/${name}/canvas`);

    await expect(page.locator("text=READ-ONLY")).toBeVisible({ timeout: 10_000 });
    for (const agent of ["eng-bot", "designer-bot", "support-bot", "ops-bot"]) {
      await expect(page.locator(`text=${agent}`).first()).toBeVisible();
    }

    const link = page.locator('a:has-text("Open in Dash")');
    await expect(link).toBeVisible();
    const href = await link.getAttribute("href");
    expect(href).toBeTruthy();
    expect(href!).toMatch(/^http:\/\/localhost:7881\/canvas\?/);
    expect(href!).toContain(`org=${encodeURIComponent(name)}`);
    expect(href!).toContain("user=");
  });
});
