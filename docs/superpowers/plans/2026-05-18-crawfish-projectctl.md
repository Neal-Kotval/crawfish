# `crawfish-projectctl` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `.crawfish/` per-project folder format as a CLI engine, MCP server, and Claude Code hooks preset that any Crawfish user can install in their own repo.

**Architecture:** A single Node package, `crawfish-projectctl/`, sibling to the existing `crawfish-orgctl/`. The CLI is the engine — it reads `.crawfish/index.json`, walks declared source globs, computes stable hashes, and re-derives output `.md` files only when sources change. The MCP server and the install-hooks preset are thin wrappers over the same verbs.

**Tech Stack:** Node ≥20, TypeScript (ESM), `@modelcontextprotocol/sdk`, `zod`, `node:test` (mirrors `crawfish-orgctl/`'s exact toolchain). No new third-party dependencies beyond what `crawfish-orgctl/` already pulls in, plus `glob` for source-globbing and `commander` for CLI parsing.

**Scope:** Slices 1–3 and 5 from the spec (engine + MCP + hooks + reference fixtures). Slice 4 (Dash + platform consumers) lives in a follow-on plan once this format is shipped.

---

## File map

```
crawfish-projectctl/
├── package.json
├── tsconfig.json
├── tsconfig.test.json
├── README.md
├── src/
│   ├── index.ts                 # CLI entrypoint (commander)
│   ├── manifest.ts              # index.json read/write + zod schema
│   ├── hash.ts                  # stable source-hash over glob results
│   ├── redact.ts                # default + user-extended redaction
│   ├── lock.ts                  # .crawfish/.lock debounce primitive
│   ├── renderers/
│   │   ├── roadmap.ts           # .planning/ + ROADMAP.md → roadmap.md
│   │   ├── memory.ts            # ~/.claude/projects/<repo>/memory/ → memory.md
│   │   ├── context.ts           # context-mode stats → context.md
│   │   ├── decisions.ts         # append-only ADR log
│   │   └── activity.ts          # append from $CLAUDE_TRANSCRIPT_PATH
│   ├── verbs/
│   │   ├── init.ts
│   │   ├── refresh.ts           # orchestrator
│   │   ├── status.ts
│   │   ├── doctor.ts
│   │   ├── memory-append.ts
│   │   ├── decision-add.ts
│   │   ├── activity-record.ts
│   │   ├── install-hooks.ts
│   │   └── uninstall-hooks.ts
│   └── mcp/
│       └── server.ts            # MCP wrapper (slice 2)
├── test/
│   ├── manifest.test.ts
│   ├── hash.test.ts
│   ├── redact.test.ts
│   ├── lock.test.ts
│   ├── renderers/
│   │   ├── roadmap.test.ts
│   │   ├── memory.test.ts
│   │   ├── decisions.test.ts
│   │   └── activity.test.ts
│   ├── verbs/
│   │   ├── init.test.ts
│   │   ├── refresh.test.ts
│   │   └── install-hooks.test.ts
│   └── integration.test.ts      # full fixture-driven E2E
└── fixtures/
    ├── gsd-project/             # synthetic repo with .planning/
    └── plain-readme-project/    # synthetic repo with just ROADMAP.md
```

---

## Task 1: Scaffold the package

**Files:**
- Create: `crawfish-projectctl/package.json`
- Create: `crawfish-projectctl/tsconfig.json`
- Create: `crawfish-projectctl/tsconfig.test.json`
- Create: `crawfish-projectctl/README.md`
- Create: `crawfish-projectctl/src/index.ts` (stub)
- Create: `crawfish-projectctl/.gitignore`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "crawfish-projectctl",
  "version": "0.1.0",
  "description": "Per-project .crawfish/ folder engine for Crawfish — CLI + MCP server + hooks preset.",
  "type": "module",
  "bin": {
    "crawfish-projectctl": "dist/index.js",
    "crawfish-projectctl-mcp": "dist/mcp/server.js"
  },
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "typecheck": "tsc --noEmit",
    "test": "tsc -p tsconfig.test.json && node --test dist-test/test/**/*.test.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.4",
    "commander": "^12.1.0",
    "glob": "^11.0.0",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "typescript": "^5.6.0"
  },
  "engines": { "node": ">=20" },
  "keywords": ["mcp", "claude", "crawfish", "project-folder"],
  "license": "MIT",
  "crawfish-contract": "1.0"
}
```

- [ ] **Step 2: Create `tsconfig.json`** (mirror `crawfish-orgctl/tsconfig.json` exactly)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "declaration": false,
    "sourceMap": true,
    "lib": ["ES2022"]
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "dist-test", "test"]
}
```

- [ ] **Step 3: Create `tsconfig.test.json`**

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "outDir": "dist-test",
    "rootDir": ".",
    "noEmit": false
  },
  "include": ["src/**/*", "test/**/*"],
  "exclude": ["node_modules", "dist", "dist-test"]
}
```

- [ ] **Step 4: Create stub `src/index.ts`**

```typescript
#!/usr/bin/env node
import { Command } from "commander";

const program = new Command();
program.name("crawfish-projectctl").version("0.1.0");
program.parse();
```

- [ ] **Step 5: Create `.gitignore`**

```
node_modules
dist
dist-test
```

- [ ] **Step 6: Create stub `README.md`**

```markdown
# crawfish-projectctl

Per-project `.crawfish/` folder engine: CLI + MCP + hooks preset.

See `docs/superpowers/specs/2026-05-18-crawfish-project-folder-design.md`.
```

- [ ] **Step 7: Install + typecheck**

```
cd crawfish-projectctl && npm install && npm run typecheck
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add crawfish-projectctl/
git commit -m "chore(projectctl): scaffold package"
```

---

## Task 2: Manifest (`index.json`) read/write + zod schema

**Files:**
- Create: `crawfish-projectctl/src/manifest.ts`
- Test: `crawfish-projectctl/test/manifest.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// test/manifest.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readManifest, writeManifest, DEFAULT_MANIFEST } from "../src/manifest.js";

test("reads a manifest written to disk", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeManifest(dir, DEFAULT_MANIFEST);
  const got = readManifest(dir);
  assert.equal(got.schema, "crawfish-project/v1");
  assert.ok(got.files["roadmap.md"]);
});

test("rejects manifests with the wrong schema version", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, ".crawfish/index.json"), JSON.stringify({ schema: "crawfish-project/v999", files: {} }), { recursive: true } as never);
  assert.throws(() => readManifest(dir), /schema/);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test` from `crawfish-projectctl/`
Expected: FAIL — `Cannot find module '../src/manifest.js'`.

- [ ] **Step 3: Implement `src/manifest.ts`**

```typescript
import { z } from "zod";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";

export const SCHEMA_VERSION = "crawfish-project/v1";

const FileEntry = z.object({
  sources: z.array(z.string()),
  hash: z.string().optional(),
  enabled: z.boolean().default(true),
});

const Manifest = z.object({
  schema: z.literal(SCHEMA_VERSION),
  files: z.record(FileEntry),
  last_updated: z.string().optional(),
});

export type Manifest = z.infer<typeof Manifest>;
export type FileEntry = z.infer<typeof FileEntry>;

export const DEFAULT_MANIFEST: Manifest = {
  schema: SCHEMA_VERSION,
  files: {
    "memory.md": { sources: ["~/.claude/projects/**/memory/**/*.md"], enabled: true },
    "context.md": { sources: ["~/.claude/projects/**/sessions/**/*.jsonl"], enabled: true },
    "roadmap.md": { sources: [".planning/**/PLAN.md", ".planning/**/ROADMAP.md", "ROADMAP.md"], enabled: true },
    "decisions.md": { sources: [], enabled: true },
    "activity.md": { sources: [], enabled: false },
  },
};

function manifestPath(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "index.json");
}

export function readManifest(repoRoot: string): Manifest {
  const raw = readFileSync(manifestPath(repoRoot), "utf8");
  const parsed = JSON.parse(raw);
  return Manifest.parse(parsed);
}

export function writeManifest(repoRoot: string, manifest: Manifest): void {
  const path = manifestPath(repoRoot);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(manifest, null, 2) + "\n");
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/manifest.ts crawfish-projectctl/test/manifest.test.ts
git commit -m "feat(projectctl): manifest read/write with zod schema"
```

---

## Task 3: Stable source hashing

**Files:**
- Create: `crawfish-projectctl/src/hash.ts`
- Test: `crawfish-projectctl/test/hash.test.ts`

The hash function takes a list of glob patterns (relative to the repo root) plus the repo root, resolves them, reads each matched file, and returns a `sha256` over `(path, size, content)` tuples sorted by path. This is the dirty-detection primitive.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { hashSources } from "../src/hash.js";

function makeRepo(): string {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".planning"), { recursive: true });
  writeFileSync(join(dir, ".planning", "PLAN.md"), "phase 1");
  writeFileSync(join(dir, "ROADMAP.md"), "milestone A");
  return dir;
}

test("hash is stable across runs for unchanged sources", async () => {
  const dir = makeRepo();
  const h1 = await hashSources(dir, [".planning/**/PLAN.md", "ROADMAP.md"]);
  const h2 = await hashSources(dir, [".planning/**/PLAN.md", "ROADMAP.md"]);
  assert.equal(h1, h2);
});

test("hash changes when a source file changes", async () => {
  const dir = makeRepo();
  const h1 = await hashSources(dir, ["ROADMAP.md"]);
  writeFileSync(join(dir, "ROADMAP.md"), "milestone B");
  const h2 = await hashSources(dir, ["ROADMAP.md"]);
  assert.notEqual(h1, h2);
});

test("hash is independent of glob ordering", async () => {
  const dir = makeRepo();
  const h1 = await hashSources(dir, ["ROADMAP.md", ".planning/**/PLAN.md"]);
  const h2 = await hashSources(dir, [".planning/**/PLAN.md", "ROADMAP.md"]);
  assert.equal(h1, h2);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL — `Cannot find module '../src/hash.js'`.

- [ ] **Step 3: Implement `src/hash.ts`**

```typescript
import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { glob } from "glob";
import { homedir } from "node:os";
import { join } from "node:path";

function expandHome(p: string): string {
  return p.startsWith("~/") ? join(homedir(), p.slice(2)) : p;
}

export async function hashSources(repoRoot: string, patterns: string[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of patterns) {
    const expanded = expandHome(pattern);
    const cwd = expanded.startsWith("/") ? "/" : repoRoot;
    const rel = expanded.startsWith("/") ? expanded.slice(1) : expanded;
    const files = await glob(rel, { cwd, nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  const sorted = [...matched].sort();
  const h = createHash("sha256");
  for (const path of sorted) {
    const size = statSync(path).size;
    const content = readFileSync(path);
    h.update(path);
    h.update(String(size));
    h.update(content);
    h.update("\x00");
  }
  return "sha256:" + h.digest("hex");
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on all three tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/hash.ts crawfish-projectctl/test/hash.test.ts
git commit -m "feat(projectctl): stable source hashing for dirty detection"
```

---

## Task 4: Redaction pass

**Files:**
- Create: `crawfish-projectctl/src/redact.ts`
- Test: `crawfish-projectctl/test/redact.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { redact } from "../src/redact.js";

test("redacts a stripe-style secret key", () => {
  const out = redact("token sk_live_abcdefghijklmnopqrstuvwx hi", []);
  assert.match(out, /\[REDACTED\]/);
  assert.doesNotMatch(out, /sk_live_abcdef/);
});

test("redacts an OpenAI-style key", () => {
  const out = redact("OPENAI_API_KEY=sk-proj-aaaaaaaaaaaaaaaaaaaaaaaa", []);
  assert.match(out, /\[REDACTED\]/);
});

test("user-supplied patterns extend the default set", () => {
  const out = redact("internal-token-XYZ", [/internal-token-[A-Z]+/]);
  assert.match(out, /\[REDACTED\]/);
});

test("leaves normal prose alone", () => {
  const out = redact("the quick brown fox", []);
  assert.equal(out, "the quick brown fox");
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL — `Cannot find module '../src/redact.js'`.

- [ ] **Step 3: Implement `src/redact.ts`**

```typescript
const DEFAULT_PATTERNS: RegExp[] = [
  /sk-(proj-)?[A-Za-z0-9_-]{20,}/g,
  /sk_live_[A-Za-z0-9]{16,}/g,
  /sk_test_[A-Za-z0-9]{16,}/g,
  /xox[baprs]-[A-Za-z0-9-]{10,}/g,                // Slack
  /ghp_[A-Za-z0-9]{30,}/g,                         // GitHub PAT
  /AKIA[0-9A-Z]{16}/g,                             // AWS access key
  /AIza[0-9A-Za-z_-]{30,}/g,                       // Google
  /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, // JWT
];

export function redact(text: string, userPatterns: RegExp[]): string {
  let out = text;
  for (const p of [...DEFAULT_PATTERNS, ...userPatterns]) {
    out = out.replace(p, "[REDACTED]");
  }
  return out;
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on all four tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/redact.ts crawfish-projectctl/test/redact.test.ts
git commit -m "feat(projectctl): default secret-pattern redaction pass"
```

---

## Task 5: Lockfile + debounce

**Files:**
- Create: `crawfish-projectctl/src/lock.ts`
- Test: `crawfish-projectctl/test/lock.test.ts`

Semantics: `acquireLock(repoRoot, debounceMs)` returns `null` if a recent lock exists (less than `debounceMs` ago), or a release function. The lock file records its acquisition timestamp.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { acquireLock } from "../src/lock.js";

test("second acquire within debounce window returns null", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  const first = acquireLock(dir, 60_000);
  assert.ok(first, "first acquire should succeed");
  const second = acquireLock(dir, 60_000);
  assert.equal(second, null, "second acquire inside window should be null");
  first!.release();
});

test("acquire after release works", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  const first = acquireLock(dir, 0);
  first!.release();
  const second = acquireLock(dir, 0);
  assert.ok(second);
  second!.release();
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL — `Cannot find module '../src/lock.js'`.

- [ ] **Step 3: Implement `src/lock.ts`**

```typescript
import { readFileSync, writeFileSync, existsSync, unlinkSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";

export interface Lock {
  release: () => void;
}

function lockPath(repoRoot: string): string {
  return join(repoRoot, ".crawfish", ".lock");
}

export function acquireLock(repoRoot: string, debounceMs: number): Lock | null {
  const path = lockPath(repoRoot);
  mkdirSync(dirname(path), { recursive: true });
  if (existsSync(path)) {
    try {
      const raw = readFileSync(path, "utf8");
      const { ts } = JSON.parse(raw) as { ts: number };
      const ageMs = Date.now() - ts;
      if (ageMs < debounceMs) return null;
    } catch {
      // corrupt lock — overwrite
    }
  }
  writeFileSync(path, JSON.stringify({ ts: Date.now(), pid: process.pid }));
  return {
    release() {
      try { unlinkSync(path); } catch { /* already gone */ }
    },
  };
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/lock.ts crawfish-projectctl/test/lock.test.ts
git commit -m "feat(projectctl): lockfile debounce primitive"
```

---

## Task 6: `init` verb

**Files:**
- Create: `crawfish-projectctl/src/verbs/init.ts`
- Test: `crawfish-projectctl/test/verbs/init.test.ts`

Behavior: writes `.crawfish/index.json` from `DEFAULT_MANIFEST` plus empty stubs for each enabled file. Idempotent — if `.crawfish/` exists, leaves it alone and prints a notice (returns `"existed"`); otherwise creates and returns `"created"`.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";

test("creates .crawfish/ on first run", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  const result = init(dir);
  assert.equal(result, "created");
  assert.ok(existsSync(join(dir, ".crawfish/index.json")));
  assert.ok(existsSync(join(dir, ".crawfish/memory.md")));
  assert.ok(existsSync(join(dir, ".crawfish/roadmap.md")));
});

test("is idempotent — second run reports existed", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  init(dir);
  const result = init(dir);
  assert.equal(result, "existed");
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL — `Cannot find module '../../src/verbs/init.js'`.

- [ ] **Step 3: Implement `src/verbs/init.ts`**

```typescript
import { existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { writeManifest, DEFAULT_MANIFEST } from "../manifest.js";

export type InitResult = "created" | "existed";

export function init(repoRoot: string): InitResult {
  const dir = join(repoRoot, ".crawfish");
  if (existsSync(dir)) return "existed";
  mkdirSync(dir, { recursive: true });
  writeManifest(repoRoot, DEFAULT_MANIFEST);
  for (const [filename, entry] of Object.entries(DEFAULT_MANIFEST.files)) {
    if (!entry.enabled) continue;
    writeFileSync(
      join(dir, filename),
      `# ${filename.replace(".md", "")}\n\n_Pending first refresh._\n`,
    );
  }
  return "created";
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/verbs/init.ts crawfish-projectctl/test/verbs/init.test.ts
git commit -m "feat(projectctl): init verb writes .crawfish scaffold"
```

---

## Task 7: `roadmap.md` renderer

**Files:**
- Create: `crawfish-projectctl/src/renderers/roadmap.ts`
- Test: `crawfish-projectctl/test/renderers/roadmap.test.ts`

Signature: `renderRoadmap(repoRoot: string, sources: string[]): Promise<string>`. Walks the source globs, groups results by directory, and emits a markdown summary that lists each source file with its first-heading text.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderRoadmap } from "../../src/renderers/roadmap.js";

test("renders headings from .planning/ PLAN.md files", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".planning", "P1"), { recursive: true });
  writeFileSync(join(dir, ".planning", "P1", "PLAN.md"), "# Phase 1 — auth\n\nbody");
  const md = await renderRoadmap(dir, [".planning/**/PLAN.md"]);
  assert.match(md, /Phase 1 — auth/);
  assert.match(md, /\.planning\/P1\/PLAN\.md/);
});

test("falls back to a single-source render for a plain ROADMAP.md", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# Roadmap\n\nMilestone A");
  const md = await renderRoadmap(dir, ["ROADMAP.md"]);
  assert.match(md, /Roadmap/);
});

test("emits a graceful empty state when no sources exist", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  const md = await renderRoadmap(dir, [".planning/**/PLAN.md"]);
  assert.match(md, /no roadmap sources/i);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL — `Cannot find module '../../src/renderers/roadmap.js'`.

- [ ] **Step 3: Implement `src/renderers/roadmap.ts`**

```typescript
import { glob } from "glob";
import { readFileSync } from "node:fs";
import { relative } from "node:path";

function firstHeading(text: string): string {
  for (const line of text.split("\n")) {
    if (line.startsWith("# ")) return line.slice(2).trim();
  }
  return "(no heading)";
}

export async function renderRoadmap(repoRoot: string, sources: string[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of sources) {
    const files = await glob(pattern, { cwd: repoRoot, nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  if (matched.size === 0) {
    return "# Roadmap\n\n_No roadmap sources found. Configure them in `.crawfish/index.json`._\n";
  }
  const sorted = [...matched].sort();
  const lines = ["# Roadmap", ""];
  for (const abs of sorted) {
    const rel = relative(repoRoot, abs);
    const heading = firstHeading(readFileSync(abs, "utf8"));
    lines.push(`## ${heading}`);
    lines.push(`Source: \`${rel}\``);
    lines.push("");
  }
  return lines.join("\n");
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on all three tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/renderers/roadmap.ts crawfish-projectctl/test/renderers/roadmap.test.ts
git commit -m "feat(projectctl): roadmap.md renderer"
```

---

## Task 8: `memory.md` renderer

**Files:**
- Create: `crawfish-projectctl/src/renderers/memory.ts`
- Test: `crawfish-projectctl/test/renderers/memory.test.ts`

Reads files under `~/.claude/projects/<repo-slug>/memory/` (when the source glob matches them). Concatenates with file-level headings; passes through the redaction pass.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderMemory } from "../../src/renderers/memory.js";

test("concatenates memory files and redacts secrets", async () => {
  const memDir = mkdtempSync(join(tmpdir(), "cfp-mem-"));
  writeFileSync(join(memDir, "feedback.md"), "user prefers terse responses");
  writeFileSync(join(memDir, "leak.md"), "key sk-proj-abcdefghijklmnopqrstuvwx");
  const md = await renderMemory("/unused", [join(memDir, "*.md")], []);
  assert.match(md, /user prefers terse responses/);
  assert.match(md, /\[REDACTED\]/);
  assert.doesNotMatch(md, /sk-proj-abcdef/);
});

test("empty state when no memory exists", async () => {
  const md = await renderMemory("/unused", ["/nonexistent/**/*.md"], []);
  assert.match(md, /no project memory/i);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL.

- [ ] **Step 3: Implement `src/renderers/memory.ts`**

```typescript
import { glob } from "glob";
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { redact } from "../redact.js";

export async function renderMemory(_repoRoot: string, sources: string[], userRedactPatterns: RegExp[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of sources) {
    const files = await glob(pattern, { nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  if (matched.size === 0) {
    return "# Memory\n\n_No project memory found. Auto-memory will populate this on the next session._\n";
  }
  const sorted = [...matched].sort();
  const lines = ["# Memory", ""];
  for (const abs of sorted) {
    const content = readFileSync(abs, "utf8");
    lines.push(`## ${basename(abs)}`);
    lines.push(redact(content, userRedactPatterns));
    lines.push("");
  }
  return lines.join("\n");
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/renderers/memory.ts crawfish-projectctl/test/renderers/memory.test.ts
git commit -m "feat(projectctl): memory.md renderer with redaction"
```

---

## Task 9: `context.md` renderer

**Files:**
- Create: `crawfish-projectctl/src/renderers/context.ts`
- Test: `crawfish-projectctl/test/renderers/context.test.ts`

v1 is intentionally simple: counts session `.jsonl` files matched by the source globs, sums their sizes, lists the top 10 largest by size. Real token counts come later when we have a stable transcript parser.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderContext } from "../../src/renderers/context.js";

test("summarizes session files by count and size", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "a.jsonl"), "x".repeat(100));
  writeFileSync(join(dir, "b.jsonl"), "y".repeat(50));
  const md = await renderContext("/unused", [join(dir, "*.jsonl")]);
  assert.match(md, /2 sessions/);
  assert.match(md, /150 B|150 bytes/);
});

test("empty state when no sessions match", async () => {
  const md = await renderContext("/unused", ["/nonexistent/*.jsonl"]);
  assert.match(md, /no sessions/i);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL.

- [ ] **Step 3: Implement `src/renderers/context.ts`**

```typescript
import { glob } from "glob";
import { statSync } from "node:fs";
import { basename } from "node:path";

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  return `${(n / 1024 / 1024).toFixed(1)} MiB`;
}

export async function renderContext(_repoRoot: string, sources: string[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of sources) {
    const files = await glob(pattern, { nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  if (matched.size === 0) {
    return "# Context\n\n_No sessions found yet._\n";
  }
  const stats = [...matched].map((abs) => ({ abs, size: statSync(abs).size }));
  const total = stats.reduce((a, s) => a + s.size, 0);
  const top = stats.sort((a, b) => b.size - a.size).slice(0, 10);
  const lines = [
    "# Context",
    "",
    `**${stats.length} sessions** · **${fmtBytes(total)}** total`,
    "",
    "## Largest sessions",
    "",
    ...top.map((s) => `- \`${basename(s.abs)}\` — ${fmtBytes(s.size)}`),
    "",
  ];
  return lines.join("\n");
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/renderers/context.ts crawfish-projectctl/test/renderers/context.test.ts
git commit -m "feat(projectctl): context.md renderer (size-based v1)"
```

---

## Task 10: `decisions.md` and `activity.md` renderers + append verbs

**Files:**
- Create: `crawfish-projectctl/src/renderers/decisions.ts`
- Create: `crawfish-projectctl/src/renderers/activity.ts`
- Create: `crawfish-projectctl/src/verbs/decision-add.ts`
- Create: `crawfish-projectctl/src/verbs/activity-record.ts`
- Create: `crawfish-projectctl/src/verbs/memory-append.ts`
- Test: `crawfish-projectctl/test/renderers/decisions.test.ts`
- Test: `crawfish-projectctl/test/renderers/activity.test.ts`

`decisions.md` and `activity.md` are append-only; their "renderer" is just a header-stub used at init time. The real content grows via `decision add` and `activity record`. `memory append` writes a deduped entry into `memory.md` directly (additive, doesn't go through the source-glob renderer).

- [ ] **Step 1: Write the failing test for `decision-add`**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { decisionAdd } from "../../src/verbs/decision-add.js";

test("appends a dated ADR entry to decisions.md", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  writeFileSync(join(dir, ".crawfish/decisions.md"), "# Decisions\n\n");
  decisionAdd(dir, "Use Postgres", "Lower ops cost than DynamoDB at our scale.");
  const got = readFileSync(join(dir, ".crawfish/decisions.md"), "utf8");
  assert.match(got, /## Use Postgres/);
  assert.match(got, /Lower ops cost/);
  assert.match(got, /\d{4}-\d{2}-\d{2}/);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL.

- [ ] **Step 3: Implement `src/verbs/decision-add.ts`**

```typescript
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export function decisionAdd(repoRoot: string, title: string, body: string): void {
  const path = join(repoRoot, ".crawfish", "decisions.md");
  const existing = existsSync(path) ? readFileSync(path, "utf8") : "# Decisions\n\n";
  const date = new Date().toISOString().slice(0, 10);
  const entry = `\n## ${title}\n\n_${date}_\n\n${body}\n`;
  writeFileSync(path, existing + entry);
}
```

- [ ] **Step 4: Write the failing test for `activity-record`**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { activityRecord } from "../../src/verbs/activity-record.js";

test("appends a session summary and trims to last N", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  writeFileSync(join(dir, ".crawfish/activity.md"), "# Activity\n\n");
  for (let i = 0; i < 60; i++) {
    activityRecord(dir, `summary ${i}`, 50);
  }
  const got = readFileSync(join(dir, ".crawfish/activity.md"), "utf8");
  const entries = got.match(/^### /gm) ?? [];
  assert.equal(entries.length, 50);
  assert.match(got, /summary 59/);
  assert.doesNotMatch(got, /summary 0\b/);
});
```

- [ ] **Step 5: Implement `src/verbs/activity-record.ts`**

```typescript
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export function activityRecord(repoRoot: string, summary: string, keep = 50): void {
  const path = join(repoRoot, ".crawfish", "activity.md");
  const existing = existsSync(path) ? readFileSync(path, "utf8") : "# Activity\n\n";
  const ts = new Date().toISOString();
  const newEntry = `\n### ${ts}\n\n${summary}\n`;
  const combined = existing + newEntry;
  // Trim oldest entries beyond `keep`
  const parts = combined.split(/(?=^### )/m);
  const header = parts.shift() ?? "# Activity\n\n";
  const trimmed = parts.slice(-keep);
  writeFileSync(path, header + trimmed.join(""));
}
```

- [ ] **Step 6: Write the failing test for `memory-append`**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { memoryAppend } from "../../src/verbs/memory-append.js";

test("appends a memory entry and dedupes identical ones", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  writeFileSync(join(dir, ".crawfish/memory.md"), "# Memory\n\n");
  memoryAppend(dir, "user prefers Postgres", []);
  memoryAppend(dir, "user prefers Postgres", []);
  const got = readFileSync(join(dir, ".crawfish/memory.md"), "utf8");
  const matches = got.match(/user prefers Postgres/g) ?? [];
  assert.equal(matches.length, 1);
});
```

- [ ] **Step 7: Implement `src/verbs/memory-append.ts`**

```typescript
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { redact } from "../redact.js";

export function memoryAppend(repoRoot: string, text: string, userPatterns: RegExp[]): void {
  const path = join(repoRoot, ".crawfish", "memory.md");
  const existing = existsSync(path) ? readFileSync(path, "utf8") : "# Memory\n\n";
  const clean = redact(text, userPatterns);
  if (existing.includes(clean)) return;
  const ts = new Date().toISOString().slice(0, 10);
  writeFileSync(path, existing + `\n- _${ts}_ ${clean}\n`);
}
```

- [ ] **Step 8: Run all tests, verify pass**

Run: `npm test`
Expected: PASS on all decision/activity/memory tests.

- [ ] **Step 9: Commit**

```bash
git add crawfish-projectctl/src/verbs/ crawfish-projectctl/test/renderers/decisions.test.ts crawfish-projectctl/test/renderers/activity.test.ts
git commit -m "feat(projectctl): decision-add, activity-record, memory-append verbs"
```

---

## Task 11: `refresh` verb (orchestrator)

**Files:**
- Create: `crawfish-projectctl/src/verbs/refresh.ts`
- Test: `crawfish-projectctl/test/verbs/refresh.test.ts`

Orchestrates: read manifest → for each enabled derived file, hash sources → if hash matches stored hash, skip → else call the renderer, redact, write, update manifest hash. Respects the lockfile / debounce. Updates `last_updated`.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";
import { refresh } from "../../src/verbs/refresh.js";

test("re-renders roadmap.md when ROADMAP.md changes", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# Roadmap v1\n\nA");
  init(dir);
  const r1 = await refresh(dir, { debounceMs: 0 });
  assert.ok(r1.refreshed.includes("roadmap.md"));
  const md1 = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(md1, /Roadmap v1/);

  // Second refresh with no source change should skip
  const r2 = await refresh(dir, { debounceMs: 0 });
  assert.equal(r2.refreshed.length, 0);
  assert.ok(r2.skipped.includes("roadmap.md"));

  // Change source, refresh again
  writeFileSync(join(dir, "ROADMAP.md"), "# Roadmap v2\n\nB");
  const r3 = await refresh(dir, { debounceMs: 0 });
  assert.ok(r3.refreshed.includes("roadmap.md"));
  const md3 = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(md3, /Roadmap v2/);
});

test("debounce returns early when lock is fresh", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  init(dir);
  await refresh(dir, { debounceMs: 60_000 });
  const r2 = await refresh(dir, { debounceMs: 60_000 });
  assert.equal(r2.debounced, true);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL.

- [ ] **Step 3: Implement `src/verbs/refresh.ts`**

```typescript
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { readManifest, writeManifest } from "../manifest.js";
import { hashSources } from "../hash.js";
import { acquireLock } from "../lock.js";
import { renderRoadmap } from "../renderers/roadmap.js";
import { renderMemory } from "../renderers/memory.js";
import { renderContext } from "../renderers/context.js";

export interface RefreshOptions {
  debounceMs?: number;
  only?: string[];
  userRedactPatterns?: RegExp[];
}

export interface RefreshResult {
  refreshed: string[];
  skipped: string[];
  debounced?: boolean;
}

type Renderer = (repoRoot: string, sources: string[], userPatterns: RegExp[]) => Promise<string>;

const RENDERERS: Record<string, Renderer> = {
  "roadmap.md": (root, sources) => renderRoadmap(root, sources),
  "memory.md": (root, sources, patterns) => renderMemory(root, sources, patterns),
  "context.md": (root, sources) => renderContext(root, sources),
};

export async function refresh(repoRoot: string, opts: RefreshOptions = {}): Promise<RefreshResult> {
  const { debounceMs = 0, only, userRedactPatterns = [] } = opts;
  const lock = acquireLock(repoRoot, debounceMs);
  if (!lock) return { refreshed: [], skipped: [], debounced: true };

  try {
    const manifest = readManifest(repoRoot);
    const result: RefreshResult = { refreshed: [], skipped: [] };
    for (const [filename, entry] of Object.entries(manifest.files)) {
      if (!entry.enabled) continue;
      if (only && !only.includes(filename)) continue;
      const renderer = RENDERERS[filename];
      if (!renderer) {
        result.skipped.push(filename);
        continue;
      }
      const newHash = await hashSources(repoRoot, entry.sources);
      if (newHash === entry.hash) {
        result.skipped.push(filename);
        continue;
      }
      const md = await renderer(repoRoot, entry.sources, userRedactPatterns);
      writeFileSync(join(repoRoot, ".crawfish", filename), md);
      manifest.files[filename] = { ...entry, hash: newHash };
      result.refreshed.push(filename);
    }
    manifest.last_updated = new Date().toISOString();
    writeManifest(repoRoot, manifest);
    return result;
  } finally {
    lock.release();
  }
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/verbs/refresh.ts crawfish-projectctl/test/verbs/refresh.test.ts
git commit -m "feat(projectctl): refresh orchestrator with dirty detection"
```

---

## Task 12: `status` and `doctor` verbs

**Files:**
- Create: `crawfish-projectctl/src/verbs/status.ts`
- Create: `crawfish-projectctl/src/verbs/doctor.ts`
- Test: `crawfish-projectctl/test/verbs/status.test.ts` (combined)

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";
import { refresh } from "../../src/verbs/refresh.js";
import { status } from "../../src/verbs/status.js";
import { doctor } from "../../src/verbs/doctor.js";

test("status reports stale files after a source change", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# v1");
  init(dir);
  await refresh(dir, { debounceMs: 0 });
  writeFileSync(join(dir, "ROADMAP.md"), "# v2");
  const s = await status(dir);
  assert.ok(s.stale.includes("roadmap.md"));
});

test("doctor flags an unknown schema version", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  init(dir);
  writeFileSync(join(dir, ".crawfish/index.json"), JSON.stringify({ schema: "crawfish-project/v999", files: {} }));
  const d = doctor(dir);
  assert.ok(d.errors.some((e) => /schema/.test(e)));
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL.

- [ ] **Step 3: Implement `src/verbs/status.ts`**

```typescript
import { readManifest } from "../manifest.js";
import { hashSources } from "../hash.js";

export async function status(repoRoot: string): Promise<{ stale: string[]; fresh: string[] }> {
  const manifest = readManifest(repoRoot);
  const stale: string[] = [];
  const fresh: string[] = [];
  for (const [filename, entry] of Object.entries(manifest.files)) {
    if (!entry.enabled) continue;
    const h = await hashSources(repoRoot, entry.sources);
    if (h === entry.hash) fresh.push(filename);
    else stale.push(filename);
  }
  return { stale, fresh };
}
```

- [ ] **Step 4: Implement `src/verbs/doctor.ts`**

```typescript
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { SCHEMA_VERSION } from "../manifest.js";

export function doctor(repoRoot: string): { errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];
  const idxPath = join(repoRoot, ".crawfish", "index.json");
  if (!existsSync(idxPath)) {
    errors.push(".crawfish/index.json is missing — run `crawfish-projectctl init`");
    return { errors, warnings };
  }
  try {
    const raw = JSON.parse(readFileSync(idxPath, "utf8"));
    if (raw.schema !== SCHEMA_VERSION) {
      errors.push(`unknown schema "${raw.schema}", expected "${SCHEMA_VERSION}"`);
    }
  } catch (e) {
    errors.push(`index.json is not valid JSON: ${(e as Error).message}`);
  }
  return { errors, warnings };
}
```

- [ ] **Step 5: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 6: Commit**

```bash
git add crawfish-projectctl/src/verbs/status.ts crawfish-projectctl/src/verbs/doctor.ts crawfish-projectctl/test/verbs/status.test.ts
git commit -m "feat(projectctl): status and doctor verbs"
```

---

## Task 13: CLI entry point

**Files:**
- Modify: `crawfish-projectctl/src/index.ts`

Wire all verbs into commander. CLI runs in the current working directory by default; takes `--cwd <dir>` to override.

- [ ] **Step 1: Replace stub `src/index.ts`**

```typescript
#!/usr/bin/env node
import { Command } from "commander";
import { init } from "./verbs/init.js";
import { refresh } from "./verbs/refresh.js";
import { status } from "./verbs/status.js";
import { doctor } from "./verbs/doctor.js";
import { decisionAdd } from "./verbs/decision-add.js";
import { activityRecord } from "./verbs/activity-record.js";
import { memoryAppend } from "./verbs/memory-append.js";
import { installHooks, uninstallHooks } from "./verbs/install-hooks.js";

const program = new Command();
program.name("crawfish-projectctl").version("0.1.0");
program.option("--cwd <dir>", "repo root", process.cwd());

function root(): string {
  return (program.opts() as { cwd: string }).cwd;
}

program.command("init").description("scaffold .crawfish/").action(() => {
  console.log(init(root()));
});

program.command("refresh [files...]")
  .option("--debounce <ms>", "skip if last refresh within window", "0")
  .action(async (files: string[], opts: { debounce: string }) => {
    const r = await refresh(root(), {
      debounceMs: Number(opts.debounce),
      only: files.length > 0 ? files : undefined,
    });
    console.log(JSON.stringify(r, null, 2));
  });

program.command("status").action(async () => {
  console.log(JSON.stringify(await status(root()), null, 2));
});

program.command("doctor").action(() => {
  const d = doctor(root());
  console.log(JSON.stringify(d, null, 2));
  if (d.errors.length > 0) process.exit(1);
});

program.command("decision add <title> <body>").action((title: string, body: string) => {
  decisionAdd(root(), title, body);
});

program.command("activity record [summary]").action((summary?: string) => {
  const text = summary ?? "(no summary)";
  activityRecord(root(), text);
});

program.command("memory append <text>").action((text: string) => {
  memoryAppend(root(), text, []);
});

program.command("install-hooks").action(() => {
  installHooks(root());
});

program.command("uninstall-hooks").action(() => {
  uninstallHooks(root());
});

program.parseAsync();
```

- [ ] **Step 2: Run typecheck**

Run: `cd crawfish-projectctl && npm run typecheck`
Expected: errors about `./verbs/install-hooks.js` — that's the next task. Skip ahead, come back; or stub a temporary import. Use this minimal stub:

```typescript
// src/verbs/install-hooks.ts (TEMPORARY STUB — replaced in Task 14)
export function installHooks(_root: string): void { throw new Error("not implemented"); }
export function uninstallHooks(_root: string): void { throw new Error("not implemented"); }
```

- [ ] **Step 3: Re-run typecheck**

Run: `npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Smoke-test the CLI**

Run: `npm run build && node dist/index.js --help`
Expected: help text listing all subcommands.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/index.ts crawfish-projectctl/src/verbs/install-hooks.ts
git commit -m "feat(projectctl): CLI entry point wired to all verbs"
```

---

## Task 14: `install-hooks` and `uninstall-hooks` verbs

**Files:**
- Modify: `crawfish-projectctl/src/verbs/install-hooks.ts`
- Test: `crawfish-projectctl/test/verbs/install-hooks.test.ts`

Writes three hook entries into `.claude/settings.json`, merging with existing hooks. Each hook is tagged with `"_crawfish": true` so uninstall can find and remove only its own entries.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { installHooks, uninstallHooks } from "../../src/verbs/install-hooks.js";

test("creates .claude/settings.json with three crawfish hooks", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  installHooks(dir);
  const settings = JSON.parse(readFileSync(join(dir, ".claude/settings.json"), "utf8"));
  assert.ok(settings.hooks.SessionEnd.some((h: any) => h._crawfish));
  assert.ok(settings.hooks.PostToolUse.some((h: any) => h._crawfish));
  assert.ok(settings.hooks.UserPromptSubmit.some((h: any) => h._crawfish));
});

test("uninstall removes only crawfish-tagged hooks", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".claude"));
  writeFileSync(join(dir, ".claude/settings.json"), JSON.stringify({
    hooks: { SessionEnd: [{ command: "echo user-hook" }] },
  }));
  installHooks(dir);
  uninstallHooks(dir);
  const settings = JSON.parse(readFileSync(join(dir, ".claude/settings.json"), "utf8"));
  assert.equal(settings.hooks.SessionEnd.length, 1);
  assert.equal(settings.hooks.SessionEnd[0].command, "echo user-hook");
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL — currently throws "not implemented".

- [ ] **Step 3: Replace `src/verbs/install-hooks.ts`**

```typescript
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";

interface HookEntry {
  matcher?: string;
  command: string;
  _crawfish?: boolean;
}

interface Settings {
  hooks?: Record<string, HookEntry[]>;
  [k: string]: unknown;
}

const HOOKS: Record<string, HookEntry[]> = {
  SessionEnd: [
    { command: "crawfish-projectctl activity record", _crawfish: true },
  ],
  PostToolUse: [
    { matcher: "Edit|Write", command: "crawfish-projectctl refresh --debounce 30000", _crawfish: true },
  ],
  UserPromptSubmit: [
    { command: "crawfish-projectctl refresh memory.md", _crawfish: true },
  ],
};

function settingsPath(repoRoot: string): string {
  return join(repoRoot, ".claude", "settings.json");
}

function loadSettings(repoRoot: string): Settings {
  const p = settingsPath(repoRoot);
  if (!existsSync(p)) return {};
  return JSON.parse(readFileSync(p, "utf8")) as Settings;
}

function saveSettings(repoRoot: string, settings: Settings): void {
  const p = settingsPath(repoRoot);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(settings, null, 2) + "\n");
}

export function installHooks(repoRoot: string): void {
  const settings = loadSettings(repoRoot);
  settings.hooks = settings.hooks ?? {};
  for (const [event, entries] of Object.entries(HOOKS)) {
    const current = settings.hooks[event] ?? [];
    const withoutOurs = current.filter((h) => !h._crawfish);
    settings.hooks[event] = [...withoutOurs, ...entries];
  }
  saveSettings(repoRoot, settings);
}

export function uninstallHooks(repoRoot: string): void {
  const settings = loadSettings(repoRoot);
  if (!settings.hooks) return;
  for (const event of Object.keys(settings.hooks)) {
    settings.hooks[event] = settings.hooks[event].filter((h) => !h._crawfish);
    if (settings.hooks[event].length === 0) delete settings.hooks[event];
  }
  saveSettings(repoRoot, settings);
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/verbs/install-hooks.ts crawfish-projectctl/test/verbs/install-hooks.test.ts
git commit -m "feat(projectctl): install-hooks / uninstall-hooks verbs"
```

---

## Task 15: MCP server (Slice 2)

**Files:**
- Create: `crawfish-projectctl/src/mcp/server.ts`
- Test: `crawfish-projectctl/test/mcp/server.test.ts`

Five tools, all shelling out to the library functions (not the CLI subprocess — direct function calls; same module). Schema: each tool takes `repo_root` plus tool-specific args. Mirrors the `crawfish-orgctl/src/index.ts` pattern.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { dispatch } from "../../src/mcp/server.js";

test("project_refresh tool runs refresh", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# v1");
  await dispatch("project_init", { repo_root: dir });
  const res = await dispatch("project_refresh", { repo_root: dir });
  assert.ok(Array.isArray(res.refreshed));
});

test("project_decision_add appends to decisions.md", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  await dispatch("project_init", { repo_root: dir });
  await dispatch("project_decision_add", { repo_root: dir, title: "T", body: "B" });
  const got = readFileSync(join(dir, ".crawfish/decisions.md"), "utf8");
  assert.match(got, /## T/);
});
```

- [ ] **Step 2: Run test, verify failure**

Run: `npm test`
Expected: FAIL.

- [ ] **Step 3: Implement `src/mcp/server.ts`**

```typescript
#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { init } from "../verbs/init.js";
import { refresh } from "../verbs/refresh.js";
import { status } from "../verbs/status.js";
import { decisionAdd } from "../verbs/decision-add.js";
import { memoryAppend } from "../verbs/memory-append.js";

const TOOLS = [
  { name: "project_init", description: "Scaffold .crawfish/ in the repo.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_refresh", description: "Re-derive .crawfish/*.md from sources.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, files: { type: "array", items: { type: "string" } } }, required: ["repo_root"] } },
  { name: "project_status", description: "Report which .crawfish files are stale.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_decision_add", description: "Append an ADR entry.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, title: { type: "string" }, body: { type: "string" } }, required: ["repo_root", "title", "body"] } },
  { name: "project_memory_append", description: "Append a deduped memory entry.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, text: { type: "string" } }, required: ["repo_root", "text"] } },
  { name: "project_read", description: "Read one .crawfish/*.md file.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, file: { type: "string" } }, required: ["repo_root", "file"] } },
];

export async function dispatch(name: string, args: Record<string, unknown>): Promise<any> {
  const root = String(args.repo_root);
  switch (name) {
    case "project_init":
      return { result: init(root) };
    case "project_refresh":
      return await refresh(root, { only: args.files as string[] | undefined });
    case "project_status":
      return await status(root);
    case "project_decision_add":
      decisionAdd(root, String(args.title), String(args.body));
      return { ok: true };
    case "project_memory_append":
      memoryAppend(root, String(args.text), []);
      return { ok: true };
    case "project_read": {
      const path = join(root, ".crawfish", String(args.file));
      if (!existsSync(path)) return { error: "file not found" };
      return { content: readFileSync(path, "utf8") };
    }
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}

async function main(): Promise<void> {
  const server = new Server({ name: "crawfish-projectctl", version: "0.1.0" }, { capabilities: { tools: {} } });
  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));
  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const result = await dispatch(req.params.name, req.params.arguments ?? {});
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  });
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/src/mcp/server.ts crawfish-projectctl/test/mcp/server.test.ts
git commit -m "feat(projectctl): MCP server exposing the six project tools"
```

---

## Task 16: Reference fixtures + integration test (Slice 5)

**Files:**
- Create: `crawfish-projectctl/fixtures/gsd-project/.planning/P1/PLAN.md`
- Create: `crawfish-projectctl/fixtures/gsd-project/.planning/P2/PLAN.md`
- Create: `crawfish-projectctl/fixtures/gsd-project/README.md`
- Create: `crawfish-projectctl/fixtures/plain-readme-project/ROADMAP.md`
- Create: `crawfish-projectctl/fixtures/plain-readme-project/README.md`
- Test: `crawfish-projectctl/test/integration.test.ts`

- [ ] **Step 1: Create `fixtures/gsd-project/`**

```bash
mkdir -p crawfish-projectctl/fixtures/gsd-project/.planning/P1
mkdir -p crawfish-projectctl/fixtures/gsd-project/.planning/P2
```

`fixtures/gsd-project/.planning/P1/PLAN.md`:

```markdown
# Phase 1 — Authentication

Tasks: GitHub OAuth, session cookies, sign-out flow.
```

`fixtures/gsd-project/.planning/P2/PLAN.md`:

```markdown
# Phase 2 — Project Import

Tasks: clone a repo, run init, open PR.
```

`fixtures/gsd-project/README.md`:

```markdown
# gsd-project fixture

Synthetic repo with `.planning/` used by `crawfish-projectctl` integration tests.
```

- [ ] **Step 2: Create `fixtures/plain-readme-project/`**

`fixtures/plain-readme-project/ROADMAP.md`:

```markdown
# Roadmap

- Milestone A — ship the thing
- Milestone B — ship the next thing
```

`fixtures/plain-readme-project/README.md`:

```markdown
# plain-readme-project fixture

Synthetic repo with just `ROADMAP.md` used by `crawfish-projectctl` integration tests.
```

- [ ] **Step 3: Write the integration test**

```typescript
// test/integration.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { cpSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { init } from "../src/verbs/init.js";
import { refresh } from "../src/verbs/refresh.js";

function cloneFixture(name: string): string {
  const src = resolve("fixtures", name);
  const dst = mkdtempSync(join(tmpdir(), `${name}-`));
  cpSync(src, dst, { recursive: true });
  return dst;
}

test("end-to-end: gsd-project produces a multi-phase roadmap.md", async () => {
  const dir = cloneFixture("gsd-project");
  init(dir);
  await refresh(dir, { debounceMs: 0 });
  const roadmap = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(roadmap, /Phase 1 — Authentication/);
  assert.match(roadmap, /Phase 2 — Project Import/);
});

test("end-to-end: plain-readme-project produces a single-source roadmap.md", async () => {
  const dir = cloneFixture("plain-readme-project");
  init(dir);
  await refresh(dir, { debounceMs: 0 });
  const roadmap = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(roadmap, /Roadmap/);
  assert.match(roadmap, /Milestone A/);
});
```

- [ ] **Step 4: Run test, verify pass**

Run: `npm test`
Expected: PASS on both integration tests.

- [ ] **Step 5: Commit**

```bash
git add crawfish-projectctl/fixtures crawfish-projectctl/test/integration.test.ts
git commit -m "test(projectctl): fixtures + end-to-end integration tests"
```

---

## Task 17: README + final wiring

**Files:**
- Modify: `crawfish-projectctl/README.md`

Document the CLI, MCP tools, and hook preset. Reference the spec.

- [ ] **Step 1: Replace `README.md`**

```markdown
# crawfish-projectctl

The per-project `.crawfish/` folder engine for Crawfish.

See the design spec: `docs/superpowers/specs/2026-05-18-crawfish-project-folder-design.md`.

## CLI

```
crawfish-projectctl init                    # scaffold .crawfish/
crawfish-projectctl refresh [files...]      # re-derive *.md from sources
crawfish-projectctl status                  # which files are stale?
crawfish-projectctl doctor                  # validate schema + sources
crawfish-projectctl decision add <t> <b>    # append an ADR entry
crawfish-projectctl activity record [s]     # append a session summary
crawfish-projectctl memory append <text>    # append a deduped memory entry
crawfish-projectctl install-hooks           # write three hook entries to .claude/settings.json
crawfish-projectctl uninstall-hooks         # remove them
```

## MCP

Run `crawfish-projectctl-mcp` over stdio. Tools:
- `project_init`, `project_refresh`, `project_status`, `project_decision_add`, `project_memory_append`, `project_read`.

## Hooks

`install-hooks` writes:
- `SessionEnd` → `crawfish-projectctl activity record`
- `PostToolUse` (Edit|Write) → `crawfish-projectctl refresh --debounce 30000`
- `UserPromptSubmit` → `crawfish-projectctl refresh memory.md`

Each entry is tagged with `_crawfish: true` so uninstall removes only its own hooks.
```

- [ ] **Step 2: Final full test pass**

Run: `cd crawfish-projectctl && npm test && npm run typecheck`
Expected: all tests pass; no type errors.

- [ ] **Step 3: Commit**

```bash
git add crawfish-projectctl/README.md
git commit -m "docs(projectctl): README covering CLI, MCP, and hooks"
```

---

## Self-review

**Spec coverage:**
- Folder shape (§ folder shape) — Tasks 2, 6 (`index.json`, init writes stubs).
- Three surfaces (§ three surfaces) — CLI: Tasks 6–13; MCP: Task 15; hooks: Task 14.
- Source→derived dependency map — Tasks 2 (`sources` in manifest), 3 (hashing), 11 (refresh orchestrator).
- Redaction pass — Task 4; integrated into Tasks 8 (memory render) and 10 (memory-append).
- Lockfile debounce — Task 5; integrated into Task 11.
- Renderers for the five derived files — Tasks 7–10.
- Reference fixtures — Task 16.
- Non-goals respected — no watcher daemon, no platform consumers (Slice 4 deferred), no monorepo dogfood.

**Placeholder scan:** Task 13 includes a temporary stub for `install-hooks` to allow the CLI typecheck to pass before Task 14. The stub is replaced in Task 14 step 3. This is explicit and tracked, not a placeholder.

**Type consistency:** Verb signatures (`init`, `refresh`, `status`, `doctor`, `decisionAdd`, `activityRecord`, `memoryAppend`, `installHooks`, `uninstallHooks`) are used consistently across the CLI (Task 13), MCP (Task 15), and tests. `RefreshOptions` / `RefreshResult` types defined in Task 11 are used unchanged by the dispatch table in Task 15.
