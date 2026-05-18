/**
 * Umbrella E2E config.
 *
 * Covers crawfish-platform (5174), crawfish-dash web (7881), the dash node
 * API (7880), and crawfish-server (7882) all from one place.
 *
 * IMPORTANT: this config does NOT start the surfaces. You must run
 *   ./dev.sh
 * from the repo root in a separate terminal first. Tests that try to talk
 * to a down surface fail with ECONNREFUSED.
 *
 * SQLite + the dash on-disk org dir are shared state, so the suite is
 * serialized: fullyParallel:false, workers:1. globalSetup resets both.
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  globalSetup: "./global-setup.ts",
  use: {
    baseURL: "http://localhost:5174",
    trace: "on-first-retry",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
