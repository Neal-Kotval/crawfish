# TRACK-5 — Orchestration & execution

**Components:** `PLAT` (primary — durable engine, queue, budget, cancel/retry) · `CLI` (worktree isolation utility) · `DASH` (cancel/retry affordances shared with the live dashboard)
**Source:** ORCHESTRATOR-USER-STORIES.md §5 · ROADMAP.md O-stages O0.2, O0.3, O0.5, O1.6, O1.8 (per-org daily cap is O5.6, TRACK-12)

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the execution core — the engine every other surface dispatches into. A task arrives
already approved (the plan gate in TRACK-4 has run); this track takes it, runs it to completion
in an isolated checkout, and hands the result to CI (TRACK-7) and PR submission (TRACK-8). What
the user experiences is indirect: they see tasks move through `queued → running → paused →
done/failed`, they can cancel or re-run, and they trust that a worker dying mid-task will not
double-post a PR. The reliability guarantees here are the product's spine.

In the request lifecycle this sits after the plan checkpoint and before verification. Everything
downstream assumes it: the live dashboard (TRACK-6) tails the event stream this engine emits, CI
(TRACK-7) runs against the worktree this engine spawns, budget breaches (TRACK-12) pause workflows
this engine owns.

Most of this is **new**. USER-STORIES §17 confirms the reusable pieces are `cli/orgctl/src/budget.ts`
(per-task budget + auto-escalate primitives, already shipped) and the cost-manager dispatch. The
single largest unmade decision is the **durable workflow engine** — Temporal vs. Inngest vs. Restate
— pending **ADR-002 (O0.1)**. §5.1's exactly-once guarantee is gated on that decision, but idempotency
keys on every external side-effect are mandatory regardless of which engine wins.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Crash-safe side-effects (§5.1) | `PLAT` | `cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts` (O0.2); engine pending ADR-002 |
| Concurrency limit (§5.2) | `PLAT` | `cloud/server/src/orchestrator/queue.ts` — custom admission gate (O0.2) |
| Cancel in-flight (§5.3) | `PLAT` + `DASH` | workflow cancel (O1.8) + cancel button in both dashboard shells |
| Worktree isolation (§5.4) | `CLI` | `cli/orgctl/src/worktree/{spawn,merge,cleanup}.ts` (O0.5) |
| Re-run failed task (§5.5) | `PLAT` + `DASH` | retry primitive (O1.8) + re-run button in both shells |
| Per-task budget cap (§5.6) | `PLAT` | `cloud/server/src/orchestrator/budget.ts` wraps `cli/orgctl/src/budget.ts` (O1.6); per-org daily cap is O5.6 (TRACK-12) |
| Live queue view (§5.7) | `PLAT` | `cloud/platform/src/pages/Orchestrator.tsx` (O0.2 queue state) |
| Idle-stuck auto-halt (§5.8) | `PLAT` | observes runtime adapter event stream (O0.3) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

5.1 **[PLAT]** Tasks queued for execution survive a worker crash or restart without rerunning the side effects (PR creation, comments) twice. *AC: durable workflow engine (Temporal-class); idempotency keys on every external side-effect call.*

5.2 **[PLAT]** Concurrent task limit per workspace and per repo (default: 5 workspace-wide, 1 per repo). *AC: tasks beyond the limit wait in queue with a visible "queued, position N" status.*

5.3 **[PLAT, DASH]** Cancel an in-flight task; the worker stops within 30s and posts a "cancelled by user" comment on the ticket. *AC: worktree is cleaned up; partial PR (if drafted) is closed; token cost up to cancel is still billed.*

5.4 **[CLI]** Each task runs in an isolated git worktree under the workspace's hosted runner; no two tasks share a checkout. *AC: worktree creation < 5s; cleanup on completion or cancel.*

5.5 **[PLAT, DASH]** Re-run a failed task with one click; the re-run inherits the original plan and budget but starts a fresh worktree. *AC: re-run count visible on the ticket; auto-disable re-run after 3 attempts without manual override.*

5.6 **[PLAT]** Set a per-task budget cap (default $5) and a per-org daily cap (default $200); exceeded tasks pause and require human approval to continue. *AC: budgets enforced at token-spend level using existing `budget.ts` / `cost-manager` patterns; pause is reversible in two clicks.*

5.7 **[PLAT]** See the live queue (tasks pending, running, paused, failed) with filters by repo, craw, and age. *AC: filter persistence in URL; auto-refresh.*

5.8 **[PLAT]** Tasks that idle without progress for > N minutes (no LLM activity, no tool call) auto-halt with a "stuck" label. *AC: N is configurable per craw; default 5 minutes; halt posts the last log entry as a debugging hint.*

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O0.2** — Cloud-server orchestrator skeleton (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`). The scaffolding §5.1, §5.2, and §5.7 all build on: a queue tasks land in, a worker that drains it, a workflow definition, shared types. The concurrency gate (§5.2) lives here as a **queue-admission check** — a decision made *before* a worker picks the task up, not a throttle applied mid-run. "queued, position N" (§5.7) requires the queue to expose ordinal position, which Temporal/Inngest do not surface natively, so this is custom queue-state on top of whatever engine ADR-002 picks.

  ```ts
  // cloud/server/src/orchestrator/queue.ts — admission gate (§5.2)
  const wsRunning = await db.task.count({ where: { workspaceId, status: "running" } });
  const repoRunning = await db.task.count({ where: { repoId, status: "running" } });
  if (wsRunning >= 5 || repoRunning >= 1) {
    const position = await db.task.count({
      where: { workspaceId, status: "queued", createdAt: { lt: task.createdAt } },
    });
    return { admit: false, status: "queued", position: position + 1 }; // §5.7 status
  }
  ```

- **O0.3** — Worker runtime adapter shim (`cloud/server/src/orchestrator/adapters/claude-code.ts`). The boundary between the orchestrator and the model runtime. §5.8 idle-detection observes *this* shim's event stream — so the adapter must emit heartbeat / activity events (LLM token, tool-call start) continuously, not just a final result. This same stream is what TRACK-6's SSE multiplexer tails; treat the event contract as load-bearing for two tracks.

- **O1.6** — Per-task budget cap enforcement (`cloud/server/src/orchestrator/budget.ts`, wraps existing `cli/orgctl/src/budget.ts`). Implements §5.6's per-task cap (default $5). Enforcement is at **token-spend granularity** — you accumulate cost as the run streams and check it against the cap on each increment, rather than only at the end. When the cap is hit, the workflow transitions to a durable `paused` state (reversible in two clicks per AC), it does **not** kill the process. The per-org daily cap ($200) is a separate deliverable — see the note below.

  ```ts
  // cloud/server/src/orchestrator/budget.ts — per-token-increment check (§5.6)
  costSoFar += increment.usd;            // accumulated from the adapter stream (O0.3)
  if (costSoFar >= task.perTaskCapUsd) { // default $5
    await workflow.pause(task.id, { reason: "budget_cap", costSoFar }); // durable, reversible
    return;
  }
  ```

- **O1.8** — Cancel + retry primitives (workflow side). Implements §5.3 cancel (stop the worker within 30s, clean up the worktree via O0.5, close the partial PR if one was drafted, still bill cost-to-cancel) and §5.5 one-click re-run (inherit the original plan and budget, spawn a *fresh* worktree, auto-disable after 3 attempts). The attempt counter must be durable and visible on the ticket. The DASH/PLAT buttons that trigger these are listed under DASH below.

**Reuses (already shipped — do not rebuild):**
- `cli/orgctl/src/budget.ts` — existing per-task budget + auto-escalate primitives (USER-STORIES §17, §5.6). O1.6 wraps it; do not fork it.
- Durable workflow engine pending **ADR-002 (O0.1)** — §5.1's Temporal-class exactly-once requirement is gated on that decision. Until it lands, code against the idempotency-key contract (see Key concepts) so the engine choice is swappable.

### DASH — `desktop/dash` (and the cloud/platform twin)

- **O1.8 (UI)** — Cancel and re-run controls live in both dashboard shells: `cloud/platform/src/pages/TaskRun.tsx` and `desktop/dash/web/src/routes/TaskRun.tsx`. The button calls the PLAT workflow primitive above; it does not implement cancel logic itself. §6.7 (TRACK-6) reuses this same cancel from any view — build the affordance once as a shared component so the two shells do not drift. The re-run button must disable itself after 3 attempts (read the durable attempt counter) unless an admin overrides.

### CLI — `cli/orgctl`

- **O0.5** — Worktree isolation utility (`cli/orgctl/src/worktree/{spawn,merge,cleanup}.ts`). Implements §5.4: each task gets its own `git worktree` checkout under the hosted runner, no two tasks share one, creation under 5s, deterministic cleanup on completion *or* cancel. This is pulled forward from LATER² wk 23–24 because §5.3 cancel and §5.5 re-run both depend on reliable cleanup — a leaked worktree is both a disk leak and a cross-task contamination risk (one task's uncommitted edits leaking into another's checkout).

  ```ts
  // cli/orgctl/src/worktree/spawn.ts — isolated checkout (§5.4)
  const dir = path.join(runnerRoot, "wt", task.id); // unique per task — never shared
  await git(`worktree add --detach ${dir} ${task.baseSha}`);
  return { dir, cleanup: () => git(`worktree remove --force ${dir}`) }; // always callable
  ```

---

## Key technical concepts, explained

**Durable workflow engine + idempotency keys (§5.1).** A *durable* engine persists every step of
a workflow so that if the worker process dies, a replacement picks up exactly where the old one
left off — without re-doing completed steps. The hard part is **external side-effects** (opening a
PR, posting a ticket comment): a naive resume re-runs them and you get two PRs. The fix is an
*idempotency key* — a stable id the external system uses to dedup. Bad vs. good:

```ts
// BAD — a crash-and-resume after the call but before recording it opens a second PR.
const pr = await github.pulls.create({ owner, repo, head, base, title });
await db.task.update({ where: { id }, data: { prNumber: pr.number } });

// GOOD — key the side-effect on the task; replays return the existing PR, never a duplicate.
const key = `pr-create:${task.id}`;
const pr = await withIdempotency(key, () =>
  github.pulls.create({ owner, repo, head, base, title })
); // withIdempotency persists the result under `key`; a replay short-circuits to it
```

Idempotency keys are mandatory **regardless of which engine ADR-002 picks** — Temporal, Inngest,
and Restate all guarantee replay, not exactly-once side-effects.

**Git worktree isolation (§5.4).** `git worktree` lets one repository have multiple working
directories checked out at once, each on its own commit, sharing the single `.git` object store.
That is exactly what concurrent tasks need: cheap, fast (no full clone), and isolated. The discipline
is cleanup — every `worktree add` needs a guaranteed matching `worktree remove`, including on the
cancel path, or the runner's disk fills and stale checkouts bleed state between tasks (see the spawn
snippet above).

**Queue position & concurrency limit (§5.2, §5.7).** The limit (5 per workspace, 1 per repo) is an
*admission gate* checked before a worker claims a task, not a mid-run throttle. "Position N" means
the queue must order waiting tasks and report each one's ordinal — a custom column on top of the
engine, since hosted engines hide queue internals (see the O0.2 snippet).

**Idle-stuck heartbeat detection (§5.8).** "Stuck" is the *absence* of activity for N minutes — no
LLM tokens, no tool calls. You cannot detect absence from final output; you need a heartbeat. The
runtime adapter (O0.3) emits an activity event on every token and tool call; a watchdog timer resets
on each event and fires the halt if it expires.

```ts
// stuck watchdog (§5.8) — N configurable per craw, default 5 min
let timer = setTimeout(halt, craw.idleMs ?? 5 * 60_000);
adapter.on("activity", () => { clearTimeout(timer); timer = setTimeout(halt, craw.idleMs ?? 5 * 60_000); });
function halt() { workflow.halt(task.id, { label: "stuck", hint: lastLogLine }); } // AC: post last log
```

---

## Gaps — work with no O-stage assigned

These have acceptance criteria but no clean numbered O0–O7 deliverable. Flag for the lead.

- **§5.1 durable engine choice (ADR-002 / O0.1).** Not a missing deliverable but an *unmade decision* that blocks the engine's shape. Temporal vs. Inngest vs. Restate anchors §5.3 cancel semantics, §4 checkpoint waits, and §16.4 provider-outage resume. *What's needed:* ADR-002 ratified before O0.2's queue/worker take final form.
- **§5.6 per-org daily cap.** O1.6 builds only the per-task cap. The $200/day org cap is **O5.6** (TRACK-12), which shares `budget.ts`. *What's needed:* confirm the two caps compose — does a re-run storm (§5.5) count against the org daily envelope? Not specified, and it decides whether retries can exhaust the org cap.

---

## Open questions

- **Re-run vs. org cap (§5.5 / §5.6):** does re-run token spend count against the per-org daily envelope? Unspecified; affects whether a retry storm can drain the org cap before a human notices.
- **Cancel billing (§5.3):** "cost up to cancel is still billed" — is the partial cost reconciled against the per-task cap, or recorded separately? Decides whether a cancelled-near-cap task can be re-run within budget.
- **Position accuracy (§5.7):** with a hosted engine that hides queue internals, is "position N" exact or best-effort? An inexact number that jumps around is worse than none.
