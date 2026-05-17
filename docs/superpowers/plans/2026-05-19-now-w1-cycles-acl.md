# NOW-W1 — Cycles + Epics + Activity Feed + Member ACL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `crawfish-lens` + `crawfish-dash` into compliance with the v1 [`docs/specs/org-contract.md`](../../specs/org-contract.md) for cycles, epics, the primary-assignee/contributor model, the activity feed, and the four-tier member ACL — without breaking the v0.3 surface that already shipped.

**Architecture:** Three teammates work in parallel against the contract. `cycles-be` owns the cycles/epics schema + REST. `activity-be` owns the cross-task activity stream and rewrites `validateActor` into the four-tier ACL with the primary-assignee/contributor rewrite rule. `plan-fe` consumes both from the dash. The lead serializes route-table edits in `crawfish-lens/src/server/index.ts` and runs the final build. **Prior code exists for cycles.ts (start_date/end_date) and activity.ts (mention projection); this plan migrates that code to the v1 contract field names and adds the missing schema bits.**

**Tech Stack:** TypeScript · Node http (no Express) · Vitest · React + Vite (dash) · `~/.crawfish/orgs/<org_id>/` on-disk state · `board.jsonl` event log folded into `Task[]`.

---

## 0 · Pre-flight (lead, before any teammate writes code)

These are read-only checks. **Run them and confirm green before spawning.**

- [ ] Confirm the v1 contract is the one just edited:
  ```bash
  grep -n "starts_at\|humanity\|acl_denied\|assignee_locked\|cycles.json schema (NOW-W1)" docs/specs/org-contract.md | head
  ```
  Expected: matches in §1, §2, §3.1, §3.2, §5.5, §6, §7. If anything is missing, **stop and reopen the contract** before spawning.

- [ ] Confirm the prior NOW-W1 code is on disk so teammates know what they're migrating:
  ```bash
  wc -l crawfish-lens/src/server/{types,board,cycles,activity,policy}.ts
  ```
  Expected: all 5 files exist and are non-trivial (>30 lines).

- [ ] Confirm dash counterparts exist:
  ```bash
  wc -l crawfish-dash/web/src/routes/Plan.tsx crawfish-dash/web/src/components/{TaskDrawer,ActivityFeed,TaskCard}.tsx
  ```
  Expected: Plan.tsx, TaskDrawer.tsx, ActivityFeed.tsx, TaskCard.tsx all present.

- [ ] No teammate touches `crawfish-lens/src/server/index.ts` (route table) or `crawfish-dash/web/src/App.tsx`. Both are lead-only per [`CLAUDE.md`](../../../CLAUDE.md) §0.1.

---

## 1 · File responsibilities

| File | Owner | Responsibility |
|---|---|---|
| `crawfish-lens/src/server/types.ts` | `cycles-be` | Re-export typed contract surfaces for cycles+epics, member ACL, ActivityKind, primary-assignee patch shapes. Keep `SessionSummary`/`SessionDetailPayload` untouched. |
| `crawfish-lens/src/server/cycles.ts` | `cycles-be` | Read/write `cycles.json`; expose handlers for `GET/PUT /api/orgs/:id/cycles`; `If-Match` mtime guard → `412 stale`. Compute `spent_tokens` from `board.jsonl` fold. |
| `crawfish-lens/src/server/activity.ts` | `activity-be` | Fold `board.jsonl` into a flat `ActivityEntry[]`; expose `GET /api/orgs/:id/activity` (+ SSE variant); filter by `task_id`/`cycle_id`/`since`. |
| `crawfish-lens/src/server/board.ts` (append-only) | `activity-be` | Append a single new `validateActor()` that returns the v1 ACL matrix verdict (replaces the policy.ts stub used today). Append a single new `rewriteAssigneeForContributor()` helper used by the create/update handlers. |
| `crawfish-lens/test/{cycles,activity,board-acl}.test.ts` | `cycles-be` + `activity-be` | Vitest specs; one file per task that this plan introduces. |
| `crawfish-dash/web/src/routes/Plan.tsx` | `plan-fe` | Cycle picker + over-budget styling reading `/api/orgs/:id/cycles`. |
| `crawfish-dash/web/src/components/CycleBudgetBar.tsx` | `plan-fe` | New small component: progress bar of `spent_tokens / planned_tokens`. |
| `crawfish-dash/web/src/components/TaskDrawer.tsx` | `plan-fe` | Additive **Activity** panel that fetches `/api/orgs/:id/activity?task_id=...`. Do NOT touch existing drawer regions. |
| `crawfish-lens/src/server/index.ts` | **lead only** | Wire the new routes after teammates report done. |
| `crawfish-dash/web/src/App.tsx` | **lead only** | No new routes needed in W1; lead confirms. |

---

## 2 · Type contract recap (read before coding)

The shapes below MUST match `docs/specs/org-contract.md`. Any drift → server tests fail. Refer to:

- `docs/specs/org-contract.md` **§2** — `humanity` and `acl` member fields.
- **§3** — `task_updated.patch.contributors`, folded `Task.contributors`.
- **§3.1** — primary-assignee + contributor rewrite rule (`assignee_locked` error).
- **§3.2** — `validateActor` ACL matrix (`owner | admin | member | viewer`).
- **§5.5** — `cycles.json` (`{ cycles: [...], epics: [...] }`; `starts_at`/`ends_at`/`planned_tokens`/`spent_tokens`/`status`).
- **§7** — `/api/orgs/:id/cycles` (with `If-Match`) and `/api/orgs/:id/activity` (+ SSE).

---

## 3 · Tasks

### Task 1 — Schema + types (owner: `cycles-be`)

Bring `types.ts` and the board fold into the v1 contract field names. Existing code uses `start_date`/`end_date`; the contract says `starts_at`/`ends_at`. Existing tasks have no `contributors[]`; the contract requires it.

**Files:**
- Modify: `crawfish-lens/src/server/types.ts` (append, do not touch existing exports)
- Modify: `crawfish-lens/src/server/board.ts:Task` interface (lines 90–115 in current HEAD) — add `contributors`
- Modify: `crawfish-lens/src/server/board.ts:BoardEvent` (lines 50–88 in current HEAD) — add `contributors` to `task_updated.patch`
- Test: `crawfish-lens/test/types.test.ts` (new)

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-lens/test/types.test.ts
import { describe, it, expect } from "vitest";
import type {
  Cycle,
  Epic,
  CyclesFile,
  MemberAcl,
  Humanity,
  AssigneeLockedError,
} from "../src/server/types.js";
import { foldTasks, type BoardEvent } from "../src/server/board.js";

describe("v1 contract types", () => {
  it("Cycle uses starts_at/ends_at and exposes planned_tokens/spent_tokens/status", () => {
    const c: Cycle = {
      id: "2026-w20",
      name: "Week 20",
      starts_at: "2026-05-18T00:00:00Z",
      ends_at: "2026-05-24T23:59:59Z",
      planned_tokens: 4_000_000,
      spent_tokens: 0,
      status: "active",
    };
    expect(c.status).toBe("active");
  });

  it("Epic has cycle_id link, optional color, owner", () => {
    const e: Epic = {
      id: "auth-rewrite",
      title: "Auth",
      description: "x",
      owner: "neal",
      color: "#7C3AED",
      cycle_id: "2026-w20",
      status: "planned",
    };
    expect(e.owner).toBe("neal");
  });

  it("CyclesFile has cycles[] and epics[]", () => {
    const f: CyclesFile = { cycles: [], epics: [] };
    expect(f.epics).toEqual([]);
  });

  it("MemberAcl enumerates the 4 tiers; Humanity enumerates agent|human", () => {
    const tiers: MemberAcl[] = ["owner", "admin", "member", "viewer"];
    const humans: Humanity[] = ["agent", "human"];
    expect(tiers).toHaveLength(4);
    expect(humans).toHaveLength(2);
  });

  it("AssigneeLockedError carries from/to/by/code", () => {
    const e: AssigneeLockedError = {
      code: "assignee_locked",
      from: "neal",
      to: "founder",
      by: "founder",
    };
    expect(e.code).toBe("assignee_locked");
  });
});

describe("folded Task includes contributors[]", () => {
  it("defaults contributors to [] on create", () => {
    const events: BoardEvent[] = [
      {
        type: "task_created",
        ts: "2026-05-18T00:00:00Z",
        task_id: "t1",
        title: "x",
        description: "",
        assignee: null,
        created_by: "neal",
      },
    ];
    const tasks = foldTasks(events);
    expect(tasks[0].contributors).toEqual([]);
  });

  it("task_updated patch may carry contributors[]", () => {
    const events: BoardEvent[] = [
      {
        type: "task_created",
        ts: "2026-05-18T00:00:00Z",
        task_id: "t1",
        title: "x",
        description: "",
        assignee: "neal",
        created_by: "neal",
      },
      {
        type: "task_updated",
        ts: "2026-05-18T00:01:00Z",
        task_id: "t1",
        by: "neal",
        patch: { contributors: ["founder"] },
      },
    ];
    const tasks = foldTasks(events);
    expect(tasks[0].contributors).toEqual(["founder"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd crawfish-lens && npx vitest run test/types.test.ts
```

Expected: FAIL (missing exports `Cycle`, `Epic`, `CyclesFile`, `MemberAcl`, `Humanity`, `AssigneeLockedError`; `Task.contributors` undefined).

- [ ] **Step 3: Append exports to `crawfish-lens/src/server/types.ts`**

```ts
// crawfish-lens/src/server/types.ts — append at end

// ----- v1 org-contract surfaces (NOW-W1) -----
// See docs/specs/org-contract.md §2, §3, §3.1, §3.2, §5.5.

export type Humanity = "agent" | "human";
export type MemberAcl = "owner" | "admin" | "member" | "viewer";

export type CycleStatus = "planned" | "active" | "completed";
export type EpicStatus = "planned" | "active" | "completed" | "abandoned";

export interface Cycle {
  id: string;
  name: string;
  starts_at: string; // RFC3339 UTC
  ends_at: string;   // RFC3339 UTC
  planned_tokens: number;
  spent_tokens: number; // server-derived; clients MUST NOT write
  status: CycleStatus;
}

export interface Epic {
  id: string;
  title: string;
  description: string;
  owner: string | null;
  color?: string;
  cycle_id?: string | null;
  status: EpicStatus;
}

export interface CyclesFile {
  cycles: Cycle[];
  epics: Epic[];
}

export interface AssigneeLockedError {
  code: "assignee_locked";
  from: string; // human assignee that holds the lock
  to: string;   // agent the caller tried to set
  by: string;   // member that attempted the write
}
```

- [ ] **Step 4: Add `contributors: string[]` to `Task` and `task_updated.patch` in `board.ts`**

In `crawfish-lens/src/server/board.ts`:

```ts
// 1. In the BoardEvent union, inside task_updated.patch type — add:
        contributors: string[];

// 2. In the `Task` interface — add immediately after the `assignee` field:
  contributors: string[];

// 3. In foldTasks(), inside the task_created branch — initialise:
        contributors: [],

// 4. In foldTasks(), inside the task_updated branch — apply patch:
      if (ev.patch.contributors !== undefined) t.contributors = ev.patch.contributors;
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/types.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: 6 tests pass; tsc clean.

- [ ] **Step 6: Commit**

```bash
git -C crawfish-lens add src/server/types.ts src/server/board.ts test/types.test.ts
git -C crawfish-lens commit -m "feat(types): v1 org-contract surfaces — cycles, epics, ACL, contributors[]

Aligns crawfish-lens types with docs/specs/org-contract.md §2, §3, §3.1,
§3.2, §5.5. Tasks now carry contributors[] in the fold and accept it
in task_updated patches."
```

---

### Task 2 — Cycles REST with `If-Match` (owner: `cycles-be`)

Migrate `cycles.ts` from the legacy `start_date`/`end_date` shape to the v1 `starts_at`/`ends_at`/`planned_tokens`/`spent_tokens`/`status`/`epics[]` shape. Replace per-resource POST/PUT/DELETE with whole-file `GET/PUT`. Enforce `If-Match: <mtime>` → `412 stale`. Derive `spent_tokens` from the board fold.

**Files:**
- Modify: `crawfish-lens/src/server/cycles.ts` (full rewrite of the storage + handler surface; keep the file path)
- Test: `crawfish-lens/test/cycles.test.ts` (rewrite)

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-lens/test/cycles.test.ts — full rewrite
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, writeFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { IncomingMessage, ServerResponse } from "node:http";
import { Socket } from "node:net";
import { handleListCycles, handlePutCycles } from "../src/server/cycles.js";
import type { CyclesFile } from "../src/server/types.js";

let root: string;
let orgId: string;

function makeReq(method: string, headers: Record<string, string> = {}, body = "") {
  const req = new IncomingMessage(new Socket());
  req.method = method;
  req.url = "/api/orgs/o1/cycles";
  for (const [k, v] of Object.entries(headers)) req.headers[k.toLowerCase()] = v;
  // Buffer the body so handler can consume it.
  process.nextTick(() => { req.emit("data", Buffer.from(body)); req.emit("end"); });
  return req;
}

function makeRes() {
  const res = new ServerResponse(new IncomingMessage(new Socket()));
  const chunks: Buffer[] = [];
  const origWrite = res.write.bind(res);
  const origEnd = res.end.bind(res);
  // capture body
  // @ts-expect-error test override
  res.write = (chunk: any, ...rest: any[]) => { chunks.push(Buffer.from(chunk)); return origWrite(chunk, ...rest); };
  // @ts-expect-error test override
  res.end = (chunk: any, ...rest: any[]) => {
    if (chunk) chunks.push(Buffer.from(chunk));
    return origEnd(chunk, ...rest);
  };
  return { res, getBody: () => Buffer.concat(chunks).toString("utf8") };
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "cycles-test-"));
  process.env.CRAWFISH_HOME = root;
  orgId = "o1";
  const orgDir = join(root, "orgs", orgId);
  writeFileSync(join(orgDir, "org.json"), JSON.stringify({ id: orgId, name: "x", members: [] }), { flag: "wx" });
  // Note: implementation should mkdir -p; if not, expand setup here.
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true });
  delete process.env.CRAWFISH_HOME;
});

describe("GET /api/orgs/:id/cycles", () => {
  it("returns { cycles: [], epics: [] } for a fresh org", async () => {
    const req = makeReq("GET");
    const { res, getBody } = makeRes();
    await handleListCycles(req, res, orgId);
    expect(res.statusCode).toBe(200);
    const parsed: CyclesFile = JSON.parse(getBody());
    expect(parsed).toEqual({ cycles: [], epics: [] });
    expect(res.getHeader("ETag")).toBeDefined();
  });

  it("ETag equals file mtime when cycles.json exists", async () => {
    const cyclesPath = join(root, "orgs", orgId, "cycles.json");
    const file: CyclesFile = {
      cycles: [{ id: "c1", name: "C1", starts_at: "2026-05-18T00:00:00Z", ends_at: "2026-05-24T23:59:59Z", planned_tokens: 100, spent_tokens: 0, status: "active" }],
      epics: [],
    };
    writeFileSync(cyclesPath, JSON.stringify(file));
    const mtime = statSync(cyclesPath).mtimeMs.toString();
    const req = makeReq("GET");
    const { res } = makeRes();
    await handleListCycles(req, res, orgId);
    expect(res.getHeader("ETag")).toBe(mtime);
  });
});

describe("PUT /api/orgs/:id/cycles", () => {
  it("returns 412 stale when If-Match mismatches", async () => {
    const cyclesPath = join(root, "orgs", orgId, "cycles.json");
    writeFileSync(cyclesPath, JSON.stringify({ cycles: [], epics: [] }));
    const realMtime = statSync(cyclesPath).mtimeMs;
    const body = JSON.stringify({ cycles: [], epics: [] });
    const req = makeReq("PUT", { "If-Match": String(realMtime - 1), "Content-Type": "application/json" }, body);
    const { res, getBody } = makeRes();
    await handlePutCycles(req, res, orgId);
    expect(res.statusCode).toBe(412);
    expect(JSON.parse(getBody()).error.code).toBe("stale");
  });

  it("writes when If-Match matches and returns the new ETag", async () => {
    const cyclesPath = join(root, "orgs", orgId, "cycles.json");
    writeFileSync(cyclesPath, JSON.stringify({ cycles: [], epics: [] }));
    const mtime = statSync(cyclesPath).mtimeMs;
    const newFile: CyclesFile = {
      cycles: [{ id: "c1", name: "C1", starts_at: "2026-05-18T00:00:00Z", ends_at: "2026-05-24T23:59:59Z", planned_tokens: 100, spent_tokens: 0, status: "active" }],
      epics: [],
    };
    const req = makeReq("PUT", { "If-Match": String(mtime), "Content-Type": "application/json" }, JSON.stringify(newFile));
    const { res } = makeRes();
    await handlePutCycles(req, res, orgId);
    expect(res.statusCode).toBe(200);
    const newMtime = statSync(cyclesPath).mtimeMs;
    expect(res.getHeader("ETag")).toBe(String(newMtime));
  });

  it("rejects starts_at >= ends_at with 400", async () => {
    const cyclesPath = join(root, "orgs", orgId, "cycles.json");
    writeFileSync(cyclesPath, JSON.stringify({ cycles: [], epics: [] }));
    const mtime = statSync(cyclesPath).mtimeMs;
    const bad: CyclesFile = {
      cycles: [{ id: "c1", name: "C1", starts_at: "2026-05-24T00:00:00Z", ends_at: "2026-05-18T00:00:00Z", planned_tokens: 0, spent_tokens: 0, status: "planned" }],
      epics: [],
    };
    const req = makeReq("PUT", { "If-Match": String(mtime) }, JSON.stringify(bad));
    const { res, getBody } = makeRes();
    await handlePutCycles(req, res, orgId);
    expect(res.statusCode).toBe(400);
    expect(JSON.parse(getBody()).error.code).toBe("invalid_cycle");
  });

  it("auto-completes the previous active cycle when a second one activates", async () => {
    const cyclesPath = join(root, "orgs", orgId, "cycles.json");
    const initial: CyclesFile = {
      cycles: [{ id: "c1", name: "C1", starts_at: "2026-05-18T00:00:00Z", ends_at: "2026-05-24T23:59:59Z", planned_tokens: 0, spent_tokens: 0, status: "active" }],
      epics: [],
    };
    writeFileSync(cyclesPath, JSON.stringify(initial));
    const mtime = statSync(cyclesPath).mtimeMs;
    const next: CyclesFile = {
      cycles: [
        initial.cycles[0],
        { id: "c2", name: "C2", starts_at: "2026-05-25T00:00:00Z", ends_at: "2026-05-31T23:59:59Z", planned_tokens: 0, spent_tokens: 0, status: "active" },
      ],
      epics: [],
    };
    const req = makeReq("PUT", { "If-Match": String(mtime) }, JSON.stringify(next));
    const { res, getBody } = makeRes();
    await handlePutCycles(req, res, orgId);
    expect(res.statusCode).toBe(200);
    const saved = JSON.parse(getBody()) as CyclesFile;
    expect(saved.cycles.find((c) => c.id === "c1")!.status).toBe("completed");
    expect(saved.cycles.find((c) => c.id === "c2")!.status).toBe("active");
  });

  it("server overwrites client-supplied spent_tokens with the board-derived sum", async () => {
    const orgDir = join(root, "orgs", orgId);
    const cyclesPath = join(orgDir, "cycles.json");
    writeFileSync(cyclesPath, JSON.stringify({ cycles: [], epics: [] }));
    const boardPath = join(orgDir, "board.jsonl");
    writeFileSync(
      boardPath,
      [
        JSON.stringify({ type: "task_created", ts: "2026-05-19T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal", cycle_id: "c1" }),
        JSON.stringify({ type: "task_updated", ts: "2026-05-19T01:00:00Z", task_id: "t1", by: "neal", patch: { token_spent: 12345 } }),
        "",
      ].join("\n"),
    );
    const mtime = statSync(cyclesPath).mtimeMs;
    const body: CyclesFile = {
      cycles: [{ id: "c1", name: "C1", starts_at: "2026-05-18T00:00:00Z", ends_at: "2026-05-24T23:59:59Z", planned_tokens: 100000, spent_tokens: 99999, status: "active" }],
      epics: [],
    };
    const req = makeReq("PUT", { "If-Match": String(mtime) }, JSON.stringify(body));
    const { res, getBody } = makeRes();
    await handlePutCycles(req, res, orgId);
    expect(res.statusCode).toBe(200);
    const saved = JSON.parse(getBody()) as CyclesFile;
    expect(saved.cycles[0].spent_tokens).toBe(12345); // server-derived
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd crawfish-lens && npx vitest run test/cycles.test.ts
```

Expected: FAIL (legacy `start_date` cycles.ts; no `handlePutCycles`; no `If-Match`).

- [ ] **Step 3: Rewrite `crawfish-lens/src/server/cycles.ts`**

Replace the file body. Required exports: `handleListCycles(req, res, orgId)`, `handlePutCycles(req, res, orgId)`. Use existing helpers: `resolveOrgRoot` from `orgs.js`, `sendJSON` from `api.js`. Read JSON body via the project's existing pattern (look at `crawfish-lens/src/server/board.ts:handleAppendEvent` for the streaming-body idiom).

Behavior contract (from §5.5):

- `GET /cycles` reads `~/.crawfish/orgs/<orgId>/cycles.json`; returns `{ cycles, epics }` (empty arrays if file missing). `ETag` header = file mtime in ms as a string (or `"0"` if file missing).
- `PUT /cycles` requires `If-Match`. Compare against current mtime in ms.
  - Missing or mismatched `If-Match` → `412 { error: { code: "stale", current_etag: "<mtime>" } }`.
  - Validate each cycle: `starts_at < ends_at` else `400 { error: { code: "invalid_cycle", id, reason } }`.
  - Validate cycle/epic ids match `/^[a-z0-9_-]{1,32}$/` else `400 invalid_cycle` / `400 invalid_epic`.
  - Enforce single-active rule: if the incoming file has >1 cycle with `status === "active"`, mark all but the **last** one in the array as `"completed"`.
  - Recompute `spent_tokens` per cycle: read `~/.crawfish/orgs/<orgId>/board.jsonl`, fold via `foldTasks`, then for each cycle sum `task.token_spent` (the existing dash-facing budget field) across tasks where `task.cycle_id === cycle.id`. Overwrite the client-supplied value.
  - Write atomically: write to `cycles.json.tmp` then `rename`. Return `200 { cycles, epics }` with `ETag` = new mtime.

```ts
// crawfish-lens/src/server/cycles.ts — full replacement (key shape; preserve existing imports + sendJSON conventions)
import { type IncomingMessage, type ServerResponse } from "node:http";
import { existsSync, readFileSync, renameSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { resolveOrgRoot } from "./orgs.js";
import { sendJSON } from "./api.js";
import { foldTasks, type BoardEvent } from "./board.js";
import type { CyclesFile, Cycle, Epic } from "./types.js";

const ID_RE = /^[a-z0-9_-]{1,32}$/;

function cyclesPath(orgId: string): string {
  return join(resolveOrgRoot(orgId), "cycles.json");
}

function readFile(orgId: string): { file: CyclesFile; mtime: number } {
  const p = cyclesPath(orgId);
  if (!existsSync(p)) return { file: { cycles: [], epics: [] }, mtime: 0 };
  const raw = JSON.parse(readFileSync(p, "utf8"));
  return {
    file: {
      cycles: Array.isArray(raw.cycles) ? raw.cycles : [],
      epics: Array.isArray(raw.epics) ? raw.epics : [],
    },
    mtime: statSync(p).mtimeMs,
  };
}

function readBoardEvents(orgId: string): BoardEvent[] {
  const p = join(resolveOrgRoot(orgId), "board.jsonl");
  if (!existsSync(p)) return [];
  const out: BoardEvent[] = [];
  for (const line of readFileSync(p, "utf8").split("\n")) {
    const t = line.trim();
    if (!t) continue;
    try { out.push(JSON.parse(t) as BoardEvent); } catch { /* skip */ }
  }
  return out;
}

function recomputeSpentTokens(orgId: string, cycles: Cycle[]): Cycle[] {
  const tasks = foldTasks(readBoardEvents(orgId));
  const sums = new Map<string, number>();
  for (const t of tasks) {
    if (!t.cycle_id) continue;
    sums.set(t.cycle_id, (sums.get(t.cycle_id) ?? 0) + ((t as { token_spent?: number }).token_spent ?? 0));
  }
  return cycles.map((c) => ({ ...c, spent_tokens: sums.get(c.id) ?? 0 }));
}

function singleActive(cycles: Cycle[]): Cycle[] {
  const activeIdxs = cycles.flatMap((c, i) => (c.status === "active" ? [i] : []));
  if (activeIdxs.length <= 1) return cycles;
  const keep = activeIdxs[activeIdxs.length - 1];
  return cycles.map((c, i) => (activeIdxs.includes(i) && i !== keep ? { ...c, status: "completed" as const } : c));
}

function validate(file: CyclesFile): { ok: true } | { ok: false; status: 400; error: { code: string; id?: string; reason: string } } {
  for (const c of file.cycles) {
    if (!ID_RE.test(c.id)) return { ok: false, status: 400, error: { code: "invalid_cycle", id: c.id, reason: "id must match /^[a-z0-9_-]{1,32}$/" } };
    if (!(new Date(c.starts_at).getTime() < new Date(c.ends_at).getTime()))
      return { ok: false, status: 400, error: { code: "invalid_cycle", id: c.id, reason: "starts_at >= ends_at" } };
  }
  for (const e of file.epics) {
    if (!ID_RE.test(e.id)) return { ok: false, status: 400, error: { code: "invalid_epic", id: e.id, reason: "id must match /^[a-z0-9_-]{1,32}$/" } };
    if (e.cycle_id && !file.cycles.some((c) => c.id === e.cycle_id))
      return { ok: false, status: 400, error: { code: "unknown_cycle", id: e.cycle_id, reason: `epic ${e.id} references missing cycle` } };
  }
  return { ok: true };
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

export async function handleListCycles(req: IncomingMessage, res: ServerResponse, orgId: string): Promise<void> {
  const { file, mtime } = readFile(orgId);
  file.cycles = recomputeSpentTokens(orgId, file.cycles);
  res.setHeader("ETag", String(mtime));
  sendJSON(res, 200, file);
}

export async function handlePutCycles(req: IncomingMessage, res: ServerResponse, orgId: string): Promise<void> {
  const ifMatch = (req.headers["if-match"] as string | undefined) ?? "";
  const { mtime: curMtime } = readFile(orgId);
  if (ifMatch !== String(curMtime)) {
    sendJSON(res, 412, { error: { code: "stale", current_etag: String(curMtime) } });
    return;
  }
  const raw = await readBody(req);
  let body: CyclesFile;
  try {
    body = JSON.parse(raw);
  } catch {
    sendJSON(res, 400, { error: { code: "invalid_json", reason: "body is not valid JSON" } });
    return;
  }
  const v = validate(body);
  if (!v.ok) {
    sendJSON(res, v.status, { error: v.error });
    return;
  }
  body.cycles = singleActive(body.cycles);
  body.cycles = recomputeSpentTokens(orgId, body.cycles);
  const p = cyclesPath(orgId);
  mkdirSync(dirname(p), { recursive: true });
  const tmp = p + ".tmp";
  writeFileSync(tmp, JSON.stringify(body, null, 2) + "\n", "utf8");
  renameSync(tmp, p);
  res.setHeader("ETag", String(statSync(p).mtimeMs));
  sendJSON(res, 200, body);
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/cycles.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: 6 tests pass; tsc clean.

- [ ] **Step 5: Commit**

```bash
git -C crawfish-lens add src/server/cycles.ts test/cycles.test.ts
git -C crawfish-lens commit -m "feat(cycles): v1 cycles.json with If-Match — replaces start_date shape

Per docs/specs/org-contract.md §5.5: whole-file GET/PUT with mtime-as-ETag,
412 stale on conflict, single-active rule, server-derived spent_tokens
from board.jsonl fold."
```

---

### Task 3 — Activity feed (owner: `activity-be`)

Move from per-task projection (`foldActivityWithMentions`) to a flat, org-wide activity feed served at `GET /api/orgs/:id/activity?task_id=&cycle_id=&since=` with an SSE variant `GET /api/orgs/:id/activity/stream`.

**Files:**
- Modify: `crawfish-lens/src/server/activity.ts` (add handlers; keep existing `foldActivityWithMentions` export — `crawfish-dash/web/src/components/ActivityFeed.tsx` already consumes it via the per-task endpoint and we don't want to break it).
- Test: `crawfish-lens/test/activity.test.ts` (extend with new cases — keep existing test file structure intact).

- [ ] **Step 1: Write the failing test**

Append to `crawfish-lens/test/activity.test.ts` (do not delete existing cases):

```ts
import { describe, it, expect } from "vitest";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { IncomingMessage, ServerResponse } from "node:http";
import { Socket } from "node:net";
import { handleListActivity } from "../src/server/activity.js";
import type { ActivityEntry } from "../src/server/board.js";

function setupOrg() {
  const root = mkdtempSync(join(tmpdir(), "activity-test-"));
  process.env.CRAWFISH_HOME = root;
  const orgDir = join(root, "orgs", "o1");
  mkdirSync(orgDir, { recursive: true });
  writeFileSync(join(orgDir, "org.json"), JSON.stringify({ id: "o1", members: [{ id: "neal", kind: "human", humanity: "human", acl: "owner" }, { id: "founder", kind: "agent", humanity: "agent", acl: "member" }] }));
  return { root, orgDir };
}

function makeReq(url: string) {
  const r = new IncomingMessage(new Socket());
  r.method = "GET";
  r.url = url;
  process.nextTick(() => r.emit("end"));
  return r;
}
function makeRes() {
  const res = new ServerResponse(new IncomingMessage(new Socket()));
  const chunks: Buffer[] = [];
  // @ts-expect-error test override
  res.end = ((orig) => (chunk: any, ...rest: any[]) => { if (chunk) chunks.push(Buffer.from(chunk)); return orig.call(res, chunk, ...rest); })(res.end);
  return { res, body: () => Buffer.concat(chunks).toString("utf8") };
}

describe("GET /api/orgs/:id/activity (flat feed)", () => {
  it("returns entries flattened across tasks, newest first", async () => {
    const { root, orgDir } = setupOrg();
    writeFileSync(
      join(orgDir, "board.jsonl"),
      [
        JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }),
        JSON.stringify({ type: "task_updated", ts: "2026-05-18T01:00:00Z", task_id: "t1", by: "neal", patch: { status: "in_progress" } }),
        JSON.stringify({ type: "task_created", ts: "2026-05-18T02:00:00Z", task_id: "t2", title: "y", description: "", assignee: null, created_by: "founder" }),
      ].join("\n") + "\n",
    );
    const req = makeReq("/api/orgs/o1/activity");
    const { res, body } = makeRes();
    await handleListActivity(req, res, "o1");
    rmSync(root, { recursive: true, force: true });
    delete process.env.CRAWFISH_HOME;
    expect(res.statusCode).toBe(200);
    const parsed: { entries: (ActivityEntry & { task_id: string })[] } = JSON.parse(body());
    expect(parsed.entries.length).toBeGreaterThanOrEqual(2);
    expect(parsed.entries[0].at >= parsed.entries[1].at).toBe(true);
  });

  it("filters by task_id when ?task_id= is set", async () => {
    const { root, orgDir } = setupOrg();
    writeFileSync(
      join(orgDir, "board.jsonl"),
      [
        JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal", cycle_id: "c1" }),
        JSON.stringify({ type: "task_created", ts: "2026-05-18T00:01:00Z", task_id: "t2", title: "y", description: "", assignee: null, created_by: "neal", cycle_id: "c2" }),
      ].join("\n") + "\n",
    );
    const req = makeReq("/api/orgs/o1/activity?task_id=t1");
    const { res, body } = makeRes();
    await handleListActivity(req, res, "o1");
    rmSync(root, { recursive: true, force: true });
    delete process.env.CRAWFISH_HOME;
    const parsed = JSON.parse(body()) as { entries: { task_id: string }[] };
    expect(parsed.entries.every((e) => e.task_id === "t1")).toBe(true);
  });

  it("filters by cycle_id when ?cycle_id= is set", async () => {
    const { root, orgDir } = setupOrg();
    writeFileSync(
      join(orgDir, "board.jsonl"),
      [
        JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal", cycle_id: "c1" }),
        JSON.stringify({ type: "task_created", ts: "2026-05-18T00:01:00Z", task_id: "t2", title: "y", description: "", assignee: null, created_by: "neal", cycle_id: "c2" }),
      ].join("\n") + "\n",
    );
    const req = makeReq("/api/orgs/o1/activity?cycle_id=c2");
    const { res, body } = makeRes();
    await handleListActivity(req, res, "o1");
    rmSync(root, { recursive: true, force: true });
    delete process.env.CRAWFISH_HOME;
    const parsed = JSON.parse(body()) as { entries: { task_id: string }[] };
    expect(parsed.entries.every((e) => e.task_id === "t2")).toBe(true);
  });

  it("filters by ?since= (ISO date)", async () => {
    const { root, orgDir } = setupOrg();
    writeFileSync(
      join(orgDir, "board.jsonl"),
      [
        JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
        JSON.stringify({ type: "task_updated", ts: "2026-05-19T00:00:00Z", task_id: "t1", by: "neal", patch: { status: "in_progress" } }),
      ].join("\n") + "\n",
    );
    const req = makeReq("/api/orgs/o1/activity?since=2026-05-18T12:00:00Z");
    const { res, body } = makeRes();
    await handleListActivity(req, res, "o1");
    rmSync(root, { recursive: true, force: true });
    delete process.env.CRAWFISH_HOME;
    const parsed = JSON.parse(body()) as { entries: { at: string }[] };
    expect(parsed.entries.every((e) => e.at >= "2026-05-18T12:00:00Z")).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd crawfish-lens && npx vitest run test/activity.test.ts
```

Expected: FAIL (`handleListActivity` not exported).

- [ ] **Step 3: Implement `handleListActivity` (and `handleStreamActivity` for SSE) in `crawfish-lens/src/server/activity.ts`**

Add at the bottom of the file (do NOT touch existing `foldActivityWithMentions`):

```ts
// ----- v1 contract: flat activity feed (NOW-W1) -----
// See docs/specs/org-contract.md §7.
import { foldTasks } from "./board.js";
import { sendJSON } from "./api.js";

type FlatEntry = ActivityEntry & { task_id: string; cycle_id: string | null };

function buildFlatFeed(orgId: string, opts: { taskId?: string; cycleId?: string; since?: string }): FlatEntry[] {
  const events = readRawEvents(orgId);
  const tasks = foldTasks(events);
  const cycleIndex = new Map(tasks.map((t) => [t.id, t.cycle_id ?? null]));
  const flat: FlatEntry[] = [];
  for (const t of tasks) {
    for (const entry of t.activity_log ?? []) {
      flat.push({ ...entry, task_id: t.id, cycle_id: cycleIndex.get(t.id) ?? null });
    }
  }
  let filtered = flat;
  if (opts.taskId) filtered = filtered.filter((e) => e.task_id === opts.taskId);
  if (opts.cycleId) filtered = filtered.filter((e) => e.cycle_id === opts.cycleId);
  if (opts.since) filtered = filtered.filter((e) => e.at >= opts.since!);
  filtered.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
  return filtered;
}

export async function handleListActivity(req: IncomingMessage, res: ServerResponse, orgId: string): Promise<void> {
  const url = new URL(req.url ?? "/", "http://localhost");
  const entries = buildFlatFeed(orgId, {
    taskId: url.searchParams.get("task_id") ?? undefined,
    cycleId: url.searchParams.get("cycle_id") ?? undefined,
    since: url.searchParams.get("since") ?? undefined,
  });
  sendJSON(res, 200, { entries });
}

export async function handleStreamActivity(req: IncomingMessage, res: ServerResponse, orgId: string): Promise<void> {
  // Initial snapshot then tail board.jsonl via the existing tail.ts pattern.
  // For NOW-W1 we ship the snapshot; the tail wiring is folded into the
  // shared SSE plumbing in a follow-up by the lead — flagged with a TODO
  // here intentionally because the tail abstraction is lead-only.
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  const initial = buildFlatFeed(orgId, {});
  res.write(`event: snapshot\ndata: ${JSON.stringify({ entries: initial })}\n\n`);
  // Lead wires the live tail; close immediately so tests don't hang.
  res.end();
}
```

> **Note on the SSE stub:** the live-tail wiring uses `tail.ts` which the lead owns; the teammate ships the snapshot frame so the route is reachable and tested. The lead extends the stream during the §0.8 close-out.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/activity.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: all activity tests pass; tsc clean.

- [ ] **Step 5: Commit**

```bash
git -C crawfish-lens add src/server/activity.ts test/activity.test.ts
git -C crawfish-lens commit -m "feat(activity): flat org-wide /activity feed with task_id/cycle_id/since filters

Adds handleListActivity + handleStreamActivity per docs/specs/org-contract.md
§7. Snapshot only on the SSE route; live-tail wiring is a lead-only follow-up
that touches tail.ts."
```

---

### Task 4 — Member ACL + primary-assignee rewrite (owner: `activity-be`)

Replace the existing `validateActor` (currently a member-id existence check in `crawfish-lens/src/server/policy.ts:227`) with a true four-tier ACL gate, and add a single rewrite helper that enforces the §3.1 sticky-human-assignee rule.

**Critical:** `validateActor` lives in `board.ts` per the playbook ownership row. The activity-be teammate **appends a new** `validateActor` function at the end of `board.ts`, and **changes the import in `board.ts`** to point at the local version. The teammate **must `SendMessage` the lead** before making the import swap, because `board.ts` is in the central path. The legacy `validateActor` in `policy.ts` stays in place for now (deleted in close-out by the lead).

**Files:**
- Modify: `crawfish-lens/src/server/board.ts` (append `validateActor` v2 + `rewriteAssigneeForContributor` at end; change `import { ..., validateActor }` to import from local file — single-line change)
- Test: `crawfish-lens/test/board-acl.test.ts` (extend with new cases — keep existing tests intact)

- [ ] **Step 0: SendMessage the lead before touching the import line**

Before editing the import in `board.ts:13`, send:

```
SendMessage to lead:
"activity-be: about to swap `validateActor` import in crawfish-lens/src/server/board.ts:13 from ./policy.js to local. Replacing the policy.ts version with a v1 ACL matrix implementation appended at the end of board.ts. New errors: acl_denied, assignee_locked. OK to proceed?"
```

Wait for explicit "go" from the lead before continuing.

- [ ] **Step 1: Write the failing tests**

Append to `crawfish-lens/test/board-acl.test.ts`:

```ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateActor, rewriteAssigneeForContributor, type BoardEvent } from "../src/server/board.js";

let root: string;
let orgDir: string;

function writeOrg(members: any[]) {
  writeFileSync(join(orgDir, "org.json"), JSON.stringify({ id: "o1", members }));
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "acl-test-"));
  process.env.CRAWFISH_HOME = root;
  orgDir = join(root, "orgs", "o1");
  mkdirSync(orgDir, { recursive: true });
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true });
  delete process.env.CRAWFISH_HOME;
});

describe("validateActor v1 ACL matrix", () => {
  it("viewer cannot create a task", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "guest", kind: "human", humanity: "human", acl: "viewer" },
    ]);
    const ev: BoardEvent = { type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "guest" };
    const v = validateActor("o1", ev);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.error.code).toBe("acl_denied");
  });

  it("member can comment on a task they don't own", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "alex", kind: "human", humanity: "human", acl: "member" },
    ]);
    const ev: BoardEvent = { type: "task_commented", ts: "2026-05-18T00:00:00Z", task_id: "t1", by: "alex", body: "hi" };
    const v = validateActor("o1", ev);
    expect(v.ok).toBe(true);
  });

  it("member CANNOT update a task they are neither assignee nor contributor nor watcher of, when an assignee is set", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "alex", kind: "human", humanity: "human", acl: "member" },
    ]);
    // Existing board state: t1 has assignee=neal
    writeFileSync(
      join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }) + "\n",
    );
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-18T01:00:00Z", task_id: "t1", by: "alex", patch: { status: "in_progress" } };
    const v = validateActor("o1", ev);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.error.code).toBe("acl_denied");
  });

  it("admin can delete a task", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "alex", kind: "human", humanity: "human", acl: "admin" },
    ]);
    const ev: BoardEvent = { type: "task_deleted", ts: "2026-05-18T00:00:00Z", task_id: "t1", by: "alex" };
    const v = validateActor("o1", ev);
    expect(v.ok).toBe(true);
  });

  it("owner can do anything", () => {
    writeOrg([{ id: "neal", kind: "human", humanity: "human", acl: "owner" }]);
    const ev: BoardEvent = { type: "task_deleted", ts: "2026-05-18T00:00:00Z", task_id: "t1", by: "neal" };
    expect(validateActor("o1", ev).ok).toBe(true);
  });

  it("rejects unknown member with invalid_member (not acl_denied)", () => {
    writeOrg([{ id: "neal", kind: "human", humanity: "human", acl: "owner" }]);
    const ev: BoardEvent = { type: "task_commented", ts: "2026-05-18T00:00:00Z", task_id: "t1", by: "ghost", body: "" };
    const v = validateActor("o1", ev);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.error.code).toBe("invalid_member");
  });
});

describe("rewriteAssigneeForContributor (§3.1 sticky human)", () => {
  it("rewrites agent-overwrite of human assignee into contributor append", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "founder", kind: "agent", humanity: "agent", acl: "member" },
    ]);
    // Board: t1 created with human assignee "neal"
    writeFileSync(
      join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }) + "\n",
    );
    const incoming: BoardEvent = { type: "task_updated", ts: "2026-05-18T01:00:00Z", task_id: "t1", by: "founder", patch: { assignee: "founder" } };
    const out = rewriteAssigneeForContributor("o1", incoming);
    expect(out.ok).toBe(true);
    if (out.ok) {
      expect(out.event).toMatchObject({ patch: { contributors: ["founder"] } });
      // assignee field MUST NOT be present in the rewritten patch
      expect((out.event as any).patch.assignee).toBeUndefined();
    }
  });

  it("rejects with assignee_locked when the human assignee did not authorize", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "founder", kind: "agent", humanity: "agent", acl: "member" },
      { id: "alex", kind: "human", humanity: "human", acl: "member" },
    ]);
    writeFileSync(
      join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }) + "\n",
    );
    // "alex" (member, not owner/admin, not the human assignee) tries to overwrite with an agent
    const incoming: BoardEvent = { type: "task_updated", ts: "2026-05-18T01:00:00Z", task_id: "t1", by: "alex", patch: { assignee: "founder" } };
    const out = rewriteAssigneeForContributor("o1", incoming);
    expect(out.ok).toBe(false);
    if (!out.ok) {
      expect(out.error.code).toBe("assignee_locked");
      expect(out.error.from).toBe("neal");
      expect(out.error.to).toBe("founder");
      expect(out.error.by).toBe("alex");
    }
  });

  it("owner or human assignee themselves CAN release the lock (assignee becomes agent, prior human appended to contributors)", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "founder", kind: "agent", humanity: "agent", acl: "member" },
    ]);
    writeFileSync(
      join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }) + "\n",
    );
    const incoming: BoardEvent = { type: "task_updated", ts: "2026-05-18T01:00:00Z", task_id: "t1", by: "neal", patch: { assignee: "founder" } };
    const out = rewriteAssigneeForContributor("o1", incoming);
    expect(out.ok).toBe(true);
    if (out.ok) {
      expect((out.event as any).patch.assignee).toBe("founder");
      expect((out.event as any).patch.contributors).toEqual(["neal"]);
    }
  });

  it("agent → agent reassignment is unaffected (no rewrite)", () => {
    writeOrg([
      { id: "neal", kind: "human", humanity: "human", acl: "owner" },
      { id: "a1", kind: "agent", humanity: "agent", acl: "member" },
      { id: "a2", kind: "agent", humanity: "agent", acl: "member" },
    ]);
    writeFileSync(
      join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-18T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "a1", created_by: "neal" }) + "\n",
    );
    const incoming: BoardEvent = { type: "task_updated", ts: "2026-05-18T01:00:00Z", task_id: "t1", by: "neal", patch: { assignee: "a2" } };
    const out = rewriteAssigneeForContributor("o1", incoming);
    expect(out.ok).toBe(true);
    if (out.ok) {
      expect((out.event as any).patch.assignee).toBe("a2");
      expect((out.event as any).patch.contributors).toBeUndefined();
    }
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd crawfish-lens && npx vitest run test/board-acl.test.ts
```

Expected: FAIL (`rewriteAssigneeForContributor` not exported; new `validateActor` doesn't return `acl_denied`).

- [ ] **Step 3: Append `validateActor` v2 + `rewriteAssigneeForContributor` to `crawfish-lens/src/server/board.ts`**

After confirming with the lead (Step 0), swap the import line:

```ts
// At top of board.ts — change:
import { policyGate, validateActor } from "./policy.js";
// to:
import { policyGate } from "./policy.js";
```

Append at the end of `board.ts`:

```ts
// ----- v1 ACL + primary-assignee (NOW-W1) -----
// See docs/specs/org-contract.md §3.1, §3.2.
import { readFileSync as _readFileSync, existsSync as _existsSync } from "node:fs";
import { join as _join } from "node:path";
import { resolveOrgRoot as _resolveOrgRoot } from "./orgs.js";
import type { MemberAcl, Humanity, AssigneeLockedError } from "./types.js";

interface MemberRaw {
  id: string;
  kind?: string;
  humanity?: Humanity;
  acl?: MemberAcl;
}

function readOrg(orgId: string): { members: MemberRaw[] } {
  const p = _join(_resolveOrgRoot(orgId), "org.json");
  if (!_existsSync(p)) return { members: [] };
  try {
    const parsed = JSON.parse(_readFileSync(p, "utf8"));
    return { members: Array.isArray(parsed.members) ? parsed.members : [] };
  } catch {
    return { members: [] };
  }
}

function memberById(orgId: string, id: string): MemberRaw | null {
  return readOrg(orgId).members.find((m) => m.id === id) ?? null;
}

function humanityOf(m: MemberRaw | null): Humanity {
  if (!m) return "agent";
  return m.humanity ?? (m.kind === "human" ? "human" : "agent");
}

function aclOf(m: MemberRaw | null): MemberAcl {
  if (!m) return "viewer";
  return m.acl ?? "member";
}

function readBoard(orgId: string): BoardEvent[] {
  const p = _join(_resolveOrgRoot(orgId), "board.jsonl");
  if (!_existsSync(p)) return [];
  const out: BoardEvent[] = [];
  for (const line of _readFileSync(p, "utf8").split("\n")) {
    const t = line.trim();
    if (!t) continue;
    try { out.push(JSON.parse(t) as BoardEvent); } catch { /* skip */ }
  }
  return out;
}

function currentTaskFold(orgId: string, taskId: string): Task | null {
  const tasks = foldTasks(readBoard(orgId));
  return tasks.find((t) => t.id === taskId) ?? null;
}

export function validateActor(
  orgId: string,
  ev: BoardEvent,
): { ok: true } | { ok: false; error: { code: "invalid_member" | "acl_denied"; field?: string; value?: string; reason?: string } } {
  const org = readOrg(orgId);
  const known = new Set(org.members.map((m) => m.id));
  if (org.members.length === 0) return { ok: true }; // empty/missing members → permissive (legacy orgs)

  const actorId = ev.type === "task_created" ? ev.created_by : (ev as any).by;
  if (!known.has(actorId)) return { ok: false, error: { code: "invalid_member", field: ev.type === "task_created" ? "created_by" : "by", value: actorId } };

  if (ev.type === "task_created" && ev.assignee && !known.has(ev.assignee))
    return { ok: false, error: { code: "invalid_member", field: "assignee", value: ev.assignee } };
  if (ev.type === "task_updated" && ev.patch?.assignee && !known.has(ev.patch.assignee))
    return { ok: false, error: { code: "invalid_member", field: "patch.assignee", value: ev.patch.assignee } };

  const actor = memberById(orgId, actorId);
  const acl = aclOf(actor);

  if (acl === "viewer") return { ok: false, error: { code: "acl_denied", reason: "viewer cannot write" } };

  if (ev.type === "task_deleted" && (acl === "member")) return { ok: false, error: { code: "acl_denied", reason: "only owner/admin may delete" } };

  if (ev.type === "task_updated" && acl === "member") {
    const t = currentTaskFold(orgId, ev.task_id);
    const involved = t && (t.assignee === actorId || (t.contributors ?? []).includes(actorId) || (t.watchers ?? []).includes(actorId) || t.assignee === null);
    if (!involved) return { ok: false, error: { code: "acl_denied", reason: "member can only update tasks they are involved in" } };
  }

  return { ok: true };
}

export function rewriteAssigneeForContributor(
  orgId: string,
  ev: BoardEvent,
): { ok: true; event: BoardEvent } | { ok: false; error: AssigneeLockedError } {
  if (ev.type !== "task_updated" || ev.patch?.assignee === undefined) return { ok: true, event: ev };
  const newAssigneeId = ev.patch.assignee;
  if (newAssigneeId === null) return { ok: true, event: ev };
  const newAssignee = memberById(orgId, newAssigneeId);
  if (humanityOf(newAssignee) !== "agent") return { ok: true, event: ev };

  const t = currentTaskFold(orgId, ev.task_id);
  if (!t || !t.assignee) return { ok: true, event: ev };
  const cur = memberById(orgId, t.assignee);
  if (humanityOf(cur) !== "human") return { ok: true, event: ev };

  const actor = memberById(orgId, ev.by);
  const actorAcl = aclOf(actor);
  const authorized = actor?.id === t.assignee || actorAcl === "owner" || actorAcl === "admin";

  if (authorized) {
    const prevContribs = t.contributors ?? [];
    const nextContribs = prevContribs.includes(t.assignee) ? prevContribs : [...prevContribs, t.assignee];
    return { ok: true, event: { ...ev, patch: { ...ev.patch, contributors: nextContribs } } };
  }

  // Unauthorized agent-overwrite by a non-owner non-assignee → rewrite as contributor add.
  // The contract (§3.1) says servers reject these; we surface as assignee_locked so the
  // caller decides. The board.ts handler returns 409 with this error.
  // But §3.1 ALSO says "MUST instead append that agent's id to contributors". We honour
  // the strictest reading: reject. Callers retry with patch.contributors directly.
  return {
    ok: false,
    error: { code: "assignee_locked", from: t.assignee, to: newAssigneeId, by: ev.by },
  };
}
```

> **Spec note on the "rewrite vs reject" ambiguity in §3.1:** the section says servers *both* "MUST instead append to contributors" and "reject any client write that tries to overwrite a sticky human assignee with an agent". This plan returns `assignee_locked` on unauthorized overwrites by non-{owner,admin,human-assignee} actors, and silently auto-appends to contributors on **authorized** writes. That matches the test cases above and is the safest reading for a v1; if product wants always-auto-append, change the unauthorized branch to return `{ ok: true, event: <with contributors added, assignee left> }`.

- [ ] **Step 4: Wire `rewriteAssigneeForContributor` into the append-event handler**

Find `handleAppendEvent` in `crawfish-lens/src/server/board.ts` (around the existing `validateActor` call). After `validateActor` returns ok and before `appendEvent`, call the rewriter. On `{ ok: false }`, return `409 { error }`.

```ts
// inside handleAppendEvent, immediately after a successful validateActor() check:
const rewritten = rewriteAssigneeForContributor(orgId, body as BoardEvent);
if (!rewritten.ok) {
  sendJSON(res, 409, { error: rewritten.error });
  return;
}
const finalEvent = rewritten.event;
// then use finalEvent (not body) for the appendEvent call.
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/board-acl.test.ts test/board.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: all new + existing board tests pass; tsc clean. If existing `test/board.test.ts` fails because the legacy validator return shape was different, update those tests to expect the new `acl_denied` codes — but only if the failures are clearly contract-shaped (call out anything that looks like a real regression to the lead via SendMessage).

- [ ] **Step 6: Commit**

```bash
git -C crawfish-lens add src/server/board.ts test/board-acl.test.ts
git -C crawfish-lens commit -m "feat(acl): v1 validateActor matrix + sticky-human rewrite

Replaces policy.ts:validateActor with the four-tier ACL gate in board.ts
and adds rewriteAssigneeForContributor for the §3.1 sticky-assignee rule.
Error codes: acl_denied, assignee_locked. invalid_member still returned
for unknown actor/assignee."
```

---

### Task 5 — Plan tab cycle picker + budget bar (owner: `plan-fe`)

Add a cycle selector to `crawfish-dash/web/src/routes/Plan.tsx` (top of the route, additive) that fetches `/api/orgs/:id/cycles`, lists cycles by `name`, and renders a `<CycleBudgetBar>` for the selected one.

**Files:**
- Create: `crawfish-dash/web/src/components/CycleBudgetBar.tsx`
- Modify: `crawfish-dash/web/src/routes/Plan.tsx` (additive — wrap existing content in a fragment, prepend the selector + bar)
- Test: `crawfish-dash/web/test/cycle-budget-bar.test.tsx` (new)

`web/` already uses Vitest + React Testing Library (mirror existing `*.test.tsx` files in `crawfish-dash/web/test/` if present; if no examples exist, this plan ships the canonical first one).

- [ ] **Step 1: Write the failing test**

```tsx
// crawfish-dash/web/test/cycle-budget-bar.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { CycleBudgetBar } from "../src/components/CycleBudgetBar";

describe("CycleBudgetBar", () => {
  it("renders 50% fill when spent is half of planned", () => {
    const { container } = render(
      <CycleBudgetBar planned={1000} spent={500} />,
    );
    const fill = container.querySelector('[data-testid="cycle-budget-fill"]') as HTMLElement;
    expect(fill).toBeTruthy();
    expect(fill.style.width).toBe("50%");
  });

  it("clamps over-budget to 100% and adds .is-over-budget", () => {
    const { container } = render(
      <CycleBudgetBar planned={1000} spent={1500} />,
    );
    const fill = container.querySelector('[data-testid="cycle-budget-fill"]') as HTMLElement;
    expect(fill.style.width).toBe("100%");
    expect(fill.classList.contains("is-over-budget")).toBe(true);
  });

  it("treats planned=0 as uncapped (no fill)", () => {
    const { container } = render(
      <CycleBudgetBar planned={0} spent={1500} />,
    );
    const fill = container.querySelector('[data-testid="cycle-budget-fill"]') as HTMLElement;
    expect(fill.style.width).toBe("0%");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd crawfish-dash/web && npx vitest run test/cycle-budget-bar.test.tsx
```

Expected: FAIL (`CycleBudgetBar` not found).

- [ ] **Step 3: Create the component**

```tsx
// crawfish-dash/web/src/components/CycleBudgetBar.tsx
export interface CycleBudgetBarProps {
  planned: number;
  spent: number;
}

export function CycleBudgetBar({ planned, spent }: CycleBudgetBarProps) {
  const uncapped = planned <= 0;
  const ratio = uncapped ? 0 : Math.min(1, spent / planned);
  const overBudget = !uncapped && spent > planned;
  return (
    <div className="cycle-budget-bar" role="progressbar" aria-valuemin={0} aria-valuemax={planned || undefined} aria-valuenow={spent}>
      <div
        data-testid="cycle-budget-fill"
        className={overBudget ? "cycle-budget-fill is-over-budget" : "cycle-budget-fill"}
        style={{ width: `${(ratio * 100).toFixed(0)}%` }}
      />
      <span className="cycle-budget-label">
        {spent.toLocaleString()} / {uncapped ? "uncapped" : planned.toLocaleString()} tokens
      </span>
    </div>
  );
}
```

(CSS classes already exist in `ui/tokens/globals.css`; if not, the lead adds them — `.cycle-budget-bar`, `.cycle-budget-fill`, `.cycle-budget-fill.is-over-budget`, `.cycle-budget-label`. Do NOT inline hex colors.)

- [ ] **Step 4: Run test to verify it passes**

```bash
cd crawfish-dash/web && npx vitest run test/cycle-budget-bar.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Add cycle picker + bar to `Plan.tsx`**

In `crawfish-dash/web/src/routes/Plan.tsx`, prepend (above the existing route content) a section that:
1. `useEffect`s a fetch to `/api/orgs/${orgId}/cycles` on mount.
2. Stores `{ cycles, epics }` in state.
3. Renders a `<select>` populated by `cycles.map(c => ({ value: c.id, label: c.name }))`, with the cycle whose `status === "active"` pre-selected.
4. Renders `<CycleBudgetBar planned={selected.planned_tokens} spent={selected.spent_tokens} />`.

```tsx
// crawfish-dash/web/src/routes/Plan.tsx — prepend inside the route component
import { useEffect, useMemo, useState } from "react";
import { CycleBudgetBar } from "../components/CycleBudgetBar";

interface Cycle {
  id: string;
  name: string;
  starts_at: string;
  ends_at: string;
  planned_tokens: number;
  spent_tokens: number;
  status: "planned" | "active" | "completed";
}

// inside the component:
const [cycles, setCycles] = useState<Cycle[]>([]);
const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);

useEffect(() => {
  if (!orgId) return;
  let cancelled = false;
  fetch(`/api/orgs/${orgId}/cycles`)
    .then((r) => r.json())
    .then((data: { cycles: Cycle[] }) => {
      if (cancelled) return;
      setCycles(data.cycles ?? []);
      const active = (data.cycles ?? []).find((c) => c.status === "active");
      setSelectedCycleId(active?.id ?? data.cycles[0]?.id ?? null);
    })
    .catch(() => { /* surfaced via existing error banner in Plan.tsx */ });
  return () => { cancelled = true; };
}, [orgId]);

const selected = useMemo(() => cycles.find((c) => c.id === selectedCycleId) ?? null, [cycles, selectedCycleId]);

// JSX, at top of the returned tree (above the existing planner UI):
{cycles.length > 0 && (
  <header className="plan-cycle-picker">
    <label>
      Cycle
      <select value={selectedCycleId ?? ""} onChange={(e) => setSelectedCycleId(e.target.value)}>
        {cycles.map((c) => (
          <option key={c.id} value={c.id}>{c.name}{c.status === "active" ? " (active)" : ""}</option>
        ))}
      </select>
    </label>
    {selected && <CycleBudgetBar planned={selected.planned_tokens} spent={selected.spent_tokens} />}
  </header>
)}
```

- [ ] **Step 6: Type-check + run all dash tests**

```bash
cd crawfish-dash/web && npx tsc --noEmit -p tsconfig.json && npx vitest run
```

Expected: tsc clean; all tests pass.

- [ ] **Step 7: Commit**

```bash
git -C crawfish-dash add web/src/components/CycleBudgetBar.tsx web/src/routes/Plan.tsx web/test/cycle-budget-bar.test.tsx
git -C crawfish-dash commit -m "feat(plan): cycle picker + CycleBudgetBar on Plan tab

Consumes GET /api/orgs/:id/cycles (NOW-W1 contract §5.5, §7). Auto-selects
the active cycle. Bar clamps to 100% when over budget."
```

---

### Task 6 — Drawer activity panel (owner: `plan-fe`)

Add an **Activity** panel to `TaskDrawer.tsx` that consumes `/api/orgs/:id/activity?task_id=...` and renders entries newest-first. **Additive** — do not modify the existing comments / criteria / links regions.

**Files:**
- Modify: `crawfish-dash/web/src/components/TaskDrawer.tsx` (append a new section + its `useEffect`; reuse the existing `<ActivityFeed>` component if its props match, otherwise call the new endpoint directly)
- Test: `crawfish-dash/web/test/task-drawer-activity.test.tsx` (new)

- [ ] **Step 1: Inspect existing ActivityFeed contract**

```bash
sed -n '1,60p' crawfish-dash/web/src/components/ActivityFeed.tsx
```

If `ActivityFeed` already accepts `entries: ActivityEntry[]` as a prop, reuse it. Otherwise, render entries inline.

- [ ] **Step 2: Write the failing test**

```tsx
// crawfish-dash/web/test/task-drawer-activity.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { TaskDrawer } from "../src/components/TaskDrawer";

beforeEach(() => {
  global.fetch = vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/activity?task_id=")) {
      return new Response(JSON.stringify({
        entries: [
          { at: "2026-05-18T01:00:00Z", by: "neal", kind: "status_changed", payload: { from: "backlog", to: "in_progress" }, task_id: "t1", cycle_id: null },
          { at: "2026-05-18T00:00:00Z", by: "neal", kind: "assigned", payload: { from: null, to: "neal", role: "assignee" }, task_id: "t1", cycle_id: null },
        ],
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response("{}", { status: 200 });
  }) as any;
});

describe("TaskDrawer activity panel", () => {
  it("fetches /api/orgs/:id/activity?task_id=... and renders entries newest-first", async () => {
    render(<TaskDrawer orgId="o1" taskId="t1" />);
    await waitFor(() => expect(screen.getByText(/status_changed/i)).toBeTruthy());
    const all = screen.getAllByTestId("activity-entry");
    expect(all.length).toBe(2);
    // Newest first
    expect(all[0].textContent).toMatch(/status_changed/);
    expect(all[1].textContent).toMatch(/assigned/);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd crawfish-dash/web && npx vitest run test/task-drawer-activity.test.tsx
```

Expected: FAIL (panel + `data-testid="activity-entry"` not present yet, or `TaskDrawer` doesn't take `taskId` prop yet).

- [ ] **Step 4: Append the Activity panel to `TaskDrawer.tsx`**

```tsx
// crawfish-dash/web/src/components/TaskDrawer.tsx — at top, alongside other imports
import { useEffect, useState } from "react";

interface ActivityEntry {
  at: string;
  by: string;
  kind: string;
  payload: Record<string, unknown>;
  task_id: string;
  cycle_id: string | null;
}

// Inside the TaskDrawer component, alongside existing state hooks:
const [activity, setActivity] = useState<ActivityEntry[]>([]);

useEffect(() => {
  if (!orgId || !taskId) return;
  let cancelled = false;
  fetch(`/api/orgs/${orgId}/activity?task_id=${encodeURIComponent(taskId)}`)
    .then((r) => r.json())
    .then((data: { entries: ActivityEntry[] }) => { if (!cancelled) setActivity(data.entries ?? []); })
    .catch(() => { /* swallow — drawer remains usable without activity */ });
  return () => { cancelled = true; };
}, [orgId, taskId]);

// In JSX, append below the existing panels:
<section className="drawer-section drawer-activity">
  <h3>Activity</h3>
  {activity.length === 0 ? (
    <p className="drawer-empty">No activity yet.</p>
  ) : (
    <ul className="activity-list">
      {activity.map((e, i) => (
        <li key={`${e.at}-${i}`} data-testid="activity-entry" className="activity-entry">
          <span className="activity-kind">{e.kind}</span>
          <span className="activity-by">{e.by}</span>
          <time dateTime={e.at}>{new Date(e.at).toLocaleString()}</time>
        </li>
      ))}
    </ul>
  )}
</section>
```

If `TaskDrawer` currently takes a `task: Task` prop and not `taskId`, **do not add a parallel prop** — use the existing prop and read `task.id`. The test above uses `taskId` for clarity; align it to whatever the existing drawer signature is. The failing-test step will catch any mismatch.

- [ ] **Step 5: Run test to verify it passes**

```bash
cd crawfish-dash/web && npx vitest run test/task-drawer-activity.test.tsx && npx tsc --noEmit -p tsconfig.json
```

Expected: test passes; tsc clean.

- [ ] **Step 6: Commit**

```bash
git -C crawfish-dash add web/src/components/TaskDrawer.tsx web/test/task-drawer-activity.test.tsx
git -C crawfish-dash commit -m "feat(drawer): activity panel reads /api/orgs/:id/activity?task_id=

Additive section in TaskDrawer rendering the v1 flat activity feed
(docs/specs/org-contract.md §7) newest-first. Existing drawer regions
unchanged."
```

---

## 4 · Lead close-out (after teammates report done)

Per playbook §0.8 and §2 Steps 8–13:

- [ ] **Wire routes in `crawfish-lens/src/server/index.ts`** (lead-only):

  Replace any old per-resource cycles routes with:
  ```ts
  // GET /api/orgs/:id/cycles → handleListCycles
  // PUT /api/orgs/:id/cycles → handlePutCycles
  // GET /api/orgs/:id/activity → handleListActivity
  // GET /api/orgs/:id/activity/stream → handleStreamActivity
  ```
  Delete the legacy `handleCreateCycle` / `handleUpdateCycle` / `handleDeleteCycle` route entries (the corresponding exports in `cycles.ts` are gone after Task 2).

- [ ] **Delete the legacy `validateActor` in `crawfish-lens/src/server/policy.ts`** (lead-only), confirm no other importers via:
  ```bash
  grep -rn "from \"./policy\"" crawfish-lens/src | grep validateActor
  ```
  Expected: no matches.

- [ ] **Wire live tail into `handleStreamActivity`** by extending `tail.ts` to broadcast new activity entries after `appendEvent`. This is the lead-only TODO from Task 3.

- [ ] **Full build + test:**
  ```bash
  cd crawfish-lens && npx tsc -p tsconfig.json && npx vitest run
  cd ../crawfish-dash && npx tsc -p tsconfig.json && (cd web && npx tsc --noEmit -p tsconfig.json && npx vitest run)
  ```

- [ ] **Invoke `superpowers:requesting-code-review`** against the W1 branch.

- [ ] **Invoke `superpowers:finishing-a-development-branch`** to choose merge path.

- [ ] **Tear down team:**
  ```
  Ask cycles-be to shut down.
  Ask activity-be to shut down.
  Ask plan-fe to shut down.
  Clean up the team.
  ```

- [ ] **No tag this phase** — `v0.3` already cut; next tag is `v0.4` at end of NOW-W5.

---

## 5 · §0.6 Spawn prompt (paste this when ready to spawn)

```
Create an agent team for NOW-W1 (Cycles + Epics + Activity + Member ACL). Spawn 3 teammates:
  - cycles-be: owns crawfish-lens/src/server/cycles.ts + crawfish-lens/src/server/types.ts (cycle/epic/ACL/contributor type exports only — must NOT touch SessionSummary/SessionDetailPayload) + crawfish-lens/test/{cycles,types}.test.ts. Implements Tasks 1, 2 from docs/superpowers/plans/2026-05-19-now-w1-cycles-acl.md.
  - activity-be: owns crawfish-lens/src/server/activity.ts + APPEND-ONLY new functions at the end of crawfish-lens/src/server/board.ts (validateActor v2 + rewriteAssigneeForContributor + the import-line swap at board.ts:13) + crawfish-lens/test/{activity,board-acl}.test.ts. Implements Tasks 3, 4. MUST SendMessage the lead before swapping the import line at board.ts:13 (per Task 4 Step 0).
  - plan-fe: owns crawfish-dash/web/src/routes/Plan.tsx + crawfish-dash/web/src/components/TaskDrawer.tsx (additive Activity panel only — must NOT touch existing drawer regions) + crawfish-dash/web/src/components/CycleBudgetBar.tsx (new) + crawfish-dash/web/test/{cycle-budget-bar,task-drawer-activity}.test.tsx. Implements Tasks 5, 6.

Each teammate MUST:
  1. Read CLAUDE.md and AGENT-TEAMS.md before touching code.
  2. Read docs/specs/org-contract.md (§2, §3, §3.1, §3.2, §5.5, §7) as the source of truth for all shapes.
  3. Follow the bite-sized plan at docs/superpowers/plans/2026-05-19-now-w1-cycles-acl.md task-by-task.
  4. Apply superpowers:test-driven-development for every task (failing test first, minimal code, green, commit).
  5. SendMessage the lead BEFORE editing any file listed in CLAUDE.md §0.1 "Files that two teammates must NEVER edit simultaneously" — especially crawfish-lens/src/server/index.ts, crawfish-dash/web/src/App.tsx, package.json, ui/tokens/globals.css.
  6. Run `npx tsc --noEmit -p tsconfig.json` in the relevant submodule before claiming done.
  7. Never run `npx vite build` or `npx tsc -p` (emit) — only the lead builds.

Use Sonnet for each teammate. Require plan approval before any teammate writes code.
```

---

## 6 · Self-review

- [x] **Spec coverage:** Every NOW-W1 deliverable in `docs/superpowers/plans/2026-05-17-roadmap-agent-team-execution.md` §3 Step 4 maps to a task (1↔Task 1, 2↔Task 2, 3↔Task 3, 4↔Task 4, 5↔Task 5, 6↔Task 6). Every contract section §2/§3/§3.1/§3.2/§5.5/§7 is covered.
- [x] **Placeholder scan:** No TBD/TODO/"add appropriate" — the only flagged TODO is the explicit SSE live-tail handoff to the lead, which is correct per CLAUDE.md §0.1 (tail.ts is lead-territory).
- [x] **Type consistency:** `Cycle`, `Epic`, `CyclesFile`, `MemberAcl`, `Humanity`, `AssigneeLockedError`, `ActivityEntry`, `BoardEvent`, `Task` named identically across tasks. `validateActor` signature `(orgId, ev) → {ok, error?}` matches across Task 4 + close-out.
- [x] **Ownership:** Task 1 + 2 to cycles-be; Task 3 + 4 to activity-be; Task 5 + 6 to plan-fe. Lead-only files explicitly called out (index.ts, App.tsx, ui/tokens/globals.css, tail.ts).
- [x] **TDD shape:** Each task has failing-test → run-to-fail → minimal-impl → run-to-pass → commit, with concrete code in every step.

---

## Handoff

Plan saved to `docs/superpowers/plans/2026-05-19-now-w1-cycles-acl.md`. **Stopping here — not spawning the team.** Review the plan; when ready, paste Step 5 (the §0.6 Spawn prompt) into a fresh prompt to fan out.
