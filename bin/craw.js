#!/usr/bin/env node
/**
 * craw — single user-facing shorthand for crawfish per-project commands.
 *
 *   $ craw init
 *   $ craw refresh
 *   $ craw status
 *   $ craw doctor
 *   $ craw decision <args>
 *   $ craw activity <args>
 *   $ craw memory   <args>
 *   $ craw install-hooks
 *
 * Dispatches to crawfish-projectctl. Resolution order:
 *   1. ../crawfish-projectctl/dist/index.js (umbrella checkout — today)
 *   2. node_modules/crawfish-projectctl/dist/index.js (future npm publish)
 *
 * Signals propagate to the child via spawn (not spawnSync).
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { argv, execPath, exit, stderr, stdout } from "node:process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

// ─── verb table ──────────────────────────────────────────────────────────

const VERBS = {
  init: "init",
  refresh: "refresh",
  status: "status",
  doctor: "doctor",
  decision: "decision-add",
  activity: "activity-record",
  memory: "memory-append",
  "install-hooks": "install-hooks",
};

const HOMEPAGE = "https://github.com/Neal-Kotval/crawfish";

function printHelp(stream) {
  const lines = [
    "craw — shorthand for crawfish per-project commands",
    "",
    "Usage:",
    "  craw init                  scaffold .crawfish/ in the current repo",
    "  craw refresh [files...]    re-index project state",
    "  craw status                show project status",
    "  craw doctor                diagnose project setup",
    "  craw decision <args>       record a decision (forwards to decision-add)",
    "  craw activity <args>       record activity (forwards to activity-record)",
    "  craw memory   <args>       append to memory (forwards to memory-append)",
    "  craw install-hooks         install git/claude hooks",
    "  craw --help | help         this message",
    "",
    `  ${HOMEPAGE}`,
    "",
  ];
  stream.write(lines.join("\n"));
}

// ─── locate projectctl entry ─────────────────────────────────────────────

function findEntry(pkgName) {
  const candidates = [
    resolve(ROOT, pkgName, "dist", "index.js"),
    resolve(ROOT, "node_modules", pkgName, "dist", "index.js"),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

// ─── parse ───────────────────────────────────────────────────────────────

const args = argv.slice(2);
const verb = args[0];
const rest = args.slice(1);

if (!verb || verb === "--help" || verb === "-h" || verb === "help") {
  printHelp(stdout);
  exit(0);
}

const forwarded = VERBS[verb];
if (!forwarded) {
  stderr.write(`craw: unknown command '${verb}'\n\n`);
  printHelp(stderr);
  exit(1);
}

const entry = findEntry("crawfish-projectctl");
if (!entry) {
  stderr.write(
    "craw: couldn't locate crawfish-projectctl. Build it first:\n",
  );
  stderr.write("    cd crawfish-projectctl && npm install && npm run build\n");
  exit(1);
}

// ─── spawn ───────────────────────────────────────────────────────────────

const child = spawn(execPath, [entry, forwarded, ...rest], {
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    // re-raise the signal so the parent shell sees the right exit status
    process.kill(process.pid, signal);
  } else {
    exit(code ?? 0);
  }
});
