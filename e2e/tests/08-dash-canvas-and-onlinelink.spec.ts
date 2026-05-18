/**
 * Dash canvas + OnlineLink titlebar pill.
 *
 * 1. Seed a linked identity + a local dash org via the dash node API.
 *    Navigate to /canvas?org=<id> and assert the 4 default agents render.
 * 2. Mock /api/orgs/:id/link and /api/orgs/:id/link/:code/status with
 *    page.route() so the OnlineLink flow transitions ● Linked → ● Online
 *    deterministically, without hitting the real device-link endpoints.
 */
import { test, expect } from "@playwright/test";
import { DASH_URL, dashCreateLocalOrg, seedDashIdentity, rnd } from "../helpers";

test.describe("dash canvas + OnlineLink", () => {
  test("canvas renders 4 default agents for a local org", async ({ page, request }) => {
    const orgName = `e2e-d-${rnd()}`;
    await seedDashIdentity(page, "dash@example.com", "Dash User");
    const org = await dashCreateLocalOrg(request, { name: orgName });

    await page.goto(`${DASH_URL}/canvas?org=${org.id}`);
    await expect(page.locator(".cfp-shell")).toBeVisible({ timeout: 10_000 });

    for (const agent of ["Eng-bot", "Designer-bot", "Support-bot", "Ops-bot"]) {
      await expect(page.locator(`text=${agent}`).first()).toBeVisible({ timeout: 10_000 });
    }
  });

  test("OnlineLink pill transitions ● Linked → ● Online via mocked endpoints", async ({
    page,
    request,
  }) => {
    const orgName = `e2e-link-${rnd()}`;
    await seedDashIdentity(page, "link@example.com", "Link User");
    const org = await dashCreateLocalOrg(request, { name: orgName });

    const code = "ABC123";
    let statusPolls = 0;

    await page.route(
      new RegExp(`/api/orgs/${org.id}/link$`),
      async (route, req) => {
        if (req.method() !== "POST") return route.fallback();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ code, verifyUrl: "about:blank" }),
        });
      },
    );

    await page.route(
      new RegExp(`/api/orgs/${org.id}/link/${code}/status$`),
      async (route) => {
        statusPolls += 1;
        // Resolve as redeemed on the very first poll so the UI advances.
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            redeemed: true,
            org: { name: orgName },
            user: { email: "link@example.com", name: "Link User" },
            linkedAt: new Date().toISOString(),
          }),
        });
      },
    );

    // online-status starts as offline so the Make-online button is visible.
    await page.route(
      new RegExp(`/api/orgs/${org.id}/online-status$`),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ online: false }),
        });
      },
    );

    await page.goto(`${DASH_URL}/canvas?org=${org.id}`);
    await expect(page.locator(".cfp-shell")).toBeVisible({ timeout: 10_000 });

    const makeOnline = page.locator('button:has-text("Make online")');
    await expect(makeOnline).toBeVisible({ timeout: 10_000 });
    await makeOnline.click();

    // ● Linked appears once the polled status returns redeemed=true.
    await expect(page.locator("text=● Linked")).toBeVisible({ timeout: 15_000 });

    // After 3s the toast collapses to ● Online.
    await expect(page.locator("text=● Online")).toBeVisible({ timeout: 8_000 });

    expect(statusPolls).toBeGreaterThan(0);
  });
});
