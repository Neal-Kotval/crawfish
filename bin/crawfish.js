#!/usr/bin/env node
/**
 * crawfish — one-command launcher for the local platform.
 *
 *   $ npx crawfish
 *
 * Boots crawfish-lens (port 7878) + crawfish-dash (port 7880), opens the
 * dashboard in the user's browser, and prints status to stderr. SIGINT/
 * SIGTERM cleanly shut down both children.
 *
 * Resolution order for finding the lens/dash dist files:
 *   1. ../desktop/<name>/dist/index.js (umbrella checkout — what we use today)
 *   2. node_modules/<name>/dist/index.js (future: separate npm packages)
 *   3. ./vendor/<name>/dist/index.js (future: bundled npm package)
 *
 * The first form is what works in this repo today. The other two are
 * stubs for when we publish — the launcher itself doesn't change.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { argv, exit, platform } from "node:process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

// ─── locate dist entries ─────────────────────────────────────────────────

function findEntry(pkgName, desktopName) {
  const candidates = [
    resolve(ROOT, "desktop", desktopName, "dist", "index.js"),
    resolve(ROOT, "node_modules", pkgName, "dist", "index.js"),
    resolve(ROOT, "vendor", pkgName, "dist", "index.js"),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

const lensEntry = findEntry("crawfish-lens", "lens");
const dashEntry = findEntry("crawfish-dash", "dash");

if (!lensEntry || !dashEntry) {
  console.error(
    "crawfish: couldn't locate built lens/dash. Run from the umbrella checkout with both submodules built:",
  );
  console.error("");
  console.error("    git clone --recurse-submodules https://github.com/Neal-Kotval/crawfish.git");
  console.error("    cd crawfish && npm run build && npx crawfish");
  console.error("");
  console.error(`Looked in:`);
  console.error(`  - ${resolve(ROOT, "desktop/lens/dist/index.js")}`);
  console.error(`  - ${resolve(ROOT, "desktop/dash/dist/index.js")}`);
  exit(1);
}

// ─── parse flags ─────────────────────────────────────────────────────────

const args = argv.slice(2);
const flags = {
  lensPort: 7878,
  dashPort: 7880,
  open: true,
  installHook: false,
  uninstallHook: false,
  showHelp: false,
};
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--no-open") flags.open = false;
  else if (a === "--lens-port") flags.lensPort = Number(args[++i]);
  else if (a === "--dash-port") flags.dashPort = Number(args[++i]);
  else if (a === "--install-hook") flags.installHook = true;
  else if (a === "--uninstall-hook") flags.uninstallHook = true;
  else if (a === "-h" || a === "--help") flags.showHelp = true;
}

if (flags.showHelp) {
  console.log(`crawfish — local token observability + policy enforcement

Usage:
  npx crawfish                          start the platform
  npx crawfish --no-open                don't auto-open the browser
  npx crawfish --lens-port 7878         override lens port
  npx crawfish --dash-port 7880         override dash port
  npx crawfish --install-hook           install the PreToolUse hook into ~/.claude/settings.json
  npx crawfish --uninstall-hook         remove the hook
  npx crawfish --help                   this message

What it does:
  • lens server on http://127.0.0.1:7878 — reads ~/.claude/projects transcripts
  • dash server on http://127.0.0.1:7880 — UI, opens in your browser
  • Both bind to 127.0.0.1 only. Nothing leaves your machine.
`);
  exit(0);
}

// ─── one-shot hook commands (no daemon) ───────────────────────────────────

if (flags.installHook || flags.uninstallHook) {
  const cmd = flags.installHook ? "install-hooks" : "uninstall-hooks";
  const hookCommand = resolve(
    ROOT,
    "desktop",
    "dash",
    "dist",
    "policy",
    "hook.js",
  );
  const proc = spawn(
    process.execPath,
    [dashEntry, cmd, "--command", hookCommand, "--yes"],
    { stdio: "inherit" },
  );
  proc.on("exit", (code) => exit(code ?? 0));
  // wait — handled by exit()
} else {
  startBoth();
}

// ─── start both ──────────────────────────────────────────────────────────

function startBoth() {
  process.stderr.write("crawfish — starting…\n");

  const lens = spawn(
    process.execPath,
    [lensEntry, "serve", "--no-open", "--port", String(flags.lensPort)],
    { stdio: ["ignore", "inherit", "inherit"] },
  );
  const dash = spawn(
    process.execPath,
    [dashEntry, "serve", "--no-open", "--port", String(flags.dashPort)],
    { stdio: ["ignore", "inherit", "inherit"] },
  );

  let exiting = false;
  function shutdown(reason) {
    if (exiting) return;
    exiting = true;
    process.stderr.write(`\ncrawfish — shutting down (${reason})…\n`);
    try {
      lens.kill("SIGTERM");
    } catch {}
    try {
      dash.kill("SIGTERM");
    } catch {}
  }

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));

  let lensExit = null;
  let dashExit = null;
  lens.on("exit", (c) => {
    lensExit = c;
    if (!exiting) shutdown(`lens exited ${c}`);
    if (dashExit !== null) exit(c ?? 0);
  });
  dash.on("exit", (c) => {
    dashExit = c;
    if (!exiting) shutdown(`dash exited ${c}`);
    if (lensExit !== null) exit(c ?? 0);
  });

  // Wait until dash answers before opening the browser. Avoids the
  // browser landing on a ECONNREFUSED page.
  const dashUrl = `http://127.0.0.1:${flags.dashPort}`;
  if (flags.open) {
    waitForReady(`${dashUrl}/api/health`, 15_000)
      .then(() => openInBrowser(dashUrl))
      .catch(() => {
        process.stderr.write(
          `crawfish — dash didn't come up at ${dashUrl}. Check logs above.\n`,
        );
      });
  }

  // Friendly banner once both are up.
  Promise.all([
    waitForReady(`${dashUrl}/api/health`, 15_000),
    waitForReady(`http://127.0.0.1:${flags.lensPort}/api/health`, 15_000),
  ])
    .then(() => {
      process.stderr.write(`\n`);
      process.stderr.write(`  crawfish ready\n`);
      process.stderr.write(`    dashboard: ${dashUrl}\n`);
      process.stderr.write(
        `    lens:      http://127.0.0.1:${flags.lensPort}\n`,
      );
      process.stderr.write(`\n`);
      process.stderr.write(`  Ctrl-C to stop.\n\n`);
    })
    .catch(() => {});
}

async function waitForReady(url, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      /* keep polling */
    }
    await new Promise((res) => setTimeout(res, 200));
  }
  throw new Error(`timeout waiting for ${url}`);
}

function openInBrowser(url) {
  const cmd =
    platform === "darwin"
      ? `open ${JSON.stringify(url)}`
      : platform === "win32"
        ? `start "" ${JSON.stringify(url)}`
        : `xdg-open ${JSON.stringify(url)}`;
  spawn(cmd, { shell: true, stdio: "ignore", detached: true }).unref();
}
