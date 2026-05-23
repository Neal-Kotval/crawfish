# Roadmap: Crawfish

> This is the GSD-structured derivation of the authoritative root `/Users/nealkotval/crawfish/ROADMAP.md`. It does not replace it. All pre-pivot paths from source docs are translated to the monorepo layout (`cloud/`, `desktop/`, `cli/`, `web/`).
>
> **Reshaped 2026-05-23 per [ADR-003](decisions/ADR-003-canonical-domain-model.md) (cloud-canonical).** Cloud Postgres is the single source of truth for the org/board/task domain; the desktop Dash is an **online thin client** (no offline board, no CRDT). This supersedes ADR-001 (disk JSONL journal). M0 is no longer local-first; the board is built in the cloud (M1), not on disk. The moat is the hosted org-OS, not the on-disk filesystem.

## Overview

Crawfish ships in four milestones. **M0** delivers a **cloud-first onboarding** MVP — sign in, get an auto-provisioned workspace, import a repo, and watch an agent open a real PR, in under fifteen minutes (no card, MIT). **M1** builds the **canonical cloud domain model and the Linear-grade agent board on it** (the NOW slice): the `Task`/`Cycle`/`Epic`/`AcceptanceCriterion`/`TaskLink`/`Activity` entities + roles in cloud Postgres, then cycles, criteria, budgets, routing, triage, decomposition, and structured search surfaced in `cloud/platform`. **M2** adds the knowledge substrate and cost-discipline pillar — org knowledge service + librarian, optimizer pack, skills backbone, packaged craws, and the native GOAP orchestration runtime. **M3** is the parallel paid track: the hosted Orchestrator that turns issues into CI-verified, checkpoint-gated PRs for mid-market engineering teams, built up O0→O7 — **blocked on ADR-002** (durable workflow engine) and built directly on the M1 cloud domain model.

## Milestones

- 📋 **M0 — Cloud-First Onboarding MVP** - Phases 1-3 (ships first; cloud-first per ADR-003)
- 📋 **M1 — Cloud Domain Model + Linear-Grade Board (NOW)** - Phases 4-7 (built on cloud Postgres)
- 📋 **M2 — Knowledge Substrate & Optimizers (NEXT/LATER)** - Phases 8-11
- ⛔ **M3 — Hosted Orchestrator (parallel paid track, O0–O7)** - Phases 12-19 — **BLOCKED on ADR-002**

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Cloud-First Onboarding MVP** - Sign in → auto-provisioned workspace → import repo → agent opens a PR, in 15 min
- [ ] **Phase 2: Web Platform Org/Project Surface** - Clerk auth, org/project model, GitHub connect, invite-by-email (cloud is canonical)
- [ ] **Phase 3: MVP Verification & Hardening** - Playwright e2e + server contract tests + review doc, cloud surfaces
- [ ] **Phase 4: Cloud Domain Model + Cycles, Epics, Activity & Member ACL** - Canonical Task/Cycle/Epic/Activity entities + roles in cloud Postgres; agents as first-class members
- [ ] **Phase 5: Acceptance Criteria, Budget & Preflight** - Evidence guard, live token-budget bar, agent self-attestation
- [ ] **Phase 6: Capability Routing, AI Triage & Auto-Decomposition** - Smart task assignment and epic breakdown
- [ ] **Phase 7: Linked-Task Graph & FTS5 Search** - Link kinds, structured search, external-ref ingestion
- [ ] **Phase 8: Org Filesystem & Knowledge Librarian** - RAG indexing, contextual-bandit router, Tier-1 connectors
- [ ] **Phase 9: Diagnoses Engine & Optimizer Pack** - Cost-manager, dynamic model switching, 2σ regression alerts
- [ ] **Phase 10: Skills Backbone, Craws Packaging & Test/Visual Agents** - Installable skills, craw manifest+policy, per-PR visual auditor
- [ ] **Phase 11: Native Orchestration Runtime (GOAP MVP)** - Plain-English goal → A* plan tree, replanning
- [ ] **Phase 12: Orchestrator Workflow Engine Foundation (O0)** ⛔ BLOCKED — Durable engine choice (ADR-002, OPEN), skeleton, worktree isolation, dep-bumper spike
- [ ] **Phase 13: Intake → Plan → Execute → CI → Merge (O1)** - End-to-end checkpoint-gated PR pipeline
- [ ] **Phase 14: Craw Library, Classifier & Eval Harness (O2)** - Curated library, auto-classifier, routing rules, eval
- [ ] **Phase 15: Live Dashboard & Failure Handling (O3)** - Per-craw SSE, team view, replay, failure taxonomy
- [ ] **Phase 16: PR-Comment Bot (O4)** - `@crawfish-bot` revision loop with caps and conflict detection
- [ ] **Phase 17: Billing, RBAC, Audit & Analytics (O5)** - Stripe seats, roles, immutable audit, cost analytics
- [ ] **Phase 18: Onboarding Polish, Notifications & Ops (O6)** - Walkthrough, notifications, escalation, status page
- [ ] **Phase 19: Public Launch, Craw Authoring & Integrations Edge (O7)** - Public signup, customer craw forking, edge resilience

## Phase Details

### Phase 1: Cloud-First Onboarding MVP
> **Reshaped per ADR-003.** No longer local-first / "platform dark." The 15-minute hire→PR promise is preserved, but it runs through the cloud platform + an account, not a disk-only Dash. The on-disk `.crawfish/` is an agent working directory, not the org of record.
**Goal**: A developer signs in to the cloud platform, gets an auto-provisioned workspace, connects a repo, and watches an agent open a real PR — in under fifteen minutes, no card.
**Depends on**: Nothing (first phase)
**Requirements**: MVP-01, MVP-02, MVP-03
**Success Criteria** (what must be TRUE):
  1. A new user signs in (Clerk / GitHub) and lands on an auto-provisioned workspace (`cloud/server` `ensureUserHasWorkspace`) — no manual "create an org" step
  2. User connects a GitHub repo as a Project (the org/project model in cloud Postgres is the source of truth)
  3. User triggers a "hire / run agent" action; agent execution runs (locally via Dash or server-side) and streams its trace to the cloud; a real PR opens end-to-end
  4. The full crawfish.dev → sign in → connect repo → PR flow is recordable in under 15 minutes
**Plans**: TBD
**UI hint**: yes

### Phase 2: Web Platform Org/Project Surface
> **Reshaped per ADR-003.** Cloud is canonical, so this is no longer a "sync mirror of a local org" — the platform org/project model *is* the org of record. Device-link survives only to let a desktop client authenticate against its cloud workspace (not to upload a local org as truth). Largely already shipped (`cloud/server` orgs/projects/invites/deviceLink + `cloud/platform`).
**Goal**: A user signs in, sees their workspace's projects (canonical in cloud Postgres), connects GitHub repos, and invites teammates by email.
**Depends on**: Phase 1
**Requirements**: MVP-04, MVP-05, MVP-06
**Success Criteria** (what must be TRUE):
  1. User signs in through the Clerk auth gate (dev shim honored in non-prod) and lands on their workspace
  2. The org/project model is canonical in cloud Postgres (Neon in prod); a desktop client authenticates against it via device-link rather than uploading a local org
  3. User connects a GitHub repo as a Project and sees it in `cloud/platform`
  4. User invites a teammate by email and the teammate can redeem the invite (valid / mismatched / expired states handled)
  5. A visitor on the marketing site is offered the correct platform download with a GitHub-release fallback
**Plans**: TBD
**UI hint**: yes

### Phase 3: MVP Verification & Hardening
> **Reshaped per ADR-003.** Targets the cloud surfaces (no local-canvas / Hire-on-disk paths).
**Goal**: The cloud-first MVP surfaces are trustworthy — covered by end-to-end and contract tests with a documented review pass. No new features.
**Depends on**: Phase 2
**Requirements**: MVP-07
**Success Criteria** (what must be TRUE):
  1. `npx playwright test` is green across the platform + marketing suites (auth gate, cloud onboarding, project connect, issues view, invite redeem states, device-link auth)
  2. Server contract tests (`npm test` via supertest) are green for health, orgs CRUD+RBAC, projects, issues sync, integrations, invites CRUD+redeem+mismatch+expiry, device-link
  3. A code-review doc exists at `docs/reviews/REVIEW-WAVE2.md` with each severity bucket addressed
**Plans**: TBD

> **M1 framing (ADR-003).** Phases 4–7 build the Linear-grade board **on the cloud canonical domain model**, not the disk board. Phase 4 establishes the foundation: the `Task`/`Cycle`/`Epic`/`AcceptanceCriterion`/`TaskLink`/`Activity` entities in `cloud/server` Prisma, the canonical `TaskStatus` enum (`triage→backlog→in_progress→in_review→blocked→done→canceled` + `escalated` flag), the `owner|admin|member|viewer` role model with a write-gate, and the `@crawfish/contracts` shared types + extended `docs/specs/org-contract.md`. The shipped disk-board work (NOW-W1..W5 in `desktop/lens`/`cli/orgctl`) is reference, not the build target. Realtime (SSE) is `cloud/server`'s responsibility (audit B3).

### Phase 4: Cloud Domain Model + Cycles, Epics, Activity & Member ACL
**Goal**: The cloud canonical domain model exists (Task/Cycle/Epic/Activity + roles) and users run a board where agents are first-class workspace members, work is organized into cycles and epics, and activity is visible.
**Depends on**: Phase 3 · [ADR-003](decisions/ADR-003-canonical-domain-model.md)
**Requirements**: REQ-linear-grade-board, REQ-tier1-personas
**Success Criteria** (what must be TRUE):
  1. Cloud Prisma defines `Task`/`Cycle`/`Epic`/`Activity` with the canonical `TaskStatus` enum (`escalated` as a flag); migration applies; `@crawfish/contracts` exports the shared types
  2. User can create cycles and epics and assign tasks into a cycle with budget rollup, surfaced in `cloud/platform`
  3. Agents appear as first-class members of the workspace (free members per Linear convention)
  4. User sees a live activity feed of board changes (cloud SSE)
  5. Member access is governed by the `owner|admin|member|viewer` role write-gate (closes the audit H4 viewer-can-write hole), and each board feature documents which Tier-1 persona it lights up
**Plans**: TBD
**UI hint**: yes

### Phase 5: Acceptance Criteria, Budget & Preflight
**Goal**: Tasks cannot be marked done without evidence, token spend is visible and enforced, and agents self-attest before acting.
**Depends on**: Phase 4
**Requirements**: REQ-linear-grade-board
**Success Criteria** (what must be TRUE):
  1. A task carries acceptance criteria (`test` / `manual` / `spec_match`), and the `done` transition is rejected with `criteria_missing_evidence` when evidence is absent
  2. User sees a live token-budget bar on tasks; a breach at ≥100% emits `budget_breach` and flips the task to `escalated`
  3. An agent performs a preflight self-attestation before executing a task
**Plans**: TBD
**UI hint**: yes

### Phase 6: Capability Routing, AI Triage & Auto-Decomposition
**Goal**: Work routes itself to the best-fit agent, incoming tasks are triaged automatically, and epics decompose into approved subtask DAGs.
**Depends on**: Phase 5
**Requirements**: REQ-linear-grade-board
**Success Criteria** (what must be TRUE):
  1. A task routes to the agent with the lowest `avg_tokens_per_task` among those with `success_rate > 0.7`, breaking ties by least-loaded
  2. User sees an AI triage column that classifies and sorts incoming tasks
  3. User can auto-decompose an epic into a subtask DAG and approve it before work begins
**Plans**: TBD
**UI hint**: yes

### Phase 7: Linked-Task Graph & FTS5 Search
**Goal**: Tasks relate to one another through typed links, and users find work through a structured search bar matching the Linear idiom.
**Depends on**: Phase 6
**Requirements**: REQ-linear-grade-board
**Success Criteria** (what must be TRUE):
  1. User can link tasks with five kinds (blocks, depends_on, duplicates, relates_to, subtask_of) and see the linked-task graph
  2. User runs structured queries through an FTS5-backed search bar
  3. External references are ingested and round-trip into the board
**Plans**: TBD
**UI hint**: yes

### Phase 8: Org Filesystem & Knowledge Librarian
**Goal**: An org accumulates a searchable knowledge substrate that learns which sources to consult per query, with cited retrieval.
**Depends on**: Phase 7
**Requirements**: REQ-org-fs-librarian, REQ-knowledge-connectors
**Success Criteria** (what must be TRUE):
  1. User connects a Tier-1 source (email, chat, docs, GitHub/GitLab, Linear/Jira, or local vault) with keychain auth and incremental sync
  2. Retrieval returns citations carrying source_id, path_or_url, chunk_text, score, source_class, and entity_path
  3. A contextual-bandit meta-router records rewards (`bandits.sqlite` + `feedback.jsonl`) and shows a visible improvement-over-time graph
  4. The knowledge graph is navigable as an LLM Wiki
**Plans**: TBD
**UI hint**: yes

### Phase 9: Diagnoses Engine & Optimizer Pack
**Goal**: The platform actively disciplines token cost — diagnosing waste, switching models dynamically, and alerting on regressions.
**Depends on**: Phase 8
**Requirements**: REQ-diagnoses-optimizers
**Success Criteria** (what must be TRUE):
  1. A cost-manager agent surfaces token-waste diagnoses on real sessions
  2. The system switches models dynamically based on the optimizer pack
  3. A regression alert fires at 2σ deviation
**Plans**: TBD

### Phase 10: Skills Backbone, Craws Packaging & Test/Visual Agents
**Goal**: Skills and craws are installable, policy-governed, benchmarked units, and per-PR test/visual agents catch regressions.
**Depends on**: Phase 9
**Requirements**: REQ-skills-backbone, REQ-craws-packaging, REQ-test-visual-agents
**Success Criteria** (what must be TRUE):
  1. User installs a vendor-neutral skill into `~/.crawfish/skills/` per-org or per-agent, and the diagnoses engine names the skill that should have fired on a failure
  2. A craw ships with a manifest, a defence policy (file/network allow-deny), and a verified token-per-doc benchmark
  3. A per-PR run screenshots every route, diffs baseline vs candidate, and posts a visual changelog
**Plans**: TBD
**UI hint**: yes

### Phase 11: Native Orchestration Runtime (GOAP MVP)
**Goal**: A user states a goal in plain English and watches the runtime plan and replan an executable plan tree — the defensible core of the org-OS thesis.
**Depends on**: Phase 10
**Requirements**: REQ-native-orchestration-runtime, REQ-agent-os-thesis
**Success Criteria** (what must be TRUE):
  1. User enters a plain-English goal and sees an A*-derived executable plan tree rendered in the Plan tab
  2. The runtime replans when state changes
  3. The MVP runtime delivers capabilities 1–3 (4–8 explicitly deferred to a later milestone)
**Plans**: TBD
**UI hint**: yes

### Phase 12: Orchestrator Workflow Engine Foundation (O0)
**Goal**: A durable workflow engine is chosen and stood up, and an end-to-end spike opens a draft PR in CI — the foundation the hosted Orchestrator builds on.
**Depends on**: Phase 7 (NOW slice board primitives are a hard prerequisite); runs as a parallel track thereafter
**Requirements**: REQ-orch-wedge-product, REQ-orch-wedge-task
**Success Criteria** (what must be TRUE):
  1. ADR-002 (durable workflow engine: Temporal vs Inngest vs Restate; reject BullMQ/pg-boss) is authored and merged — currently an OPEN decision
  2. A cloud-server orchestrator skeleton and a claude-code worker shim exist (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`)
  3. A worktree-isolation utility exists (`cli/orgctl/src/worktree/`) and a dep-bumper craw runs against a boring-and-bounded task class
  4. An e2e spike opens a draft PR in CI
**Plans**: TBD

### Phase 13: Intake → Plan → Execute → CI → Merge (O1)
**Goal**: A team connects a repo and watches a Linear/GitHub issue flow all the way to a CI-verified, checkpoint-gated PR.
**Depends on**: Phase 12
**Requirements**: REQ-orch-onboarding, REQ-orch-issue-intake, REQ-orch-plan-checkpoint, REQ-orch-execution, REQ-orch-ci-verification, REQ-orch-merge-checkpoint
**Success Criteria** (what must be TRUE):
  1. User signs up via GitHub OAuth, creates a workspace in <90s, connects Linear + a GitHub App, and completes a walkthrough ending in a real sandbox PR in <10min
  2. An incoming ticket is read and classified for craw-eligibility, with the decision posted as a comment + label
  3. User approves a pre-code plan (Gate 1) via reaction or dashboard button before any code is written
  4. The durable workflow executes in an isolated worktree, survives a worker crash without double side-effects, and respects per-task and per-org budget caps
  5. Customer CI runs on the draft PR, fix-up revisions happen on failure up to N, and on CI pass the PR becomes ready-for-review and merges through Gate 2 (respecting branch protection)
**Plans**: TBD
**UI hint**: yes

### Phase 14: Craw Library, Classifier & Eval Harness (O2)
**Goal**: Workspaces choose from a curated, benchmarked craw library with routing rules, and the classifier's quality is measured and trusted.
**Depends on**: Phase 13
**Requirements**: REQ-orch-craw-config, REQ-orch-eval-quality
**Success Criteria** (what must be TRUE):
  1. User browses a curated library (8–12 craws) with published bench scores and installs/uninstalls in one idempotent click, with version pinning + rollback + changelog
  2. User configures routing rules (label→craw, first-match-wins, mandatory fallback) and per-craw repo allow/deny
  3. Classifier accuracy (precision/recall/FPR) is measured over 30 days against a per-workspace eval set with weekly re-eval, and a regression alert fires at 2σ
  4. User runs a custom-benchmark dry-run that produces no PRs or comments
**Plans**: TBD
**UI hint**: yes

### Phase 15: Live Dashboard & Failure Handling (O3)
**Goal**: Users watch craws work in real time, replay completed runs, and understand failures through a structured taxonomy.
**Depends on**: Phase 14
**Requirements**: REQ-orch-live-dashboard, REQ-orch-failure-handling
**Success Criteria** (what must be TRUE):
  1. User opens a running task and sees real-time per-craw streaming tool-calls and reasoning over SSE, and can kill it from any view
  2. User replays a completed task from its JSONL transcript and filters by repo/craw/status/reviewer with URL-persisted state
  3. Failures surface in one source of truth (ticket + dashboard + optional email/Slack) under a 7-category taxonomy with trend lines
  4. A craw auto-disables on a failure spike (>50% in 24h over >5 attempts), and manual takeover is detected when a human pushes
**Plans**: TBD
**UI hint**: yes

### Phase 16: PR-Comment Bot (O4)
**Goal**: Reviewers iterate with `@crawfish-bot` directly in GitHub PRs, with honest scope handling and hard caps.
**Depends on**: Phase 15
**Requirements**: REQ-orch-pr-comment-loop
**Success Criteria** (what must be TRUE):
  1. User @-mentions `@crawfish-bot` on a PR and it re-engages (mention-only default), replying with estimated cost and ETA
  2. The bot halts at a per-PR cap (default 5 revisions / $10) and on detecting conflicting reviewers, pinging a human
  3. The bot honestly declines out-of-scope requests and stops within 30s on `@crawfish-bot halt`
**Plans**: TBD
**UI hint**: yes

### Phase 17: Billing, RBAC, Audit & Analytics (O5)
**Goal**: The Orchestrator is a governable, billable product — seats and usage are metered, roles and audit are enforced, and cost analytics prove ROI.
**Depends on**: Phase 16
**Requirements**: REQ-orch-billing-seats, REQ-orch-admin-audit-policy, REQ-orch-analytics
**Success Criteria** (what must be TRUE):
  1. User is billed per human seat via Stripe Connect (agents free), with usage metering, overage warnings, a hard monthly cap that pauses tasks, and PDF invoices
  2. RBAC (admin/member/viewer with per-resource override) governs actions, with a workspace kill switch and per-craw file/egress policy
  3. An immutable append-only audit log (JSONL, exportable, 90-day retention) records every governance action
  4. User exports cost analytics (by workspace/repo/craw/ticket, CSV) including per-ticket cycle-time vs human baseline and an org-wide ROI proxy
**Plans**: TBD
**UI hint**: yes

### Phase 18: Onboarding Polish, Notifications & Ops (O6)
**Goal**: The Orchestrator is operable at scale — guided onboarding, reliable notifications and escalation, and operational visibility.
**Depends on**: Phase 17
**Requirements**: REQ-orch-notifications
**Success Criteria** (what must be TRUE):
  1. User receives in-app + email notifications for plan-approval, PR-ready, and stuck-ticket events with per-event settings, digest mode, and mute controls
  2. A one-way Slack webhook delivers notifications, and an escalation chain fires after 24h unanswered
  3. An onboarding walkthrough, manual-takeover UX, status page, and 2σ regression alert are in place
**Plans**: TBD
**UI hint**: yes

### Phase 19: Public Launch, Craw Authoring & Integrations Edge (O7)
**Goal**: The Orchestrator opens to the public, customers can fork their own craws, and the system survives integration edge cases.
**Depends on**: Phase 18
**Requirements**: REQ-orch-integrations-edge, REQ-orch-success-metrics
**Success Criteria** (what must be TRUE):
  1. Public signup is open, and customers can fork/author craws with a `craw test` CLI and a per-workspace registry
  2. Integration edges are handled: emergency GitHub App disable per repo, direct-push-to-craw-branch detection → halt, GitHub/LLM outage → pause + auto-resume, Issues↔Linear migration preserving history, and cancel → 90-day export then deletion
  3. The wedge success metrics are instrumented and trackable (paying teams, auto-classify rate, post-merge-fix rate, P50 ticket→draft-PR, throughput, cost per merged PR)
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19.
M3 (Phases 12–19) is a parallel paid track; per [ADR-003](decisions/ADR-003-canonical-domain-model.md) it builds directly on the M1 cloud domain model (its hard prerequisite is Phase 4's canonical entities + Phase 7) and is **BLOCKED on ADR-002** (durable workflow engine, OPEN) until Phase 12's first success criterion is met. It may proceed alongside M2 (Phases 8–11) once unblocked.

**Reshape note (2026-05-23, ADR-003):** M0 redefined cloud-first; M1 now leads with the cloud canonical domain model (Phase 4); M3 marked blocked. Migration owed (tracked in STATE.md): desktop board ownership → cloud, remove dash first-run org quiz, deprecate lens board endpoints, author `@crawfish/contracts`, rewrite GRAND_PLAN §3.3 + ROADMAP-MVP Wave 1.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Cloud-First Onboarding MVP | M0 | 0/TBD | Not started | - |
| 2. Thin Web Platform Sync | M0 | 0/TBD | Not started | - |
| 3. MVP Verification & Hardening | M0 | 0/TBD | Not started | - |
| 4. Cycles, Epics, Activity & Member ACL | M1 | 0/TBD | Not started | - |
| 5. Acceptance Criteria, Budget & Preflight | M1 | 0/TBD | Not started | - |
| 6. Capability Routing, AI Triage & Auto-Decomposition | M1 | 0/TBD | Not started | - |
| 7. Linked-Task Graph & FTS5 Search | M1 | 0/TBD | Not started | - |
| 8. Org Filesystem & Knowledge Librarian | M2 | 0/TBD | Not started | - |
| 9. Diagnoses Engine & Optimizer Pack | M2 | 0/TBD | Not started | - |
| 10. Skills, Craws Packaging & Test/Visual Agents | M2 | 0/TBD | Not started | - |
| 11. Native Orchestration Runtime (GOAP MVP) | M2 | 0/TBD | Not started | - |
| 12. Orchestrator Workflow Engine Foundation (O0) | M3 | 0/TBD | ⛔ Blocked (ADR-002) | - |
| 13. Intake → Plan → Execute → CI → Merge (O1) | M3 | 0/TBD | Not started | - |
| 14. Craw Library, Classifier & Eval Harness (O2) | M3 | 0/TBD | Not started | - |
| 15. Live Dashboard & Failure Handling (O3) | M3 | 0/TBD | Not started | - |
| 16. PR-Comment Bot (O4) | M3 | 0/TBD | Not started | - |
| 17. Billing, RBAC, Audit & Analytics (O5) | M3 | 0/TBD | Not started | - |
| 18. Onboarding Polish, Notifications & Ops (O6) | M3 | 0/TBD | Not started | - |
| 19. Public Launch, Craw Authoring & Integrations Edge (O7) | M3 | 0/TBD | Not started | - |
| 20. Cloud Issue Ingestion (Linear + GitHub) | M0/M1 (pulled fwd, depends Phase 2) | 3/4 | In progress (Waves 1–3 done; Wave 4 paused) | - |

### Phase 20: Cloud Issue Ingestion — Linear + GitHub connectors with Postgres Issue model, Linear-Team to Project mapping, OAuth integrations, and project issues UI in cloud/platform

> **Milestone note (updated per ADR-003):** Pulled forward into the M0/M1 cloud-platform line; extends Phase 2. The cloud `Issue` model is a **provider mirror** (GitHub/Linear), distinct from the authored `Task` board built in Phase 4 — an `Issue` may be linked to or *promoted into* a `Task`. (The `provider="native"` value is retired per ADR-003.) Phase 13's webhook/poller feeds the same cloud model. **Status:** Waves 1–3 (schema + GitHub + Linear sync) implemented + tested on branch `feat/cloud-issue-ingestion`; Wave 4 (Board+Projects nav + onboarding reconciliation) paused pending the Phase 4 domain model.

**Goal**: From the cloud platform, a user connects GitHub and Linear to their workspace and auto-loads issues into a per-Project issues view — GitHub issues mapping by repo (the existing 1:1 `Project.githubRepo` binding) and Linear issues mapping by Team (each Linear Team → one Crawfish Project), persisted in a new Postgres `Issue` model and re-syncable idempotently.
**Requirements**: REQ-knowledge-connectors, REQ-orch-issue-intake
**Depends on:** Phase 2
**Success Criteria** (what must be TRUE):
  1. The Prisma schema gains an `Integration` model (per-org, per-provider OAuth token store, `@@unique([orgId, provider])`) and an `Issue` model scoped to `Project` with `@@unique([projectId, provider, externalId])`; `Project` gains `linearTeamId` / `linearTeamKey`. The migration applies cleanly.
  2. A user connects GitHub (reusing the existing Clerk GitHub OAuth token) and runs a sync that upserts that Project's repo issues into `Issue`; re-running the sync is idempotent (no duplicates).
  3. A user completes a Linear OAuth connect, selects which Linear Team binds to a given Project, and runs a sync that upserts that Team's issues into `Issue` carrying Linear project/cycle as metadata/labels.
  4. The `cloud/platform` project page lists issues from `GET /api/orgs/:id/projects/:pid/issues` with state/labels, and a "Sync now" control triggers ingestion and reflects updated counts.
  5. Issue state, title, labels, and external key/url round-trip from the provider into the cloud DB and render in the UI.
**Plans:** 4 plans

Plans:
- [ ] 20-01-PLAN.md — Prisma schema (Integration + Issue + Project.linearTeam*), apply migration, Wave 0 test scaffolds
- [ ] 20-02-PLAN.md — GitHub vertical slice: listRepoIssues (PR-filtered) + syncProjectIssues + issues/sync routes (idempotent, RBAC)
- [ ] 20-03-PLAN.md — Linear slice: OAuth+GraphQL client (refresh-on-401), integrations routes + public callback, team-mapping sync (OAuth-app checkpoint)
- [ ] 20-04-PLAN.md — cloud/platform UI: Connections panel + Project Issues view (Sync now, Team picker), OrgRoute wiring

---
*Roadmap created: 2026-05-22 from doc ingest (mode: new-project-from-ingest)*
*Source of truth for the active schedule: /Users/nealkotval/crawfish/ROADMAP.md*
