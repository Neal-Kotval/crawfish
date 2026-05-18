/**
 * Dash account page.
 *
 * Clicking the titlebar avatar navigates to /settings/account, which
 * renders the AccountPanel with the linked email and an Unlink button.
 * Unlinking returns the user to the SignInGate.
 */
import { test, expect } from "@playwright/test";
import { DASH_URL, seedDashIdentity } from "../helpers";

test("avatar opens /settings/account; Unlink restores the gate", async ({ page }) => {
  const email = "acct-user@example.com";
  await seedDashIdentity(page, email, "Acct User");

  await page.goto(`${DASH_URL}/canvas`);
  await expect(page.locator(".cfp-shell")).toBeVisible({ timeout: 10_000 });

  await page.locator(".cfp-titlebar__avatar").click();
  await expect(page).toHaveURL(/\/settings\/account/, { timeout: 10_000 });

  // Email + Unlink button render in the account panel.
  await expect(page.locator(`text=${email}`).first()).toBeVisible();
  const unlink = page.locator('button:has-text("Unlink")');
  await expect(unlink).toBeVisible();
  await unlink.click();

  // Reload so the App component re-reads localStorage on mount.
  await page.reload();
  await expect(page.locator('[data-testid="signin-gate"]')).toBeVisible({ timeout: 10_000 });
});
