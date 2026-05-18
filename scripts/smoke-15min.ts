#!/usr/bin/env -S npx tsx
// Stage-1 smoke test. Time-budget: 15 minutes wall clock; on a warm cache
// it should finish in <30s. Steps:
//
//   1. Spawn `crawfish-lens serve` on a free port + wait for /api/orgs.
//   2. POST a new org from the `startup` template into a tmp HOME.
//   3. POST a cron `run now` (member: founder, runtime: claude-code with
//      no network — just shells out, the `claude` CLI may not be present
//      in CI; if absent we still assert the cron *fired* by checking that
//      `last_run` got updated).
//   4. Assert a `task_commented` event lands in board.jsonl within 60s of
//      the cron fire (the runtime may return an error comment if `claude`
//      isn't installed — that's still a board event).
//   5. Total wall clock ≤ 15 min — exit non-zero otherwise.
//
// Usage:  npx tsx scripts/smoke-15min.ts

import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, existsSync, readFileSync, writeFileSync, mkdirSync, copyFileSync, readdirSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");
const LENS_DIR = join(REPO_ROOT, "desktop", "lens");
const TEMPLATES_DIR = join(REPO_ROOT, "desktop", "dash", "src", "templates");

const TIME_BUDGET_MS = 15 * 60 * 1000;
const startedAt = Date.now();

function elapsed(): number { return Date.now() - startedAt; }
function log(msg: string) { console.log(`[${(elapsed() / 1000).toFixed(1)}s] ${msg}`); }
function die(msg: string): never {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}

async function freePort(): Promise<number> {
  const { default: net } = await import("node:net");
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(0, () => {
      const addr = s.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      s.close(() => resolve(port));
    });
  });
}

function copyDir(src: string, dst: string) {
  mkdirSync(dst, { recursive: true });
  for (const e of readdirSync(src, { withFileTypes: true })) {
    const s = join(src, e.name);
    const d = join(dst, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else copyFileSync(s, d);
  }
}

async function main() {
  const HOME = mkdtempSync(join(tmpdir(), "crawfish-smoke-"));
  process.env.HOME = HOME;
  process.env.USERPROFILE = HOME;
  log(`HOME=${HOME}`);

  // 1. Plant a fresh org from the `startup` template under ~/.crawfish/orgs/.
  const ORG_ID = "smoke-startup";
  const orgRoot = join(HOME, ".crawfish", "orgs", ORG_ID);
  const tplRoot = join(TEMPLATES_DIR, "startup");
  copyDir(tplRoot, orgRoot);
  // Promote template.json → org.json so the server treats this as a real org.
  if (existsSync(join(orgRoot, "template.json"))) {
    const cfg = JSON.parse(readFileSync(join(orgRoot, "template.json"), "utf8"));
    cfg.id = ORG_ID;
    cfg.name = "Smoke Startup";
    cfg.created_at = new Date().toISOString();
    writeFileSync(join(orgRoot, "org.json"), JSON.stringify(cfg, null, 2));
  }
  log(`org ${ORG_ID} planted`);

  // 2. Start lens on a free port (use tsx — no build required).
  const PORT = await freePort();
  log(`spawning lens on port ${PORT}`);
  const lens: ChildProcess = spawn(
    "npx",
    ["tsx", "src/index.ts", "serve", "--port", String(PORT), "--no-open"],
    {
      cwd: LENS_DIR,
      env: { ...process.env, HOME, USERPROFILE: HOME },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  lens.stdout?.on("data", (b) => process.stdout.write(`[lens] ${b}`));
  lens.stderr?.on("data", (b) => process.stderr.write(`[lens] ${b}`));

  const teardown = () => {
    try { lens.kill("SIGTERM"); } catch { /* */ }
  };
  process.on("exit", teardown);
  process.on("SIGINT", () => { teardown(); process.exit(130); });

  // 3. Wait until the lens responds.
  const BASE = `http://127.0.0.1:${PORT}`;
  let ready = false;
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`${BASE}/api/orgs`);
      if (r.ok) { ready = true; break; }
    } catch { /* not yet */ }
    await sleep(500);
  }
  if (!ready) die("lens never came up");
  log("lens responding");

  // 4. Verify the org is visible.
  const orgs = await (await fetch(`${BASE}/api/orgs`)).json() as { orgs: Array<{ id: string }> };
  if (!orgs.orgs.some((o) => o.id === ORG_ID)) die(`org ${ORG_ID} not listed`);
  log(`org listed (${orgs.orgs.length} total)`);

  // 5. Fire the daily-standup cron.
  const crons = JSON.parse(readFileSync(join(orgRoot, "crons.json"), "utf8")) as { crons: Array<{ id: string }> };
  const cronId = crons.crons[0]?.id;
  if (!cronId) die("no cron in template");
  log(`firing cron ${cronId}`);

  const fireRes = await fetch(`${BASE}/api/orgs/${ORG_ID}/crons/${cronId}/run`, { method: "POST" });
  if (!fireRes.ok) {
    const text = await fireRes.text().catch(() => "");
    die(`cron fire returned ${fireRes.status}: ${text}`);
  }

  // 6. Poll board.jsonl for the resulting comment event (claude CLI may
  // not exist; cron still records an error comment).
  const boardPath = join(orgRoot, "board.jsonl");
  let foundComment = false;
  const cutoff = Date.now() + 60_000;
  while (Date.now() < cutoff) {
    if (existsSync(boardPath)) {
      const raw = readFileSync(boardPath, "utf8");
      const lines = raw.split("\n").filter(Boolean);
      for (const line of lines.slice(-20)) {
        try {
          const ev = JSON.parse(line) as { type?: string; task_id?: string };
          if (ev.type === "task_commented" && ev.task_id?.startsWith(`cron-${cronId}`)) {
            foundComment = true;
            break;
          }
        } catch { /* skip */ }
      }
    }
    if (foundComment) break;
    await sleep(500);
  }
  if (!foundComment) die("no task_commented event emitted by cron within 60s");
  log("cron output landed on board");

  // 7. Time budget check.
  if (elapsed() > TIME_BUDGET_MS) die(`smoke exceeded ${TIME_BUDGET_MS / 1000}s budget`);

  log(`SMOKE GREEN — total ${(elapsed() / 1000).toFixed(1)}s`);
  teardown();
  process.exit(0);
}

main().catch((e) => die(String(e?.message ?? e)));
