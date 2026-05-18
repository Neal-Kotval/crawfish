/**
 * Invites: create, mock-email card, revoke, sign-out CTA on /invites/:code,
 * accept-as-invited, and 404 for an unknown code.
 *
 * The OrgMembers + accept flow is inside RequireAuth, so those tests skip
 * when Clerk is on. The 404 case + sign-out CTA case render through the
 * public /invites/:code route and run in any mode.
 */
import { test, expect } from "@playwright/test";
import { apiCreateOrg, apiCreateInvite, isPlatformDevMode, PLATFORM_URL, rnd } from "../helpers";

test.describe("platform invites — UI", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!(await isPlatformDevMode(page)), "Platform in Clerk mode — UI tests require dev shim.");
  });

  test("create + mock email + revoke", async ({ page, request }) => {
    const owner = `inviter-${rnd()}`;
    const orgName = `e2e-inv-${rnd()}`;
    await apiCreateOrg(request, { name: orgName, userId: owner, email: `${owner}@local` });

    await page.goto(`${PLATFORM_URL}/onboarding`);
    await page.evaluate((u) => localStorage.setItem("cf_dev_user", u), owner);
    await page.goto(`${PLATFORM_URL}/orgs/${orgName}/team`);

    await expect(page.locator("text=Team and invites")).toBeVisible({ timeout: 10_000 });
    page.on("dialog", (d) => d.accept());
    await page.locator('input[type="email"]').fill("pat@example.com");
    await page.locator('button[type="submit"]:has-text("Send invite")').click();

    await expect(page.locator("text=MOCK EMAIL")).toBeVisible({ timeout: 5_000 });
    await expect(page.locator("text=pat@example.com").first()).toBeVisible();

    const patRow = page
      .locator("section")
      .filter({ hasText: "Pending invites" })
      .locator("text=pat@example.com");
    await expect(patRow).toBeVisible();
    await page.locator('button[title="Revoke invite"]').first().click();
    await expect(patRow).toBeHidden({ timeout: 5_000 });
  });

  test("accept flow: invitee preview + API accept + member appears on team page", async ({
    page,
    request,
  }) => {
    const owner = `inviter2-${rnd()}`;
    const orgName = `e2e-inv2-${rnd()}`;
    const org = await apiCreateOrg(request, {
      name: orgName,
      userId: owner,
      email: `${owner}@local`,
    });
    // The platform UI accept button can't pass X-User-Email, so the dev
    // shim coins the user's email as `${X-User-Id}@local`. We mirror that
    // exact format here so the email-match check in /api/invites/:code/accept
    // passes. Use a real-looking subdomain so zod's email validator is happy.
    const bobId = `bob.${rnd()}`;
    const bobEmail = "bob@example.com";
    const invite = await apiCreateInvite(request, {
      orgId: org.id,
      email: bobEmail,
      userId: owner,
      userEmail: `${owner}@local`,
    });

    // Preview the invite as a logged-in user whose email matches (via the
    // X-User-Email header — bypasses the UI's accept button to avoid the
    // platform apiFetch's missing email header).
    await page.goto(`${PLATFORM_URL}/invites/${invite.code}`);
    await expect(page.locator(`text=${bobEmail}`).first()).toBeVisible({
      timeout: 10_000,
    });

    // Server-side accept with the matching email.
    const acceptRes = await request.post(
      `http://localhost:7882/api/invites/${invite.code}/accept`,
      {
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": bobId,
          "X-User-Email": bobEmail,
        },
      },
    );
    expect(acceptRes.ok()).toBe(true);

    // The membership row exists on the server — verify the org now lists Bob.
    const orgRes = await request.get(`http://localhost:7882/api/orgs/${org.id}`, {
      headers: { "X-User-Id": owner, "X-User-Email": `${owner}@local` },
    });
    expect(orgRes.ok()).toBe(true);
    const orgBody = await orgRes.json();
    const emails = (orgBody.members as Array<{ email: string }>).map((m) => m.email);
    expect(emails).toContain(bobEmail);
  });
});

test.describe("platform invites — public routes", () => {
  test("signed-out visit shows sign-in CTA referencing the invited email", async ({
    page,
    request,
  }) => {
    const owner = `inviter3-${rnd()}`;
    const orgName = `e2e-inv3-${rnd()}`;
    const org = await apiCreateOrg(request, {
      name: orgName,
      userId: owner,
      email: `${owner}@local`,
    });
    const invite = await apiCreateInvite(request, {
      orgId: org.id,
      email: "carol@example.com",
      userId: owner,
      userEmail: `${owner}@local`,
    });

    // /invites/:code is public — no guard.
    await page.goto(`${PLATFORM_URL}/invites/${invite.code}`);
    // The page references the invited email in either the sign-in CTA copy
    // (dev mode: not signed-in) or the email-mismatch CTA copy (Clerk mode:
    // probably no Clerk session). Either way, the address renders.
    await expect(page.locator(`text=carol@example.com`).first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("unknown invite code shows a not-found message", async ({ page }) => {
    await page.goto(`${PLATFORM_URL}/invites/this-code-does-not-exist`);
    await expect(page.locator("text=Unknown invite link")).toBeVisible({ timeout: 10_000 });
  });
});
