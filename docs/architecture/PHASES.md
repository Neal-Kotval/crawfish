# Crawfish — Per-Phase Documentation

A readable companion to the planning roadmap (`.planning/ROADMAP.md`). One entry per phase, grouped by milestone. This mirrors the roadmap as reshaped on 2026-05-23 by [ADR-003](../../.planning/decisions/ADR-003-canonical-domain-model.md) (cloud-canonical). It does not introduce scope the roadmap lacks.

See also: [ARCHITECTURE.md](./ARCHITECTURE.md) (tier/monorepo layout) and [KEY-CONCEPTS.md](./KEY-CONCEPTS.md) (the canonical nouns: Task vs Issue, TaskStatus, roles) — siblings in this directory.

---

## The four milestones

Crawfish ships in four milestones. M3 runs as a parallel paid track.

- **M0 — Cloud-First Onboarding MVP** (Phases 1–3). Sign in, get an auto-provisioned workspace, connect a repo, watch an agent open a real PR — under fifteen minutes, no card, MIT. Cloud-first per ADR-003 (no longer local-first / "platform dark").
- **M1 — Cloud Domain Model + Linear-Grade Board** (Phases 4–7). The "NOW" slice. Builds the canonical `Task`/`Cycle`/`Epic`/`AcceptanceCriterion`/`TaskLink`/`Activity` entities + roles in cloud Postgres, then cycles, criteria, budgets, routing, triage, decomposition, linked-task graph, and structured search — all surfaced in `cloud/platform`.
- **M2 — Knowledge Substrate & Optimizers** (Phases 8–11). The "NEXT/LATER" slice. Org knowledge service + librarian, the diagnoses/optimizer pack, the skills/craws backbone, and the native GOAP orchestration runtime.
- **M3 — Hosted Orchestrator** (Phases 12–19, stages O0–O7). The parallel paid track: turns issues into CI-verified, checkpoint-gated PRs for mid-market engineering teams. **Blocked on ADR-002** (durable workflow engine) and built directly on the M1 cloud domain model.

Plus one pulled-forward phase: **Phase 20 — Cloud Issue Ingestion** (M0/M1 line, depends on Phase 2; Waves 1–3 shipped, Wave 4 paused).

## The cloud-canonical principle (ADR-003)

Cloud Postgres (Neon in prod) is the **single source of truth** for the org/board/task/issue/member domain. The desktop Dash is an **online thin client** — it runs agent execution and transcript/diagnoses analysis locally and streams results up, but it does not own board state. There is no offline board and no CRDT/sync layer. `.crawfish/` on disk is demoted to an agent working directory, not the org of record. This supersedes ADR-001 (the disk JSONL event journal is no longer canonical). Key ratified rules:

- **Identity:** every entity has a stable opaque id (cuid); org name/slug is a mutable label, never a join key.
- **TaskStatus (one enum):** `triage → backlog → in_progress → in_review → blocked → done → canceled`, with `escalated` as an orthogonal boolean flag.
- **Task ≠ Issue:** `Task` is an authored board work item; `Issue` is an external provider mirror (GitHub/Linear) that may be promoted into a `Task`. The `provider="native"` value is retired.
- **Roles:** `owner | admin | member | viewer`, with a write-gate (board/project/integration mutations require ≥ member; settings/billing require admin/owner).
- **Contracts:** shared TypeScript types via `@crawfish/contracts` + an extended `docs/specs/org-contract.md`.

## Status legend

- **Not started** — planned, no work begun.
- **In progress** — partially implemented (e.g. Phase 20 Waves 1–3).
- **Blocked** — cannot proceed until a named dependency resolves (e.g. Phase 12 on ADR-002).

Note on current-vs-target: a meaningful slice of board work (cycles, criteria, ACL, budget, FTS5) already shipped **on the disk side** (orgctl/lens, the NOW-W1..W5 work) before ADR-003. Under cloud-canonical that is reference, not the build target — the same features are (re)built on cloud Postgres in M1. STATE.md's "Phase 1 / 0%" cursor is stale relative to that shipped disk work.

---

# M0 — Cloud-First Onboarding MVP (Phases 1–3)

### Phase 1: Cloud-First Onboarding MVP
**Milestone:** M0 · **Status:** Not started · **Depends on:** Nothing (first phase)

**Goal:** A developer signs in to the cloud platform, gets an auto-provisioned workspace, connects a repo, and watches an agent open a real PR — under fifteen minutes, no card.

**What it delivers:**
- New user signs in (Clerk / GitHub) and lands on an auto-provisioned workspace — no manual "create an org" step.
- User connects a GitHub repo as a Project; the org/project model in cloud Postgres is the source of truth.
- A "hire / run agent" action runs agent execution (locally via Dash or server-side), streams its trace to the cloud, and opens a real PR end-to-end.
- The full crawfish.dev → sign in → connect repo → PR flow is recordable in under 15 minutes.

**Key areas/files:** `cloud/server` (`ensureUserHasWorkspace`, org/project model in Postgres), `cloud/platform` (onboarding/sign-in surface), `desktop/dash` (local agent execution + trace streaming).

**Notes:** Reshaped per ADR-003 — no longer local-first / "platform dark." The 15-min hire→PR promise is preserved but runs through the cloud platform + an account, not a disk-only Dash. On-disk `.crawfish/` is an agent working directory. Tangled with the onboarding fork (audit H3: three org-creation paths) that ADR-003's "one user, one workspace" rule resolves.

### Phase 2: Web Platform Org/Project Surface
**Milestone:** M0 · **Status:** Not started (largely shipped) · **Depends on:** Phase 1

**Goal:** A user signs in, sees their workspace's projects (canonical in cloud Postgres), connects GitHub repos, and invites teammates by email.

**What it delivers:**
- Sign-in through the Clerk auth gate (dev shim honored in non-prod); land on the workspace.
- The org/project model is canonical in cloud Postgres (Neon in prod); a desktop client authenticates against it via device-link rather than uploading a local org as truth.
- Connect a GitHub repo as a Project and see it in `cloud/platform`.
- Invite a teammate by email; teammate redeems (valid / mismatched / expired states handled).
- Marketing-site visitor is offered the correct platform download with a GitHub-release fallback.

**Key areas/files:** `cloud/server` (orgs/projects/invites/deviceLink — largely already shipped), `cloud/platform` (workspace/projects UI), `web/` (marketing download surface).

**Notes:** Reshaped per ADR-003 — no longer a "sync mirror of a local org"; the platform org/project model *is* the org of record. Device-link survives only to authenticate a desktop client against its cloud workspace. Closes audit H3 (org-creation fork). Note: the audit flags the dev auth shim as a full header bypass in any non-prod env — a hardening item.

### Phase 3: MVP Verification & Hardening
**Milestone:** M0 · **Status:** Not started · **Depends on:** Phase 2

**Goal:** The cloud-first MVP surfaces are trustworthy — covered by end-to-end and contract tests with a documented review pass. No new features.

**What it delivers:**
- `npx playwright test` green across platform + marketing suites (auth gate, cloud onboarding, project connect, issues view, invite-redeem states, device-link auth).
- Server contract tests (`npm test` via supertest) green for health, orgs CRUD+RBAC, projects, issues sync, integrations, invites CRUD+redeem+mismatch+expiry, device-link.
- A code-review doc at `docs/reviews/REVIEW-WAVE2.md` with each severity bucket addressed.

**Key areas/files:** `cloud/platform` + `web/` Playwright e2e; `cloud/server/test` supertest contract suite; `docs/reviews/REVIEW-WAVE2.md`.

**Notes:** Reshaped per ADR-003 — targets the cloud surfaces (no local-canvas / Hire-on-disk paths).

---

# M1 — Cloud Domain Model + Linear-Grade Board (Phases 4–7)

> **M1 framing (ADR-003).** Phases 4–7 build the Linear-grade board **on the cloud canonical domain model**, not the disk board. Phase 4 establishes the foundation; the shipped disk-board work (NOW-W1..W5 in `desktop/lens` / `cli/orgctl`) is reference, not the build target. Realtime (SSE) is `cloud/server`'s responsibility (audit B3). M1 is **not safely buildable until B1/H1/H2 are settled** — ADR-003 settles B1 and H2; Phase 4 closes H1.

### Phase 4: Cloud Domain Model + Cycles, Epics, Activity & Member ACL
**Milestone:** M1 · **Status:** In progress (foundation done) · **Depends on:** Phase 3 + [ADR-003](../../.planning/decisions/ADR-003-canonical-domain-model.md)

> **Done so far:** Prisma `Task`/`Cycle`/`Epic`/`AcceptanceCriterion`/`TaskLink`/`Activity` + migration; `cloud/server/src/domain/contract.ts` (canonical `TaskStatus`/roles/zod); `routes/board.ts` (tasks/cycles/epics/activity) with the `requireRole` write-gate (viewer read / member write) and activity emission; contract tests green; **cloud board UI** (`cloud/platform/src/pages/Board.tsx` — project picker + kanban-by-status + add-task + status moves + activity feed) wired into the sidebar nav alongside **Projects** and **Connections**; **SSE realtime** (`lib/events.ts` hub + `/:pid/stream` + `streamBoard()` client) so the board updates live (verified live); and the **Connect → Project → Issues → Board** flow (issues can be promoted to board tasks via "→ Board"). API + SSE verified live; browser render not yet Playwright-checked. **Pending:** drag-drop, budget rollup, agents-as-members surfacing, `@crawfish/contracts` extraction, multi-instance SSE backing.

**Goal:** The cloud canonical domain model exists (Task/Cycle/Epic/Activity + roles) and users run a board where agents are first-class members, work is organized into cycles and epics, and activity is visible.

**What it delivers:**
- Cloud Prisma defines `Task`/`Cycle`/`Epic`/`Activity` with the canonical `TaskStatus` enum (`escalated` as a flag); migration applies; `@crawfish/contracts` exports the shared types.
- Create cycles and epics; assign tasks into a cycle with budget rollup, surfaced in `cloud/platform`.
- Agents appear as first-class workspace members (free members per Linear convention).
- A live activity feed of board changes (cloud SSE).
- Member access governed by the `owner|admin|member|viewer` write-gate (closes audit H4 viewer-can-write hole); each board feature documents which Tier-1 persona it lights up.

**Key areas/files:** `cloud/server` Prisma schema + migration + board routes + SSE transport; `@crawfish/contracts` (new shared-types package); `cloud/platform` board UI; extended `docs/specs/org-contract.md`.

**Notes:** This is the foundation phase — it builds the cloud canonical domain model that **supersedes the disk board** and closes audit H1 (cloud Prisma was a sync-mirror, not a domain model). It gates the rest of M1 and the paused Phase 20 Wave 4. Requires the new SSE transport in `cloud/server` (audit B3).

### Phase 5: Acceptance Criteria, Budget & Preflight
**Milestone:** M1 · **Status:** In progress (evidence guard done) · **Depends on:** Phase 4

> **Done so far:** (1) acceptance-criteria evidence guard — `POST/PATCH /:pid/tasks/:taskId/criteria` + a guard on the task PATCH that rejects a `done` transition with `criteria_missing_evidence` until every criterion is `met`; (2) token-budget breach — `POST /:pid/tasks/:taskId/usage` records spend; crossing `tokenBudget` (≥100%) flips `escalated` and emits a `budget_breach` activity over SSE (once). `routes/board.ts`, contract schemas, tests (85 green); (3) the live **budget bar** on board cards (`Board.tsx` — spent/budget + %, turns danger on breach; browser-verified). **Pending:** agent preflight self-attestation.

**Goal:** Tasks cannot be marked done without evidence, token spend is visible and enforced, and agents self-attest before acting.

**What it delivers:**
- A task carries acceptance criteria (`test` / `manual` / `spec_match`); the `done` transition is rejected with `criteria_missing_evidence` when evidence is absent.
- A live token-budget bar on tasks; a breach at ≥100% emits `budget_breach` and flips the task to `escalated`.
- An agent performs a preflight self-attestation before executing a task.

**Key areas/files:** `cloud/server` (AcceptanceCriterion model, done-transition guard, budget meter + breach event, preflight endpoint, SSE for the live bar); `cloud/platform` (criteria UI + budget bar).

**Notes:** The live budget bar depends on the cloud SSE transport from Phase 4 (audit B3). The `escalated` flag (not status) is the ADR-003 fix for the prior bug where budget breaches wrote a status the board rejected.

### Phase 6: Capability Routing, AI Triage & Auto-Decomposition
**Milestone:** M1 · **Status:** Not started · **Depends on:** Phase 5

**Goal:** Work routes itself to the best-fit agent, incoming tasks are triaged automatically, and epics decompose into approved subtask DAGs.

**What it delivers:**
- A task routes to the agent with the lowest `avg_tokens_per_task` among those with `success_rate > 0.7`, ties broken by least-loaded.
- An AI triage column that classifies and sorts incoming tasks.
- Auto-decompose an epic into a subtask DAG with human approval before work begins.

**Key areas/files:** `cloud/server` (routing engine — inherits the `cli/projectctl/src/router.ts` 70%-threshold pattern, triage classifier, decomposition); `cloud/platform` (triage column, DAG approval UI).

**Notes:** The routing engine and 70%-success threshold are the substrate the M3 auto-classifier later sits on. Routing/triage logic is ported onto the cloud model rather than the disk board.

### Phase 7: Linked-Task Graph & FTS5 Search
**Milestone:** M1 · **Status:** Not started · **Depends on:** Phase 6

**Goal:** Tasks relate through typed links, and users find work through a structured search bar matching the Linear idiom.

**What it delivers:**
- Link tasks with five kinds (`blocks`, `depends_on`, `duplicates`, `relates_to`, `subtask_of`) and see the linked-task graph.
- Run structured queries through a full-text-backed search bar.
- External references are ingested and round-trip into the board.

**Key areas/files:** `cloud/server` (TaskLink model, search index, external-ref ingestion); `cloud/platform` (graph view + search bar).

**Notes:** Per ADR-003 sub-decision H2, the original "FTS5" (sqlite-only) requirement is reinterpreted as **structured full-text search on the canonical store (Postgres FTS)**, not literal sqlite FTS5. Phase 7 is also the hard board prerequisite for the M3 orchestrator track (alongside Phase 4).

---

# M2 — Knowledge Substrate & Optimizers (Phases 8–11)

### Phase 8: Org Filesystem & Knowledge Librarian
**Milestone:** M2 · **Status:** Not started · **Depends on:** Phase 7

**Goal:** An org accumulates a searchable knowledge substrate that learns which sources to consult per query, with cited retrieval.

**What it delivers:**
- Connect a Tier-1 source (email, chat, docs, GitHub/GitLab, Linear/Jira, or local vault) with keychain auth and incremental sync.
- Retrieval returns citations carrying `source_id`, `path_or_url`, `chunk_text`, `score`, `source_class`, `entity_path`.
- A contextual-bandit meta-router records rewards (`bandits.sqlite` + `feedback.jsonl`) and shows an improvement-over-time graph.
- The knowledge graph is navigable as an LLM Wiki.

**Key areas/files:** knowledge service (RAG core already exists — sqlite-vec + byte-range citations); Tier-1 connectors; contextual-bandit router; LLM Wiki UI in `cloud/platform`.

**Notes:** Per audit H7 the knowledge moat is half-built — the RAG core is real, but the bandit router, Tier-1 connectors, knowledge zones, and worktree isolation are absent, so Phase 8 is largely greenfield. Under ADR-003 the knowledge/RAG substrate as a cloud service is part of the reframed moat (the hosted org-OS), not the on-disk filesystem.

### Phase 9: Diagnoses Engine & Optimizer Pack
**Milestone:** M2 · **Status:** Not started · **Depends on:** Phase 8

**Goal:** The platform actively disciplines token cost — diagnosing waste, switching models dynamically, and alerting on regressions.

**What it delivers:**
- A cost-manager agent surfaces token-waste diagnoses on real sessions.
- The system switches models dynamically based on the optimizer pack.
- A regression alert fires at 2σ deviation.

**Key areas/files:** `desktop/lens` diagnoses engine (fault-isolated pure-function rules already exist); `cli/orgctl/src/budget.ts` cost-manager pattern; optimizer pack; regression-alert pipeline.

**Notes:** The cost-manager work here feeds directly into the M3 orchestrator's per-task budget enforcement and the O3/O6 regression alerting.

### Phase 10: Skills Backbone, Craws Packaging & Test/Visual Agents
**Milestone:** M2 · **Status:** Not started · **Depends on:** Phase 9

**Goal:** Skills and craws are installable, policy-governed, benchmarked units, and per-PR test/visual agents catch regressions.

**What it delivers:**
- Install a vendor-neutral skill into `~/.crawfish/skills/` per-org or per-agent; the diagnoses engine names the skill that should have fired on a failure.
- A craw ships with a manifest, a defence policy (file/network allow-deny), and a verified token-per-doc benchmark.
- A per-PR run screenshots every route, diffs baseline vs candidate, and posts a visual changelog.

**Key areas/files:** skills backbone (`~/.crawfish/skills/`); craw manifest + policy (`cli/orgctl/src/craws/`, GRAND_PLAN §3.16/§3.17 patterns); `bench/` fixtures; per-PR visual auditor agent.

**Notes:** The craw manifest + defence policy + benchmark format defined here is the unit the M3 orchestrator's curated craw library (O2) builds on. The test/visual agents ship as orchestrator craws in M3 stage O3.

### Phase 11: Native Orchestration Runtime (GOAP MVP)
**Milestone:** M2 · **Status:** Not started · **Depends on:** Phase 10

**Goal:** A user states a goal in plain English and watches the runtime plan and replan an executable plan tree — the defensible core of the org-OS thesis.

**What it delivers:**
- Enter a plain-English goal and see an A*-derived executable plan tree rendered in the Plan tab.
- The runtime replans when state changes.
- The MVP runtime delivers capabilities 1–3 (capabilities 4–8 explicitly deferred to a later milestone).

**Key areas/files:** native GOAP orchestration runtime (GRAND_PLAN §3.14); Plan tab UI in `cloud/platform` / `desktop/dash`.

**Notes:** This is the org-OS thesis core. Distinct from the M3 hosted Orchestrator: Phase 11 is the native GOAP planner (plan tree from a goal); M3 is the durable issue→PR workflow product. Per the GRAND_PLAN scope-add, P5 ships the MVP and P6 deepens it.

---

# M3 — Hosted Orchestrator (Phases 12–19, O0–O7)

> **Parallel paid track.** Per ADR-003 it builds directly on the M1 cloud domain model — its hard prerequisites are Phase 4's canonical entities and Phase 7. The whole track is **BLOCKED on ADR-002** (durable workflow engine, OPEN) until Phase 12's first success criterion is met. It may proceed alongside M2 once unblocked. Each phase maps to an orchestrator stage detailed in [ORCHESTRATOR-STAGES.md](../roadmap/ORCHESTRATOR-STAGES.md).

### Phase 12: Orchestrator Workflow Engine Foundation (O0)
**Milestone:** M3 · **Status:** Blocked (ADR-002) · **Depends on:** Phase 7 (board primitives, hard prerequisite); parallel track thereafter

**Goal:** A durable workflow engine is chosen and stood up, and an end-to-end spike opens a draft PR in CI.

**What it delivers:**
- ADR-002 (durable workflow engine: Temporal vs Inngest vs Restate; reject BullMQ/pg-boss) authored and merged — currently OPEN.
- A cloud-server orchestrator skeleton + claude-code worker shim (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`).
- A worktree-isolation utility (`cli/orgctl/src/worktree/`) and a dep-bumper craw against a boring-and-bounded task class.
- An e2e spike opens a draft PR in CI.

**Key areas/files:** `cloud/server/src/orchestrator/` (queue/worker/workflow/types + claude-code adapter); `cli/orgctl/src/worktree/` (spawn/merge/cleanup); `cli/orgctl/src/craws/dep-bumper/`; `scripts/spike-orchestrator-e2e.ts`; `.planning/decisions/ADR-002-*.md`.

**Notes:** The blocking phase for all of M3. ADR-002 is the gate (audit B2). Open O0 questions must also resolve before this phase closes: cloud-server host (AWS/GCP/Fly.io), per-task token-cost ceiling, shared vs separate domain, single vs per-customer GitHub App, craw-authorship policy, and the definition of "merge approval" vs GitHub branch protection. The worktree-isolation primitive is pulled forward from GRAND_PLAN LATER² (CRDT half stays deferred).

### Phase 13: Intake → Plan → Execute → CI → Merge (O1)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 12

**Goal:** A team connects a repo and watches a Linear/GitHub issue flow all the way to a CI-verified, checkpoint-gated PR.

**What it delivers:**
- GitHub-OAuth signup, workspace in <90s, Linear + GitHub App connect, walkthrough ending in a real sandbox PR in <10min.
- Incoming ticket read and classified for craw-eligibility; decision posted as comment + label.
- Gate 1: human approves a pre-code plan (reaction or dashboard button) before any code is written.
- Durable workflow executes in an isolated worktree, survives a worker crash without double side-effects, respects per-task and per-org budget caps.
- Customer CI runs on the draft PR; fix-up revisions on failure up to N; on pass the PR becomes ready-for-review and merges through Gate 2 (respecting branch protection).

**Key areas/files:** `cloud/server/src/inbound/` (Linear webhook + GitHub Issues poller), `cloud/server/src/orchestrator/checkpoints/{plan,merge}.ts`, `ci.ts`, `budget.ts`; `cloud/platform` Orchestrator dashboard widget.

**Notes:** Audit H5 — GitHub inbound is currently implemented twice incompatibly (`gh` CLI in `cli/orgctl/src/inbound` vs REST+Clerk in `cloud/server`); cross-source dedup requires unifying inbound on the cloud path before O1 intake is sound. Phase 20's connectors feed the same cloud model.

### Phase 14: Craw Library, Classifier & Eval Harness (O2)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 13

**Goal:** Workspaces choose from a curated, benchmarked craw library with routing rules, and the classifier's quality is measured and trusted.

**What it delivers:**
- A curated library (8–12 craws) with published bench scores; idempotent one-click install/uninstall with version pinning + rollback + changelog.
- Routing rules (label→craw, first-match-wins, mandatory fallback) and per-craw repo allow/deny.
- Classifier accuracy (precision/recall/FPR) measured over 30 days against a per-workspace eval set with weekly re-eval; regression alert at 2σ.
- A custom-benchmark dry-run that produces no PRs or comments.

**Key areas/files:** `cli/orgctl/src/craws/` (test-backfill, lint-cleaner, type-annotator); `cloud/server/src/classifier/` (index/prompts/eval + eval-harness); `cloud/platform` RoutingRules UI; `bench/craws/`.

**Notes:** Reuses the M1 triage heuristics and capability router. Classifier targets precision ≥80% in v1 (the human Gate-1 checkpoint catches false positives).

### Phase 15: Live Dashboard & Failure Handling (O3)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 14

**Goal:** Users watch craws work in real time, replay completed runs, and understand failures through a structured taxonomy.

**What it delivers:**
- Real-time per-craw streaming tool-calls + reasoning over SSE; kill from any view.
- Replay a completed task from its JSONL transcript; filter by repo/craw/status/reviewer with URL-persisted state.
- Failures in one source of truth (ticket + dashboard + optional email/Slack) under a 7-category taxonomy with trend lines.
- Auto-disable a craw on a failure spike (>50% in 24h over >5 attempts); detect manual takeover when a human pushes.

**Key areas/files:** `cloud/server/src/orchestrator/{team,stream,failure-taxonomy,craw-health,takeover-detector}.ts`; `cloud/platform` TaskRun view.

**Notes:** Requires the cloud SSE transport (audit B3). ORCHESTRATOR-STAGES originally assumed reuse of `desktop/lens` SSE, but per ADR-003/B3 realtime is cloud/server's responsibility (lens is a different process). Test/visual-auditor agents accelerate into this stage as craws.

### Phase 16: PR-Comment Bot (O4)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 15

**Goal:** Reviewers iterate with `@crawfish-bot` directly in GitHub PRs, with honest scope handling and hard caps.

**What it delivers:**
- @-mention `@crawfish-bot` on a PR; it re-engages (mention-only default), replying with estimated cost and ETA.
- Halts at a per-PR cap (default 5 revisions / $10) and on detecting conflicting reviewers, pinging a human.
- Honestly declines out-of-scope requests; stops within 30s on `@crawfish-bot halt`.

**Key areas/files:** `cloud/server/src/orchestrator/pr-bot/` (listener, state-machine, conflict-detector, scope-detector, templates).

**Notes:** Introduces a bot identity distinct from human `OrgMember` accounts. Extends the per-task budget enforcement to per-PR scope.

### Phase 17: Billing, RBAC, Audit & Analytics (O5)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 16

**Goal:** The Orchestrator is a governable, billable product — seats and usage metered, roles and audit enforced, cost analytics prove ROI.

**What it delivers:**
- Per-human-seat billing via Stripe Connect (agents free), with usage metering, overage warnings, a hard monthly cap that pauses tasks, and PDF invoices.
- RBAC (admin/member/viewer with per-resource override), a workspace kill switch, and per-craw file/egress policy.
- An immutable append-only audit log (JSONL, exportable, 90-day retention) recording every governance action.
- Cost analytics export (by workspace/repo/craw/ticket, CSV) including per-ticket cycle-time vs human baseline and an org-wide ROI proxy.

**Key areas/files:** `cloud/server/src/billing/` (stripe/seats/usage/budget-cap), `src/auth/rbac.ts`, `src/audit/`, `src/policy/egress.ts`; `cloud/platform` AuditLog UI.

**Notes:** The RBAC roles here align with ADR-003's `owner|admin|member|viewer` lexicon and write-gate (the Phase 4 substrate). Closes audit H4 / O5 governance. Basic RBAC + audit ship here; full per-resource RBAC and SOC2-shaped audit stay GRAND_PLAN Stage 3.

### Phase 18: Onboarding Polish, Notifications & Ops (O6)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 17

**Goal:** The Orchestrator is operable at scale — guided onboarding, reliable notifications and escalation, operational visibility.

**What it delivers:**
- In-app + email notifications for plan-approval, PR-ready, and stuck-ticket events with per-event settings, digest mode, and mute controls.
- A one-way Slack webhook for notifications; an escalation chain firing after 24h unanswered.
- An onboarding walkthrough, manual-takeover UX, status page, and a 2σ regression alert.

**Key areas/files:** `cloud/server/src/notifications/`, `src/quality/regression.ts`; `cloud/platform` onboarding walkthrough; external status page.

**Notes:** PagerDuty/Discord/Teams deferred to v2. The regression-alert pipeline reuses the M2 cost-manager pattern.

### Phase 19: Public Launch, Craw Authoring & Integrations Edge (O7)
**Milestone:** M3 · **Status:** Not started (track blocked) · **Depends on:** Phase 18

**Goal:** The Orchestrator opens to the public, customers can fork their own craws, and the system survives integration edge cases.

**What it delivers:**
- Public signup open; customers fork/author craws with a `craw test` CLI and a per-workspace registry.
- Integration edges handled: emergency GitHub App disable per repo; direct-push-to-craw-branch detection → halt; GitHub/LLM outage → pause + auto-resume; Issues↔Linear migration preserving history; cancel → 90-day export then deletion.
- Wedge success metrics instrumented and trackable (paying teams, auto-classify rate, post-merge-fix rate, P50 ticket→draft-PR, throughput, cost per merged PR).

**Key areas/files:** `cloud/platform` (public signup, CrawEditor); `cli/orgctl/src/craws/templates/`; `web/` marketing update; `docs/orchestrator/authoring-craws/`.

**Notes:** Begins GRAND_PLAN Stage 2 prep (hosted-RAG, RL data-export). Customer-authored craws v1; full marketplace/AI-generated craws stay deferred to v2.

---

# Phase 20 — Cloud Issue Ingestion (Linear + GitHub) — pulled forward

**Milestone:** M0/M1 line (pulled forward) · **Status:** In progress — Waves 1–3 done, Wave 4 paused · **Depends on:** Phase 2 (extends it)

**Goal:** From the cloud platform, a user connects GitHub and Linear, auto-loads issues into a per-Project issues view (GitHub by repo via the existing 1:1 `Project.githubRepo` binding; Linear by Team, each Linear Team → one Crawfish Project), persisted in a Postgres `Issue` model and re-syncable idempotently.

**What it delivers:**
- Prisma gains an `Integration` model (per-org, per-provider OAuth token store, `@@unique([orgId, provider])`) and an `Issue` model scoped to `Project` with `@@unique([projectId, provider, externalId])`; `Project` gains `linearTeamId` / `linearTeamKey`. *(shipped, Wave 1)*
- GitHub connect (reusing the Clerk GitHub OAuth token) + idempotent sync that upserts repo issues into `Issue`. *(shipped, Wave 2)*
- Linear OAuth connect, Team→Project binding, idempotent sync carrying Linear project/cycle as metadata/labels. *(shipped, Wave 3)*
- `cloud/platform` project page lists issues from `GET /api/orgs/:id/projects/:pid/issues` with state/labels, plus a "Sync now" control. *(Wave 4 — paused)*
- Issue state, title, labels, and external key/url round-trip from provider into the cloud DB and render in the UI. *(Wave 4 — paused)*

**Key areas/files:** `cloud/server` Prisma (`Integration` + `Issue` + `Project.linearTeam*`), `src/inbound/` (GitHub `listRepoIssues` PR-filtered + `syncProjectIssues`; Linear OAuth+GraphQL client with refresh-on-401), issues/sync + integrations routes + public OAuth callback; `cloud/platform` Connections panel + Project Issues view + OrgRoute wiring (Wave 4). Branch: `feat/cloud-issue-ingestion`. Plans `20-01`..`20-04`.

**Notes:** Pulled forward into the M0/M1 cloud-platform line; extends Phase 2. Per ADR-003 the cloud `Issue` is a **provider mirror** (GitHub/Linear), distinct from the authored `Task` board built in Phase 4 — an `Issue` may be linked to or *promoted into* a `Task`, and `provider="native"` is retired. Phase 13's webhook/poller feeds the same model. **Wave 4 (Board+Projects nav + onboarding reconciliation) is paused pending the Phase 4 domain model** — ADR-003 now makes that work unambiguously cloud-side, clearing it to resume. The audit flagged that the `Issue` model added a fifth task store; ADR-003 resolves that by fixing it as a provider mirror, not the board.

---

# Critical path & blockers

- **ADR-002 blocks all of M3.** The durable workflow engine choice (Temporal vs Inngest vs Restate; BullMQ/pg-boss rejected) is OPEN. It is Phase 12's first success criterion (audit B2). Until it is authored and merged, Phases 12–19 cannot proceed. M3 is correctly classified **blocked**, not "not started."
- **Phase 4 (canonical model build) gates M1 and Phase 20 Wave 4.** Phase 4 builds the `Task`/`Cycle`/`Epic`/`AcceptanceCriterion`/`TaskLink`/`Activity` entities + roles in cloud Postgres that **supersede the disk board** (closes audit H1). Phases 5–7 depend on it, and the paused Phase 20 Wave 4 is waiting on it.
- **M3's hard board prerequisites are Phase 4 + Phase 7.** Per ADR-003 the orchestrator builds directly on the M1 cloud domain model. Even once ADR-002 lands, M3 cannot run ahead of those board primitives.
- **Cloud realtime/SSE (audit B3).** `cloud/server` has no SSE transport today. Phase 4 (activity feed), Phase 5 (live budget bar), and Phase 15 (per-craw SSE) all require it; ADR-003 assigns realtime to `cloud/server` (not `desktop/lens`).
- **The desktop→cloud board migration (owed by ADR-003).** Board ownership moves from disk (lens/orgctl/projectctl) to cloud; the dash board becomes a cloud-API client; lens board endpoints are deprecated/proxied; the dash first-run org quiz is removed; `@crawfish/contracts` is authored and `org-contract.md` extended. Part of the shipped NOW-W1..W5 disk-board work is reworked. This migration is the connective tissue between the shipped disk board and the M1 cloud build.
- **GitHub inbound dedup (audit H5).** GitHub inbound exists twice incompatibly (orgctl `gh` CLI vs cloud REST+Clerk); it must be unified on the cloud path before Phase 13 (O1 intake) is sound. Phase 20 already added Linear cloud-side.
- **Hygiene (cheap, anytime):** gitignore `cli/orgctl/dist*` (committed today), align the dash `@crawfish/ui` alias, reconcile submodule branch skew, refresh the stale STATE.md cursor.

---

*Companion to `.planning/ROADMAP.md` (the authoritative schedule) and `/Users/nealkotval/crawfish/ROADMAP.md` (root source of truth). Reshaped per ADR-003 (2026-05-23). Generated as a readable mirror — no scope invented beyond the roadmap.*
