import { test, expect } from "@playwright/test";

test.describe("Marketing index — hero + nav", () => {
  test("renders eyebrow and headline", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText("For the founder spinning up their first five agents")
    ).toBeVisible();
    await expect(page.locator("h1")).toContainText("Hire your");
    await expect(page.locator("h1")).toContainText("company in");
    await expect(page.locator("h1")).toContainText("fifteen minutes.");
  });

  test("Github nav link has correct href", async ({ page }) => {
    await page.goto("/");
    const gh = page.getByRole("link", { name: "Github" });
    await expect(gh).toHaveAttribute("href", "https://github.com/crawfish");
  });

  test("invite-teammate CTA links to onboarding/team", async ({ page }) => {
    await page.goto("/");
    const link = page.getByRole("link", { name: /Invite a teammate later/i });
    await expect(link).toHaveAttribute(
      "href",
      "https://app.crawfish.dev/onboarding/team"
    );
  });
});

test.describe("Platform detection — primary download label", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  test("mac UA shows Mac primary button", async ({ page }) => {
    await page.goto("/");
    const primary = page.locator("a, button").filter({ hasText: /Download for Mac/ }).first();
    await expect(primary).toBeVisible();
  });
});

test.describe("Platform detection — linux", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  test("linux UA shows Linux primary button", async ({ page }) => {
    await page.goto("/");
    const primary = page.locator("a, button").filter({ hasText: /Download for Linux/ }).first();
    await expect(primary).toBeVisible();
  });
});

test.describe("Platform detection — windows", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  test("windows UA shows Windows primary button", async ({ page }) => {
    await page.goto("/");
    const primary = page.locator("a, button").filter({ hasText: /Download for Windows/ }).first();
    await expect(primary).toBeVisible();
  });
});
