# TRACK-5 — Orchestration & execution

## Overview
The execution core: a durable queue/worker/workflow that runs approved tasks in isolated git worktrees, with crash-safe side-effects, concurrency limits, cancel/retry, per-task and per-org budget caps, and idle-stuck auto-halt. Primary personas: PLAT (durability, concurrency, worktree isolation, live queue), EM (cancel, re-run), VPE (budget caps), IC (stuck detection). This is the engine every other surface dispatches into; it sits after the plan gate (TRACK-4) and drives CI (TRACK-7) and PR submission (TRACK-8).
Source: ORCHESTRATOR-USER-STORIES.md §5.

---

## User stories

5.1 **[PLAT]** Tasks queued for execution survive a worker crash or restart without rerunning the side effects (PR creation, comments) twice. *AC: durable workflow engine (Temporal-class); idempotency keys on every external side-effect call.*

5.2 **[PLAT]** Concurrent task limit per workspace and per repo (default: 5 workspace-wide, 1 per repo). *AC: tasks beyond the limit wait in queue with a visible "queued, position N" status.*

5.3 **[EM]** Cancel an in-flight task; the worker stops within 30s and posts a "cancelled by user" comment on the ticket. *AC: worktree is cleaned up; partial PR (if drafted) is closed; token cost up to cancel is still billed.*

5.4 **[PLAT]** Each task runs in an isolated git worktree under the workspace's hosted runner; no two tasks share a checkout. *AC: worktree creation < 5s; cleanup on completion or cancel.*

5.5 **[EM]** Re-run a failed task with one click; the re-run inherits the original plan and budget but starts a fresh worktree. *AC: re-run count visible on the ticket; auto-disable re-run after 3 attempts without manual override.*

5.6 **[VPE]** Set a per-task budget cap (default $5) and a per-org daily cap (default $200); exceeded tasks pause and require human approval to continue. *AC: budgets enforced at token-spend level using existing `budget.ts` / `cost-manager` patterns; pause is reversible in two clicks.*

5.7 **[PLAT]** See the live queue (tasks pending, running, paused, failed) with filters by repo, craw, and age. *AC: filter persistence in URL; auto-refresh.*

5.8 **[IC]** Tasks that idle without progress for > N minutes (no LLM activity, no tool call) auto-halt with a "stuck" label. *AC: N is configurable per craw; default 5 minutes; halt posts the last log entry as a debugging hint.*

---

## Coding tasks (from ROADMAP.md)

- **O0.2** — Cloud-server orchestrator skeleton (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`) — the queue/worker/workflow that §5.1, §5.2, §5.7 build on.
- **O0.3** — Worker runtime adapter shim (`cloud/server/src/orchestrator/adapters/claude-code.ts`) — the runtime boundary §5.8 idle-detection observes (LLM activity / tool calls).
- **O0.5** — Worktree isolation utility (`cli/orgctl/src/worktree/{spawn,merge,cleanup}.ts`) — implements §5.4 (creation <5s, cleanup on completion/cancel) and the fresh-worktree guarantee in §5.5.
- **O1.6** — Per-task budget cap enforcement (`cloud/server/src/orchestrator/budget.ts`, wraps existing `cli/orgctl/src/budget.ts`) — implements §5.6 per-task cap; per-org daily cap overlaps O5.6 (TRACK-12).
- **O1.8** — Cancel + retry primitives (dashboard + workflow) — implements §5.3 cancel (stop <30s, cleanup, close partial PR) and §5.5 one-click re-run (inherit plan/budget, fresh worktree, 3-attempt auto-disable).
  - Reuses: `cli/orgctl/src/budget.ts` — existing per-task budget + auto-escalate primitives (USER-STORIES §17, §5.6).
  - Reuses: durable workflow engine pending **ADR-002** (O0.1) — §5.1's Temporal-class requirement is gated on that decision.

Note: §5.6's **per-org daily cap ($200)** is implemented by **O5.6** (Monthly budget cap + pause, TRACK-12), not O1.6. O1.6 is the per-task cap. USER-STORIES §17 confirms: "v1 work is the org-wide daily cap + the cost-manager agent dispatch." Both caps share `budget.ts`. Cross-reference TRACK-12.

---

## Tech stack considerations

- Durable workflow engine is the single largest unmade decision (ADR-002 pending, O0.1): Temporal vs. Inngest vs. Restate. §5.1 requires side-effects (PR creation, ticket comments) to be exactly-once across worker crash — idempotency keys on every external call are mandatory regardless of engine. The engine choice anchors §5.3 cancel semantics, §4 checkpoint waits, and §16.4 provider-outage resume.
- Worktree isolation (O0.5) is pulled forward from LATER² wk 23–24; the spawn/merge/cleanup utility must hit <5s creation (§5.4) and guarantee no shared checkout. Cancel (§5.3) and re-run (§5.5) both depend on deterministic cleanup — a leaked worktree on the hosted runner is a disk-leak and a cross-task contamination risk.
- §5.2 concurrency limits (5 workspace / 1 per repo) are queue-admission gates, not worker-side throttles; "queued, position N" (§5.7) requires the queue to expose ordinal position, which Temporal/Inngest don't surface natively — this is custom queue-state on top of the engine.
- §5.6 budget enforcement is at token-spend granularity using `budget.ts`; the pause-and-require-approval flow must be a durable workflow state (reversible in two clicks), not a process kill. The plan's estimated cost (§4.1) and the enforced cap must use one cost model to stay consistent.
- §5.8 idle detection (no LLM activity / no tool call for N min) observes the runtime adapter (O0.3) event stream; "stuck" halt posts the last log entry. This needs the adapter to emit heartbeat/activity events, not just final output — a contract requirement on O0.3, and the same stream TRACK-6 SSE consumes.
- §5.5 re-run inherits plan + budget but starts fresh worktree, auto-disables after 3 attempts: the attempt counter must be durable and visible on the ticket. Open question: does the per-org daily cap (§5.6) count re-run token spend against the same envelope? Not specified — affects whether a retry storm can exhaust the org cap.
