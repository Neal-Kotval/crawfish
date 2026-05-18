/**
 * Full 5-stage onboarding wizard.
 *
 * /onboarding is OUTSIDE the RequireAuth guard so it runs in both dev
 * mode and Clerk mode. The POST /api/orgs goes through apiFetch, which
 * sends X-User-Id when dev-mode is detected and a Clerk Bearer otherwise.
 * The server's dev shim falls back to a "dev-user" identity when no
 * header is present (NODE_ENV != production), so the wizard works either
 * way.
 *
 * The 409 retry path re-submits the same org name and asserts the wizard
 * bounces back to /propose with an error.
 */
import { test, expect } from "@playwright/test";
import { apiCreateOrg, PLATFORM_URL, rnd } from "../helpers";

test.describe("platform onboarding", () => {
  test("walks all five stages and confirms four hired agents", async ({ page }) => {
    const orgName = `e2e-onb-${rnd()}`;

    await page.goto(`${PLATFORM_URL}/onboarding`);

    await expect(page.locator("text=Let's hire your company.")).toBeVisible();
    await page.locator('input[placeholder*="B2B SaaS"]').fill("an e2e test project");
    await page.locator('input[placeholder*="acme-co"]').fill(orgName);
    await page.locator("button", { hasText: "Continue" }).click();

    await expect(page.locator("text=Here's what")).toBeVisible();
    await expect(page.locator(`text=${orgName}`).first()).toBeVisible();
    await page.locator("button", { hasText: "Continue" }).click();

    await expect(page.locator("text=Hiring your team.")).toBeVisible();

    await expect(page.locator("text=You have")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("text=four agents")).toBeVisible();
    await expect(page.locator("text=4 agents ready")).toBeVisible();
    await page.locator("button", { hasText: "Continue" }).click();

    await expect(page.locator("text=Where do you want to work today?")).toBeVisible();
    await expect(page.locator("text=Open in Dash")).toBeVisible();
    await expect(page.locator("text=Stay in the browser")).toBeVisible();
  });

  test("409 retry: duplicate org name surfaces an error and bounces to propose", async ({
    page,
    request,
  }) => {
    const orgName = `e2e-dup-${rnd()}`;

    // Seed the name via the API as a different user so the second-attempt
    // POST runs into a unique-name conflict regardless of which user the
    // platform frontend is acting as.
    await apiCreateOrg(request, {
      name: orgName,
      userId: `pre-${rnd()}`,
      email: `pre-${rnd()}@local`,
    });

    await page.goto(`${PLATFORM_URL}/onboarding`);
    await page.locator('input[placeholder*="acme-co"]').fill(orgName);
    await page.locator("button", { hasText: "Continue" }).click();
    await page.locator("button", { hasText: "Continue" }).click();

    await expect(page).toHaveURL(/\/onboarding\/propose/, { timeout: 15_000 });
    await expect(page.locator("text=/not available|exists|already|taken|unique/i")).toBeVisible({
      timeout: 5_000,
    });
  });
});
