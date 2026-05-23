# Roadmap: Crawfish

> This is the GSD-structured derivation of the authoritative root `/Users/nealkotval/crawfish/ROADMAP.md`. It does not replace it. All pre-pivot paths from source docs are translated to the monorepo layout (`cloud/`, `desktop/`, `cli/`, `web/`).

## Overview

Crawfish ships in four milestones. **M0** delivers the preserved local-first MVP — a standalone Dash that gets a developer from crawfish.dev to an agent-authored PR in fifteen minutes, plus a thin web sync layer and a verification pass. **M1** builds the Linear-grade agent board (the NOW slice): cycles, criteria, budgets, routing, triage, decomposition, and structured search. **M2** adds the knowledge substrate and cost-discipline pillar — org filesystem + librarian, optimizer pack, skills backbone, packaged craws, and the native GOAP orchestration runtime that makes the org-OS thesis defensible. **M3** is the parallel paid track: the hosted Orchestrator that turns issues into CI-verified, checkpoint-gated PRs for mid-market engineering teams, built up O0→O7 from a durable workflow engine through to public launch.

## Milestones

- 📋 **M0 — Local-First MVP** - Phases 1-3 (preserved earlier milestone; ships first)
- 📋 **M1 — Linear-Grade Agent Board (NOW)** - Phases 4-7
- 📋 **M2 — Knowledge Substrate & Optimizers (NEXT/LATER)** - Phases 8-11
- 📋 **M3 — Hosted Orchestrator (parallel paid track, O0–O7)** - Phases 12-19

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Standalone Dash MVP** - Local-first one-surface Canvas; 15-min crawfish.dev → agent PR
- [ ] **Phase 2: Thin Web Platform Sync** - Clerk auth, org sync, device-link, read-only online canvas, invite-by-email
- [ ] **Phase 3: MVP Verification & Hardening** - Playwright e2e + server contract tests + Wave-2 review doc
- [ ] **Phase 4: Cycles, Epics, Activity & Member ACL** - Board foundation with agents as first-class members
- [ ] **Phase 5: Acceptance Criteria, Budget & Preflight** - Evidence guard, live token-budget bar, agent self-attestation
- [ ] **Phase 6: Capability Routing, AI Triage & Auto-Decomposition** - Smart task assignment and epic breakdown
- [ ] **Phase 7: Linked-Task Graph & FTS5 Search** - Link kinds, structured search, external-ref ingestion
- [ ] **Phase 8: Org Filesystem & Knowledge Librarian** - RAG indexing, contextual-bandit router, Tier-1 connectors
- [ ] **Phase 9: Diagnoses Engine & Optimizer Pack** - Cost-manager, dynamic model switching, 2σ regression alerts
- [ ] **Phase 10: Skills Backbone, Craws Packaging & Test/Visual Agents** - Installable skills, craw manifest+policy, per-PR visual auditor
- [ ] **Phase 11: Native Orchestration Runtime (GOAP MVP)** - Plain-English goal → A* plan tree, replanning
- [ ] **Phase 12: Orchestrator Workflow Engine Foundation (O0)** - Durable engine choice (ADR-002), skeleton, worktree isolation, dep-bumper spike
- [ ] **Phase 13: Intake → Plan → Execute → CI → Merge (O1)** - End-to-end checkpoint-gated PR pipeline
- [ ] **Phase 14: Craw Library, Classifier & Eval Harness (O2)** - Curated library, auto-classifier, routing rules, eval
- [ ] **Phase 15: Live Dashboard & Failure Handling (O3)** - Per-craw SSE, team view, replay, failure taxonomy
- [ ] **Phase 16: PR-Comment Bot (O4)** - `@crawfish-bot` revision loop with caps and conflict detection
- [ ] **Phase 17: Billing, RBAC, Audit & Analytics (O5)** - Stripe seats, roles, immutable audit, cost analytics
- [ ] **Phase 18: Onboarding Polish, Notifications & Ops (O6)** - Walkthrough, notifications, escalation, status page
- [ ] **Phase 19: Public Launch, Craw Authoring & Integrations Edge (O7)** - Public signup, customer craw forking, edge resilience

## Phase Details

### Phase 1: Standalone Dash MVP
**Goal**: A developer downloads the standalone Dash and gets an agent to open a real PR with no platform, auth, or backend involved.
**Depends on**: Nothing (first phase)
**Requirements**: MVP-01, MVP-02, MVP-03
**Success Criteria** (what must be TRUE):
  1. User launches Dash and sees exactly one surface (Canvas); Board/Sessions/Knowledge/Diagnoses are hidden
  2. User completes a first-run wizard that writes an org to disk, and Canvas reads it back and persists drag operations
  3. User can run the Hire stream and watch a spawned agent open a real PR end-to-end
  4. The full crawfish.dev → download → PR flow is recordable in under 15 minutes
**Plans**: TBD
**UI hint**: yes

### Phase 2: Thin Web Platform Sync
**Goal**: A user can sign in to the web platform, link their desktop device, and view a read-only mirror of their local org, and invite teammates by email.
**Depends on**: Phase 1
**Requirements**: MVP-04, MVP-05, MVP-06
**Success Criteria** (what must be TRUE):
  1. User signs in through the Clerk auth gate and lands on their org
  2. User links a desktop device via device code and the local org syncs to the platform (Postgres + Prisma on Neon)
  3. User views a read-only online canvas that mirrors the local org
  4. User invites a teammate by email and the teammate can redeem the invite (valid / mismatched / expired states handled)
  5. A visitor on the marketing site is offered the correct platform download with a GitHub-release fallback
**Plans**: TBD
**UI hint**: yes

### Phase 3: MVP Verification & Hardening
**Goal**: The Wave 1/Wave 2 MVP surfaces are trustworthy — covered by end-to-end and contract tests with a documented review pass. No new features.
**Depends on**: Phase 2
**Requirements**: MVP-07
**Success Criteria** (what must be TRUE):
  1. `npx playwright test` is green across the platform, marketing, and dash-web suites (auth gate, onboarding, OrgPicker, read-only canvas, invite redeem states, device-link, Hire stream)
  2. Server contract tests (`npm test` via supertest) are green for health, orgs CRUD+RBAC, invites CRUD+redeem+mismatch+expiry, device-link
  3. A Wave-2 code-review doc exists at `docs/reviews/REVIEW-WAVE2.md` with each severity bucket addressed
**Plans**: TBD

### Phase 4: Cycles, Epics, Activity & Member ACL
**Goal**: Users run a Linear-grade board where agents are first-class workspace members, work is organized into cycles and epics, and activity is visible.
**Depends on**: Phase 3
**Requirements**: REQ-linear-grade-board, REQ-tier1-personas
**Success Criteria** (what must be TRUE):
  1. User can create cycles and epics and drag tasks into a cycle with budget rollup
  2. Agents appear as first-class members of the workspace (billed as free members per Linear convention)
  3. User sees a live activity feed of board changes
  4. Member access is governed by an ACL, and each board feature documents which Tier-1 persona it lights up
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
M3 (Phases 12–19) is a parallel paid track whose only hard prerequisite is the M1 board (Phase 7); it may proceed alongside M2 (Phases 8–11) given resourcing.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Standalone Dash MVP | M0 | 0/TBD | Not started | - |
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
| 12. Orchestrator Workflow Engine Foundation (O0) | M3 | 0/TBD | Not started | - |
| 13. Intake → Plan → Execute → CI → Merge (O1) | M3 | 0/TBD | Not started | - |
| 14. Craw Library, Classifier & Eval Harness (O2) | M3 | 0/TBD | Not started | - |
| 15. Live Dashboard & Failure Handling (O3) | M3 | 0/TBD | Not started | - |
| 16. PR-Comment Bot (O4) | M3 | 0/TBD | Not started | - |
| 17. Billing, RBAC, Audit & Analytics (O5) | M3 | 0/TBD | Not started | - |
| 18. Onboarding Polish, Notifications & Ops (O6) | M3 | 0/TBD | Not started | - |
| 19. Public Launch, Craw Authoring & Integrations Edge (O7) | M3 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-22 from doc ingest (mode: new-project-from-ingest)*
*Source of truth for the active schedule: /Users/nealkotval/crawfish/ROADMAP.md*
