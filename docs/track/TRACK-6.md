# TRACK-6 — Live team-execution dashboard

## Overview
The real-time observability surface for running tasks: per-craw streaming logs over SSE, a multi-craw "team" view (implementer + tester + reviewer), replay of completed tasks, dashboard filters, an org-wide rollup, and step-rationale drill-down. Primary personas: IC/EM (watch and debug live runs), VPE (org rollup), PLAT (kill from any view). Sits on top of the execution engine (TRACK-5), consuming its event stream; reuses lens REST+SSE and replay primitives.
Source: ORCHESTRATOR-USER-STORIES.md §6.

---

## User stories

6.1 **[IC, EM]** Open a running task and see, in real time, which craw is executing what step, with a streaming log of tool calls and reasoning. *AC: SSE stream; one row per craw in the multi-craw team; collapsed by default, expandable per craw.*

6.2 **[EM]** See the multi-craw "team" view per task: implementer craw + tester craw + reviewer craw, with their parallel progress and which one is currently active. *AC: visible even for v1's mostly-single-craw runs (renders as "1 of 1" rather than 0); pulls forward for v1.5 multi-craw tasks.*

6.3 **[IC]** Replay a completed task end-to-end — every tool call, every diff, every checkpoint — for debugging. *AC: same UI as live view; reads from JSONL transcript; uses existing lens replay primitives.*

6.4 **[EM]** Filter the dashboard by repo, craw, status, or active reviewer. *AC: filters persist in URL.*

6.5 **[VPE]** See an org-wide rollup: how many tasks ran today, how many are queued, how many are stuck. *AC: counts refresh on a 30s timer; click-through to the filtered list.*

6.6 **[IC]** Click on a craw's current step to see why that step was chosen (planning agent's rationale + which past trajectories it consulted). *AC: trajectory hint uses GRAND_PLAN §3.11 cache mechanism; for v1 may be empty if no historical data exists yet.*

6.7 **[PLAT]** Kill any in-flight task from the dashboard with a confirmation modal. *AC: same effect as 5.3 but reachable from any view.*

---

## Coding tasks (from ROADMAP.md)

- **O1.5** — Basic execution dashboard widget (`cloud/platform/src/pages/Orchestrator.tsx` + `desktop/dash/web/src/routes/Orchestrator.tsx`) — the v1 dashboard shell hosting §6.4 filters and §6.5 rollup.
- **O3.1** — Multi-craw collab primitive (impl + tester + reviewer in one worktree) (`cloud/server/src/orchestrator/team.ts`) — the backend §6.2 team view renders.
- **O3.2** — Per-craw SSE stream + aggregation (`cloud/server/src/orchestrator/stream.ts`) — implements §6.1 streaming (one row per craw, expandable).
- **O3.3** — Team execution view (vertical lane per craw) (`cloud/platform/src/pages/TaskRun.tsx` + `desktop/dash/web/src/routes/TaskRun.tsx`) — implements §6.2 lanes and §6.1 live view.
- **O3.4** — Replay mode (reuse lens replay primitives) (shared with O3.3) — implements §6.3 (same UI as live, reads JSONL).
  - Reuses: lens REST+SSE infrastructure — the existing stream substrate O3.2 aggregates over (USER-STORIES §17, §6.1).
  - Reuses: lens session replay primitives — the existing replay engine O3.4 wraps (USER-STORIES §17, §6.3).

Note: §6.7 kill-from-any-view is the same effect as §5.3 cancel (TRACK-5, O1.8); it is a UI affordance, not a new backend deliverable. The canonical map does not list a §6 deliverable for it — it reuses O1.8. Cross-reference TRACK-5.

Note: §6.6 step rationale + consulted trajectories depends on **GRAND_PLAN §3.11** cache mechanism; AC states it "may be empty if no historical data exists yet" in v1. No O-stage builds the trajectory cache here — it is inherited from GRAND_PLAN. Flag: the rationale-display UI has no numbered deliverable; it rides on O3.3.

---

## Tech stack considerations

- SSE multiplexing (O3.2) is per task with one row per craw; v1 mostly renders 1-of-1 (§6.2), but the wire format must pull forward to multi-craw runs without a schema break. Design the event envelope for N craws now even though v1 emits one — retrofitting the stream format after v1.5 ships is the expensive path.
- §6.3 replay reuses lens replay primitives and reads the JSONL transcript; live view and replay must share one renderer (AC: "same UI as live view") so they can't diverge. The transcript is the source of truth for both — the live SSE stream is a tail of the same JSONL the replay reads.
- §6.5 org rollup refreshes on a 30s timer with click-through; this is a cheap aggregate query, not a live stream — keep it off the SSE path to avoid coupling a polling widget to per-task connections. Counts (ran today / queued / stuck) read queue state from TRACK-5's engine, not the stream.
- §6.6 trajectory hint depends on GRAND_PLAN §3.11; v1 has no historical data so the panel renders empty-but-present. Don't gate the step-drill-down UI on the cache existing — ship the affordance, populate later.
- §6.4 filters persist in URL (also §6.5 click-through targets a filtered list); URL-state filtering must be shared between the cloud/platform route and the desktop/dash route since both host the dashboard. Two route registries (`App.tsx` equivalents) — coordinate per CLAUDE.md registry rules.
- The dashboard ships in two shells (cloud/platform and desktop/dash) per O1.5/O3.3 paths; the SSE client and replay renderer should be shared components, not duplicated per shell, or the two will drift. Open question: is there a shared component package, or does each shell vendor its own?
