/**
 * globalSetup — wipe shared state before the suite runs.
 *
 *   1. Reset crawfish-server's SQLite DB by running prisma db push with
 *      --force-reset. This drops every Org / User / Invite from earlier
 *      runs so tests start from a known-empty slate.
 *   2. Remove any dash on-disk orgs created by prior e2e runs (their
 *      folders live under ~/crawfish/<name>/). We only remove folders
 *      whose names start with "e2e-" so we don't nuke the user's real
 *      orgs.
 *
 * If dev.sh isn't running, this won't fail by itself — but the actual
 * tests will, with ECONNREFUSED.
 */
import { execSync } from "node:child_process";
import { readdirSync, rmSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

export default async function globalSetup(): Promise<void> {
  const repoRoot = join(__dirname, "..");
  const serverDir = join(repoRoot, "crawfish-server");

  // 1. Reset the platform server DB.
  try {
    execSync("npx prisma db push --force-reset --skip-generate --accept-data-loss", {
      cwd: serverDir,
      stdio: "inherit",
      env: { ...process.env },
    });
  } catch (err) {
    console.warn("[e2e global-setup] prisma reset failed:", (err as Error).message);
  }

  // 2. Wipe stale dash on-disk e2e orgs.
  const orgsRoot = join(homedir(), "crawfish");
  if (existsSync(orgsRoot)) {
    try {
      for (const entry of readdirSync(orgsRoot)) {
        if (!entry.startsWith("e2e-")) continue;
        const full = join(orgsRoot, entry);
        try {
          if (statSync(full).isDirectory()) {
            rmSync(full, { recursive: true, force: true });
          }
        } catch {
          /* ignore */
        }
      }
    } catch (err) {
      console.warn("[e2e global-setup] dash org wipe failed:", (err as Error).message);
    }
  }
}
