import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/contract/**/*.spec.ts"],
    environment: "node",
    globals: false,
    // Run sequentially — all specs share the dev SQLite db that setup.ts wipes.
    fileParallelism: false,
    setupFiles: ["tests/contract/setup.ts"],
    testTimeout: 30_000,
    hookTimeout: 60_000,
  },
});
