# Crawfish — Key Concepts & Glossary

A single, authoritative definition for every load-bearing noun in the
Crawfish codebase. Each entry is grounded in the actual schema, contract,
or decision record — not invented.

The governing principle for the entire domain is **[ADR-003 —
cloud-canonical](../../.planning/decisions/ADR-003-canonical-domain-model.md)**:
cloud Postgres is the single source of truth; the desktop is a thin client.
Read that ADR first if a definition here surprises you.

Siblings: `ARCHITECTURE.md` (system shape) and `PHASES.md` (build schedule)
live next to this file. Where a concept maps to a roadmap phase, the phase
number is cited inline — see
[`.planning/ROADMAP.md`](../../.planning/ROADMAP.md) for the full schedule.

---

## 1. Domain model (the canonical cloud entities)

These are the entities Postgres owns under ADR-003. The canonical
vocabularies (statuses, roles, link kinds, criterion kinds, activity kinds)
are enforced in
[`cloud/server/src/domain/contract.ts`](../../cloud/server/src/domain/contract.ts)
via zod — sqlite/Postgres carry the columns as strings; the contract module
is the enforcement layer. The Prisma entities live in
[`cloud/server/prisma/schema.prisma`](../../cloud/server/prisma/schema.prisma).

### Org / Workspace
An organization is the top-level tenant. Exactly one is auto-provisioned per
user on first sign-in (`cloud/server` `ensureUserHasWorkspace`); there is no
manual "create an org" step (Phase 1). An Org is multi-member and is the
canonical container for projects, members, integrations, and agents. Its
`id` (a cuid) is the only join key — the `name`/slug is a **mutable label,
never a join key** (ADR-003 fixed the prior slug-collision break). "Org" and
"workspace" are the same thing; "workspace" is the user-facing word.
*Lives in:* `Org` model, `prisma/schema.prisma`.

### Project
A Project is a unit of work inside an Org, bound 1:1 to a GitHub repo
(`Project.githubRepo` / `githubRepoId`, unique per org via
`@@unique([orgId, githubRepoId])`). It is the scope that Issues, Tasks,
Cycles, Epics, and Activity all attach to. A Project also carries an optional
Linear Team binding (`linearTeamId` / `linearTeamKey`) — **one Linear Team
maps to one Crawfish Project** (Phase 20), making a Project the rough
equivalent of a Linear Team. Clone state for the agent working directory
(`cloneStatus`, `localPath`, `deviceId`) hangs off the Project too.
*Lives in:* `Project` model.

### Member & Roles
A Member (`OrgMember`) joins a `User` to an `Org` with a role. The canonical
role lexicon is **`owner | admin | member | viewer`**, ordered by rank
(`owner=3 > admin=2 > member=1 > viewer=0`). Roles are the **write-gate**:
board/project/integration mutations require ≥ `member`; settings/billing
require ≥ `admin`. Legacy lexicons normalize in via `normalizeRole`
(`founder→owner`, `contributor→member`). This closes the audit H4
"viewer-can-write" hole. **Agents are first-class members** — assignable,
@mentionable, addable to projects exactly like humans (Linear convention),
and they do **not** count as billable seats (M3 billing posture).
*Lives in:* `OrgMember` model; `ROLES` / `normalizeRole` / `roleAtLeast` in
`contract.ts`. (The schema column default still reads `"contributor"`;
`normalizeRole` is the runtime gate.)

### Task — and Task vs Issue
A **Task** is the *authored* board work item — the canonical unit of work an
org member (human or agent) creates and tracks. Cycles, epics, acceptance
criteria, task links, and activity all attach to a Task. This is the entity
the M1 Linear-grade board (Phases 4–7) is built on.

**Task vs Issue** is the central distinction ADR-003 ratified:

| | **Task** | **Issue** |
|---|---|---|
| Origin | Authored inside Crawfish | Mirrored from an external provider |
| Provider | n/a (native) | `github` \| `linear` |
| Mutability | Read/write board item | Read-mostly mirror |
| Attaches | cycles, epics, criteria, links, activity | nothing (it is a leaf mirror) |

An Issue can be *linked to* or *promoted into* a Task — promotion creates a
real `Task` row. The old `Issue.provider="native"` value is **retired**:
native work is a Task, never an Issue.
*Lives in:* `Task` model; `createTaskSchema` / `updateTaskSchema` in
`contract.ts`.

### Issue
An Issue is an external provider record (GitHub issue or Linear issue) synced
into a Project. It is read-mostly and idempotently upserted on
`@@unique([projectId, provider, externalId])`, carrying `externalKey`
(human id like `ENG-123` or `#42`), normalized `state` (`open`/`closed`),
`labels` (JSON-encoded), and `url`. Phase 20 shipped GitHub + Linear sync;
Phase 13's webhook/poller will feed the same model. An Issue is a *mirror*,
not the board of record — see Task vs Issue above.
*Lives in:* `Issue` model.

### TaskStatus
The single canonical status enum, replacing three forked vocabularies
(audit B1). The lifecycle is:

```
triage → backlog → in_progress → in_review → blocked → done → canceled
```

`escalated` is **not a status** — it is an orthogonal boolean flag on the
Task. This fixes the budget-breach bug where a breach tried to write a
status the board rejected: a breach now sets `escalated = true` while
`status` stays valid. Legacy mappings: orgctl `review→in_review`; dash
`todo→backlog`, `doing→in_progress`.
*Lives in:* `TASK_STATUSES` / `taskStatusSchema` in `contract.ts`;
`Task.status` (default `triage`) and `Task.escalated` (default `false`).

### Cycle
A time-boxed iteration (a sprint) scoped to a Project, with a `name`, a
`status` (`upcoming | active | completed`), and optional `startsAt`/`endsAt`.
Tasks are assigned into a Cycle, and the cycle-planning view rolls up token
budgets across its tasks (Phase 4–5).
*Lives in:* `Cycle` model; `createCycleSchema` in `contract.ts`.

### Epic
A larger body of work that groups Tasks under one Project. Carries a
`title`, optional `description`, and a `status` drawn from the canonical
`TaskStatus`. An epic can be auto-decomposed into a subtask DAG (Phase 6).
*Lives in:* `Epic` model; `createEpicSchema` in `contract.ts`.

### Acceptance Criterion
A typed, testable condition attached to a Task. The canonical kinds are
**`test | manual | spec_match`**. Each criterion tracks `met` and an optional
`evidence` payload (JSON when met). Phase 5 builds the **evidence guard** on
this: the `done` transition is rejected with `criteria_missing_evidence`
unless every criterion has evidence. A Task with zero criteria may go `done`
freely.
*Lives in:* `AcceptanceCriterion` model; `CRITERION_KINDS` /
`criterionKindSchema` in `contract.ts`.

### Task Link
A typed directed edge between two Tasks. The five canonical kinds are
**`blocks | depends_on | duplicates | relates_to | subtask_of`**, unique per
`(fromTaskId, toTaskId, kind)`. Phase 7 renders the linked-task graph on
these.
*Lives in:* `TaskLink` model; `TASK_LINK_KINDS` / `taskLinkKindSchema` in
`contract.ts`.

### Activity
An append-only feed entry, scoped to a Project and optionally a Task, with an
`actorMemberId` (null = system) and a JSON `payload`. Canonical kinds:
`task_created`, `status_changed`, `assigned`, `linked`, `labeled`,
`budget_breach`, `cycle_changed`, `epic_changed`. The live activity feed
(Phase 4) streams over cloud SSE.
*Lives in:* `Activity` model; `ACTIVITY_KINDS` in `contract.ts`.

### Integration
A per-org, per-provider OAuth connection store, unique on
`@@unique([orgId, provider])`, holding the access/refresh tokens used to pull
Issues from GitHub and Linear. Tokens are plaintext this phase
(encryption-at-rest is a tracked follow-up) — **never serialize or log
them**. Also stores the external workspace id/name (e.g. the Linear org).
*Lives in:* `Integration` model (Phase 20).

---

## 2. Agents, runtimes & execution

### Agent
A non-human Org member with a runtime. Agents are first-class members
(assignable, @mentionable, budgeted, board-tasked) and route by capability
(see Capability Routing). On the cloud they are mirrored as `AgentMeta`
(name, role, runtime) — enough for the read-only canvas; the heavier
on-disk member definition (system prompt + tool list) is an execution detail
of the desktop working directory.
*Lives in:* `AgentMeta` model; agent member shape historically in
`docs/specs/org-contract.md` §2 (now an execution-side artifact, not the
canonical store).

### Runtime / Adapter
A **runtime** is the backend that actually executes an agent and produces a
transcript. Four providers exist today: **`claude-code`, `claude-api`,
`openai-api`, `codex`** (OpenClaw is the first non-Claude adapter; Cursor and
SDK adapters are planned). Each is a separate file under
`desktop/lens/src/adapters/` implementing the same **adapter contract**: lens
reads transcripts uniformly and diagnoses rules fire on any runtime without
modification. The native orchestration runtime (M2) implements the same
contract so it slots in beside the others.
*Lives in:* `desktop/lens/src/adapters/`; contract spec
`docs/specs/adapter-contract.md` (per repo conventions).

### Capability Routing
Auto-assignment of an unassigned Task to the best-fit agent: the router picks
the agent with the lowest `avg_tokens_per_task` among those with
`success_rate > 0.7`, breaking ties by least-loaded (Phase 6). One-click
override. This is the substrate the M3 orchestrator's classifier and
routing rules build on.

---

## 3. The board, the filesystem & the canonical principle

### Board
The board is the canonical view over cloud Tasks (with their cycles, epics,
criteria, links, and activity), rendered in `cloud/platform` and the desktop
Dash. Under ADR-003 the board *is* cloud Postgres state. The **legacy disk
`board.jsonl`** (the append-only JSONL event journal from ADR-001, defined in
`docs/specs/org-contract.md` §3) is **demoted**: it is no longer canonical,
at most a local execution artifact. The cli/orgctl and projectctl board
writers become cloud-API clients.

### Canonical domain model / cloud-canonical
The central architectural principle (ADR-003): **cloud Postgres is the single
source of truth for the org/board/task/issue/member domain. The desktop is an
online thin client — no offline board, no client↔server sync, no CRDT.** The
desktop retains real local value (running agent execution, transcript and
diagnoses analysis) and *streams results up* to the cloud, but it does not own
board state. This resolved audit blocker B1 (four forked board stores, three
status vocabularies, three role lexicons) and supersedes ADR-001. The shared
TypeScript types are intended to live in a `@crawfish/contracts` package; for
now `cloud/server/src/domain/contract.ts` is the sole writer.
*Lives in:* [ADR-003](../../.planning/decisions/ADR-003-canonical-domain-model.md).

### `.crawfish/` filesystem
Per ADR-003, the on-disk `.crawfish/` directory is **an agent working
directory** — repo checkout + per-run scratch + git worktree for the code
being worked on. It is **not the board of record**. (Pre-ADR-003 docs,
including `docs/specs/org-contract.md`, describe `~/.crawfish/orgs/<id>/` as
the canonical org store; that framing is superseded — read it as the legacy
disk layout, not current truth.)

### The moat
Under cloud-canonical, the moat is **reframed to the hosted org-OS** — the
defensible core is *not* the on-disk filesystem. The moat is the combination
of: capability-routed agent organization, durable orchestration, the
knowledge/RAG substrate as a cloud service, and the accumulated org / board /
eval data an org builds over months. The filesystem becomes an execution
detail. (GRAND_PLAN §3.3 still names the filesystem as the moat and is owed a
rewrite — ADR-003 follow-up.)

---

## 4. Product & roadmap concepts

These are vision-level concepts from
[`docs/roadmap/GRAND_PLAN.md`](../roadmap/GRAND_PLAN.md), mapped to the build
schedule in [`.planning/ROADMAP.md`](../../.planning/ROADMAP.md).

### Craw
**The installable unit of Crawfish** — one file, one install, one marketplace
entry (GRAND_PLAN §3.16). A craw is packaged as a `craw.yaml` manifest +
policy (file/network allow-deny defence policy) + payload, and is benchmarked
(verified token-per-doc cost). Kinds include: agent, skill, template,
connector, optimizer, cron-recipe, methodology, defence, and benchmark craws.
Craws packaging lands in M2 (Phase 10).

### Orchestrator
The hosted, durable workflow that turns Linear/GitHub Issues into
**CI-verified, checkpoint-gated pull requests** for mid-market engineering
teams. It is the **paid wedge** (M3, phases 12–19 / O0–O7) funding the
free MIT org-OS, built directly on the M1 cloud domain model. It writes
Postgres directly under the durable workflow engine. **Currently blocked on
ADR-002** (the durable engine choice — Temporal vs Inngest vs Restate;
BullMQ/pg-boss rejected), which is OPEN and not yet authored.
*Lives in (planned):* `cloud/server/src/orchestrator/`.

### Knowledge librarian / RAG
The org knowledge substrate (M2, Phase 8): a local-only RAG (SQLite +
`sqlite-vec`, `transformers.js` embeddings) over the org's ingested sources,
with knowledge-graph extraction surfaced as an LLM Wiki. The **librarian** is
a contextual-bandit meta-router that learns *per-org* which source classes to
consult for which query type, recording rewards and showing
improvement-over-time. In the GRAND_PLAN vision this learned, accumulated
source taxonomy is the durable surface frontier vendors cannot replicate;
under ADR-003 it is delivered as a cloud service and is part of the reframed
moat.

### Diagnoses / Optimizers
Two halves of the token-discipline pillar (M2, Phase 9). **Diagnoses** is a
rule engine over agent transcripts in `desktop/lens` detecting token-waste
patterns — eight rules ship today (`oversized-tool-result`, `re-read-loops`,
`low-cache-hit-rate`, `dom-dump-detected`, `log-truncation-pattern`,
`thinking-overhead`, `grep-then-read-storms`, `agent-fanout-cost`).
**Optimizers** are token-thinning MCP servers (e.g. `opt-codebase`, ~3.25×
token reduction on bench) plus a cost-manager that switches models
dynamically and fires regression alerts at 2σ deviation. Each optimizer is a
craw reporting `tokens_used`.
*Lives in:* `desktop/lens/src/diagnoses/` (rules); `desktop/opt*` (optimizers).

---

## 5. Platform plumbing & onboarding

### M0 — cloud-first onboarding
Per ADR-003, the MVP (M0, phases 1–3) is **cloud-first, not local-first**:
sign in (Clerk/GitHub) → auto-provisioned workspace → import a repo → hire an
agent that opens a real PR — in under 15 minutes, no card, MIT. The earlier
"local-first / platform-dark / dash-is-the-whole-product" framing is retired.

### Device-link
A short-lived 6-character code (`DeviceLinkCode`) the platform generates and a
desktop client redeems to **bind a desktop client to its cloud workspace**. On
redeem the server mints a JWT the Dash polls for, then deletes. Under
cloud-canonical its role is narrowed: it authenticates a desktop client
against its cloud Org, *not* to upload a local org as truth.
*Lives in:* `DeviceLinkCode` model.

### Dev auth shim
A first-class development bypass of Clerk auth, honored only in non-prod. With
a blank `VITE_CLERK_PUBLISHABLE_KEY` in `cloud/platform/.env.local`, the SPA
fabricates a fake user (`id: dev-user`, `email: dev@local`), `RequireAuth`
lets every route through, and `apiFetch` sends `X-User-Id: dev-user`. The
backend honors that header at `cloud/server/src/middleware/auth.ts` instead of
verifying a Clerk bearer token. Use this for visual-audit / Playwright walks
rather than attempting OAuth.
*Lives in:* [`cloud/platform/DEV-AUTH.md`](../../cloud/platform/DEV-AUTH.md);
`cloud/server/src/middleware/auth.ts`.

---

*Definitions track ADR-003 (recorded 2026-05-23) and the schema/contract as
of branch `feat/cloud-issue-ingestion`. When the schema, contract, or a
decision changes, update the cited entry here.*
