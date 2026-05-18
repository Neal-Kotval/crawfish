/**
 * Dash sign-in gate.
 *
 * With no cf-linked-user in localStorage and no ?user= deep-link, dash
 * renders the SignInGate fullscreen and nothing else. Once we seed the
 * key, reload, and the shell renders.
 */
import { test, expect } from "@playwright/test";
import { DASH_URL, PLATFORM_URL, clearDashIdentity, seedDashIdentity } from "../helpers";

test.describe("dash sign-in gate", () => {
  test("renders gate when no linked user, hides shell", async ({ page }) => {
    await clearDashIdentity(page);
    await page.goto(`${DASH_URL}/canvas`);

    const gate = page.locator('[data-testid="signin-gate"]');
    await expect(gate).toBeVisible({ timeout: 10_000 });

    const portal = page.locator('[data-testid="signin-gate-portal"]');
    await expect(portal).toHaveAttribute("href", PLATFORM_URL);

    // The regular shell must not be in the DOM behind the gate.
    await expect(page.locator(".cfp-shell")).toHaveCount(0);
  });

  test("disappears after we seed cf-linked-user and reload", async ({ page }) => {
    await seedDashIdentity(page, "linked@example.com", "Linked User");
    await page.goto(`${DASH_URL}/canvas`);
    await expect(page.locator('[data-testid="signin-gate"]')).toHaveCount(0);
    await expect(page.locator(".cfp-shell")).toBeVisible({ timeout: 10_000 });
  });
});
