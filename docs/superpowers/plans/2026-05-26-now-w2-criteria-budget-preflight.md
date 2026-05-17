# NOW-W2 — Acceptance Criteria + Token-Budget Bar + Agent Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-task acceptance criteria with a done-transition guard, per-task token-budget visualisation, and an agent-side preflight-attestation primitive — extending NOW-W1's contract without breaking it.

**Architecture:** Three teammates work in parallel against the updated [`docs/specs/org-contract.md`](../../specs/org-contract.md) (§3.3 done-transition, §3.4 activity kinds, `Criterion` type, three new MCP tools, two new error codes) and the new [`docs/specs/preflight-contract.md`](../../specs/preflight-contract.md). `criteria-be` adds types + the done-transition guard + criteria event flow to lens. `budget-fe` ships the per-task budget bar and the drawer criteria editor + evidence chips. `preflight-orgctl` writes the lens preflight endpoint and the orgctl MCP wrapper that forwards into it. Lead-only at close-out: wiring the new lens route into `index.ts`, registering the preflight MCP tool in orgctl's `index.ts`.

**Tech Stack:** TypeScript · Node http (no framework) · Vitest in `crawfish-lens` + `crawfish-dash/web` · `node --test` in `crawfish-orgctl` (already configured per `package.json:test`) · `@modelcontextprotocol/sdk` for orgctl · React + Vite (dash).

**Built on NOW-W1 (already shipped — do not reinvent):**
- `contributors[]` on Task and `task_updated.patch` — fold semantics in `crawfish-lens/src/server/board.ts:foldTasks`.
- v1 `validateActor` four-tier ACL + `rewriteAssigneeForContributor` appended at the end of `board.ts` (see board.ts:540 and 588). New ACL gates in W2 reuse this function — DO NOT fork it.
- Flat activity feed `GET /api/orgs/:id/activity` (lens) and the SSE snapshot — `crawfish-lens/src/server/activity.ts`. New activity kinds (`criterion_met`, `criterion_cleared`, `preflight_attested`) project through the existing `buildFlatFeed` path.
- Cycles `cycles.json` + `GET/PUT /cycles` with `If-Match` — irrelevant to W2 except that the per-task `budget_breach` activity entries now disambiguate `scope: "task" | "cycle"` (contract §3.4).

---

## 0 · Pre-flight (lead, before any teammate writes code)

- [ ] Confirm contract additions exist:
  ```bash
  grep -nE "criteria_unmet|preflight_attested|CriterionKind|criterion_met" docs/specs/org-contract.md docs/specs/preflight-contract.md
  ```
  Expected: matches in org-contract.md §3.3, §3.4, §6, and across preflight-contract.md.

- [ ] Confirm NOW-W1 primitives are in place (sanity):
  ```bash
  grep -n "validateActor\|rewriteAssigneeForContributor\|foldTasks" crawfish-lens/src/server/board.ts | head
  ```
  Expected: `validateActor` at ~line 540, `rewriteAssigneeForContributor` at ~588, `foldTasks` at ~175.

- [ ] Confirm orgctl test framework:
  ```bash
  cd crawfish-orgctl && grep '"test"' package.json
  ```
  Expected: `"test": "tsc -p tsconfig.test.json && node --test dist-test/test/contract.test.js"` — node's built-in test runner, not Vitest.

- [ ] No teammate touches `crawfish-lens/src/server/index.ts`, `crawfish-orgctl/src/index.ts`, `crawfish-dash/web/src/App.tsx`, `ui/tokens/globals.css`, or any `package.json`. All five are lead-only per [`CLAUDE.md`](../../../CLAUDE.md) §0.1.

---

## 1 · File responsibilities

| File | Owner | Responsibility |
|---|---|---|
| `crawfish-lens/src/server/types.ts` | `criteria-be` | Append `Criterion`, `CriterionEvidence`, `CriterionKind` (re-exported from board.ts source of truth, or defined here — pick types.ts; both files re-export). |
| `crawfish-lens/src/server/board.ts` | `criteria-be` | Add `criteria: Criterion[]`, `token_budget`, `token_spent` to `Task`; add `criteria` to `task_updated.patch`; add `preflight_attested` BoardEvent member and `criterion_met` / `criterion_cleared` to `ActivityKind`. Append `validateDoneTransition()` + `projectCriteriaActivity()` + `onBudgetBreach()` at end of file. Wire into `handlePostBoard` (existing handler at board.ts:443). |
| `crawfish-lens/test/criteria.test.ts` | `criteria-be` | New file: done-transition guard cases + criteria_set + criteria_attest event flow + budget-breach projection. |
| `crawfish-lens/src/server/preflight.ts` | `preflight-orgctl` | New file: `handlePostPreflight(req, res, orgId)` — validates agent membership, validates criterion exists, enforces `statement.length >= 16`, idempotent on `(task_id, criterion_id, by)` within 5 minutes, appends `preflight_attested` event via `appendEvent()`. |
| `crawfish-lens/test/preflight.test.ts` | `preflight-orgctl` | New file: validates §2 behaviour from preflight-contract.md. |
| `crawfish-orgctl/src/preflight.ts` | `preflight-orgctl` | New file: `PREFLIGHT_TOOL_DEFS` + `dispatchPreflight()` — thin RPC to `POST /api/orgs/:org_id/preflight`. Mirror the shape of `tools/activity.ts`. |
| `crawfish-orgctl/test/preflight.test.ts` | `preflight-orgctl` | New file: node:test cases mocking the lens fetch. |
| `crawfish-dash/web/src/components/TaskBudgetBar.tsx` | `budget-fe` | New. Per-task analog of `CycleBudgetBar` — same visual treatment, different props. |
| `crawfish-dash/web/src/components/TaskDrawer.tsx` | `budget-fe` | ADDITIVE only — append a criteria editor + evidence chips panel and mount `<TaskBudgetBar>` near the existing header. No other regions edited. |
| `crawfish-dash/web/test/budget-bar.test.tsx` | `budget-fe` | New. |
| `crawfish-dash/web/test/criteria-panel.test.tsx` | `budget-fe` | New. |
| `crawfish-lens/src/server/index.ts` | **lead only** | Wire `POST /api/orgs/:id/preflight` to `handlePostPreflight` after teammates report done. |
| `crawfish-orgctl/src/index.ts` | **lead only** | Register `PREFLIGHT_TOOL_DEFS` + `dispatchPreflight` in the same pattern as `ACTIVITY_TOOL_DEFS`. |

---

## 2 · Type contract recap (read before coding)

- `docs/specs/org-contract.md` **§3** — `Criterion`, `CriterionEvidence`, `CriterionKind` types (already defined in the contract; you just mirror them in code).
- **§3.3** — done-transition guard: a `task_updated.patch` setting `status: "done"` is rejected with `409 { error: { code: "criteria_unmet", task_id, unmet: [criterion_id, ...] } }` unless every criterion has non-null `evidence`. Tasks with **zero** criteria transition freely.
- **§3.4** — new activity kinds `criterion_met` / `criterion_cleared`; `budget_breach` payload disambiguates `scope: "task" | "cycle"`.
- **§6** — new MCP tools `criteria_set`, `criteria_attest`, `preflight_attest` (with error codes `criteria_unmet` and `unknown_criterion`).
- `docs/specs/preflight-contract.md` **§2** — server behaviour for `preflight_attest` (validate `by` is agent, validate `criterion_id` exists, `statement.length >= 16`, append `preflight_attested` event, auto-set evidence when `criterion.kind === "preflight"`).
- **§3** — `preflight_attested` BoardEvent shape + `ActivityKind` extension.
- **§5** — REST: `POST /api/orgs/:org_id/preflight`; idempotent on `(task_id, criterion_id, by)` within 5 minutes.

---

## 3 · Tasks

### Task 1 — Criterion + token_budget/token_spent types (owner: `criteria-be`)

Surface the new types on `Task` and the `task_updated.patch`. Also append the `preflight_attested` BoardEvent member and the two new `ActivityKind` values — they're cheap to land here and unblock the other two teammates.

**Files:**
- Modify: `crawfish-lens/src/server/types.ts` (append v1 NOW-W2 exports — do not touch SessionSummary/SessionDetailPayload or the existing NOW-W1 exports)
- Modify: `crawfish-lens/src/server/board.ts:Task` interface — add `criteria`, `token_budget`, `token_spent`
- Modify: `crawfish-lens/src/server/board.ts:BoardEvent` union — add `task_updated.patch.criteria`, append `preflight_attested` member, extend `ActivityKind` with `criterion_met` and `criterion_cleared`
- Modify: `crawfish-lens/src/server/board.ts:foldTasks` — initialise `criteria: [], token_budget: 0, token_spent: 0` on `task_created`; apply `criteria` and `token_spent`/`token_budget` patches on `task_updated`
- Test: `crawfish-lens/test/criteria.test.ts` (new — first tests just for the type/fold layer)

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-lens/test/criteria.test.ts
import { describe, it, expect } from "vitest";
import type {
  Criterion,
  CriterionKind,
  CriterionEvidence,
} from "../src/server/types.js";
import { foldTasks, type BoardEvent } from "../src/server/board.js";

describe("NOW-W2 types", () => {
  it("CriterionKind enumerates the 5 kinds", () => {
    const kinds: CriterionKind[] = ["behavioral", "test", "metric", "preflight", "manual"];
    expect(kinds).toHaveLength(5);
  });

  it("Criterion + CriterionEvidence shapes compile", () => {
    const e: CriterionEvidence = { kind: "preflight", payload: { event_id: "01k", by: "a1", at: "2026-05-20T00:00:00Z" } };
    const c: Criterion = { id: "spec-reviewed", statement: "Read the spec", kind: "preflight", evidence: e };
    expect(c.evidence?.kind).toBe("preflight");
  });
});

describe("Task fold gains criteria + budget fields", () => {
  it("defaults to empty criteria + zero budget on task_created", () => {
    const events: BoardEvent[] = [
      { type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" },
    ];
    const tasks = foldTasks(events);
    expect(tasks[0].criteria).toEqual([]);
    expect(tasks[0].token_budget).toBe(0);
    expect(tasks[0].token_spent).toBe(0);
  });

  it("applies criteria + token_budget + token_spent patches", () => {
    const events: BoardEvent[] = [
      { type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" },
      {
        type: "task_updated",
        ts: "2026-05-20T00:01:00Z",
        task_id: "t1",
        by: "neal",
        patch: {
          criteria: [{ id: "c1", statement: "must X", kind: "behavioral" }],
          token_budget: 50000,
          token_spent: 1234,
        },
      },
    ];
    const tasks = foldTasks(events);
    expect(tasks[0].criteria).toHaveLength(1);
    expect(tasks[0].criteria[0].id).toBe("c1");
    expect(tasks[0].token_budget).toBe(50000);
    expect(tasks[0].token_spent).toBe(1234);
  });

  it("token_spent accumulates additively across multiple patches", () => {
    const events: BoardEvent[] = [
      { type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" },
      { type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { token_spent: 1000 } },
      { type: "task_updated", ts: "2026-05-20T00:02:00Z", task_id: "t1", by: "neal", patch: { token_spent: 1500 } },
    ];
    const tasks = foldTasks(events);
    // Decision: token_spent is a *replace*, not a delta. Patches always carry the running total.
    // Server-side recomputation is the job of the activity projector, not the fold.
    expect(tasks[0].token_spent).toBe(1500);
  });
});

describe("preflight_attested BoardEvent + new ActivityKinds", () => {
  it("preflight_attested events fold through (do not change Task state)", () => {
    const events: BoardEvent[] = [
      { type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" },
      {
        type: "preflight_attested",
        ts: "2026-05-20T00:01:00Z",
        event_id: "01k",
        task_id: "t1",
        criterion_id: "spec-reviewed",
        by: "a1",
        statement: "I read the spec and verified §3.3",
        payload: {},
      },
    ];
    const tasks = foldTasks(events);
    expect(tasks).toHaveLength(1);
    // preflight_attested does NOT mutate the task — it's purely an activity event.
    // (Auto-setting criterion.evidence is done by Task 5, not the fold.)
    expect(tasks[0].criteria).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd crawfish-lens && npx vitest run test/criteria.test.ts
```

Expected: FAIL on missing exports `Criterion`, `CriterionKind`, `CriterionEvidence`; `Task.criteria` undefined; `preflight_attested` not in `BoardEvent`.

- [ ] **Step 3: Append types to `crawfish-lens/src/server/types.ts`**

```ts
// crawfish-lens/src/server/types.ts — append at end (preserve NOW-W1 exports above)

// ----- NOW-W2 acceptance criteria -----
// See docs/specs/org-contract.md §3 (Criterion), §3.3 (done guard), §3.4 (activity kinds).

export type CriterionKind = "behavioral" | "test" | "metric" | "preflight" | "manual";

export interface CriterionEvidence {
  kind: CriterionKind;
  payload: Record<string, unknown>;
}

export interface Criterion {
  id: string;                  // /^[a-z0-9_-]{1,32}$/, unique within task
  statement: string;           // ≥ 8 chars
  kind: CriterionKind;
  evidence?: CriterionEvidence;
}
```

- [ ] **Step 4: Extend `board.ts:Task`, `BoardEvent`, `foldTasks`**

In `crawfish-lens/src/server/board.ts`:

```ts
// 1. Imports — add at top of NOW-W2 import block:
import type { Criterion } from "./types.js";

// 2. In the `Task` interface — add immediately after `contributors`:
  criteria: Criterion[];
  token_budget: number;
  token_spent: number;

// 3. In task_updated.patch — add inside the partial:
        criteria: Criterion[];
        token_budget: number;
        token_spent: number;

// 4. Extend ActivityKind union — add:
  | "criterion_met"
  | "criterion_cleared"
  | "preflight_attested"   // also used by preflight-orgctl Task 5

// 5. Append a new BoardEvent union member (alongside task_created/updated/commented/deleted):
  | {
      type: "preflight_attested";
      ts: string;
      event_id: string;     // ULID — matches the fold key
      task_id: string;
      criterion_id: string;
      by: string;           // agent member id
      statement: string;    // ≥ 16 chars (validated at endpoint, not fold)
      payload: Record<string, unknown>;
    };

// 6. In foldTasks — task_created branch — initialise:
        criteria: [],
        token_budget: 0,
        token_spent: 0,

// 7. In foldTasks — task_updated branch — apply patches:
      if (ev.patch.criteria !== undefined) t.criteria = ev.patch.criteria;
      if (ev.patch.token_budget !== undefined) t.token_budget = ev.patch.token_budget;
      if (ev.patch.token_spent !== undefined) t.token_spent = ev.patch.token_spent;

// 8. In foldTasks — handle preflight_attested (no-op on Task state, but skip the unknown-type
//    default that would otherwise log a warning). Just `case "preflight_attested": continue;`
//    in the switch, or guard with `if (ev.type === "preflight_attested") continue;` before
//    the switch — match whichever style the existing fold uses.
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/criteria.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: 5 tests pass; tsc clean. Existing W1 tests must still pass:

```bash
cd crawfish-lens && npx vitest run
```

Expected: 65+5 = 70 tests pass total.

- [ ] **Step 6: Commit**

```bash
git -C crawfish-lens add src/server/types.ts src/server/board.ts test/criteria.test.ts
git -C crawfish-lens commit -m "feat(types): NOW-W2 Criterion/budget surfaces; preflight_attested event

Adds Criterion + CriterionEvidence + CriterionKind types and threads
criteria/token_budget/token_spent through Task fold + task_updated patch.
Appends preflight_attested to BoardEvent and three new ActivityKinds
(criterion_met, criterion_cleared, preflight_attested). Per
docs/specs/org-contract.md §3.3 / §3.4 and preflight-contract.md §3."
```

---

### Task 2 — Done-transition guard + budget-breach projector (owner: `criteria-be`)

Append two pure functions at the end of `board.ts` and wire them into `handlePostBoard` (the existing event-append handler at board.ts:443). NOW-W1's `validateActor` + `rewriteAssigneeForContributor` already live at the end of the file — your new functions slot in alongside them. The pre-existing call sequence inside `handlePostBoard` is `validateActor → rewriteAssigneeForContributor → appendEvent`; you insert your guard between `rewriteAssigneeForContributor` and `appendEvent`.

**Files:**
- Modify: `crawfish-lens/src/server/board.ts` (append `validateDoneTransition` + `projectCriteriaActivity` + `onBudgetBreach` at end; modify `handlePostBoard` call sequence — minimal in-place insert)
- Modify: `crawfish-lens/test/criteria.test.ts` (extend with done-guard + budget-breach cases)

- [ ] **Step 1: Write the failing tests**

Append to `crawfish-lens/test/criteria.test.ts`:

```ts
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateDoneTransition, type BoardEvent } from "../src/server/board.js";

function makeOrg(): { root: string; orgDir: string; cleanup: () => void } {
  const root = mkdtempSync(join(tmpdir(), "criteria-test-"));
  process.env.CRAWFISH_HOME = root;
  const orgDir = join(root, "orgs", "o1");
  mkdirSync(orgDir, { recursive: true });
  writeFileSync(join(orgDir, "org.json"), JSON.stringify({ id: "o1", members: [
    { id: "neal",    kind: "human", humanity: "human", acl: "owner"  },
    { id: "founder", kind: "agent", humanity: "agent", acl: "member" },
  ]}));
  return {
    root, orgDir,
    cleanup: () => { rmSync(root, { recursive: true, force: true }); delete process.env.CRAWFISH_HOME; },
  };
}

describe("validateDoneTransition (§3.3)", () => {
  it("allows status:done when there are zero criteria (v0.3 back-compat)", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }) + "\n");
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T01:00:00Z", task_id: "t1", by: "neal", patch: { status: "done" } };
    expect(validateDoneTransition("o1", ev).ok).toBe(true);
    cleanup();
  });

  it("rejects status:done when any criterion lacks evidence", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [
        { id: "c1", statement: "must X", kind: "behavioral" },
        { id: "c2", statement: "must Y", kind: "manual",     evidence: { kind: "manual", payload: { by: "neal", at: "2026-05-20T00:02:00Z" } } },
      ]}}),
    ].join("\n") + "\n");
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T01:00:00Z", task_id: "t1", by: "neal", patch: { status: "done" } };
    const v = validateDoneTransition("o1", ev);
    expect(v.ok).toBe(false);
    if (!v.ok) {
      expect(v.error.code).toBe("criteria_unmet");
      expect(v.error.task_id).toBe("t1");
      expect(v.error.unmet).toEqual(["c1"]);
    }
    cleanup();
  });

  it("allows status:done when every criterion has evidence", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [
        { id: "c1", statement: "must X", kind: "behavioral", evidence: { kind: "behavioral", payload: { note: "verified" } } },
      ]}}),
    ].join("\n") + "\n");
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T01:00:00Z", task_id: "t1", by: "neal", patch: { status: "done" } };
    expect(validateDoneTransition("o1", ev).ok).toBe(true);
    cleanup();
  });

  it("ignores non-done transitions", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }) + "\n");
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T01:00:00Z", task_id: "t1", by: "neal", patch: { status: "in_progress" } };
    expect(validateDoneTransition("o1", ev).ok).toBe(true);
    cleanup();
  });

  it("returns ok when the patch carries no status field", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"),
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }) + "\n");
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T01:00:00Z", task_id: "t1", by: "neal", patch: { token_spent: 500 } };
    expect(validateDoneTransition("o1", ev).ok).toBe(true);
    cleanup();
  });
});

describe("budget-breach projection (§3.4)", () => {
  it("projects a single budget_breach activity entry the first time token_spent exceeds token_budget", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { token_budget: 1000 } }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:02:00Z", task_id: "t1", by: "neal", patch: { token_spent: 1500 } }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:03:00Z", task_id: "t1", by: "neal", patch: { token_spent: 2000 } }),
    ].join("\n") + "\n");
    const { foldTasks } = require("../src/server/board.js");
    const events = readFileSync(join(orgDir, "board.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
    const tasks = foldTasks(events);
    const breaches = tasks[0].activity_log.filter((e: { kind: string }) => e.kind === "budget_breach");
    expect(breaches).toHaveLength(1);
    expect((breaches[0] as { payload: { scope: string } }).payload.scope).toBe("task");
    cleanup();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd crawfish-lens && npx vitest run test/criteria.test.ts
```

Expected: 6 new failures — `validateDoneTransition` not exported; budget-breach not projected.

- [ ] **Step 3: Append `validateDoneTransition` + `onBudgetBreach` to `board.ts`**

At the very end of `crawfish-lens/src/server/board.ts` (after `rewriteAssigneeForContributor`):

```ts
// ----- NOW-W2 done-transition guard + budget-breach projector -----
// See docs/specs/org-contract.md §3.3, §3.4.

export interface CriteriaUnmetError {
  code: "criteria_unmet";
  task_id: string;
  unmet: string[];
}

export function validateDoneTransition(
  orgId: string,
  ev: BoardEvent,
): { ok: true } | { ok: false; error: CriteriaUnmetError } {
  if (ev.type !== "task_updated") return { ok: true };
  if (ev.patch?.status !== "done") return { ok: true };
  const t = currentTaskFold(orgId, ev.task_id);
  if (!t) return { ok: true };  // unknown task — let appendEvent handle
  const criteria = ev.patch.criteria ?? t.criteria ?? [];
  if (criteria.length === 0) return { ok: true };
  const unmet = criteria.filter((c) => !c.evidence).map((c) => c.id);
  if (unmet.length === 0) return { ok: true };
  return { ok: false, error: { code: "criteria_unmet", task_id: ev.task_id, unmet } };
}

// onBudgetBreach is invoked by the fold projector when a task_updated patch
// raises token_spent above the running token_budget AND no prior budget_breach
// is already in activity_log for this task (dedupe). Returns an ActivityEntry
// to be appended, or null to skip.
export function onBudgetBreach(
  taskBeforePatch: Task,
  patch: { token_spent?: number; token_budget?: number },
  ts: string,
  by: string,
): ActivityEntry | null {
  const nextSpent = patch.token_spent ?? taskBeforePatch.token_spent;
  const nextBudget = patch.token_budget ?? taskBeforePatch.token_budget;
  if (nextBudget <= 0) return null;
  if (nextSpent <= nextBudget) return null;
  const already = (taskBeforePatch.activity_log ?? []).some(
    (e) => e.kind === "budget_breach" && (e.payload as { scope?: string })?.scope === "task",
  );
  if (already) return null;
  return {
    by,
    at: ts,
    kind: "budget_breach",
    payload: { scope: "task", id: taskBeforePatch.id, spent: nextSpent, budget: nextBudget },
  };
}
```

- [ ] **Step 4: Wire `validateDoneTransition` into `handlePostBoard`**

Find `handlePostBoard` in `crawfish-lens/src/server/board.ts:443`. Immediately after the existing `rewriteAssigneeForContributor` call and before `appendEvent`, insert:

```ts
const doneGuard = validateDoneTransition(orgId, rewritten.event as BoardEvent);
if (!doneGuard.ok) {
  sendJSON(res, 409, { error: doneGuard.error });
  return;
}
```

The existing `rewritten.event` variable is the patched event (W1 may have appended `contributors`). Pass that one — not the raw body — so done-guard sees the canonical event.

- [ ] **Step 5: Wire `onBudgetBreach` into the foldTasks projector**

In `foldTasks` at `crawfish-lens/src/server/board.ts:175`, inside the `task_updated` branch, **before** applying the `token_spent` / `token_budget` patch fields, snapshot the pre-patch task, then after applying patches push the optional breach entry into `t.activity_log`:

```ts
case "task_updated": {
  const t = byId.get(ev.task_id);
  if (!t) break;
  const snapshot: Task = { ...t, activity_log: [...t.activity_log] };
  // ... existing patch applications, including the new criteria/token_* patches from Task 1 ...

  // After token_spent / token_budget patches:
  const breach = onBudgetBreach(snapshot, ev.patch ?? {}, ev.ts, ev.by);
  if (breach) t.activity_log.push(breach);

  break;
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/criteria.test.ts test/board.test.ts test/activity.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: 11 criteria tests pass; existing 22 board + 8 activity tests still pass; tsc clean.

- [ ] **Step 7: Commit**

```bash
git -C crawfish-lens add src/server/board.ts test/criteria.test.ts
git -C crawfish-lens commit -m "feat(criteria): done-transition guard + per-task budget_breach projector

Per docs/specs/org-contract.md §3.3: a task_updated patch setting
status:done is rejected with 409 criteria_unmet unless every criterion
has non-null evidence. Tasks with zero criteria still transition freely.
Per §3.4: budget_breach activity entries now disambiguate scope=task vs
scope=cycle; per-task breaches fire exactly once per breach episode."
```

---

### Task 3 — Criteria set/attest event flow (owner: `criteria-be`)

`criteria_set` and `criteria_attest` are MCP tool names (per contract §6), but their server-side implementation is **just additional cases on top of the existing `task_updated` patch** — no new endpoint needed. The MCP wrapper would forward to `POST /api/orgs/:id/board` with the appropriate patch. The work here is the **activity projection** for `criterion_met` / `criterion_cleared` and the **ACL gate** for clearing evidence.

**Files:**
- Modify: `crawfish-lens/src/server/board.ts` — extend `foldTasks` to project `criterion_met` / `criterion_cleared` entries on each criteria-patch transition
- Modify: `crawfish-lens/src/server/board.ts:validateActor` — extend to reject `criteria` patches that clear evidence by a non-owner / non-admin / non-current-assignee actor
- Modify: `crawfish-lens/test/criteria.test.ts` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `crawfish-lens/test/criteria.test.ts`:

```ts
import { validateActor } from "../src/server/board.js";

describe("criteria activity projection", () => {
  it("projects criterion_met when evidence is added", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral" }] }}),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:02:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral", evidence: { kind: "behavioral", payload: { note: "ok" } } }] }}),
    ].join("\n") + "\n");
    const { foldTasks } = require("../src/server/board.js");
    const events = readFileSync(join(orgDir, "board.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
    const tasks = foldTasks(events);
    const met = tasks[0].activity_log.filter((e: { kind: string }) => e.kind === "criterion_met");
    expect(met).toHaveLength(1);
    expect((met[0] as { payload: { id: string } }).payload.id).toBe("c1");
    cleanup();
  });

  it("projects criterion_cleared when evidence is removed", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral", evidence: { kind: "behavioral", payload: {} } }] }}),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:02:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral" }] }}),
    ].join("\n") + "\n");
    const { foldTasks } = require("../src/server/board.js");
    const events = readFileSync(join(orgDir, "board.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
    const tasks = foldTasks(events);
    const cleared = tasks[0].activity_log.filter((e: { kind: string }) => e.kind === "criterion_cleared");
    expect(cleared).toHaveLength(1);
    cleanup();
  });
});

describe("clearing evidence is ACL-gated (§3.3)", () => {
  it("non-owner / non-admin / non-assignee gets acl_denied when clearing evidence", () => {
    const { orgDir, cleanup } = makeOrg();
    // Add a non-assignee member with acl:member.
    writeFileSync(join(orgDir, "org.json"), JSON.stringify({ id: "o1", members: [
      { id: "neal",    kind: "human", humanity: "human", acl: "owner"  },
      { id: "alex",    kind: "human", humanity: "human", acl: "member" },
    ]}));
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral", evidence: { kind: "behavioral", payload: {} } }] }}),
    ].join("\n") + "\n");
    // alex tries to clear evidence
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T00:02:00Z", task_id: "t1", by: "alex", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral" }] }};
    const v = validateActor("o1", ev);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.error.code).toBe("acl_denied");
    cleanup();
  });

  it("owner can clear evidence", () => {
    const { orgDir, cleanup } = makeOrg();
    writeFileSync(join(orgDir, "board.jsonl"), [
      JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: "neal", created_by: "neal" }),
      JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral", evidence: { kind: "behavioral", payload: {} } }] }}),
    ].join("\n") + "\n");
    const ev: BoardEvent = { type: "task_updated", ts: "2026-05-20T00:02:00Z", task_id: "t1", by: "neal", patch: { criteria: [{ id: "c1", statement: "must X", kind: "behavioral" }] }};
    expect(validateActor("o1", ev).ok).toBe(true);
    cleanup();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd crawfish-lens && npx vitest run test/criteria.test.ts
```

Expected: 4 new failures — projection missing; ACL gate on criteria-clear missing.

- [ ] **Step 3: Project criteria transitions in `foldTasks`**

In `crawfish-lens/src/server/board.ts:foldTasks`, inside the `task_updated` branch where you currently apply `ev.patch.criteria`, compute the diff between `t.criteria` (pre-patch) and the incoming `ev.patch.criteria` and push activity entries:

```ts
if (ev.patch.criteria !== undefined) {
  const prev = t.criteria ?? [];
  const next = ev.patch.criteria;
  const prevById = new Map(prev.map((c) => [c.id, c]));
  for (const c of next) {
    const p = prevById.get(c.id);
    if (c.evidence && !p?.evidence) {
      t.activity_log.push({
        by: ev.by, at: ev.ts, kind: "criterion_met",
        payload: { id: c.id, kind: c.kind, evidence: c.evidence },
      });
    } else if (!c.evidence && p?.evidence) {
      t.activity_log.push({
        by: ev.by, at: ev.ts, kind: "criterion_cleared",
        payload: { id: c.id, by: ev.by },
      });
    }
  }
  t.criteria = next;
}
```

- [ ] **Step 4: Extend `validateActor` to gate evidence-clear**

In `crawfish-lens/src/server/board.ts:validateActor` (the W1 function at line ~540), after the existing member-ACL checks but before the `return { ok: true }`, add an evidence-clear check:

```ts
// NOW-W2: clearing evidence on an existing criterion requires owner/admin/current-assignee
if (ev.type === "task_updated" && ev.patch?.criteria !== undefined && (acl === "member" || acl === "viewer")) {
  const t = currentTaskFold(orgId, ev.task_id);
  if (t) {
    const prevById = new Map((t.criteria ?? []).map((c) => [c.id, c]));
    const wouldClear = ev.patch.criteria.some((c) => !c.evidence && prevById.get(c.id)?.evidence);
    if (wouldClear && actorId !== t.assignee) {
      return { ok: false, error: { code: "acl_denied", reason: "only owner/admin/current-assignee may clear criterion evidence" } };
    }
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run && npx tsc --noEmit -p tsconfig.json
```

Expected: full lens suite green (75+ tests); tsc clean.

- [ ] **Step 6: Commit**

```bash
git -C crawfish-lens add src/server/board.ts test/criteria.test.ts
git -C crawfish-lens commit -m "feat(criteria): activity projection + evidence-clear ACL

Projects criterion_met / criterion_cleared into Task.activity_log on
each criteria-patch transition. Extends validateActor to reject
evidence-clear by a non-owner/admin/assignee actor (acl_denied)."
```

---

### Task 4 — TaskBudgetBar + drawer criteria panel (owner: `budget-fe`)

Mirror `CycleBudgetBar` for the per-task case, then append a criteria editor + evidence-chip panel to `TaskDrawer`. **Additive only** — do not touch existing drawer regions. CSS classes reuse the `cycle-budget-bar` family — if a `task-budget-bar` variant is needed, `SendMessage` the lead before adding to `globals.css`.

**Files:**
- Create: `crawfish-dash/web/src/components/TaskBudgetBar.tsx`
- Modify: `crawfish-dash/web/src/components/TaskDrawer.tsx` (additive only)
- Test: `crawfish-dash/web/test/budget-bar.test.tsx` (new)
- Test: `crawfish-dash/web/test/criteria-panel.test.tsx` (new)

- [ ] **Step 1: Write the failing test for TaskBudgetBar**

```tsx
// crawfish-dash/web/test/budget-bar.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TaskBudgetBar } from "../src/components/TaskBudgetBar";

describe("TaskBudgetBar", () => {
  it("renders 25% fill when spent is a quarter of budget", () => {
    const { container } = render(<TaskBudgetBar budget={4000} spent={1000} />);
    const fill = container.querySelector('[data-testid="task-budget-fill"]') as HTMLElement;
    expect(fill.style.width).toBe("25%");
  });

  it("clamps over-budget to 100% and adds .is-over-budget", () => {
    const { container } = render(<TaskBudgetBar budget={1000} spent={1500} />);
    const fill = container.querySelector('[data-testid="task-budget-fill"]') as HTMLElement;
    expect(fill.style.width).toBe("100%");
    expect(fill.classList.contains("is-over-budget")).toBe(true);
  });

  it("renders 0% fill when budget is 0 (uncapped)", () => {
    const { container } = render(<TaskBudgetBar budget={0} spent={500} />);
    const fill = container.querySelector('[data-testid="task-budget-fill"]') as HTMLElement;
    expect(fill.style.width).toBe("0%");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd crawfish-dash && npx vitest run --config web/vitest.config.ts test/budget-bar.test.tsx
```

Expected: FAIL — `TaskBudgetBar` not found.

- [ ] **Step 3: Create `TaskBudgetBar`**

```tsx
// crawfish-dash/web/src/components/TaskBudgetBar.tsx
export interface TaskBudgetBarProps {
  budget: number;
  spent: number;
}

export function TaskBudgetBar({ budget, spent }: TaskBudgetBarProps) {
  const uncapped = budget <= 0;
  const ratio = uncapped ? 0 : Math.min(1, spent / budget);
  const overBudget = !uncapped && spent > budget;
  return (
    <div className="cycle-budget-bar" role="progressbar" aria-valuemin={0} aria-valuemax={budget || undefined} aria-valuenow={spent}>
      <div
        data-testid="task-budget-fill"
        className={overBudget ? "cycle-budget-fill is-over-budget" : "cycle-budget-fill"}
        style={{ width: `${(ratio * 100).toFixed(0)}%` }}
      />
      <span className="cycle-budget-label">
        {spent.toLocaleString()} / {uncapped ? "uncapped" : budget.toLocaleString()} tokens
      </span>
    </div>
  );
}
```

(Reuses `cycle-budget-bar` / `cycle-budget-fill` classes intentionally — same visual semantics. If you need a distinct treatment, `SendMessage` the lead first.)

- [ ] **Step 4: Run test to verify it passes**

```bash
cd crawfish-dash && npx vitest run --config web/vitest.config.ts test/budget-bar.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Write the failing test for the criteria panel**

```tsx
// crawfish-dash/web/test/criteria-panel.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TaskDrawer } from "../src/components/TaskDrawer";

beforeEach(() => {
  global.fetch = vi.fn(async () => new Response(JSON.stringify({ entries: [] }), { status: 200 })) as any;
});

describe("TaskDrawer criteria panel", () => {
  it("renders a row per criterion with evidence chips", () => {
    const task = {
      id: "t1", title: "x", description: "", assignee: null, contributors: [],
      status: "in_progress", created_by: "neal", created_at: "", updated_at: "",
      comments: [], cycle_id: null, epic_id: null, links: [], labels: [], watchers: [],
      activity_log: [],
      criteria: [
        { id: "c1", statement: "Tests green", kind: "test", evidence: { kind: "test", payload: { path: "test/x.test.ts", case: "smoke" } } },
        { id: "c2", statement: "Spec reviewed", kind: "preflight" },
      ],
      token_budget: 5000, token_spent: 1200,
    };
    render(<TaskDrawer orgId="o1" task={task as any} />);
    expect(screen.getByText("Tests green")).toBeTruthy();
    expect(screen.getByText("Spec reviewed")).toBeTruthy();
    const rows = screen.getAllByTestId("criterion-row");
    expect(rows).toHaveLength(2);
    expect(rows[0].querySelector('[data-testid="evidence-chip"]')).toBeTruthy(); // c1 has evidence
    expect(rows[1].querySelector('[data-testid="evidence-chip"]')).toBeFalsy();  // c2 unmet
  });

  it("renders a TaskBudgetBar when token_budget > 0", () => {
    const task = {
      id: "t1", title: "x", description: "", assignee: null, contributors: [],
      status: "in_progress", created_by: "neal", created_at: "", updated_at: "",
      comments: [], cycle_id: null, epic_id: null, links: [], labels: [], watchers: [],
      activity_log: [], criteria: [], token_budget: 1000, token_spent: 250,
    };
    render(<TaskDrawer orgId="o1" task={task as any} />);
    expect(screen.getByTestId("task-budget-fill")).toBeTruthy();
  });
});
```

> **NOTE:** the test uses `task={task}` as the drawer prop. If `TaskDrawer.tsx` actually takes a `taskId` prop and fetches the task itself, adapt the test to match — do NOT add a parallel prop to the drawer. Read `crawfish-dash/web/src/components/TaskDrawer.tsx` first to confirm the existing signature, then align the test.

- [ ] **Step 6: Run test to verify it fails**

```bash
cd crawfish-dash && npx vitest run --config web/vitest.config.ts test/criteria-panel.test.tsx
```

Expected: FAIL — no criterion rows; no `task-budget-fill`.

- [ ] **Step 7: Append the criteria panel + TaskBudgetBar mount to `TaskDrawer.tsx`**

Append at the bottom of the existing component's JSX tree (after the W1 Activity panel from Task 6 of NOW-W1):

```tsx
import { TaskBudgetBar } from "./TaskBudgetBar";

// At top of the drawer's returned JSX, near the title row:
{task.token_budget > 0 || task.token_spent > 0 ? (
  <TaskBudgetBar budget={task.token_budget} spent={task.token_spent} />
) : null}

// Lower in the drawer, before the W1 Activity panel:
<section className="drawer-section drawer-criteria">
  <h3>Acceptance criteria</h3>
  {(!task.criteria || task.criteria.length === 0) ? (
    <p className="drawer-empty">No criteria yet.</p>
  ) : (
    <ul className="criteria-list">
      {task.criteria.map((c) => (
        <li key={c.id} data-testid="criterion-row" className={c.evidence ? "criterion-row is-met" : "criterion-row"}>
          <span className="criterion-statement">{c.statement}</span>
          <span className="criterion-kind">{c.kind}</span>
          {c.evidence ? (
            <span data-testid="evidence-chip" className="evidence-chip">{c.evidence.kind}</span>
          ) : null}
        </li>
      ))}
    </ul>
  )}
</section>
```

If the existing `TaskDrawer` does not take a `task` prop (i.e. it only takes `taskId` + `orgId` and fetches the task itself), use `useEffect` to fetch `/api/orgs/:id/board` and find the task by id, **or** adapt the test in Step 5 to wrap the fetch the same way the W1 Activity panel test does it. The fetch URL `/api/orgs/${orgId}/board` is already used by the Board route — do NOT invent a new endpoint.

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd crawfish-dash && npx vitest run --config web/vitest.config.ts && npx tsc --noEmit -p web/tsconfig.json
```

Expected: 7 (NOW-W1) + 5 (NOW-W2) = 12 tests pass; tsc clean.

- [ ] **Step 9: Commit**

```bash
git -C crawfish-dash add web/src/components/TaskBudgetBar.tsx web/src/components/TaskDrawer.tsx web/test/budget-bar.test.tsx web/test/criteria-panel.test.tsx
git -C crawfish-dash commit -m "feat(drawer): TaskBudgetBar + acceptance-criteria panel with evidence chips

Renders per-task budget bar (reuses cycle-budget-bar CSS family) when
token_budget > 0 OR token_spent > 0. Criteria panel lists each
acceptance criterion with evidence chip when evidence is set. Additive
only — existing drawer regions untouched."
```

---

### Task 5 — Lens preflight endpoint (owner: `preflight-orgctl`)

Implements `POST /api/orgs/:org_id/preflight` per preflight-contract.md §5. Appends a `preflight_attested` BoardEvent (Task 1 added the type), validates per §2, idempotent on `(task_id, criterion_id, by)` within 5 minutes, auto-sets `evidence` when `criterion.kind === "preflight"` (by emitting a follow-on `task_updated` patch with criteria).

**Files:**
- Create: `crawfish-lens/src/server/preflight.ts`
- Create: `crawfish-lens/test/preflight.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-lens/test/preflight.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { IncomingMessage, ServerResponse } from "node:http";
import { Socket } from "node:net";
import { handlePostPreflight } from "../src/server/preflight.js";

let root: string;
let orgDir: string;

function makeReq(body: string) {
  const r = new IncomingMessage(new Socket());
  r.method = "POST";
  r.url = "/api/orgs/o1/preflight";
  process.nextTick(() => { r.emit("data", Buffer.from(body)); r.emit("end"); });
  return r;
}
function makeRes() {
  const res = new ServerResponse(new IncomingMessage(new Socket()));
  const chunks: Buffer[] = [];
  // @ts-expect-error
  res.end = ((orig) => (chunk: any, ...rest: any[]) => { if (chunk) chunks.push(Buffer.from(chunk)); return orig.call(res, chunk, ...rest); })(res.end);
  return { res, body: () => Buffer.concat(chunks).toString("utf8") };
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "preflight-test-"));
  process.env.CRAWFISH_HOME = root;
  orgDir = join(root, "orgs", "o1");
  mkdirSync(orgDir, { recursive: true });
  writeFileSync(join(orgDir, "org.json"), JSON.stringify({ id: "o1", members: [
    { id: "neal",    kind: "human", humanity: "human", acl: "owner"  },
    { id: "founder", kind: "agent", humanity: "agent", acl: "member" },
  ]}));
  writeFileSync(join(orgDir, "board.jsonl"), [
    JSON.stringify({ type: "task_created", ts: "2026-05-20T00:00:00Z", task_id: "t1", title: "x", description: "", assignee: null, created_by: "neal" }),
    JSON.stringify({ type: "task_updated", ts: "2026-05-20T00:01:00Z", task_id: "t1", by: "neal", patch: { criteria: [
      { id: "spec-reviewed", statement: "Read the spec",          kind: "preflight" },
      { id: "manual-sign",   statement: "Manual sign-off needed", kind: "manual" },
    ]}}),
  ].join("\n") + "\n");
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true });
  delete process.env.CRAWFISH_HOME;
});

describe("POST /api/orgs/:id/preflight (§2, §5)", () => {
  it("appends preflight_attested and returns event_id", async () => {
    const req = makeReq(JSON.stringify({
      task_id: "t1", criterion_id: "spec-reviewed", by: "founder",
      statement: "Read docs/specs/org-contract.md §3.3 thoroughly",
    }));
    const { res, body } = makeRes();
    await handlePostPreflight(req, res, "o1");
    expect(res.statusCode).toBe(200);
    const parsed = JSON.parse(body());
    expect(parsed.event_id).toMatch(/^[0-9A-Z]{26}$/i);
    const jsonl = readFileSync(join(orgDir, "board.jsonl"), "utf8");
    expect(jsonl).toContain('"type":"preflight_attested"');
    expect(jsonl).toContain('"criterion_id":"spec-reviewed"');
  });

  it("auto-sets evidence when criterion.kind === 'preflight'", async () => {
    const req = makeReq(JSON.stringify({
      task_id: "t1", criterion_id: "spec-reviewed", by: "founder",
      statement: "Read the §3.3 done-transition guard",
    }));
    const { res } = makeRes();
    await handlePostPreflight(req, res, "o1");
    const jsonl = readFileSync(join(orgDir, "board.jsonl"), "utf8");
    // The fold should now see evidence on spec-reviewed.
    const { foldTasks } = await import("../src/server/board.js");
    const events = jsonl.trim().split("\n").map((l) => JSON.parse(l));
    const tasks = foldTasks(events);
    const c = tasks[0].criteria.find((x) => x.id === "spec-reviewed");
    expect(c?.evidence).toBeTruthy();
    expect(c?.evidence?.kind).toBe("preflight");
  });

  it("does NOT auto-set evidence when criterion.kind !== 'preflight'", async () => {
    const req = makeReq(JSON.stringify({
      task_id: "t1", criterion_id: "manual-sign", by: "founder",
      statement: "I read the manual sign-off note in the doc",
    }));
    const { res } = makeRes();
    await handlePostPreflight(req, res, "o1");
    const { foldTasks } = await import("../src/server/board.js");
    const events = readFileSync(join(orgDir, "board.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
    const tasks = foldTasks(events);
    const c = tasks[0].criteria.find((x) => x.id === "manual-sign");
    expect(c?.evidence).toBeUndefined();
  });

  it("rejects when `by` is not an agent member (humans don't preflight)", async () => {
    const req = makeReq(JSON.stringify({
      task_id: "t1", criterion_id: "spec-reviewed", by: "neal",
      statement: "Humans cannot preflight per §2",
    }));
    const { res, body } = makeRes();
    await handlePostPreflight(req, res, "o1");
    expect(res.statusCode).toBe(400);
    expect(JSON.parse(body()).error.code).toBe("invalid_member");
  });

  it("rejects when criterion_id is not on the task", async () => {
    const req = makeReq(JSON.stringify({
      task_id: "t1", criterion_id: "ghost", by: "founder",
      statement: "Trying to attest a missing criterion",
    }));
    const { res, body } = makeRes();
    await handlePostPreflight(req, res, "o1");
    expect(res.statusCode).toBe(404);
    expect(JSON.parse(body()).error.code).toBe("unknown_criterion");
  });

  it("rejects when statement is too short", async () => {
    const req = makeReq(JSON.stringify({
      task_id: "t1", criterion_id: "spec-reviewed", by: "founder",
      statement: "too short",
    }));
    const { res, body } = makeRes();
    await handlePostPreflight(req, res, "o1");
    expect(res.statusCode).toBe(400);
    expect(JSON.parse(body()).error.code).toBe("invalid_statement");
  });

  it("is idempotent on (task_id, criterion_id, by) within 5 minutes — returns prior event_id", async () => {
    const send = async () => {
      const req = makeReq(JSON.stringify({
        task_id: "t1", criterion_id: "spec-reviewed", by: "founder",
        statement: "First attestation — read the doc",
      }));
      const { res, body } = makeRes();
      await handlePostPreflight(req, res, "o1");
      return JSON.parse(body()).event_id;
    };
    const first = await send();
    const second = await send();
    expect(first).toBe(second);
    const lines = readFileSync(join(orgDir, "board.jsonl"), "utf8").trim().split("\n");
    const preflights = lines.filter((l) => l.includes('"type":"preflight_attested"'));
    expect(preflights).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd crawfish-lens && npx vitest run test/preflight.test.ts
```

Expected: FAIL — `handlePostPreflight` not exported.

- [ ] **Step 3: Implement `handlePostPreflight`**

```ts
// crawfish-lens/src/server/preflight.ts
import { type IncomingMessage, type ServerResponse } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { resolveOrgRoot } from "./orgs.js";
import { sendJSON } from "./api.js";
import { appendEvent, foldTasks, ulid, type BoardEvent } from "./board.js";

const IDEMPOTENCY_WINDOW_MS = 5 * 60 * 1000;

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

function readOrg(orgId: string): { members: Array<{ id: string; humanity?: string; kind?: string }> } {
  const p = join(resolveOrgRoot(orgId), "org.json");
  if (!existsSync(p)) return { members: [] };
  try {
    const parsed = JSON.parse(readFileSync(p, "utf8"));
    return { members: Array.isArray(parsed.members) ? parsed.members : [] };
  } catch {
    return { members: [] };
  }
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

export async function handlePostPreflight(
  req: IncomingMessage,
  res: ServerResponse,
  orgId: string,
): Promise<void> {
  const raw = await readBody(req);
  let body: { task_id?: string; criterion_id?: string; by?: string; statement?: string; payload?: Record<string, unknown> };
  try { body = JSON.parse(raw); } catch {
    return sendJSON(res, 400, { error: { code: "invalid_json" } });
  }
  const { task_id, criterion_id, by, statement } = body;
  if (!task_id || !criterion_id || !by || typeof statement !== "string") {
    return sendJSON(res, 400, { error: { code: "invalid_request", reason: "task_id, criterion_id, by, statement required" } });
  }
  if (statement.length < 16) {
    return sendJSON(res, 400, { error: { code: "invalid_statement", reason: "statement must be at least 16 chars" } });
  }

  // Validate `by` is an agent member
  const org = readOrg(orgId);
  const member = org.members.find((m) => m.id === by);
  if (!member) return sendJSON(res, 400, { error: { code: "invalid_member", field: "by", value: by } });
  const humanity = member.humanity ?? (member.kind === "human" ? "human" : "agent");
  if (humanity !== "agent") return sendJSON(res, 400, { error: { code: "invalid_member", field: "by", reason: "humans do not preflight" } });

  // Validate criterion_id is on the task
  const events = readBoardEvents(orgId);
  const tasks = foldTasks(events);
  const task = tasks.find((t) => t.id === task_id);
  if (!task) return sendJSON(res, 404, { error: { code: "not_found", value: task_id } });
  const criterion = (task.criteria ?? []).find((c) => c.id === criterion_id);
  if (!criterion) return sendJSON(res, 404, { error: { code: "unknown_criterion", value: criterion_id } });

  // Idempotency: (task_id, criterion_id, by) within IDEMPOTENCY_WINDOW_MS
  const now = Date.now();
  for (const e of events) {
    if (e.type !== "preflight_attested") continue;
    if (e.task_id !== task_id || e.criterion_id !== criterion_id || e.by !== by) continue;
    if (now - new Date(e.ts).getTime() <= IDEMPOTENCY_WINDOW_MS) {
      return sendJSON(res, 200, { event_id: e.event_id });
    }
  }

  // Append the event
  const ts = new Date().toISOString();
  const event_id = ulid();
  const ev: BoardEvent = {
    type: "preflight_attested",
    ts, event_id, task_id, criterion_id, by, statement,
    payload: body.payload ?? {},
  };
  appendEvent(orgId, ev);

  // Auto-set evidence on preflight-kind criteria via a follow-on task_updated
  if (criterion.kind === "preflight") {
    const nextCriteria = task.criteria.map((c) =>
      c.id === criterion_id
        ? { ...c, evidence: { kind: "preflight" as const, payload: { event_id, by, at: ts } } }
        : c,
    );
    const follow: BoardEvent = {
      type: "task_updated",
      ts,
      task_id,
      by,
      patch: { criteria: nextCriteria },
    };
    appendEvent(orgId, follow);
  }

  return sendJSON(res, 200, { event_id });
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd crawfish-lens && npx vitest run test/preflight.test.ts && npx tsc --noEmit -p tsconfig.json
```

Expected: 7 tests pass; tsc clean.

- [ ] **Step 5: Commit**

```bash
git -C crawfish-lens add src/server/preflight.ts test/preflight.test.ts
git -C crawfish-lens commit -m "feat(preflight): POST /api/orgs/:id/preflight endpoint

Implements docs/specs/preflight-contract.md §2: validates agent membership,
criterion_id exists, statement.length >= 16; idempotent on
(task_id, criterion_id, by) within 5 minutes. Auto-sets evidence on
preflight-kind criteria via a follow-on task_updated patch."
```

---

### Task 6 — orgctl MCP wrapper (owner: `preflight-orgctl`)

A thin MCP tool that forwards `preflight_attest` calls to the lens endpoint from Task 5. Mirror the shape of `crawfish-orgctl/src/tools/activity.ts`.

**Files:**
- Create: `crawfish-orgctl/src/preflight.ts`
- Create: `crawfish-orgctl/test/preflight.test.ts` (uses node's built-in test runner — see `package.json:test`)

- [ ] **Step 1: Write the failing test**

```ts
// crawfish-orgctl/test/preflight.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { PREFLIGHT_TOOL_DEFS, dispatchPreflight } from "../src/preflight.js";

describe("PREFLIGHT_TOOL_DEFS", () => {
  it("exposes a single preflight_attest tool", () => {
    assert.equal(PREFLIGHT_TOOL_DEFS.length, 1);
    assert.equal(PREFLIGHT_TOOL_DEFS[0].name, "preflight_attest");
    assert.ok(PREFLIGHT_TOOL_DEFS[0].description?.length > 50);
    const schema = PREFLIGHT_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).sort(),
      ["by", "criterion_id", "org_id", "statement", "task_id"],
    );
  });
});

describe("dispatchPreflight", () => {
  it("forwards to POST /api/orgs/:id/preflight and returns the event_id", async () => {
    const fetchStub = async (url: string, init: RequestInit) => {
      assert.equal(url, "http://127.0.0.1:7880/api/orgs/o1/preflight");
      assert.equal(init.method, "POST");
      const body = JSON.parse(init.body as string);
      assert.equal(body.task_id, "t1");
      assert.equal(body.criterion_id, "c1");
      assert.equal(body.by, "founder");
      assert.ok(body.statement.length >= 16);
      return new Response(JSON.stringify({ event_id: "01k" }), { status: 200 });
    };
    const result = await dispatchPreflight(
      { org_id: "o1", task_id: "t1", criterion_id: "c1", by: "founder", statement: "Read the spec §3.3 in full" },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.equal(result.event_id, "01k");
  });

  it("surfaces lens errors verbatim", async () => {
    const fetchStub = async () =>
      new Response(JSON.stringify({ error: { code: "unknown_criterion", value: "ghost" } }), { status: 404 });
    const result = await dispatchPreflight(
      { org_id: "o1", task_id: "t1", criterion_id: "ghost", by: "founder", statement: "Attesting a missing criterion" },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.equal(result.error?.code, "unknown_criterion");
  });

  it("rejects locally when statement is too short (no network round-trip)", async () => {
    let called = false;
    const fetchStub = async () => { called = true; return new Response("{}", { status: 200 }); };
    const result = await dispatchPreflight(
      { org_id: "o1", task_id: "t1", criterion_id: "c1", by: "founder", statement: "short" },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(called, false);
    assert.equal(result.error?.code, "invalid_statement");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd crawfish-orgctl && npm test
```

Expected: FAIL — `PREFLIGHT_TOOL_DEFS` not found.

- [ ] **Step 3: Implement the wrapper**

```ts
// crawfish-orgctl/src/preflight.ts

export const PREFLIGHT_TOOL_DEFS = [
  {
    name: "preflight_attest",
    description:
      "Record that you have read the relevant spec, verified the test fixture, or otherwise completed the preparatory work for a criterion BEFORE you take the action that would satisfy it. Pass criterion_id from the task's `criteria` list. Statements must describe what you actually checked, in ≥16 characters. Do NOT preflight without doing the work — the activity log is auditable.",
    inputSchema: {
      type: "object",
      properties: {
        org_id:       { type: "string" },
        task_id:      { type: "string" },
        criterion_id: { type: "string" },
        by:           { type: "string", description: "Your member id." },
        statement:    { type: "string", minLength: 16 },
        payload:      { type: "object", description: "Optional kind-specific evidence detail." },
      },
      required: ["org_id", "task_id", "criterion_id", "by", "statement"],
      additionalProperties: false,
    },
  },
] as const;

export interface PreflightArgs {
  org_id: string;
  task_id: string;
  criterion_id: string;
  by: string;
  statement: string;
  payload?: Record<string, unknown>;
}

export interface PreflightResult {
  tokens_used: number;
  event_id?: string;
  error?: { code: string; message?: string };
}

export async function dispatchPreflight(
  args: PreflightArgs,
  opts: { fetch?: typeof fetch; lensBase?: string } = {},
): Promise<PreflightResult> {
  if (args.statement.length < 16) {
    return { tokens_used: 0, error: { code: "invalid_statement", message: "statement must be at least 16 chars" } };
  }
  const fetchImpl = opts.fetch ?? globalThis.fetch;
  const lensBase = opts.lensBase ?? process.env.CRAWFISH_LENS_BASE ?? "http://127.0.0.1:7880";
  const url = `${lensBase}/api/orgs/${encodeURIComponent(args.org_id)}/preflight`;
  const body = {
    task_id: args.task_id,
    criterion_id: args.criterion_id,
    by: args.by,
    statement: args.statement,
    payload: args.payload,
  };
  const r = await fetchImpl(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: { code: "lens_error", message: `HTTP ${r.status}` } }));
    return { tokens_used: 0, error: err.error ?? { code: "lens_error", message: `HTTP ${r.status}` } };
  }
  const parsed = (await r.json()) as { event_id: string };
  return { tokens_used: 0, event_id: parsed.event_id };
}
```

- [ ] **Step 4: SendMessage the lead before touching `crawfish-orgctl/src/index.ts`**

Per CLAUDE.md, `crawfish-orgctl/src/index.ts` is lead-only. Before claiming the task done, `SendMessage` the lead with:

> "preflight-orgctl: src/preflight.ts shipped (SHA …). Lead: please register `PREFLIGHT_TOOL_DEFS` and `dispatchPreflight` in `crawfish-orgctl/src/index.ts` mirroring the existing `ACTIVITY_TOOL_DEFS` registration pattern (line ~32 for the import, line ~154 for the TOOL_DEFS spread, and the runTool switch case)."

Do NOT edit `index.ts` yourself.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd crawfish-orgctl && npm test
```

Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git -C crawfish-orgctl add src/preflight.ts test/preflight.test.ts
git -C crawfish-orgctl commit -m "feat(preflight): MCP wrapper forwarding to lens /preflight

Thin RPC per docs/specs/preflight-contract.md §4. tokens_used: 0
(metadata, not an LLM call). Local statement-length validation skips
the network round-trip on obviously-too-short attestations."
```

---

## 4 · Lead close-out (after teammates report done)

Per playbook §0.8 + §2 Steps 8–13:

- [ ] **Wire the preflight route** in `crawfish-lens/src/server/index.ts` (lead-only):
  ```ts
  // Near the other org-scoped routes:
  import { handlePostPreflight } from "./preflight.js";
  // ...
  const preflightRoute = pathname.match(/^\/api\/orgs\/([a-z0-9_-]{1,32})\/preflight$/);
  if (preflightRoute && req.method === "POST") {
    return handlePostPreflight(req, res, preflightRoute[1]);
  }
  ```

- [ ] **Register the MCP tool** in `crawfish-orgctl/src/index.ts` (lead-only):
  ```ts
  // Top of file:
  import { PREFLIGHT_TOOL_DEFS, dispatchPreflight } from "./preflight.js";
  // ...
  // In the TOOL_DEFS spread (~line 154):
  ...PREFLIGHT_TOOL_DEFS,
  // ...
  // In runTool (case match on req.params.name):
  if (req.params.name === "preflight_attest") {
    const r = await dispatchPreflight(req.params.arguments as never);
    return { content: [{ type: "text", text: JSON.stringify(r) }] };
  }
  ```

- [ ] **Full build + test:**
  ```bash
  cd crawfish-lens && npx tsc --noEmit -p tsconfig.json && npx vitest run
  cd ../crawfish-dash && npx tsc --noEmit -p web/tsconfig.json && npm test
  cd ../crawfish-orgctl && npm test
  ```

- [ ] **Invoke `superpowers:requesting-code-review`** against the W2 branch.

- [ ] **Invoke `superpowers:finishing-a-development-branch`** to choose merge path.

- [ ] **Tear down team:** shutdown_request to each teammate.

- [ ] **No tag this phase** — `v0.3` already cut; next tag is `v0.4` at end of NOW-W5.

---

## 5 · §0.6 Spawn prompt

```
Create an agent team for NOW-W2 (Acceptance criteria + Budget bar + Preflight). Spawn 3 teammates:
  - criteria-be: owns crawfish-lens/src/server/types.ts (NOW-W2 exports — append only, must NOT touch SessionSummary/SessionDetailPayload or NOW-W1 exports), crawfish-lens/src/server/board.ts (Task interface + task_updated.patch + BoardEvent union + ActivityKind union + foldTasks + validateActor extension + APPEND-ONLY new functions validateDoneTransition / onBudgetBreach / criteria projection at end of file), crawfish-lens/test/criteria.test.ts. Implements Tasks 1, 2, 3 from docs/superpowers/plans/2026-05-26-now-w2-criteria-budget-preflight.md.
  - budget-fe: owns crawfish-dash/web/src/components/TaskBudgetBar.tsx (NEW), crawfish-dash/web/src/components/TaskDrawer.tsx (additive criteria panel + TaskBudgetBar mount only — must NOT touch existing drawer regions or the NOW-W1 Activity panel), crawfish-dash/web/test/budget-bar.test.tsx, crawfish-dash/web/test/criteria-panel.test.tsx. Implements Task 4. Reuses .cycle-budget-bar / .cycle-budget-fill / .is-over-budget CSS classes from NOW-W1; SendMessage lead before requesting any new CSS in ui/tokens/globals.css.
  - preflight-orgctl: owns crawfish-lens/src/server/preflight.ts (NEW endpoint), crawfish-lens/test/preflight.test.ts, crawfish-orgctl/src/preflight.ts (NEW MCP wrapper), crawfish-orgctl/test/preflight.test.ts. Implements Tasks 5, 6. MUST SendMessage the lead instead of editing crawfish-orgctl/src/index.ts or crawfish-lens/src/server/index.ts — both are lead-only per CLAUDE.md.

Each teammate MUST:
  1. Read CLAUDE.md and AGENT-TEAMS.md before touching code.
  2. Read docs/specs/org-contract.md (§3, §3.3, §3.4, §6) and docs/specs/preflight-contract.md (§2, §3, §5) as source of truth.
  3. Follow the bite-sized plan at docs/superpowers/plans/2026-05-26-now-w2-criteria-budget-preflight.md task-by-task.
  4. Apply superpowers:test-driven-development for every task (failing test first, minimal code, green, commit).
  5. Reuse NOW-W1 primitives (validateActor at board.ts:540, rewriteAssigneeForContributor at 588, foldTasks at 175, the flat /activity feed, CycleBudgetBar) — do NOT reinvent them.
  6. SendMessage the lead BEFORE editing any file in CLAUDE.md §0.1 — especially crawfish-lens/src/server/index.ts, crawfish-orgctl/src/index.ts, crawfish-dash/web/src/App.tsx, ui/tokens/globals.css, any package.json.
  7. Run the relevant verify command before claiming done:
     - crawfish-lens:  npx tsc --noEmit -p tsconfig.json && npx vitest run
     - crawfish-dash:  npx tsc --noEmit -p web/tsconfig.json && npm test
     - crawfish-orgctl: npm test
  8. Never run `npx vite build` or emit-mode `tsc -p` — only the lead builds.

Use Sonnet for each teammate. Require plan approval before any teammate writes code.
```

---

## 6 · Self-review

- [x] **Spec coverage:** every section from the inputs is mapped to a task. §3 Criterion type → Task 1. §3.3 done-guard → Task 2. §3.4 activity kinds + scope disambiguation → Tasks 2 + 3. §3.3 evidence-clear ACL → Task 3. §6 criteria_set / criteria_attest semantics → Task 3 (events flow through the existing handlePostBoard, no new endpoint). §6 preflight_attest → Tasks 5 + 6. preflight-contract.md §2 server behaviour → Task 5. §3 BoardEvent extension → Task 1. §5 REST + idempotency → Task 5. §4 wrapper + context injection → Task 6.
- [x] **Placeholder scan:** no TBD/TODO/"add appropriate" anywhere. The only forwarding-out is the lead-only `index.ts` registration in §4, which is correct per CLAUDE.md.
- [x] **Type consistency:** `Criterion`, `CriterionEvidence`, `CriterionKind`, `CriteriaUnmetError`, `BoardEvent`, `ActivityKind`, `Task`, `validateDoneTransition`, `onBudgetBreach`, `handlePostPreflight`, `PREFLIGHT_TOOL_DEFS`, `dispatchPreflight`, `PreflightArgs`, `PreflightResult` are named identically wherever they reappear.
- [x] **Ownership:** Tasks 1+2+3 → criteria-be; Task 4 → budget-fe; Tasks 5+6 → preflight-orgctl. Lead-only files explicitly flagged at every touchpoint.
- [x] **TDD shape:** every task has failing-test → run-to-fail → minimal-impl → run-to-pass → commit, with concrete code on every step.
- [x] **Reuse of W1:** plan references validateActor / rewriteAssigneeForContributor / foldTasks / CycleBudgetBar / /activity feed by exact line number or class name; no duplicate primitives.

---

## Handoff

Plan saved to `docs/superpowers/plans/2026-05-26-now-w2-criteria-budget-preflight.md`. **Stopping here — not spawning the team.** Review the plan; when ready, paste §5 (the spawn prompt) into a fresh message to fan out.
