/**
 * Contract-test harness.
 *
 * Wipes the dev SQLite DB before the suite runs, then imports the Express
 * `app` from src/index.ts. All specs share this single in-process app so we
 * never bind a TCP port (supertest gives us its own ephemeral one per call).
 *
 * Tests run sequentially (vitest.config.ts: singleFork, fileParallelism off)
 * so the shared DB state is predictable.
 */
import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { beforeAll, afterAll } from "vitest";
import supertest from "supertest";

// Force dev-mode auth shim: even though .env may set a real Clerk key, the
// middleware currently TODOs the real verification and falls through to the
// X-User-Id header path. Unsetting here keeps the intent explicit.
process.env.CLERK_SECRET_KEY = "";
process.env.NODE_ENV = "test";
// Isolate the test DB from the dev DB. The harness force-resets the database
// in beforeAll; pointing it at a dedicated file means running tests no longer
// wipes `dev.db` (or disrupts a running `npm run dev` server). Set before the
// db-push execSync (which inherits process.env) and before src/index.js
// constructs PrismaClient.
process.env.DATABASE_URL = "file:./test.db";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const serverRoot = path.resolve(__dirname, "..", "..");

beforeAll(() => {
  // Wipe + recreate the dev SQLite schema. This is a contract suite, not a
  // unit suite — we want the database in a known clean state per run.
  execSync("npx prisma db push --force-reset --skip-generate", {
    cwd: serverRoot,
    stdio: "pipe",
    env: { ...process.env },
  });
});

// Dynamic import after the DB reset so PrismaClient constructs against a
// fresh schema.
const { app, db } = await import("../../src/index.js");

afterAll(async () => {
  await db.$disconnect();
});

export { app, db };

export function client() {
  return supertest(app);
}

/**
 * Attach dev-auth headers to a supertest request. `email` is optional but
 * required for invite-accept flows where the server compares the signed-in
 * user's email against the invite recipient.
 */
export function asUser<T extends { set: (h: string, v: string) => T }>(
  req: T,
  userId: string,
  email?: string,
): T {
  req.set("X-User-Id", userId);
  if (email) req.set("X-User-Email", email);
  return req;
}
