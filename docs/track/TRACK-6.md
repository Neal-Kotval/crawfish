# TRACK-6 — Live team-execution dashboard

**Components:** `PLAT` + `DASH` (the dashboard ships in both shells) · backend stream/team primitives are `PLAT`
**Source:** ORCHESTRATOR-USER-STORIES.md §6 · ROADMAP.md O-stages O1.5, O3.1, O3.2, O3.3, O3.4

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the real-time window into running work. A user opens a task and watches, live, which craw
is executing which step, with a streaming log of tool calls and reasoning. For multi-craw tasks they
see a "team" view — implementer, tester, reviewer — as parallel lanes with the active one highlighted.
A completed task can be replayed end-to-end for debugging. Across the workspace there is an org-wide
rollup (ran today / queued / stuck) and dashboard filters by repo, craw, status, reviewer.

In the lifecycle this sits *on top of* the execution engine (TRACK-5): it does not run tasks, it
observes them. It consumes the same event stream TRACK-5's runtime adapter (O0.3) emits and reads the
same JSONL transcript the engine writes. That shared substrate is the design constraint — live view
and replay must render from one source so they cannot diverge.

The reusable foundation is substantial. USER-STORIES §17 confirms the **lens REST + SSE
infrastructure** and the **lens session-replay primitives** already exist in `desktop/lens` (which
`desktop/dash` proxies to). You are not building a streaming substrate or a replay engine from scratch;
you are aggregating the existing SSE per-craw, wrapping the existing replay, and rendering both in two
dashboard shells. The dashboard ships in **both** `cloud/platform` and `desktop/dash` — hence the
`PLAT, DASH` tags on the widget stories.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Live per-craw stream (§6.1) | `PLAT` (stream) + `PLAT, DASH` (view) | `cloud/server/src/orchestrator/stream.ts` (O3.2); `TaskRun.tsx` in both shells (O3.3) |
| Multi-craw team view (§6.2) | `PLAT` (primitive) + `PLAT, DASH` (lanes) | `cloud/server/src/orchestrator/team.ts` (O3.1); `TaskRun.tsx` (O3.3) |
| Replay completed task (§6.3) | `PLAT, DASH` | replay mode in `TaskRun.tsx` (O3.4), reuses lens replay |
| Dashboard filters (§6.4) | `PLAT, DASH` | `Orchestrator.tsx` in both shells (O1.5), URL-state filters |
| Org-wide rollup (§6.5) | `PLAT, DASH` | `Orchestrator.tsx` (O1.5), 30s polling aggregate |
| Step-rationale drill-down (§6.6) | `PLAT, DASH` | rides on `TaskRun.tsx` (O3.3); cache is GRAND_PLAN §3.11 |
| Kill from any view (§6.7) | `PLAT, DASH` | reuses §5.3 cancel (O1.8, TRACK-5) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

6.1 **[PLAT, DASH]** Open a running task and see, in real time, which craw is executing what step, with a streaming log of tool calls and reasoning. *AC: SSE stream; one row per craw in the multi-craw team; collapsed by default, expandable per craw.*

6.2 **[PLAT, DASH]** See the multi-craw "team" view per task: implementer craw + tester craw + reviewer craw, with their parallel progress and which one is currently active. *AC: visible even for v1's mostly-single-craw runs (renders as "1 of 1" rather than 0); pulls forward for v1.5 multi-craw tasks.*

6.3 **[PLAT, DASH]** Replay a completed task end-to-end — every tool call, every diff, every checkpoint — for debugging. *AC: same UI as live view; reads from JSONL transcript; uses existing lens replay primitives.*

6.4 **[PLAT, DASH]** Filter the dashboard by repo, craw, status, or active reviewer. *AC: filters persist in URL.*

6.5 **[PLAT, DASH]** See an org-wide rollup: how many tasks ran today, how many are queued, how many are stuck. *AC: counts refresh on a 30s timer; click-through to the filtered list.*

6.6 **[PLAT, DASH]** Click on a craw's current step to see why that step was chosen (planning agent's rationale + which past trajectories it consulted). *AC: trajectory hint uses GRAND_PLAN §3.11 cache mechanism; for v1 may be empty if no historical data exists yet.*

6.7 **[PLAT, DASH]** Kill any in-flight task from the dashboard with a confirmation modal. *AC: same effect as 5.3 but reachable from any view.*

---

## Coding tasks, by component

### PLAT — `cloud/server` (stream + team backend)

- **O3.1** — Multi-craw collab primitive (`cloud/server/src/orchestrator/team.ts`). The backend §6.2's team view renders: implementer + tester + reviewer running in one worktree with a shared task context. v1 runs are mostly single-craw, but the primitive must model a *team of N* so the UI can render lanes consistently. (This same primitive is what TRACK-7 §7.6 reuses to run a test-gen / visual-auditor craw "in parallel.")

- **O3.2** — Per-craw SSE stream + aggregation (`cloud/server/src/orchestrator/stream.ts`). Implements §6.1. It tails the runtime adapter event stream (O0.3, TRACK-5) and re-emits it over Server-Sent Events as one logical stream where every event is tagged with which craw produced it. The wire envelope must be designed for N craws *now* even though v1 emits one — retrofitting the format after v1.5 multi-craw ships is the expensive path.

  ```ts
  // cloud/server/src/orchestrator/stream.ts — per-craw event envelope (§6.1, §6.2)
  type StreamEvent = {
    taskId: string;
    crawId: string;              // present even when there is exactly one craw — never optional
    crawRole: "implementer" | "tester" | "reviewer";
    seq: number;                 // monotonic per task, for ordered replay
    kind: "tool_call" | "reasoning" | "diff" | "checkpoint" | "status";
    payload: unknown;
  };
  // SSE write — the UI groups by crawId to render one expandable row per craw
  res.write(`data: ${JSON.stringify(event)}\n\n`);
  ```

### PLAT + DASH — dashboard widgets in both `cloud/platform` and `desktop/dash`

- **O1.5** — Basic execution dashboard widget (`cloud/platform/src/pages/Orchestrator.tsx` + `desktop/dash/web/src/routes/Orchestrator.tsx`). The v1 shell hosting §6.4 filters and §6.5 rollup. Filters persist in URL (so a filtered view is shareable and survives reload) and the rollup polls a cheap aggregate query on a 30s timer — **not** over SSE. Keep the polling widget off the stream path so a dashboard refresh does not open per-task connections.

  ```ts
  // Orchestrator.tsx — URL-state filters (§6.4) shared across both shells
  const [params, setParams] = useSearchParams();
  const filter = { repo: params.get("repo"), craw: params.get("craw"), status: params.get("status") };
  // §6.5 rollup — plain aggregate, 30s poll, click-through sets the same filter params
  const { data } = useQuery(["rollup"], fetchRollup, { refetchInterval: 30_000 });
  ```

- **O3.3** — Team execution view, vertical lane per craw (`cloud/platform/src/pages/TaskRun.tsx` + `desktop/dash/web/src/routes/TaskRun.tsx`). Implements §6.2 lanes and §6.1 live view. Subscribes to the O3.2 SSE stream and groups events by `crawId` into expandable rows (collapsed by default). v1 renders "1 of 1" rather than zero. §6.6's step-rationale panel rides on this view — clicking a step opens a drawer; for v1 the trajectory hint may be empty.

- **O3.4** — Replay mode, reusing lens replay primitives (shared with O3.3). Implements §6.3. The replay reads the JSONL transcript and feeds it through the *same renderer* as the live view (AC: "same UI as live view"). The live SSE stream is just a tail of the same JSONL the replay reads — one source of truth, so the two cannot diverge.

**Reuses (already shipped — do not rebuild):**
- lens REST + SSE infrastructure — the existing stream substrate O3.2 aggregates over (USER-STORIES §17, §6.1). It lives in `desktop/lens`; `desktop/dash` proxies to it.
- lens session-replay primitives — the existing replay engine O3.4 wraps (USER-STORIES §17, §6.3).

Note: **§6.7 kill-from-any-view** is the same effect as §5.3 cancel (TRACK-5, O1.8). It is a UI
affordance — a confirm-modal button reachable from the dashboard list and the task view — not a new
backend deliverable. The canonical map lists no §6 deliverable for it; it reuses O1.8. Build the
cancel button once as a shared component (see TRACK-5 DASH). Cross-reference TRACK-5.

Note: **§6.6 step rationale + consulted trajectories** depends on **GRAND_PLAN §3.11** cache
mechanism. AC states it "may be empty if no historical data exists yet" in v1. No O-stage builds the
trajectory cache here — it is inherited from GRAND_PLAN. The rationale-display UI has no numbered
deliverable; it rides on O3.3. Flag in Gaps.

---

## Key technical concepts, explained

**SSE multiplexing for N craws (§6.1, §6.2).** Server-Sent Events is a one-way HTTP stream: the
server holds the connection open and pushes `data:` lines as events happen. "Multiplexing" here means
*one* SSE connection per task carries the interleaved events of *all* craws on that task, each event
tagged with its `crawId`. The trap is to design the v1 envelope around a single craw (omit `crawId`,
assume one log) and then have to break the schema when v1.5 ships real teams. Tag every event with
`crawId` from day one even though v1 always sends the same id (see the O3.2 snippet) — the client
groups by it to render one expandable row per craw, and "1 of 1" falls out naturally.

**Replay reads the same JSONL as live (§6.3).** The execution engine writes a JSONL transcript — one
JSON object per line, one line per event. The live SSE stream is a *tail* of that file as it grows;
replay is a *full read* of it after the task completes. Because both feed the identical renderer,
there is exactly one rendering codepath, so a fix to the live view automatically fixes replay:

```ts
// one renderer, two sources (§6.3 — "same UI as live view")
function renderEvents(source: AsyncIterable<StreamEvent>) { /* groups by crawId, draws lanes */ }

// live: tail the SSE stream            // replay: read the completed JSONL transcript
renderEvents(sseStream(taskId));        renderEvents(jsonlReader(transcriptPath));
```

**Two shells, shared components (O1.5 / O3.3).** The dashboard exists in `cloud/platform` and
`desktop/dash`, registered in two route tables. The SSE client and the replay renderer must be
*shared* components, not copied per shell, or they drift. Per CLAUDE.md registry rules the two route
registries (`App.tsx` equivalents) are coordinated edits — do not let two teammates append routes to
both shells simultaneously.

---

## Gaps — work with no O-stage assigned

These have acceptance criteria but no clean numbered O0–O7 deliverable. Flag for the lead.

- **§6.6 step-rationale display + trajectory hint.** The trajectory *cache* comes from GRAND_PLAN
  §3.11; the *UI* that displays rationale and consulted trajectories has **no numbered O-stage** — it
  rides on O3.3. *What's needed:* confirm the rationale-display panel is in O3.3's scope (and renders
  empty-but-present in v1), or assign it its own O3.x.
- **Shared component package.** O1.5 and O3.3 each ship in two shells. There is no named deliverable
  for the *shared* SSE-client / replay-renderer package the two shells consume. *What's needed:* decide
  whether a shared package exists or each shell vendors its own — the latter guarantees drift.

---

## Open questions

- **Shared components (O1.5 / O3.3):** is there a shared component package the two shells import, or does each shell vendor its own SSE client and renderer? Without one, the cloud and desktop dashboards diverge.
- **Rollup vs. stream coupling (§6.5):** confirmed the 30s rollup is a plain aggregate off the SSE path — but does "stuck" count (§6.5) read TRACK-5's idle-halt label (§5.8) or recompute idleness? They must agree on the definition of stuck.
- **Replay of in-flight tasks (§6.3):** can a user scrub backward on a *still-running* task, or is replay only post-completion? The "same UI as live" AC is ambiguous on mid-run seeking.
