# Team — Phase 3: Native operations

**Goal:** ship the Phase 3 deliverables from `ROADMAP.md` — native planning,
upgraded board, activity/comments/mentions, inter-agent flow graph, and
governance primitives v1 — without relying on any external tracker, chat,
or review tool.

**Why an agent team:** the five workstreams are independent at the submodule
level, each produces a clear deliverable (a tab + an API surface), and the
work spans dash UI, lens server, and `crawfish-orgctl` MCP tools. Perfect
fan-out shape.

**Read before spawning:** `AGENT-TEAMS.md` (root), `CLAUDE.md` (root),
`DESIGN.md` (root), `ROADMAP.md` §Phase 3, `docs/specs/org-contract.md`.

---

## Shape

```
                              ┌──────────────┐
                              │     LEAD     │
                              │ (you / main) │
                              └──────┬───────┘
                                     │
   ┌────────────┬────────────┬───────┴────────┬────────────┬───────────┐
   │            │            │                │            │           │
┌──▼───┐   ┌────▼────┐   ┌───▼─────┐    ┌─────▼─────┐   ┌──▼──────┐
│ plan │   │  board  │   │activity │    │ flow-graph│   │governance│
└──────┘   └─────────┘   └─────────┘    └───────────┘   └─────────┘
  Plan tab    Board tab   Activity feed   Analytics      Policies
  + cycles    upgrades    + comments      flow tab       + budgets
  + epics                 + mentions      + lens API     + audit
  + links
  + search
```

Five teammates, each owning one submodule subtree. Lead handles cross-cutting
glue: shared types, route table, MCP tool registry, design-token additions,
end-of-phase wiring.

---

## Ownership matrix

Conflict rules from `CLAUDE.md` apply: if a teammate needs to touch anything
outside its column, it MUST `SendMessage` the lead first.

| Teammate | Owns | Forbidden |
|----|----|----|
| **plan** | `crawfish-dash/web/src/routes/Plan.tsx` (new); `crawfish-dash/web/src/lib/plan.ts` (new); `crawfish-lens/src/server/cycles.ts` (new); `crawfish-lens/src/server/search.ts` (FTS5 index, new); test fixtures under `crawfish-lens/test/fixtures/plan/` | `App.tsx`, `server/index.ts`, `org-contract.md`, board UI, message UI |
| **board** | `crawfish-dash/web/src/routes/Board.tsx`; `crawfish-dash/web/src/lib/board.ts`; `crawfish-dash/web/src/components/TaskDrawer.tsx` (new); `crawfish-dash/web/src/components/TaskCard.tsx` (new) | Plan tab files, server-side cycle code, activity feed component (read-only consumer) |
| **activity** | `crawfish-dash/web/src/components/ActivityFeed.tsx` (new); `crawfish-dash/web/src/components/Comments.tsx` (new); `crawfish-dash/web/src/lib/activity.ts` (new); `crawfish-lens/src/server/activity.ts` (new event emitters); `crawfish-orgctl/src/tools/activity.ts` (new MCP tool group) | Board/Plan route files; `orgctl/src/tools.ts` registry (lead-only); shared schema |
| **flow-graph** | `crawfish-dash/web/src/routes/Analytics.tsx` (extend with Flow sub-tab); `crawfish-dash/web/src/components/FlowGraph.tsx` (new); `crawfish-lens/src/server/flow.ts` (new aggregation endpoint) | Plan/Board/Activity UI; any non-Analytics route |
| **governance** | `crawfish-lens/src/server/policy.ts` (new enforcement layer); `crawfish-lens/src/server/audit.ts` (new audit log writer); `crawfish-dash/web/src/routes/policies.tsx` (already exists — extend); `crawfish-dash/web/src/components/PolicyEditor.tsx` (new) | Plan/Board/Activity UI; flow graph code; shared schema |

### Shared-but-lead-only

The lead does these in a single sequential pass at the end of the phase:

- Append the new `cycle_id`, `epic_id`, `links`, `labels`, `watchers`,
  `activity_log` fields to the `CrawfishTask` schema in
  `docs/specs/org-contract.md` and the matching TS types.
- Register new routes in `crawfish-lens/src/server/index.ts`
  (`/api/cycles`, `/api/search`, `/api/flow`, `/api/policy`, `/api/audit`).
- Register new MCP tools in `crawfish-orgctl/src/tools.ts`
  (`board_*` additions for cycles/links, `msg_*` if surfaced here,
  `activity_*`, `policy_check`).
- Add new sidebar entries + routes in `crawfish-dash/web/src/App.tsx`
  (`/plan`, `/policies` already exists, `/analytics` already exists).
- Any new `.cf-*` utility classes shared by ≥2 teammates land in
  `ui/tokens/globals.css` — lead writes once, teammates consume.

---

## Acceptance per teammate

A teammate's task is **done** when:

1. The owned files type-check: `npx tsc --noEmit -p tsconfig.json` in the
   relevant submodule.
2. The new surface is visible in dash (lead runs `npm run dev` in
   `crawfish-dash/web` to verify).
3. No file outside the ownership column was modified.
4. No registry file (per `CLAUDE.md`) was modified.
5. A one-paragraph note is dropped in `docs/teams/phase-3-notes.md`
   describing what shipped and any deferred work.

### Per-teammate acceptance criteria

**plan:**
- `/plan` renders a backlog list with structured-query filter input
- Cycle picker dropdown; tasks have `cycle_id` round-trip via `/api/cycles`
- Epic with ≥1 subtask renders rollup (status, token budget, % complete)
- Cross-task link types render in the drawer (consumed via prop, not own
  component)
- `/api/search?q=…` returns FTS5 hits across title/description/comments
- Backed by SQLite FTS5 index rebuildable from JSONL event log

**board:**
- WIP limits per column (configurable in `org.json` reads)
- Drag-to-rank within a column persists via `task_updated` event
- Bulk select + bulk status transition + bulk label
- Task drawer renders acceptance criteria, token timeline, links section,
  and a slot that consumes the `<ActivityFeed/>` component
- Budget breach renders red card + auto-escalate on 100%

**activity:**
- `<ActivityFeed/>` renders chronological list of activity entries
- Comment composer with `@mention` autocomplete against `org.json` members
- `@mention` emits a `mentioned` activity entry and fires notification
- Reactions (emoji) on comments
- Watchers list + auto-watch on assignment / mention / comment
- MCP tools: `activity_post_comment`, `activity_list_for_task`,
  `activity_mention`

**flow-graph:**
- D3 force-directed graph in Analytics → Flow sub-tab
- Node = agent or human; edge = aggregated comm events in time window
- Edge weight = token volume; edge color ramp = cost
- Time-scrubber input drives `/api/flow?from=…&to=…` re-fetch
- Click node → detail panel (history, success rate, token efficiency)
- Click edge → comm log between the two endpoints

**governance:**
- Token budget per agent per week — enforced in `policy.ts`; agent cannot
  start a new task when at limit (server returns `policy_violation`)
- Authorization policies: task-type → approval gate
- Audit log writer appends to `~/.crawfish/orgs/<id>/audit.jsonl`
- Policy editor UI in `/policies` route
- Approval gate UI: pending-approval queue + approve/deny buttons

---

## Build order inside the phase

Lead does **0** before spawning, then spawns, then does **6** at the end.

0. **Schema additions (lead).** Add `cycle_id`, `epic_id`, `links`,
   `labels`, `watchers`, `activity_log` to the CrawfishTask schema and the
   shared TS types. This is a registry file, lead-only.
1. Spawn 5 teammates per the matrix above. All run in parallel.
2. Plan + Board land first (most UI-visible).
3. Activity ships its components; Board consumes them.
4. Flow graph ships independently.
5. Governance ships its enforcement layer + policy UI.
6. **Lead finalization pass.** Append route/tool registrations in the four
   registry files. Run full build (`npx vite build` in dash, `npx tsc -p`
   in lens). Verify end-to-end demo: create cycle → add tasks with epic +
   links → run an agent → watch activity feed + flow graph populate →
   trigger budget breach → see governance block.

---

## Model + permissions

- **Model per teammate:** Sonnet 4.6 — cheap enough at 5× fan-out, plenty
  capable for the per-teammate scope.
- **Lead model:** Opus 4.7 (1M) — keeps the cross-cutting context.
- **Plan-approval required:** YES for `governance` (touches enforcement
  semantics) and `activity` (touches MCP tool registry indirectly).
  Optional for the others.
- **Permission mode:** inherit from lead. Teammates start with whatever the
  lead has at spawn.

---

## Spawn prompt

The literal prompt to paste into the lead session is in
[`docs/teams/phase-3-spawn-prompt.md`](./phase-3-spawn-prompt.md). Open
that file and copy-paste the fenced block.
