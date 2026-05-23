# Crawfish Orchestrator — development stages

Companion to [`ORCHESTRATOR-ONEPAGER.md`](./ORCHESTRATOR-ONEPAGER.md) and [`ORCHESTRATOR-USER-STORIES.md`](./ORCHESTRATOR-USER-STORIES.md). This file sequences the orchestrator build against the active [`../../ROADMAP.md`](../../ROADMAP.md). The orchestrator is a *parallel track* to the existing NOW / NEXT / LATER / LATER² slices, not a replacement. Many stages depend on substrate that is already shipping; some pull forward work that was originally Stage 2 or LATER².

This doc commits to: (a) a numbered stage sequence with concrete deliverables, file paths, and exit criteria; (b) explicit reuse-vs-build calls per stage; (c) explicit slip-impact calls (what gets pushed in the existing ROADMAP because the orchestrator pulls resources or scope forward); (d) gate criteria that must be green before the next stage starts.

Conventions: `O0` … `O7` are orchestrator stages. Stage durations are weeks of focused work, not calendar weeks. A two-engineer team is assumed (one full-stack for the orchestrator core, one for the dashboard + cloud-server work). With one engineer, multiply by ~1.8. With three, by ~0.75.

---

## Pre-stage — substrate readiness (weeks 1–5, already in flight)

This is the existing `ROADMAP.md` NOW slice. It is not orchestrator work, but the orchestrator depends on it landing without slip.

**What ships before O0 can start:**

- Linear-grade board: cycles, epics, criteria evidence, token-budget bar, activity feed, capability-matched routing, AI triage, auto-decomposition, linked-task graph, FTS5 search, external-ref ingestion, multi-org switcher, stats endpoint, cycle planner. [`ROADMAP.md`](../../ROADMAP.md) §NOW Weeks 1–5.
- v0.3 tag across umbrella + each submodule.

**Why this is a hard prerequisite for the orchestrator:**

- The orchestrator uses the existing board as its task substrate (`cli/orgctl/src/board.ts`). Without cycles + criteria evidence + activity feed shipped, the orchestrator has no canonical place to write run state.
- The capability-matched router (`cli/projectctl/src/router.ts`) is the routing engine the orchestrator inherits. The router's 70%-success threshold and per-agent stats are the substrate the auto-classifier will sit on top of.
- The activity-feed event taxonomy (`task_*`, `cycle_*`, `criterion_*`, `budget_breach`) is the event vocabulary the orchestrator extends.

**Exit gate:** v0.3 tag cut. All `desktop/lens` and `desktop/dash` tests green. Smoke-15min.ts (when it ships in NEXT week 8) green in CI is the formal gate, but O0 can start once the v0.3 surface is feature-complete.

---

## O0 — foundation choices + end-to-end spike (weeks 6–8)

**Goal:** Prove the cloud-hosted orchestrator can drive one craw to open one PR against a sandbox repo, end-to-end, using the existing `claude-code` runtime adapter and the existing board substrate. Decide the durable workflow engine before any production code is written.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O0.1 | ADR-002 — durable workflow engine choice | `.planning/decisions/ADR-002-orchestrator-workflow-engine.md` | Compare Temporal, Inngest, Restate; reject BullMQ/pg-boss on the grounds in [the orchestrator design conversation]; defend pick on durable-execution semantics, multi-hour pause support, deployment burden. |
| O0.2 | Cloud-server orchestrator module skeleton | `cloud/server/src/orchestrator/{queue.ts,worker.ts,workflow.ts,types.ts}` | Server-side workflow definitions; extends the existing Express app, not a new service. Uses the existing Prisma `Org`/`Project`/`User` models. |
| O0.3 | Worker runtime adapter shim | `cloud/server/src/orchestrator/adapters/claude-code.ts` | Wraps the existing `desktop/lens/src/adapters/openclaw.ts` pattern for server-side use. Spawns the runtime in an isolated worker process. |
| O0.4 | One craw definition (dep-bumper) | `cli/orgctl/src/craws/dep-bumper/{craw.yaml,SKILL.md,impl.ts}` | First curated craw. Operates as a `kind: agent` craw per GRAND_PLAN §3.17 manifest. v0 scope: reads `package.json`, picks one bumped dep with passing tests, opens a PR. |
| O0.5 | Worktree isolation utility | `cli/orgctl/src/worktree/{spawn.ts,merge.ts,cleanup.ts}` | Pulled forward from GRAND_PLAN §3.3 LATER² weeks 23–24. The isolation primitive — not the CRDT layer, that stays deferred. |
| O0.6 | End-to-end spike script | `scripts/spike-orchestrator-e2e.ts` | Manual ticket creation → spike script invokes the workflow → dep-bumper runs → PR opens against a sandbox repo. Run-and-record on commit. |

**Reuse:** existing Prisma models (`Org`, `Project`, `User`, `OrgMember`); existing `cli/orgctl` MCP server pattern; existing `desktop/lens/src/adapters/openclaw.ts` adapter shape; existing GitHub OAuth from `cloud/server`.

**New:** the orchestrator subsystem itself (queue + worker + workflow); the worktree utility; the craws/ directory under `cli/orgctl/src/`; the spike script.

**Slip impact:** NEXT week 6 (RAG indexing) holds; week 7 (token-discipline optimizers) holds; week 8 (founder-dash polish) holds because the orchestrator team is the parallel-track engineer plus the new orchestrator engineer, not the existing lens + dash team.

**Exit gate:** the spike script runs in CI; produces a draft PR on a sandbox repo without manual intervention. Per-step latency logged. ADR-002 merged.

---

## O1 — single-craw PR loop, single design partner (weeks 9–14)

**Goal:** Replace the spike script with a real durable workflow. One workspace, one repo, one craw. A real ticket lands and a real PR opens against a real customer repo. Five design partners signed up to test on a private staging tier.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O1.1 | Linear webhook receiver | `cloud/server/src/inbound/linear.ts` | Subscribes to issue.created / issue.updated. Verifies signature. Lands a `task_created` event on the existing board via `cli/orgctl/src/board.ts:appendEvent`. |
| O1.2 | GitHub Issues poller (5-minute interval) | `cloud/server/src/inbound/github-issues-poller.ts` | Extends the existing `cli/orgctl/src/inbound/github-issues.ts` pattern; dedups against the board. Required because not every customer has Linear webhooks available. |
| O1.3 | Plan checkpoint workflow | `cloud/server/src/orchestrator/checkpoints/plan.ts` | After the craw produces its plan, post to the ticket + dashboard; wait for human approval (durable wait); time out + escalate per the SLA policy. |
| O1.4 | Pre-merge checkpoint workflow | `cloud/server/src/orchestrator/checkpoints/merge.ts` | After CI passes and the PR is ready-for-review, wait for human merge (auto-poll GitHub PR status). |
| O1.5 | Basic execution dashboard widget | `cloud/platform/src/pages/Orchestrator.tsx` + `desktop/dash/web/src/routes/Orchestrator.tsx` | Single-craw view; list of in-flight tasks; click for live SSE log. No multi-craw view yet. |
| O1.6 | Per-task budget cap enforcement | `cloud/server/src/orchestrator/budget.ts` | Wires the existing `cli/orgctl/src/budget.ts` cost-manager pattern to the orchestrator's per-task token meter. |
| O1.7 | CI gate (GitHub Actions only) | `cloud/server/src/orchestrator/ci.ts` | Polls GitHub status checks; required checks list configurable per repo; failed CI triggers up to 3 fix attempts. |
| O1.8 | Cancel + retry primitives | dashboard + workflow | One-click cancel from dashboard; one-click retry from a failed task. |
| O1.9 | Design partner onboarding doc | `docs/orchestrator/design-partner-onboarding.md` | 1-page setup runbook. Use for the first 5 partners. |
| O1.10 | Integration test suite | `cloud/server/test/orchestrator/*.test.ts` | At minimum: webhook → board, plan checkpoint timeout, CI failure + retry, cancel mid-run, budget cap. |

**Reuse:** existing board substrate (cycles, criteria, budget, activity); existing GitHub OAuth; existing `cli/orgctl/src/inbound/github-issues.ts` for the polling shape; existing `cli/orgctl/src/budget.ts` for cost-manager logic; existing `desktop/lens` SSE infrastructure (shared between local lens and the new cloud dashboard).

**New:** Linear webhook receiver; the checkpoint workflows (plan, merge); CI gate logic; the dashboard widget; per-task budget cap enforcement at the worker level.

**Slip impact:** NEXT week 9–10 (buffer + alpha-readiness) becomes O1's slip buffer rather than independent buffer time. LATER weeks 11–13 (skill backbone + Codespaces local) lose ~30% of capacity if the parallel-track engineer is partially reassigned; mitigation is to slip those by 2 weeks rather than cut scope.

**Exit gate:** five design partners actively using the orchestrator against their own repos with the dep-bumper craw. At least 20 PRs merged across all five partners. Mean ticket-to-draft-PR latency under 15 minutes. Zero P0 incidents in the last 7 days.

---

## O2 — curated craw library + auto-classifier v1 (weeks 15–18)

**Goal:** Three more craws shipped (test-backfill, lint-cleaner, type-annotator). LLM-based auto-classifier replaces "label-only" eligibility as the default. Per-customer eval harness in place from day one. Ten design partners.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O2.1 | test-backfill craw | `cli/orgctl/src/craws/test-backfill/` | Reads coverage report; identifies un-covered modules; writes tests against a fixture; verifies against CI. |
| O2.2 | lint-cleaner craw | `cli/orgctl/src/craws/lint-cleaner/` | Runs the customer's linter; applies auto-fixable rules; opens PR with the diff. |
| O2.3 | type-annotator craw | `cli/orgctl/src/craws/type-annotator/` | TypeScript-only initially; adds type annotations to JS-flavored files via TS compiler API. |
| O2.4 | Auto-classifier service | `cloud/server/src/classifier/{index.ts,prompts.ts,eval.ts}` | Haiku-class model classifies each inbound ticket as eligible / ineligible / borderline. Eligibility decision posted as a Linear/GitHub comment + label. |
| O2.5 | Per-workspace eval harness | `cloud/server/src/classifier/eval-harness.ts` + dashboard | EMs label past classifier decisions as correct/incorrect; weekly re-evaluation; precision/recall surfaced in dashboard. |
| O2.6 | Label-only fallback toggle | dashboard + workflow | When confidence is below threshold (default 0.7) OR when EM opts out, fall back to label-only eligibility. |
| O2.7 | Per-craw routing rules UI | `cloud/platform/src/pages/RoutingRules.tsx` | EM defines: label `dep-bump` → `dep-bumper-craw v3`; first match wins; explicit fallback rule required. |
| O2.8 | Per-craw allow/deny file-path lists | dashboard + worker | Enforced at the worktree mount level (rejects writes outside allowed paths). Matches GRAND_PLAN §3.16 defence-toolcall pattern. |
| O2.9 | Craw version pinning | dashboard | EM pins a version per workspace; rollback to previous version available for 30 days. |
| O2.10 | Bench fixtures for the 4 craws | `bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/` | Each craw publishes verified scores on Crawfish's reference bench. |

**Reuse:** existing `triage.ts` heuristic shaping (runs first to normalize labels before the classifier); existing `cli/projectctl/src/router.ts` capability matching (runs second to pick which craw given the rules); the existing `bench/` directory pattern.

**New:** the four craws (one was the spike, three are new); the auto-classifier service + eval harness; the routing rules UI; the version pinning surface; the file-path allow/deny enforcement.

**Slip impact:** LATER week 14 (Crawfish IDE v0.1) slips by 4 weeks (was scheduled for week 14, lands in week 18 of LATER track at earliest). LATER week 15 (LLM Wiki + Obsidian sync) holds because it's local-first work not on the orchestrator path. LATER week 16 (cron recipes + cost-manager) holds because the orchestrator inherits the cost-manager work directly.

**Exit gate:** four craws live, each with published bench scores. Auto-classifier shipped with eval harness. Ten design partners. Classifier precision ≥ 80% on the aggregated eval set (intentionally not "perfect" — the human checkpoint catches false positives, so precision matters more than recall in v1). At least 100 PRs merged across all partners.

---

## O3 — live team-execution dashboard + multi-craw collab (weeks 19–22)

**Goal:** The dashboard shows multi-craw collaboration in real time. The "team shape" is visible to the customer even when it's a single craw (rendered as "1 of 1" but with the infrastructure to scale). Replay mode. Failure categorization.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O3.1 | Multi-craw collab primitive | `cloud/server/src/orchestrator/team.ts` | A task can dispatch to N craws collaborating in the same worktree (impl + tester + reviewer). For v1 the default is single-craw; the primitive exists for v1.5 expansion. |
| O3.2 | Per-craw SSE stream | `cloud/server/src/orchestrator/stream.ts` | One stream per craw per task; aggregated at the dashboard level. Uses the existing lens SSE infrastructure. |
| O3.3 | Team execution view | `cloud/platform/src/pages/TaskRun.tsx` + `desktop/dash/web/src/routes/TaskRun.tsx` | Vertical lane per craw; live tool calls + reasoning; collapsed by default; expandable per craw. |
| O3.4 | Replay mode | shared with O3.3 | Same UI; reads from the JSONL transcript instead of live SSE. Uses existing lens replay primitives. |
| O3.5 | Failure categorization taxonomy | `cloud/server/src/orchestrator/failure-taxonomy.ts` | Categories: `plan-rejected`, `ci-failed-after-fixes`, `budget-exceeded`, `craw-error`, `timeout`, `cancelled-by-user`, `policy-blocked`. Each task ending in failure gets exactly one category. |
| O3.6 | Failure dashboard widget | dashboard | Filter by category, by craw, by repo; trend lines. |
| O3.7 | Auto-disable craw on failure spike | `cloud/server/src/orchestrator/craw-health.ts` | Spike threshold: >50% failures in 24h on >5 attempts; auto-pauses new dispatches; pings EM. |
| O3.8 | Manual takeover detection | `cloud/server/src/orchestrator/takeover-detector.ts` | When a human pushes a commit to a craw's branch, orchestrator detects and exits gracefully; ticket links the human PR. |

**Reuse:** existing lens SSE; existing JSONL transcript store; existing `desktop/dash/web/src/components/FlowGraph.tsx` for the lane layout; existing diagnoses-engine event shape.

**New:** the team primitive; the per-craw stream aggregation; the team execution view; the failure taxonomy + UI; auto-disable; takeover detection.

**Slip impact:** LATER² weeks 19–20 (test-generator + visual-auditor agents) accelerate because they ship as additional craws in the orchestrator, not as separate work. Net: the LATER² CI/CD week 19–20 work merges into O3 and runs at the same time. PARALLEL TRACK weeks 11–13 (collaboration: presence, comments, CRDT drawer) holds — orchestrator collaboration is server-side workflow, not concurrent human editing.

**Exit gate:** dashboard shows live multi-craw view (even if mostly 1-of-1 runs). Replay mode works for all v0.3+ tasks. Failure taxonomy applied to all failed tasks for the last 7 days. Auto-disable verified end-to-end on a synthetic failure-rate spike.

---

## O4 — PR-comment loop with budget + halt heuristics (weeks 23–26)

**Goal:** Reviewers can leave comments and the craw addresses them within an explicit budget. No infinite loops. No reviewer-vs-bot arguments. Halt criteria are explicit and auditable.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O4.1 | Bot identity + mention listener | `cloud/server/src/orchestrator/pr-bot/listener.ts` | GitHub App identity; listens for @-mentions, `@crawfish-bot halt`, etc. |
| O4.2 | Comment-resolution state machine | `cloud/server/src/orchestrator/pr-bot/state-machine.ts` | States: `idle`, `addressing`, `awaiting-feedback`, `halted-conflict`, `halted-budget`, `halted-out-of-scope`, `merged`. Each transition is logged. |
| O4.3 | Per-PR revision + token cap | shared with O4.2 | Defaults: 5 revisions, $10. Configurable per repo. On cap: halt with explicit reason. |
| O4.4 | Conflict-with-reviewer detector | `cloud/server/src/orchestrator/pr-bot/conflict-detector.ts` | Heuristic: when two reviewers' comments are semantically incompatible OR one reviewer comment contradicts a prior bot revision, halt and ping a human. False positives are tolerable; false negatives are expensive. |
| O4.5 | Out-of-scope detector | `cloud/server/src/orchestrator/pr-bot/scope-detector.ts` | Comments that require architectural decisions, comments that ask for changes outside the original plan's scope. Halt with an honest "I can't address this without X." |
| O4.6 | Auto-respond mode toggle | dashboard | Per-repo mode: `mention-only` (default), `respond-to-all`, `off`. |
| O4.7 | Bot reply templates | `cloud/server/src/orchestrator/pr-bot/templates.ts` | "Working on it (est cost: $X, est ETA: Y)"; "Halted: budget exceeded after N revisions"; "Halted: conflicting feedback from @A and @B, please clarify"; "Halted: out-of-scope (this requires Z)." Standardized + reviewable. |
| O4.8 | Audit trail per revision | reuses §14 audit log surface | Every bot revision is an audit-log entry: who triggered, what changed, tokens spent. |

**Reuse:** existing GitHub App; existing audit JSONL substrate; existing budget enforcement (extended to per-PR scope rather than per-task).

**New:** the bot identity (separate from the human user accounts in `OrgMember`); the state machine; the conflict detector; the scope detector; the comment templates; the per-PR cap logic.

**Slip impact:** LATER² weeks 21–22 (agent-web proxy MVP) slips by 4 weeks because the parallel-track engineer is now full-time on the PR-bot work. PARALLEL TRACK weeks 11–13 collaboration features still hold; orchestrator PR-bot is server-side, doesn't conflict.

**Exit gate:** PR-bot ships behind a per-workspace flag; turn-on rate among the 10 design partners ≥ 60% within 2 weeks of launch; zero PRs require an emergency manual disable across all partners in a 7-day window after enablement.

---

## O5 — multi-user, RBAC, billing, audit (weeks 27–30)

**Goal:** The orchestrator becomes a real multi-user product. Mid-market eng teams can buy it. Billing is metered. RBAC is enforced. Audit is queryable. This is the pulled-forward PARALLEL TRACK D (weeks 14–16 in the original ROADMAP).

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O5.1 | Stripe Connect integration | `cloud/server/src/billing/{stripe.ts,seats.ts,usage.ts}` | Subscriptions, seats, usage metering, invoices, webhooks. Per the GRAND_PLAN §3.2 Linear convention: humans bill, agents don't. |
| O5.2 | RBAC roles + permission matrix | `cloud/server/src/auth/rbac.ts` + docs | Roles: admin, member, viewer. Per-resource overrides (e.g., a member can be admin on one repo only). Matrix documented in `docs/orchestrator/rbac-matrix.md`. |
| O5.3 | Audit log projection + UI | `cloud/server/src/audit/{index.ts,query.ts}` + `cloud/platform/src/pages/AuditLog.tsx` | Reads the JSONL substrate; per-actor + per-resource + per-action filters; 90-day default retention; export as JSONL. |
| O5.4 | Seat enforcement | shared with O5.1 | Adding a `humanity: "human"` member when over plan returns 402 `seat_limit`. Agents always allowed. |
| O5.5 | Usage metering | shared with O5.1 | Tokens consumed per user (attributed to whoever created or @-mentioned the task) above the per-seat allowance bill at the per-token rate. |
| O5.6 | Monthly budget cap + pause | `cloud/server/src/billing/budget-cap.ts` | Hard cap at the workspace level; on hit, new tasks queue with `paused-for-budget` status; in-flight tasks complete. |
| O5.7 | Invite flow polish | existing `cloud/server` invite model + new UI | Email invite, magic-link accept, role chosen at invite. Most of the model exists in Prisma; UI is the new work. |
| O5.8 | Per-craw + per-org network egress policy | `cloud/server/src/policy/egress.ts` | Default allow: GitHub + LLM provider only. Per-craw override allowed. Matches GRAND_PLAN §3.16 defence-toolcall pattern. |
| O5.9 | Workspace-wide kill switch | dashboard + workflow | Pause all dispatches. In-flight tasks complete; new tasks queue. Reversible in two clicks. |

**Reuse:** existing Prisma `User` / `Org` / `OrgMember` / `Invite` / `DeviceLinkCode` models; existing JSONL substrate for audit; existing notification primitives (extended for billing events).

**New:** Stripe integration; RBAC enforcement; usage metering at the worker level; the audit-log query projection; the egress policy enforcement; the kill switch.

**Slip impact:** PARALLEL TRACK D (weeks 14–16) is *consumed* by O5 rather than running separately. The PARALLEL TRACK marketing site work (weeks 6–7) and authed web dashboard work (weeks 8–10) hold their slots — they're complementary to the orchestrator, not competing. The LATER² CRDT + git-worktree work (weeks 23–24, agent-side) holds; only the worktree-isolation half was pulled forward into O0; the CRDT half stays in LATER².

**Exit gate:** Stripe webhook live; first paying team (one of the existing design partners) signed; RBAC matrix doc + UI shipped; audit log queryable in dashboard. SOC2 readiness checklist drafted (not yet implemented — the GRAND_PLAN §5 Stage 3 compliance work).

---

## O6 — closed beta with 10–20 paying teams (weeks 31–36)

**Goal:** Convert design partners into paying teams. Polish the onboarding flow. Ship the failure-mode UX (escalation, manual takeover, support runbooks). Build the muscle of supporting real customers on real repos.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O6.1 | Onboarding walkthrough | `cloud/platform/src/onboarding/orchestrator/*` | 4-step empty-state walkthrough; ends with a real PR opened against a Crawfish-provided sandbox repo within 10 minutes. |
| O6.2 | Escalation policy + UI | dashboard | When a checkpoint goes unanswered for N hours, escalate to a configured fallback reviewer. Configurable chain. |
| O6.3 | Manual-takeover UX | dashboard + Linear/GitHub comments | A failed task surfaces a "take this over manually" button that hands the worktree off (or links to the repo + branch); orchestrator gracefully exits. |
| O6.4 | Notifications (in-app + email + Slack webhook) | `cloud/server/src/notifications/` | In-app + email at minimum; one-way Slack webhook for workspace events. PagerDuty/Discord/Teams deferred to v2. |
| O6.5 | Support runbooks | `docs/orchestrator/support/{onboarding,common-failures,billing-questions}.md` | Internal-facing first, customer-facing later. |
| O6.6 | Status page | hosted (statuspage.io or equivalent) | Public uptime + incident history. |
| O6.7 | First-line on-call rotation | not a code deliverable | Internal: 1 engineer on rotation per week for the 10–20 customer fleet. |
| O6.8 | Customer feedback channel | shared Linear/Slack with each design partner | Weekly check-in; structured bug-report template. |
| O6.9 | Per-craw release notes + changelog | `docs/orchestrator/craws/<id>/CHANGELOG.md` | When a craw bumps version, customers see what changed before they accept the bump. |
| O6.10 | Regression alert pipeline | `cloud/server/src/quality/regression.ts` | Per-craw success-rate monitoring; alert at 2σ drop. Uses existing cost-manager pattern. |

**Reuse:** existing Linear/GitHub integrations; existing JSONL substrate for changelogs; existing notification primitives.

**New:** the onboarding flow; escalation logic; manual-takeover handoff; Slack-webhook adapter; on-call rotation tooling; the customer-feedback intake.

**Slip impact:** the Stage 1 endgame in GRAND_PLAN §3 (specifically the LLM Wiki + Obsidian sync from LATER week 15, and the cron recipes from LATER week 16) holds because they're parallel-track work. The Stage 2 prep work (LATER² week 28) compresses into O7.

**Exit gate:** 10–20 paying teams. Mean ticket-to-merged-PR < 2 hours for boring & bounded tasks. P95 < 8 hours. Net-promoter score ≥ 30 from design partners. Monthly recurring revenue ≥ $10k.

---

## O7 — public beta + customer-authored craws v1 (weeks 37–44)

**Goal:** Open the orchestrator to public signup. Customer-authored craws ship via the fork-from-template path. Begin GRAND_PLAN Stage 2 work in earnest.

**Deliverables:**

| # | Deliverable | Files / location | Notes |
|---|---|---|---|
| O7.1 | Public signup + onboarding | `cloud/platform` | Open the signup flow that was design-partner-only; pricing page live; sandbox-repo onboarding works for cold leads. |
| O7.2 | Customer-authored craw forking | `cloud/platform/src/pages/CrawEditor.tsx` + `cli/orgctl/src/craws/templates/` | Customer can fork any curated craw, edit the system prompt + skill list + policy, save as a private craw scoped to their workspace. |
| O7.3 | Craw authoring docs | `docs/orchestrator/authoring-craws/{introduction,system-prompt,skills,testing,deployment}.md` | Five-page docs set. Bench fixtures + a `craw test` CLI. |
| O7.4 | Per-workspace craw registry | extends O5.7 | Private craws listed alongside curated craws in the workspace; clearly badged as "yours." |
| O7.5 | Marketing site update | `web/` | Public positioning. Pricing. Customer logos (with permission). |
| O7.6 | Begin GRAND_PLAN Stage 2 prep | per [`GRAND_PLAN.md`](./GRAND_PLAN.md) §4 | Hosted RAG spike, RL data-export pipeline (was LATER² week 28). |
| O7.7 | Post-mortem of the closed beta | `docs/orchestrator/post-mortems/closed-beta-v1.md` | What worked. What didn't. What we'd cut in v2. |

**Reuse:** all of the above. By O7 the orchestrator is fully built; this stage is mostly external-facing polish + the beginning of next-stage work.

**New:** the public signup; the craw authoring surfaces; the customer-authored craws v1 scope; marketing site update.

**Slip impact:** Stage 2 begins at week 37 of this plan instead of month 9 (week 36) per GRAND_PLAN §3.0 sequencing. Effectively on-track, +1 week.

**Exit gate:** public signup live; ≥3 customers have authored their own craws; ≥30 paying teams. ARR ≥ $50k. Begin hosted-RAG and RL data-export spike work for Stage 2.

---

## Cumulative slip impact on the existing ROADMAP

The orchestrator pulls forward several items that were originally LATER² or Stage 2. To be honest about what slips:

**Stays on schedule:**

- NOW weeks 1–5 (Linear-grade board) — unchanged; this is the substrate the orchestrator depends on.
- NEXT week 6 (RAG indexing), week 7 (token-discipline optimizers), week 8 (founder-dash polish) — independent work; held by the existing lens + dash team.
- LATER week 11–12 (skill backbone) — held; the orchestrator's curated craws use the skill backbone format.
- LATER week 15 (LLM Wiki + Obsidian sync) — held; local-first work, not on the orchestrator path.
- LATER week 16 (cron recipes + dynamic model switching) — held; the cost-manager work feeds directly into the orchestrator's budget enforcement.
- PARALLEL TRACK weeks 6–10 (marketing site + authed web dashboard tunnel) — held; complementary to the orchestrator.
- PARALLEL TRACK weeks 11–13 (collaboration: presence, comments, CRDT drawer) — held.

**Slips:**

- LATER week 13 (local Codespaces) — slips ~3 weeks; the orchestrator's worktree-isolation work (O0.5) covers part of the surface but not the full Codespaces experience. Code-OSS Codespaces work can resume after O3.
- LATER week 14 (Crawfish IDE v0.1) — slips ~4 weeks. The IDE is on the local-first stack but reuses dashboard components that the orchestrator team is also editing.
- LATER² weeks 17–18 (native code review P6 start) — slips ~4 weeks because the parallel-track engineer's bandwidth is on O3/O4 dashboard + PR-bot.
- LATER² weeks 19–20 (test-generator + visual-auditor) — accelerates; these ship as orchestrator craws in O3.
- LATER² weeks 21–22 (agent-web proxy MVP) — slips ~4 weeks because of the same bandwidth reallocation.
- LATER² weeks 23–24 (CRDT + git-worktree isolation) — split: worktree isolation pulls forward to O0.5; CRDT layer holds at original timing.
- LATER² weeks 25–27 (communication-graph features) — slips ~6 weeks.
- LATER² week 28 (Stage 2 prep) — folds into O7.6.
- PARALLEL TRACK weeks 14–16 (team mode + Stripe billing) — *consumed* by O5; this is the cleanest pull-forward.

**Pulls forward from Stage 2:**

- §4.1 hosted everything — partial; orchestrator hosts itself starting O0, but org-fs and team dashboard stay local-first.
- §4.4 invite employees / multi-user — full; the orchestrator MVP requires multi-user from O5.
- §4.6 24/7 issue tracking — partial; auto-classifier + auto-pickup ship in O2, but always-on customer-facing handoff stays Stage 2.
- §4.10 pricing — full; Stage 2's hybrid pricing model lands in O5.

**Pulls forward from Stage 3 (§5):**

- Basic RBAC ships in O5. Full RBAC + customizable per-resource permissions stays Stage 3.
- Audit log shipped in O5 (basic projection). SOC 2-shaped audit export, retention policies, attestation primitives stay Stage 3.

---

## Resourcing assumptions

This plan assumes two full-time engineers on the orchestrator (one backend + workflow, one frontend + dashboard + cloud-platform), plus the existing lens + dash + ui team continuing on the local-first stack. With this resourcing, the 44-week plan above is plausible. With one engineer on the orchestrator, multiply by ~1.8 (~78 weeks). With three engineers, the plan compresses to ~33 weeks but requires a tight coordination model (the existing CLAUDE.md ownership rules become load-bearing).

The "hire the second orchestrator engineer" gate is O0. If only one engineer is available, O1 is the right stage to invest in the hire — the workload bifurcates cleanly into "workflow + queue + worker" (backend) and "dashboard + PR loop + classifier UI" (frontend) starting at that point.

A product designer is needed from O3 onward (the live execution dashboard is the customer-facing differentiator, and the dashboard + onboarding work in O6 are the conversion gate). A part-time product designer is sufficient through O7.

---

## Open questions before any code

These need to resolve before O0 closes, not as O0 work:

1. **Where is the cloud-server orchestrator hosted?** AWS (matches existing infra assumption), GCP, or Fly.io for cheap multi-region. The choice constrains the worker isolation model.
2. **What's the per-task token-cost ceiling that makes the unit economics work?** Without an answer, the per-seat usage allowance in O5 is unanchored. Build a spreadsheet model from the spike's measured per-task cost (O0.6 spike output).
3. **Does the orchestrator share the same domain (crawfish.dev) as the local-first product, or a separate one (e.g., orchestrator.crawfish.dev)?** Brand decision; affects marketing site work.
4. **Is the GitHub App a single app across all customers, or per-customer?** A single app simplifies operations but caps installs per the GitHub App tier; per-customer apps add ops burden but no scale ceiling.
5. **What's the policy for craw authorship while we're still curated-only (O0–O6)?** Are external contributors invited to submit craws before customer-authored (O7) ships? Decision affects marketing positioning.
6. **What constitutes "merge approval" for a craw PR in a customer's workspace?** Does GitHub's branch protection enforce this on its own, or does the orchestrator add a layer? Most teams will want both belts.

---

*Owner: lead. Edits land through PR per [CLAUDE.md](../../CLAUDE.md). Last updated: 2026-05-22.*
