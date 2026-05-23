# Requirements: Crawfish

**Defined:** 2026-05-22
**Core Value:** A developer can install Crawfish and, within fifteen minutes, have a spawned agent open a real pull request.

> Requirement IDs are preserved from the ingest intel (`.planning/intel/requirements.md`). PRD requirements keep their `REQ-{slug}` IDs. The preserved local-first MVP milestone (derived from SPEC docs ROADMAP-MVP.md / ROADMAP-WAVE3.md, which carry build-schedule constraints rather than PRD requirements) is captured here under the `MVP-*` category so it gets phase coverage.

## v1 Requirements

### Local-First MVP (preserved earlier milestone — from ROADMAP-MVP.md / ROADMAP-WAVE3.md)

- [ ] **MVP-01**: Standalone Dash runs local-first with no platform, no auth, no backend — one surface (Canvas); Board/Sessions/Knowledge/Diagnoses hidden
- [ ] **MVP-02**: First-run wizard writes an org to disk; Canvas reads from disk and persists drag operations
- [ ] **MVP-03**: A 15-minute recorded flow goes crawfish.dev → download → spawned agent opens a PR (Hire stream)
- [ ] **MVP-04**: Thin web platform sync — Clerk auth gate, org sync API (Postgres + Prisma on Neon), device-link via device code
- [ ] **MVP-05**: Read-only online canvas mirrors the local org; invite-by-email with redeem flow (3 states + 410 + 404)
- [ ] **MVP-06**: Marketing site detects platform and offers correct download with GitHub-release fetch fallback
- [ ] **MVP-07**: Verification & hardening — Playwright e2e green across platform/marketing/dash-web; server contract tests green; Wave-2 code-review doc produced

### Linear-Grade Agent Board (NOW slice — GRAND_PLAN §3.2)

- [ ] **REQ-linear-grade-board**: Native task board better than Linear for agent-native orgs — agents are first-class members; cycles, epics, capability-matched routing, AI triage, auto-decomposition, linked-task graph, FTS5 structured search
- [ ] **REQ-tier1-personas**: Every Stage-1 feature is graded against three Tier-1 personas (solo founder, small-company CEO, individual engineer) and lists which it lights up

### Knowledge Substrate & Optimizers (NEXT / LATER — GRAND_PLAN)

- [ ] **REQ-org-fs-librarian**: Org filesystem + knowledge librarian — per-source-class embedding spaces, contextual-bandit meta-router, LightRAG (`sqlite-vec` + `transformers.js`), knowledge-graph LLM Wiki, cited retrieval
- [ ] **REQ-knowledge-connectors**: Tier-1 connectors ship as benchmarked craws (email, chat, docs, GitHub/GitLab, Linear/Jira, local vaults) with keychain auth + incremental sync
- [ ] **REQ-diagnoses-optimizers**: Diagnoses engine + optimizer pack as the cost-discipline pillar — cost-manager agent, dynamic model switching, 2σ regression alerts
- [ ] **REQ-skills-backbone**: Vendor-neutral MIT skill collection in `~/.crawfish/skills/`, installable per-org/per-agent; diagnoses knows which skill should have fired on failure
- [ ] **REQ-craws-packaging**: Craw manifest + kinds; per-craw defence policy (file/network allow-deny); benchmarked token-per-doc cost (signed marketplace is Stage 2)
- [ ] **REQ-test-visual-agents**: Test-generator agent + Playwright visual-auditor agent — per-PR run app, screenshot routes, diff baseline vs candidate, post visual changelog
- [ ] **REQ-native-orchestration-runtime**: Native GOAP runtime — plain-English goal → A* state-space → executable plan tree in Plan tab, replans on state change (MVP capabilities 1–3)
- [ ] **REQ-agent-os-thesis**: Crawfish is the OS for companies running on AI agents — agent filesystem + librarian is the moat, native orchestration runtime makes it defensible

### Hosted Orchestrator — Wedge (ORCHESTRATOR-* docs, O0–O7)

- [ ] **REQ-orch-wedge-product**: Cloud-hosted service — Linear/GitHub Issues in → auto-classify eligibility → dispatch curated craws (impl + tester + reviewer) in isolated worktrees → CI-verified → checkpoint-gated PR out
- [ ] **REQ-orch-wedge-task**: v1 narrows to boring-and-bounded tickets (dep bumps, test backfill, lint/dead-code cleanup, type-annotation backfill, low-risk CVE patches) with machine-verifiable outcomes
- [ ] **REQ-orch-onboarding**: GitHub-OAuth signup + workspace <90s; invite by email/domain; connect Linear + GitHub App per-repo; CI detection; 4-step walkthrough ending in a real sandbox PR <10min
- [ ] **REQ-orch-issue-intake**: Read Linear ticket <60s and decide craw-eligibility (webhook <10s, classifier <20s); per-workspace threshold; manual override; "Craw will attempt this" comment; GitHub Issues 5-min poll
- [ ] **REQ-orch-plan-checkpoint**: Gate 1 — pre-code plan as ticket comment (files, tests, est diff/cost); approve via reaction/button; reject with reason; inline-edit + re-approve; per-label auto-approval; SLA + escalation
- [ ] **REQ-orch-execution**: Durable workflow survives worker crash without double side-effects (idempotency keys); concurrency limits; cancel <30s; isolated worktree per task; re-run; per-task + per-org budget caps; idle auto-halt
- [ ] **REQ-orch-ci-verification**: Customer GitHub Actions runs on craw PR (draft until CI); required-jobs gate; on fail read log + fix up to N revisions; regression guard; optional test-generator + visual-auditor CI checks
- [ ] **REQ-orch-merge-checkpoint**: Gate 2 — on CI pass draft→ready with structured description; auto-assign reviewer (CODEOWNERS); single/N approvals merge (respects branch protection); auto-close ticket; reject returns to backlog
- [ ] **REQ-orch-craw-config**: Browse curated library (8–12 craws) with published bench; 1-click idempotent install/uninstall; version pinning + rollback + changelog; routing rules (label→craw); per-craw repo allow/deny; drift indicator
- [ ] **REQ-orch-eval-quality**: Classifier accuracy (precision/recall/FPR over 30 days); label-correctness eval set + weekly re-eval; public per-craw bench; custom-benchmark dry-run; 2σ regression alert
- [ ] **REQ-orch-live-dashboard**: Open running task — real-time per-craw streaming tool-calls + reasoning (SSE); multi-craw team view; replay from JSONL; URL-persisted filters; org-wide rollup; kill from any view
- [ ] **REQ-orch-failure-handling**: Failure surfaces in ticket + dashboard + optional email/Slack; 7-category taxonomy with trend lines; manual takeover detection; auto-disable craw on failure spike; opt-in weekly digest
- [ ] **REQ-orch-pr-comment-loop**: `@crawfish-bot` re-engages (mention-only default); per-repo mode; "working on it" reply with cost+ETA; per-PR revision/$ cap; conflicting-reviewer detection; out-of-scope honesty; `halt` <30s
- [ ] **REQ-orch-billing-seats**: Stripe Connect, per-seat humans (agents free); usage vs plan with overage warnings; per-seat allowance + metering; hard monthly cap → pause; projected EOM cost; pro-rated seats; PDF invoices
- [ ] **REQ-orch-admin-audit-policy**: Immutable append-only audit log (JSONL, exportable, 90-day retention); RBAC (admin/member/viewer + per-resource override); workspace kill switch; per-craw file/egress policy; versioned policy bundle
- [ ] **REQ-orch-analytics**: Cost by workspace/repo/craw/ticket (CSV export); compounding-factor metric; per-craw + per-engineer (privacy-respecting) stats; org-wide ROI proxy; per-ticket cycle-time vs human baseline
- [ ] **REQ-orch-notifications**: In-app + email for plan-approval/PR-ready/stuck-ticket (per-event settings); digest mode; mute per repo/ticket; one-way Slack webhook; billing notifications; escalation chain
- [ ] **REQ-orch-integrations-edge**: Emergency GitHub App disable per repo; detect direct push to craw branch → halt; GitHub/LLM outage → pause + auto-resume; migrate Issues↔Linear preserving history; cancel → 90-day export then deletion
- [ ] **REQ-orch-success-metrics**: 12-month wedge targets — 20 paying teams (~12 seats avg), ≥60% auto-classified complete without escalation, ≤10% merged PRs need post-merge fix, <15min P50 ticket→draft-PR, 2x IC throughput, cost/merged-PR <30% of an IC hour

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### GRAND_PLAN later stages

- **REQ-stage2-hosted**: Stage 2 (m9–m24) — hosted everything, RL fine-tunes per org, multi-user, 24/7 issue tracking, manager-grade analytics, hybrid pricing
- **REQ-stage3-enterprise**: Stage 3 (m18+) — compliance tier, audit export, attestation primitive, SSO/SAML/OIDC, on-prem, SOC2

### Orchestrator deferred-but-on-roadmap

- **REQ-orch-out-of-v1**: Customer-authored craws (partial in O7), marketplace, AI-generated craws, refactor/feature-class tasks, IDE, local Codespaces, Pilot Protocol, methodology packs, SSO/SAML, on-prem

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Slack-as-execution-surface | Deferred forever in the wedge — execution belongs in worktrees + GitHub, not chat |
| Per-PR pricing | Deferred forever — pricing is seat + usage (humans bill, agents free) |
| Fully-autonomous PRs without checkpoints | Deferred forever — plan + merge gates are core trust mechanism |
| Auto-installation of craws | Anti-goal across all docs |
| Per-execution paywall on community craws | Anti-goal — community craws stay free |
| Enterprise paywalling of compliance | Anti-goal — compliance is not a gate |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MVP-01 | Phase 1 | Pending |
| MVP-02 | Phase 1 | Pending |
| MVP-03 | Phase 1 | Pending |
| MVP-04 | Phase 2 | Pending |
| MVP-05 | Phase 2 | Pending |
| MVP-06 | Phase 2 | Pending |
| MVP-07 | Phase 3 | Pending |
| REQ-linear-grade-board | Phase 4 | Pending |
| REQ-tier1-personas | Phase 4 | Pending |
| REQ-org-fs-librarian | Phase 8 | Pending |
| REQ-knowledge-connectors | Phase 8 | Pending |
| REQ-diagnoses-optimizers | Phase 9 | Pending |
| REQ-skills-backbone | Phase 10 | Pending |
| REQ-craws-packaging | Phase 10 | Pending |
| REQ-test-visual-agents | Phase 10 | Pending |
| REQ-native-orchestration-runtime | Phase 11 | Pending |
| REQ-agent-os-thesis | Phase 11 | Pending |
| REQ-orch-wedge-product | Phase 12 | Pending |
| REQ-orch-wedge-task | Phase 12 | Pending |
| REQ-orch-onboarding | Phase 13 | Pending |
| REQ-orch-issue-intake | Phase 13 | Pending |
| REQ-orch-plan-checkpoint | Phase 13 | Pending |
| REQ-orch-execution | Phase 13 | Pending |
| REQ-orch-ci-verification | Phase 13 | Pending |
| REQ-orch-merge-checkpoint | Phase 13 | Pending |
| REQ-orch-craw-config | Phase 14 | Pending |
| REQ-orch-eval-quality | Phase 14 | Pending |
| REQ-orch-live-dashboard | Phase 15 | Pending |
| REQ-orch-failure-handling | Phase 15 | Pending |
| REQ-orch-pr-comment-loop | Phase 16 | Pending |
| REQ-orch-billing-seats | Phase 17 | Pending |
| REQ-orch-admin-audit-policy | Phase 17 | Pending |
| REQ-orch-analytics | Phase 17 | Pending |
| REQ-orch-notifications | Phase 18 | Pending |
| REQ-orch-integrations-edge | Phase 19 | Pending |
| REQ-orch-success-metrics | Phase 19 | Pending |

**Coverage:**
- v1 requirements: 37 total (7 MVP-* + 30 REQ-*)
- Mapped to phases: 37
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-22*
*Last updated: 2026-05-22 after initial definition*
