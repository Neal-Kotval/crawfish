# Crawfish — System Architecture

> Documentation of the **current** system plus the **decided** direction. Where code still
> reflects the old (disk-canonical) model, it is labeled *current state, migrating to
> cloud-canonical per ADR-003*. The disk board is not presented as the intended end state.
>
> Companion docs: [`KEY-CONCEPTS.md`](./KEY-CONCEPTS.md) (domain vocabulary) ·
> [`PHASES.md`](./PHASES.md) (roadmap milestones M0–M3).
> Governing decision: [`/.planning/decisions/ADR-003-canonical-domain-model.md`](../../.planning/decisions/ADR-003-canonical-domain-model.md).

---

## 1. Overview

Crawfish is an **agent-organizations platform** — a hosted "org-OS" for running a company
on AI agents. A user signs in, gets an auto-provisioned workspace, imports a repo, and hires
agents that do real work (open PRs, triage issues) against a Linear-grade board. The free
local surfaces (desktop Dash + Lens) run agent execution and transcript analysis; the paid
cloud surface hosts the org, the board, and (M3) the durable Orchestrator that turns issues
into CI-verified pull requests.

**The canonical principle (ADR-003, accepted 2026-05-23):** **cloud Postgres is the single
source of truth** for the org/board/task/issue/member domain. The desktop Dash is an
**online thin client** — it renders the board from cloud state and streams execution results
up; it does **not** own board state. There is no offline board and no client↔server
sync/CRDT layer. This supersedes ADR-001 (disk JSONL event journal as the canonical board).
The moat is the **hosted org-OS** (capability-routed orchestration + the knowledge/eval data
substrate), not the on-disk filesystem — `.crawfish/` on disk is demoted to an agent working
directory (repo checkout + per-run scratch + git worktree), not canonical state.

Much of the *shipped* board code still lives on the disk side (`cli/orgctl`, `desktop/lens`).
That is current state; ADR-003 commits to migrating board ownership to `cloud/server`. The
cloud `Task`/`Cycle`/`Epic`/`Activity` schema (already in `schema.prisma`) is the target.

---

## 2. Monorepo layout

The umbrella repo holds five tiers; `desktop/*` are **git submodules** (each its own repo,
its own branch). Per `CLAUDE.md`, each submodule is the ownership boundary for one teammate
in agent-team mode.

| Path | Tier | Responsibility (one line) |
|---|---|---|
| `cloud/server` | Cloud backend | Express + Prisma. **Source of truth** (Postgres/Neon): org/board/issue/member domain, REST API, RBAC, provider sync; future home of realtime + Orchestrator. |
| `cloud/platform` | Cloud web app | React + Vite + Clerk SPA. The signed-in platform: workspace, projects, connections, board UI. |
| `desktop/app` *(submodule)* | Desktop shell | Tauri shell that spawns `lens` + `dash` as child processes. `src-tauri/tauri.conf.json` is the single source of truth for the shell. |
| `desktop/dash` *(submodule)* | Dashboard UI | Board/canvas UI. **Thin client → cloud API** (target). Retains local value: drives agent execution + renders traces. |
| `desktop/lens` *(submodule)* | Transcript reader | Reads Claude Code/OpenClaw transcripts; REST API + server-side reductions; fault-isolated diagnoses engine. Currently also serves disk board endpoints (to be demoted/proxied). |
| `desktop/opt*` *(submodules + in-tree)* | Optimizers | MCP optimizer servers: `opt` (browser), `opt-codebase`, in-tree `opt-artifact`, `opt-logs`. |
| `cli/orgctl` | Org-control CLI | MCP server for the org/board. Currently writes a disk `board.jsonl`; becoming a cloud-API client (ADR-003). |
| `cli/projectctl` | Project engine | Per-project `.crawfish/` engine (tasks/cycles/epics/links/search). Disk-backed today; repurposed to execution scratch under cloud-canonical. |
| `ui/` | Shared design tokens | **Single CSS source** — `ui/tokens/globals.css` is the only `.css` in the tree; lens + dash alias `@crawfish/ui` to it. |
| `web/` | Marketing site | Public marketing + onboarding site. |

---

## 3. Canonical domain model (ADR-003)

The entities and vocabularies below are defined in
[`cloud/server/prisma/schema.prisma`](../../cloud/server/prisma/schema.prisma) and enforced
(zod, since sqlite has no enum type) in
[`cloud/server/src/domain/contract.ts`](../../cloud/server/src/domain/contract.ts).

### Entity relationships

```
User ──< OrgMember >── Org
                        │
        ┌───────────────┼───────────────┬───────────────┐
   AgentMeta        Project          Integration       Invite / Session / DeviceLinkCode
                        │             (per provider:
        ┌───────────────┼──────────┐   github|linear,
      Issue           Task       Cycle / Epic           OAuth tokens)
   (provider          │
    mirror,    ┌──────┼───────────────┬──────────┐
    read-      AcceptanceCriterion  TaskLink   Activity
    mostly)    (test|manual|        (blocks|    (append-only
               spec_match)          depends_on| feed; payload JSON)
                                    duplicates|
                                    relates_to|
                                    subtask_of)
```

- `User` ↔ `Org` is many-to-many via `OrgMember` (unique `[orgId, userId]`). Every entity has
  a stable cuid id. **Org `name`/slug is a mutable label, never a join key** — all joins key on
  `id` (fixes the slug-collision break called out in audit B1).
- `Project` is org-scoped and is the parent of **all** board entities (`Task`, `Cycle`, `Epic`,
  `Activity`) and of synced `Issue`s. A project optionally binds to a GitHub repo
  (`githubRepo`/`githubRepoId`) and/or a Linear team (`linearTeamId`).

### Task vs Issue (the distinction that B1 forked)

- **`Task`** = the **authored board work item**. Cycles, epics, acceptance criteria, typed
  links, and activity attach here. This is "the board."
- **`Issue`** = an **external provider record** (GitHub/Linear), read-mostly, synced via Phase 20
  (`Issue.upsert` on the `[projectId, provider, externalId]` compound key). An Issue may be
  *linked to* or *promoted into* a Task (creating a real `Task` row). Per ADR-003 the
  `Issue.provider="native"` value is **retired** — native authored work is always a `Task`.

### Canonical `TaskStatus` (single enum)

`triage → backlog → in_progress → in_review → blocked → done → canceled`
(`contract.ts` `TASK_STATUSES`; `Task.status` defaults to `triage`).

`escalated` is an **orthogonal boolean flag** on `Task`, **not** a status — this fixes the
budget-breach-writes-a-rejected-status bug from the old disk board. Legacy vocabularies map
in: orgctl `review→in_review`; dash `todo→backlog`, `doing→in_progress`.

### Role model

`owner | admin | member | viewer` (`contract.ts` `ROLES`, ranked owner=3 > admin=2 > member=1
> viewer=0). Legacy lexicons normalize via `normalizeRole`: `founder→owner`,
`contributor→member`. **Write-gate:** board/project/integration mutations require ≥ `member`;
settings/billing require ≥ `admin`/`owner` (`roleAtLeast`). This closes the viewer-can-write
hole (audit H4).

> **Current-vs-target:** the schema still stores legacy role strings on some rows
> (`OrgMember.role` defaults to `"contributor"`; `workspace.ts` seeds `"founder"`).
> `normalizeRole` reads these into the canonical lexicon; a data migration to canonical values
> is owed.

---

## 4. Tier responsibilities under cloud-canonical

### `cloud/server` — source of truth
Express + Prisma. Owns the canonical domain (§3), the REST API
([`src/index.ts`](../../cloud/server/src/index.ts) route map), auth + RBAC (§5), and provider
sync ([`lib/sync.ts`](../../cloud/server/src/lib/sync.ts)). Under ADR-003 this also becomes the
home of: M1 board write paths (the `Task`/`Cycle`/`Epic`/`Activity` tables already exist here
but lack route handlers — the board *features* still live on disk), realtime transport (§7),
and the M3 Orchestrator (writes Postgres directly).

### `cloud/platform` — the web app
React + Vite + Clerk SPA. The signed-in surface: workspace, project list, the connections
panel (GitHub/Linear OAuth), project issues, and the board UI. Has a documented dev-auth
bypass (`cloud/platform/DEV-AUTH.md`) for local work without Clerk.

### desktop Dash — thin client + local execution
**Target (ADR-003):** board routes read/write the cloud API; the first-run org quiz is
**removed** (onboarding is cloud-side). Dash keeps its genuine local value: running agent
execution (Claude Code sessions) and rendering transcript/diagnoses traces, streaming results
up to the cloud. **Current:** dash still has a local board and first-run wizard (the disk
model). This is the largest piece of the owed desktop refactor.

### `desktop/lens` — transcript reader (board endpoints demoted)
**Keep:** the transcript reader, server-side reductions, and the fault-isolated diagnoses
engine over **local** logs (sqlite retained for local analysis only, per H2). **Demote:** lens
currently serves disk-board endpoints — `GET/POST /api/orgs/:org/board`,
`GET …/board/stream` (SSE), and `…/cycles` (see
[`desktop/lens/src/server/index.ts`](../../desktop/lens/src/server/index.ts)). Under ADR-003
these are deprecated or proxied; lens **posts findings to the cloud** rather than owning board
state. Note its board SSE is *not* the cloud realtime transport (see §7).

### `cli/orgctl` + `cli/projectctl` — MCP servers becoming cloud clients
`orgctl` is a clean prefix-dispatch MCP server (`src/index.ts`, `board.ts`, `budget.ts`,
`triage.ts`, `inbound/`). It currently writes a disk `board.jsonl`. `projectctl` is the
per-project `.crawfish/` engine (`tasks.ts`, `cycles.ts`, `epics.ts`, `links.ts`, `search.ts`,
with a real `lock.ts` single-writer guard). **Target:** their board writers become cloud-API
clients (or are repurposed to agent execution scratch); GitHub inbound unifies on the cloud
path (closes the double-implementation, audit H5).

---

## 5. Auth & RBAC

Implemented in [`middleware/auth.ts`](../../cloud/server/src/middleware/auth.ts) and
[`lib/rbac.ts`](../../cloud/server/src/lib/rbac.ts).

**Three credential paths** (`authMiddleware`, in order):
1. **Dash-sync JWT** (`X-Crawfish-Token`, aud-scoped) — only for opt-in dash-sync routes
   (`dashSyncMiddleware`, mounted on `/api/dash/*` before user auth). Sets `req.userId` from
   the verified token; not accepted as user-equivalent on user routes.
2. **Clerk Bearer** in prod — verifies the token, resolves/links a `User` by `clerkId` (upsert
   by unique email), fails closed (401, no fall-through to dev).
3. **Dev shim** (`X-User-Id` / `X-User-Email`) when `NODE_ENV !== "production"` — upserts a
   `…@local` user. *Audit note (CLOUD.md):* the shim is enabled in **any** non-prod env
   regardless of Clerk config, which contradicts the middleware doc-comment that claims it
   only runs when no `CLERK_SECRET_KEY` is set — a known hygiene gap.

Both real paths call `ensureUserHasWorkspace` (auto-provision, §6a).

**RBAC.** `requireMember(req, orgIdParam)` resolves the org by **id-or-name**, confirms the
caller is an `OrgMember`, and **collapses both unauthorized and unknown-org to 404** so the API
never leaks org existence (the 403→404 collapse). It returns the member's `role` + `memberId`.
`requireRole(req, orgIdParam, min)` builds on it to enforce the **canonical write-gate** (ADR-003):
a non-member still collapses to 404, but a member whose role is below `min` gets **403 `forbidden`**.
Roles are normalized via `contract.ts` (`founder→owner`, `contributor→member`). Both guards live in
`lib/rbac.ts` and are shared by the projects, integrations, and board routers.

**Status:** the write-gate is **wired** as of Phase 4 — the board routes (`routes/board.ts`) require
`>= member` for mutations (`POST/PATCH` tasks, cycles, epics) and allow `viewer+` for reads,
closing audit H4. Older routers (projects, integrations) are still membership-only and should adopt
`requireRole` for their mutations as a follow-up.

---

## 6. Key data flows

### 6a. Onboarding / auto-provision
On the first authenticated request, `ensureUserHasWorkspace`
([`lib/workspace.ts`](../../cloud/server/src/lib/workspace.ts)) checks for any `OrgMember`
row; if none, it creates one workspace `Org` (slug sanitized from the email prefix, made unique
via `uniqueOrgName`), an `OrgMember` (`role: "founder"`), and the `DEFAULT_AGENTS` set — in one
transaction, cached in-process. This realizes the "one user, one workspace" decision and the
ADR-003 M0 redefinition (cloud-first onboarding: sign in → workspace → import repo → hire agent
→ real PR in <15 min). *Audit H3:* this is one of three historical org-creation paths; the
cloud auto-provision path is the canonical one, the dash first-run quiz is to be removed.

### 6b. GitHub / Linear issue ingestion (Phase 20)
A `Project` binds to a provider (`githubRepo` or `linearTeamId`); the org holds the OAuth
tokens in `Integration` (unique `[orgId, provider]`). `syncProjectIssues`
([`lib/sync.ts`](../../cloud/server/src/lib/sync.ts)) dispatches: Linear binding takes
precedence, else GitHub. Each provider pages issues (GitHub 10×100, Linear 40×50 caps) and
**upserts** into `Issue` on `[projectId, provider, externalId]`, so re-sync is idempotent.
Linear refreshes its access token once on a 401 and persists the refreshed pair. Provider
issues are read-mostly mirrors — they are **not** the board (§3).

### 6c. The board (Task lifecycle + Activity)
**Target:** Tasks are created/updated against `cloud/server` (zod-validated by
`createTaskSchema`/`updateTaskSchema`), with status moving through the canonical enum and
`escalated` toggled orthogonally. Every meaningful mutation appends an `Activity` row
(`task_created | status_changed | assigned | linked | labeled | budget_breach | …`), giving an
append-only feed. `AcceptanceCriterion` rows back the Phase 5 evidence guard; `TaskLink` rows
back the Phase 7 graph. **Status:** the cloud board write paths exist — `routes/board.ts`
serves `/:pid/{tasks,cycles,epics,activity}` with the role write-gate and activity emission
(Phase 4). The legacy disk write paths (orgctl `board.ts` / lens board endpoints) are being
demoted per ADR-003. Still pending on cloud: a cloud UI for the board, `TaskLink`/criteria
handlers (Phases 5/7), and realtime SSE.

### 6d. Hosted Orchestrator (M3)
**Blocked on ADR-002** (durable workflow engine — OPEN). The target flow: issue intake →
classifier → plan checkpoint → durable execution → CI gate → merge checkpoint → PR-comment
loop. Under ADR-003 the Orchestrator writes Postgres directly (planned `WorkflowRun`/`AuditLog`
models) — no journal-replay/materializer needed. It is the paid wedge; M3 is **blocked**, not
"not started" (audit B2).

---

## 7. Realtime

`cloud/server` has **no SSE/WebSocket transport today** (audit B3). The only streaming in the
codebase is lens's disk-board SSE (`…/board/stream`), which lives in a different process/repo
and is being demoted (§4). Per ADR-003, realtime is **`cloud/server`'s responsibility** and is
required by **Phase 5** (live token-budget bar) and **Phase 15** (per-craw SSE). An earlier
assumption that the cloud Orchestrator could reuse lens SSE is explicitly wrong (different
process). This transport is owed.

---

## 8. Persistence & migrations

- **ORM:** Prisma. **Datasource:** `provider = "sqlite"` for dev (`schema.prisma` carries the
  comment "swap to postgresql for prod"); **Postgres on Neon** in prod.
- **Migrations:** currently `db push`-driven in dev; tracked Prisma migrations are owed as the
  schema stabilizes on the canonical model.
- **sqlite limitations leak into the schema** (current state): no native enum (vocabularies are
  zod-enforced in `contract.ts`), and no array/JSON type — `Issue.labels` and `Activity.payload`
  are JSON-encoded strings. These resolve naturally on Postgres.
- **Search (H2 resolution):** the canonical store is **Postgres**, and full-text search is
  **Postgres FTS**. Phase 7's "FTS5" requirement is reinterpreted as "structured full-text
  search on the canonical store," **not** literal sqlite FTS5. Local sqlite in lens is retained
  only for transcript/diagnoses analysis, never the board.

---

## 9. Open architectural items

- **ADR-002 — durable workflow engine (OPEN).** Temporal vs Inngest vs Restate. Phase 12's
  first success criterion; gates all of M3. M3 should be classified **blocked**.
- **Desktop migration owed (ADR-003 cost, accepted).** Move board ownership off disk to cloud:
  dash board → cloud-API client; remove dash first-run org quiz; deprecate/proxy lens board +
  cycles endpoints; repurpose orgctl/projectctl board writers to cloud clients or execution
  scratch. Part of the shipped NOW-W1..W5 disk-board work is reworked.
- **Cloud board realtime + remaining handlers.** Phase 4 shipped `routes/board.ts`
  (tasks/cycles/epics/activity + write-gate); still missing: SSE/WebSocket transport (§7),
  `TaskLink`/`AcceptanceCriterion` handlers (Phases 7/5), and a cloud board UI.
- **RBAC write-gate** is wired for the board router (`requireRole`, Phase 4); the projects and
  integrations routers are still membership-only and should adopt it. Dev-auth shim over-broad (§5).
- **`@crawfish/contracts` extraction.** `contract.ts` is the single contract today but lives in
  `cloud/server`; ADR-003 calls for extracting it to a shared package once a second tier (the
  desktop thin client) needs it, and extending `docs/specs/org-contract.md` to span all tiers.
- **Hygiene (audit medium).** `cli/orgctl/dist` + `dist-test` (~24 files) are committed to git
  with no umbrella `.gitignore` dist rule — parallel builds will clobber. Submodule branch skew:
  `desktop/lens` is pinned to `wk5/stage1-now` while `desktop/dash` is on `main`. Stale STATE.md
  cursor ("Phase 1/19, 0%") despite landed NOW-W1/W2 board code on the disk side.

---

*See [`KEY-CONCEPTS.md`](./KEY-CONCEPTS.md) for the domain vocabulary in prose and
[`PHASES.md`](./PHASES.md) for the M0–M3 milestone schedule and what each phase delivers.*
