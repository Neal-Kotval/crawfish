import { test, expect } from "@playwright/test";

const FAKE_RELEASE = {
  tag_name: "v9.9.9",
  html_url: "https://github.com/anthropics/crawfish/releases/tag/v9.9.9",
  assets: [
    {
      name: "Crawfish_9.9.9_aarch64.dmg",
      browser_download_url: "https://example.test/dl/Crawfish_9.9.9_aarch64.dmg",
    },
    {
      name: "Crawfish_9.9.9_x64.dmg",
      browser_download_url: "https://example.test/dl/Crawfish_9.9.9_x64.dmg",
    },
    {
      name: "Crawfish_9.9.9_amd64.AppImage",
      browser_download_url: "https://example.test/dl/Crawfish_9.9.9_amd64.AppImage",
    },
    {
      name: "Crawfish_9.9.9_x64.msi",
      browser_download_url: "https://example.test/dl/Crawfish_9.9.9_x64.msi",
    },
  ],
};

test.describe("Release fetch — happy path", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  test("primary button URL swaps to mocked .dmg asset", async ({ page, context }) => {
    await context.route("**/api.github.com/repos/**/releases/latest", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_RELEASE),
      });
    });

    await page.addInitScript(() => {
      try { window.localStorage.clear(); } catch { /* noop */ }
    });

    await page.goto("/");

    const primary = page.locator("a").filter({ hasText: /Download for Mac/ }).first();
    await expect(primary).toBeVisible();
    await expect.poll(async () => primary.getAttribute("href"), { timeout: 5000 })
      .toMatch(/example\.test\/dl\/.*\.dmg$/);
  });
});

test.describe("Release fetch — failure fallback", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });

  test("500 response falls back without crashing", async ({ page, context }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await context.route("**/api.github.com/repos/**/releases/latest", async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
    });

    await page.addInitScript(() => {
      try { window.localStorage.clear(); } catch { /* noop */ }
    });

    await page.goto("/");

    const primary = page.locator("a").filter({ hasText: /Download for Mac/ }).first();
    await expect(primary).toBeVisible();
    const href = await primary.getAttribute("href");
    expect(href).toBeTruthy();
    expect(href).toMatch(/github\.com\/.*\/releases/);

    // Page renders headline regardless
    await expect(page.locator("h1")).toContainText("fifteen minutes.");

    // Filter out 500-network noise (browser will log a failed fetch line); only fail on app-level errors.
    const appErrors = consoleErrors.filter(
      (e) => !/500|Failed to load resource|GitHub API/i.test(e)
    );
    expect(appErrors).toEqual([]);
  });
});
