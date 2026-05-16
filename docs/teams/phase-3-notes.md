# Phase 3 — Teammate notes

## board teammate

Shipped: `crawfish-dash/web/src/components/TaskCard.tsx` (standalone kanban card with token-budget burn bar, label chips via `<Badge>`, drag handles, bulk-select checkbox, red state at >80% budget consumed and breach state at 100%); `crawfish-dash/web/src/components/TaskDrawer.tsx` (rich slide-over drawer with acceptance criteria checklist, token timeline block, links section with kind-chip + resolved title, watchers list, `activityFeedSlot` ReactNode prop for the `activity` teammate's `<ActivityFeed/>`, and fallback comment list); `crawfish-dash/web/src/routes/Board.tsx` (full upgrade — WIP limits per column read from `org.json.wip_limits` with warning/breach badge in column headers, drag-to-rank within a column via HTML5 drag-and-drop persisting `rank` via `task_updated` events, drag-to-move across columns, bulk-select toolbar with bulk status transition and bulk label application, budget-breach auto-escalation emitting `activity_log` entries of kind `budget_breach` + `escalated` at 100% token spend); `crawfish-dash/web/src/lib/board.ts` (extended with `WipLimits`, `OrgConfig`, `OrgMember`, `AcceptanceCriterion`, `BulkOperation` types, `rank`/`token_budget`/`token_spent`/`acceptance_criteria` fields on `Task`, `rank` + `activity_log` in the `task_updated` patch, and `fetchOrgConfig` helper). `npx tsc --noEmit` passes with zero errors in `crawfish-dash/web`. Deferred: the lead must wire the `activityFeedSlot` prop in Board.tsx once the `activity` teammate ships `<ActivityFeed/>`; the `plan` teammate's `TaskLinksPanel` can be dropped into the drawer via the same slot pattern. The `TaskLinksPanel` import path is `crawfish-dash/web/src/routes/Plan.tsx` per the plan teammate's notes above.

## flow-graph teammate

Shipped: `crawfish-lens/src/server/flow.ts` (new `handleGetFlow` handler — reads `board.jsonl` activity_log entries for an org in an optional `from`/`to` ISO time window, aggregates directed comm edges keyed by member pair, returns `{ nodes, edges, from, to, totalEvents }` where each node carries `eventCount`/`tokensSpent`/`successRate` and each edge carries `count`/`tokenVolume`/`kinds`/`sample`); `crawfish-dash/web/src/components/FlowGraph.tsx` (hand-rolled Verlet force-directed graph — d3 is absent from package.json; sim loop ~150 LOC including repulsion + spring + center-pull + damping; renders SVG via existing `.cf-graph-*` and `.cf-graph-overlay*` CSS classes; edge color = cool→hot RGB ramp on token volume; click node → NodePanel overlay with event count / token spend / success rate; click edge → EdgePanel overlay with comm-log sample; date inputs drive `?from=&to=` refetch); `crawfish-dash/web/src/routes/Analytics.tsx` (converted binary Dev/Product toggle to `.cf-tabs` / `.cf-tab` three-tab bar — Dev, Product, Flow — existing panes untouched). `npx tsc --noEmit` passes with zero errors in `crawfish-dash/web`; `crawfish-lens` tsc has one pre-existing error in `activity.ts` (another teammate's file); `flow.ts` is error-free. **Lead action required:** import `handleGetFlow from "./flow.js"` in `crawfish-lens/src/server/index.ts` and add a route match for `^/api/orgs/([a-z0-9_-]{1,32})/flow$` with method GET.

## activity teammate

Shipped: `crawfish-lens/src/server/activity.ts` (server-side comment/mention business logic — `postComment`, `postMention`, `foldActivityWithMentions` which synthesizes `mentioned` ActivityEntries on-the-fly from `@member` patterns in comment bodies without a new event type; HTTP handlers `handleGetActivity`, `handlePostActivity`, `handlePostMention`; auto-watch: commenter and mentioned members are appended to `watchers` via a `task_updated` patch after each relevant event); `crawfish-orgctl/src/tools/activity.ts` (MCP tool group exporting `ACTIVITY_TOOL_DEFS` + `dispatchActivity` — tools: `activity_post_comment`, `activity_list_for_task`, `activity_mention`; all conform to optimizer contract v1.0 with `tokens_used` on every response); `crawfish-dash/web/src/lib/activity.ts` (client-side helpers — `postComment`, `postMention`, `ensureWatcher`; `postMention` fires a `crawfish:mention` DOM CustomEvent for in-app notification listeners; reactions are ephemeral client-side state in v1 — TODO: persist via board event in P4); `crawfish-dash/web/src/components/ActivityFeed.tsx` (pure presentational component — `activityLog: ActivityEntry[]`, `members: OrgMember[]` props; kind→icon map; payload summaries with `<Badge>` chips for status transitions; timestamps via `fmtMtime`); `crawfish-dash/web/src/components/Comments.tsx` (comment list + composer — `@mention` autocomplete popup against org member list with keyboard nav; reactions panel with 3 fixed emojis, ephemeral client state; watchers strip; auto-watch on post/mention). `npx tsc --noEmit` passes with zero errors in `crawfish-lens`, `crawfish-orgctl`, and `crawfish-dash/web`. **Lead actions required:** (1) mount `handleGetActivity` and `handlePostActivity` / `handlePostMention` in `crawfish-lens/src/server/index.ts` at `GET/POST /api/orgs/:id/activity/:task_id` and `POST /api/orgs/:id/activity/:task_id/mention`; (2) register `ACTIVITY_TOOL_DEFS` and `dispatchActivity` from `crawfish-orgctl/src/tools/activity.ts` in `crawfish-orgctl/src/index.ts`. Coordination: board teammate should wire `<ActivityFeed activityLog={task.activity_log} members={orgConfig.members}/>` and `<Comments taskId orgId comments={task.comments} watchers={task.watchers} members={orgConfig.members} currentUser="human"/>` into `TaskDrawer` via the `activityFeedSlot` prop pattern already in place.

## governance teammate

Shipped:

`crawfish-lens/src/server/audit.ts` — single `appendAudit(orgId, entry)` write point for all governance audit entries; appends to `~/.crawfish/orgs/<id>/audit.jsonl` (one JSON line per `AuditEntry`). Auto-stamps `id` (ULID) and `ts` (RFC3339) when absent. HTTP handler `handleGetAudit` supports `?limit=N&kind=...&task_id=...` query params; returns `{ entries, total }` most-recent-first. The `activity` teammate imports `appendAudit` from here for task-transition, comment, mention, and escalation audit writes — do not add a second appender.

`crawfish-lens/src/server/policy.ts` — enforcement layer. Owns `~/.crawfish/orgs/<id>/policies.json` (v1.0 schema: `{ version, updated_at, rules: PolicyRule[] }`) and `~/.crawfish/orgs/<id>/pending_approvals.jsonl`. Exports:
- `checkTokenBudget(orgId, agentId)` — reads optional `token_budget_weekly`/`token_spent_weekly` from `org.json` members; treats absent fields as unlimited.
- `checkTaskAuth(orgId, task, requestedBy)` — fires matching `task_auth` rules, appends to `pending_approvals.jsonl`, calls `appendAudit` for `approval_requested`.
- `resolveApproval(orgId, approvalId, status, by)` — updates approval status via full file rewrite, calls `appendAudit` for `approval_resolved`.
- `policyGate(orgId, event)` — **lead wires this into `handlePostBoard` in `crawfish-lens/src/server/index.ts`**. The exact integration is: after parsing the POST body but before calling `appendEvent`, add `const gate = policyGate(orgId, parsedBody); if (!gate.ok) return sendJSON(res, 409, gate);`. It fires only on `task_updated` events with `patch.status === "in_progress"`. Returns `{ ok: true }` or `{ error: { code: "policy_violation", message: "..." } }`.
- HTTP handlers: `handleGetPolicy`, `handlePutPolicy`, `handleGetPendingApprovals`, `handlePostResolveApproval`.

**Lead mount points in `server/index.ts`:**
```
GET  /api/orgs/:id/policy                              → handleGetPolicy
PUT  /api/orgs/:id/policy                              → handlePutPolicy
GET  /api/orgs/:id/policy/pending                      → handleGetPendingApprovals
POST /api/orgs/:id/policy/pending/:approvalId/resolve  → handlePostResolveApproval
GET  /api/orgs/:id/audit                               → handleGetAudit
```
Import pattern: `import { handleGetPolicy, handlePutPolicy, handleGetPendingApprovals, handlePostResolveApproval, policyGate } from "./policy.js"; import { handleGetAudit } from "./audit.js";`

`crawfish-dash/web/src/lib/governance.ts` — client-side types (`PolicyRule`, `OrgPolicy`, `PendingApproval`, `AuditEntry`) and fetch helpers (`fetchOrgPolicy`, `saveOrgPolicy`, `fetchPendingApprovals`, `resolveApproval`, `fetchAuditLog`). Not appended to `lib/api.ts` to avoid conflicts — kept in a dedicated file.

`crawfish-dash/web/src/components/PolicyEditor.tsx` — inline editor for a single `PolicyRule`. Handles both `token_budget` (agent picker + weekly cap input) and `task_auth` (assignee picker, label input, approver picker) kinds with client-side validation.

`crawfish-dash/web/src/routes/policies.tsx` — extended with `OrgGovernanceSection` component (exported, accepts `orgId: string`). Renders token budget cards, auth rule cards, pending-approval queue with Approve/Deny buttons, and audit log table. The existing tool-policy surface (ComplianceStrip, PolicyCard, DecisionLog) is untouched; the new section is appended below. **Lead wires `<OrgGovernanceSection orgId={activeOrgId} />` into the existing `/policies` route render in App.tsx once the active org context is available.**

Both submodules type-check clean: `npx tsc --noEmit -p tsconfig.json` in `crawfish-lens/` and `npx tsc --noEmit` in `crawfish-dash/web/` — zero errors.

## plan teammate

Shipped: `crawfish-lens/src/server/cycles.ts` (CRUD for cycles.json with rollup — planned/delivered/slipped counts derived from board.jsonl fold); `crawfish-lens/src/server/search.ts` (SQLite FTS5 index over task title/description/comments/activity body, rebuildable on demand via POST /api/orgs/:id/search/rebuild); `crawfish-dash/web/src/lib/plan.ts` (typed fetch helpers for cycles API + search API + task cycle patching); `crawfish-dash/web/src/routes/Plan.tsx` (Plan tab with Backlog list + structured-query filter bar, Cycle picker with create-cycle modal, Epic rollup with progress bar + status mix, cross-task links panel exported as `TaskLinksPanel` for the board teammate's drawer, FTS5 search with debounced input). Both submodules type-check clean (`npx tsc --noEmit` in crawfish-lens and crawfish-dash/web pass with no errors in owned files). Deferred: the lead must mount the new routes (`GET/POST /api/orgs/:id/cycles`, `PUT/DELETE /api/orgs/:id/cycles/:cycle_id`, `GET /api/orgs/:id/search`, `POST /api/orgs/:id/search/rebuild`) in `crawfish-lens/src/server/index.ts` and add the `/plan` route to `crawfish-dash/web/src/App.tsx`. The `TaskLinksPanel` component is exported from `crawfish-dash/web/src/routes/Plan.tsx`; board teammate should import `{ TaskLinksPanel, TaskLinksPanelProps }` from there.

---

## Lead finalization (2026-05-16)

All five teammates idled with clean type-checks. Lead pass completed:

- **Schema (pre-spawn).** Extended `docs/specs/org-contract.md` §3 and the three mirrored TS files (`crawfish-lens/src/server/board.ts`, `crawfish-dash/web/src/lib/board.ts`, `crawfish-orgctl/src/board.ts`) with `cycle_id`, `epic_id`, `links`, `labels`, `watchers`, `activity_log` plus `TaskLink` / `ActivityEntry` types. Lens fold now projects `status_changed`, `assigned`, `labeled`, `linked`, `commented` activity entries.
- **Dep add.** `better-sqlite3@^11.10.0` + `@types/better-sqlite3@^7.6.13` added to `crawfish-lens` for the FTS5 search index.
- **CSS additions** to `ui/tokens/globals.css`: activity / comments / mention popup / composer / watchers (requested by `activity`); task-card budget bar / breach states + WIP-limit column header states (requested by `board`).
- **Lens route table** (`crawfish-lens/src/server/index.ts`): mounted GET/POST `/api/orgs/:id/cycles`, PUT/DELETE `/api/orgs/:id/cycles/:cycle_id`, GET `/api/orgs/:id/search`, POST `/api/orgs/:id/search/rebuild`, GET `/api/orgs/:id/flow`, GET/POST `/api/orgs/:id/activity/:task_id`, POST `/api/orgs/:id/activity/:task_id/mention`, GET/PUT `/api/orgs/:id/policy`, GET `/api/orgs/:id/policy/pending`, POST `/api/orgs/:id/policy/pending/:approvalId/resolve`, GET `/api/orgs/:id/audit`.
- **Governance gate.** `policyGate` wired into `handlePostBoard` in `crawfish-lens/src/server/board.ts` — denied transitions return HTTP 409 with `{ ok: false, error }` and never persist.
- **MCP tools.** `ACTIVITY_TOOL_DEFS` + `dispatchActivity` from `crawfish-orgctl/src/tools/activity.ts` wired into `crawfish-orgctl/src/index.ts` via `...spread` and a name-prefix fallback in the dispatcher.
- **Dash sidebar + route.** Added `/plan` to `crawfish-dash/web/src/main.tsx` (with a `PlanRouteShell` wrapper that reads `?org=` and prompts to pick an org otherwise) and to the App sidebar TABS with the `kanban` icon.

**Final build evidence:**
- `crawfish-dash/web` — `npx tsc --noEmit -p tsconfig.json` clean; `npx vite build` succeeds (497 kB / 146 kB gz).
- `crawfish-lens` — `npx tsc -p tsconfig.json` clean.
- `crawfish-orgctl` — `npx tsc --noEmit -p tsconfig.json` clean.

**Deferred / known follow-ups:**
- Reactions persist only in client state in v1 (`activity` documented TODO).
- WIP-limits source field (`wip_limits` on `org.json`) is consumed by Board but the org-contract schema doesn't yet enumerate it — purely additive on read.
- Patch-shape parity (resolved post-finalization): `board` flagged that lens/orgctl-side `BoardEvent.task_updated.patch` was missing `rank`, `token_budget`, `token_spent`, and `activity_log`. Mirrored on the server side in `crawfish-lens/src/server/board.ts` and `crawfish-orgctl/src/board.ts` plus `docs/specs/org-contract.md`; lens fold now applies them (rank/budgets overwrite; `activity_log` append-merges). Re-type-checked clean.
- `OrgGovernanceSection` is exported from `routes/policies.tsx`; per-org rendering still relies on caller passing an active `orgId`. Multi-org switcher (see ROADMAP v2 candidate #9) will connect the wires.

## End-to-end demo run (lens server bound to 127.0.0.1:7879, org `01krq5xe4m3p6s71e117g4xsan`)

Walked the full Phase-3 flow against a live lens server. Results:

**Verified working:**
- `POST/GET /api/orgs/:id/cycles` — cycle created and listed
- `POST /api/orgs/:id/board` with `cycle_id` + `epic_id` on `task_created`, `links`/`token_budget`/`token_spent` in `task_updated.patch`, and a client-emitted `activity_log` array (budget_breach + escalated) on breach
- Folded board returns the subtask with `links=[{kind:"blocks",task_id:<epic>}]`, `token_budget=1000`, `token_spent=1100`, and `activity_log` of length 4 (`linked`, `commented`, `budget_breach`, `escalated`) — all four phase-3 fold paths exercised
- `GET /api/orgs/:id/flow` — D3-ready `{nodes, edges}`; `eng` node showed `eventCount=4` from the four events emitted against it
- `GET /api/orgs/:id/activity/:task_id` — returns the projected activity feed
- `GET/PUT /api/orgs/:id/policy` — file persists; default empty `{version:"1.0", rules:[]}` auto-created on first read

**Issues surfaced by the demo (would have shipped broken):**
1. **`GET /api/orgs/:id/search?q=…` throws `TypeError: Cannot read properties of null (reading 'slice')`** even after `POST /search/rebuild` returns `{ok:true}`. Bug in `crawfish-lens/src/server/search.ts` — likely a null-deref on the SQLite prepared-statement result handling. File against `plan` work.
2. **`policyGate` with `weekly_token_cap=0` for the assignee did not block a `status: "in_progress"` transition** — request returned 200 + the event appended normally. Likely because the gate computes `agent.token_spent_weekly` (absent on members from the startup template) as 0 and `0 <= 0` evaluates allowed. Either: enforce strictly when cap is 0 (treat as "blocked"), or require non-null `token_spent_weekly` (will arrive when v2 candidate #1 — real cron runs — actually accumulates spend). File against `governance` work.

**Other observation (not a bug):** Audit log stays empty because v1 only writes audit entries from the `/activity/*` HTTP route and on policy violations. Direct `POST /board` task_commented events bypass audit. Acceptable for v1 (audit is opt-in via the activity surface).
