# Crawfish Orchestrator — v1 one-pager

> **Hosted agent orchestration for mid-market engineering organizations.**
> Linear/GitHub Issues in → multi-craw collaboration → CI-verified PR out → checkpointed human review.

This is the v1 wedge product. It is not a pivot away from the [Grand Plan](./GRAND_PLAN.md); it is the way Stage 1's bottoms-up motion converts to mid-market revenue without waiting for the Stage 2 plan to fully land. Roughly 70% of the substrate already exists in the v0.3 codebase (board, triage, capability routing, criteria, budgets, GitHub mirror, runtime adapters, dash, partial cloud auth). This doc reframes that substrate as a product that an engineering manager at a 30-person company buys, not just a tool that a founder installs.

The companion docs are [`GRAND_PLAN.md`](./GRAND_PLAN.md) (north-star vision — kept intact) and [`../../ROADMAP.md`](../../ROADMAP.md) (active build schedule — orchestrator stages land alongside the existing NOW / NEXT slices, see [`./ORCHESTRATOR-STAGES.md`](./ORCHESTRATOR-STAGES.md) for the sequencing).

---

## What it is, in one paragraph

A cloud-hosted service that connects to a customer's Linear or GitHub Issues, classifies which inbound tickets are eligible for autonomous handling, dispatches each one to a curated team of "craws" (specialist agent containers — implementer + tester + reviewer) running in isolated worktrees, verifies the result against CI, and produces a checkpoint-gated pull request. The human reviewer approves the plan and the final merge; the system handles everything in between, including a budget-capped loop that addresses PR comments without infinite back-and-forth. Pricing is hybrid seat-plus-usage. Engineering and adjacent functions (PM, QA) see and gate the work; the eng leader sees the cost line.

## ICP

Mid-market engineering startups, 10–50 engineers. Linear or GitHub Projects as the issue tracker. Postgres-scale CI already in place. Eng leader (VPE or founding eng) is the buyer; an eng manager or platform engineer is the installer; ICs are the daily users who review craw-authored PRs in their normal workflow. Adjacent functions (PM, QA) participate by creating eligible tickets and reading the rollup dashboard. Stage 1's solo-founder ICP from GRAND_PLAN is *not* abandoned — the local desktop dash + free tier remain that path. The orchestrator is the paid-tier wedge.

## Wedge task

The product nails a narrow shape first: **boring & bounded** tickets that are well-defined, low-ambiguity, and historically eat IC time. Specifically: dependency bumps with passing tests, test backfill for un-covered modules, lint and dead-code cleanup, type-annotation backfill, low-risk dependency CVE patches. These have low blast radius, machine-verifiable outcomes, and high IC opportunity cost. The multi-craw "team shape" stays mostly internal at this stage (implementer + tester + reviewer behind a single PR); the live execution dashboard exposes it as marketing scaffolding for what the v1.5 expansion to small-feature work will showcase.

## Architecture (reuses v0.3 substrate)

- **Intake** — Linear webhook + GitHub Issues poll (extends existing `cli/orgctl/src/inbound/github-issues.ts` + `notion-pages.ts` pattern). A new auto-classification step (Haiku-class LLM) decides eligibility per inbound; the existing heuristic `triage_normalize` shapes labels and priority.
- **Routing** — Existing capability-matched router (`cli/projectctl/src/router.ts`, 70% success-rate threshold) selects which craw set handles the task. Manual mapping (label → craw) overrides the router.
- **Queue + workers** — New. A durable workflow engine (Temporal, Inngest, or Restate — chosen by a separate ADR; *not* BullMQ, see [stages doc](./ORCHESTRATOR-STAGES.md) §1.2) holds tasks across multi-hour runs, handles checkpoints, resumes from failure. Workers spawn isolated worktrees under `~/.crawfish/worktrees/<task-id>/` (the §3.3 worktree pattern, pulled forward from Stage 1 LATER² weeks 23–24).
- **Execution** — Existing runtime adapters (`claude-code`, `claude-api`, `openai-api`, `codex`, `openclaw`) dispatch the actual agent runs. Multi-craw collaboration is internal (impl craw + test craw + review craw) writing to a shared worktree.
- **Verification** — CI as ground truth. The customer's existing CI pipeline (GitHub Actions, CircleCI, etc.) gates auto-promotion; on green, the PR moves to the human checkpoint. The agent-CI features in GRAND_PLAN §3.9 (test-gen agent, visual-auditor) ship as part of this layer.
- **Checkpoints** — Two gates: plan submitted (human approves the craw's proposed approach before code is written) and pre-merge (human approves the final PR). Both gates emit structured events to the existing board JSONL log; auto-escalate (existing budget-breach mechanism) on idle.
- **PR comment loop** — Budgeted auto-respond. Mention-to-resume by default; opt-in to auto-respond-on-every-comment with a per-PR token + revision cap.
- **Dashboard** — Live team-execution view rendered in `desktop/dash` (existing Tauri shell) and `cloud/platform` (existing Clerk-authed SPA). Streams subprocess telemetry per craw; replays from the same JSONL substrate the diagnoses engine reads.
- **Billing** — Stripe Connect on `cloud/server` (extends existing Prisma models). Seat tier on humans only (agents free, per Linear-for-Agents convention adopted in GRAND_PLAN §3.2); usage metering on token consumption above a per-seat allowance.
- **Org primitives** — RBAC + audit log + SSO eventually. The existing `User` / `Org` / `OrgMember` / `Invite` Prisma models cover the basics; RBAC is new work.

## In v1 / out of v1

**In:** auto-classification for eligibility, manual label→craw routing, curated library of 8–12 craws (impl, tester, reviewer, doc, dep-bumper, lint-cleaner, type-backfiller, CVE-patcher), cloud-hosted execution, multi-craw collab (internal), CI-as-truth verification, two human checkpoints (plan + merge), budgeted PR-comment loop, live execution dashboard, hybrid seat+usage pricing, basic RBAC, audit log, Linear + GitHub Issues + GitHub PR integration, in-app + email notifications, eval harness for the classifier.

**Out of v1, on the roadmap:** customer-authored craws (SDK + docs), marketplace, AI-generated craws, refactor-class tasks, autonomous features (anything beyond boring & bounded), org filesystem + librarian brain (GRAND_PLAN §3.3 / §3.3.1 — stays in roadmap), IDE (§3.5), local Codespaces (§3.8), Pilot Protocol (§3.7 Track B), full methodology packs (§3.15), SSO/SAML (§5), on-prem.

**Deliberately deferred forever in this wedge:** Slack-as-execution-surface (no chat-driven agent dispatch in v1; conversational PM tool is Stage 2+); per-PR pricing (creates perverse incentives — see stages doc §1.5); fully autonomous PRs without checkpoints (the failure mode is worse than the savings).

## Success metrics (12-month)

- **20** mid-market eng teams paying, average 12 seats.
- **≥60%** of auto-classified eligible tasks complete end-to-end without escalation.
- **≤10%** of merged PRs require a post-merge fix attributable to the craw.
- **<15 min** P50 ticket-to-draft-PR latency on the wedge task set.
- **2x** IC throughput on the wedge task class (measured as tickets-closed-per-eng-week against a 4-week pre-install baseline).
- Customer's amortized cost per merged craw PR **< 30%** of the loaded cost of the equivalent IC hour.

## Risks (top six)

1. **Auto-classification silent misroutes.** Worst case: agent picks up a ticket that needed senior eng judgment, ships a confidently-wrong PR, costs trust. Mitigation: eval harness shipped with v1; per-customer ground-truth labeling baked into onboarding; default to label-only when classifier confidence is below threshold.
2. **PR-comment loop infinite recursion or reviewer fights.** Mitigation: explicit state machine (`addressing` / `awaiting-feedback` / `halted-need-human` / `merged`), hard caps on revisions + tokens, halt-on-conflict-with-reviewer heuristic.
3. **Wedge task set has low team-shape payoff.** Dep bumps don't need three craws. The differentiation narrative may feel hollow in the v1 dashboard. Mitigation: position v1 as "high-trust autonomous PRs at predictable cost"; surface team shape in marketing for v1.5 expansion to small features.
4. **Mid-market won't switch issue trackers.** Mitigation: never ask them to. Orchestrator is *layer on top of* Linear/GitHub Issues, not a replacement. PM-tool ambition from GRAND_PLAN deferred indefinitely or pursued only if v1 earns the right.
5. **Linear/Jira/GitHub ship competing native AI features.** They will. The defense is multi-runtime + cross-tracker + the substrate that already exists in v0.3 (board, criteria, budgets, diagnoses, optimizers, library of curated craws) which is structurally orthogonal to what Linear/Jira can ship as a feature.
6. **Compounding token cost on a per-customer basis.** A runaway craw on a bad ticket can burn $50 of API. Mitigation: per-task budget cap; per-org daily budget; cost-manager agent (GRAND_PLAN §3.11) on by default in every install.

## What this preserves from GRAND_PLAN

The full §1 north-star ("OS for agent-native companies + agent filesystem as moat") is unchanged as the 24-month destination. The orchestrator is the path that funds it. Specifically:

- **Org-fs + librarian (§3.3 / §3.3.1):** deferred from v1 but remains the long-range moat. The orchestrator earns the revenue that justifies the R&D.
- **Multi-runtime (§3.8 + §6 strategic posture):** preserved. v1 ships with the existing four adapters; CMA + Ruflo + Goose + Cursor adapters land in v1.5–v2.
- **Local-first as principle:** preserved for the dev tools. The cloud orchestrator is the *first* hosted product, but the desktop dash and lens remain local-first and free, matching the §3-Stage-1 commitment.
- **Tokens as unit of account:** preserved. Hybrid pricing exposes tokens as the metered unit above the seat allowance.
- **Diagnoses engine + optimizers (§3.11):** preserved and central — they're the cost-discipline pillar that makes the per-task economics work.
- **Anti-goal: no auto-installation, no per-execution paywall on community craws, no enterprise paywalling of compliance.** All carry forward.

## What this changes from GRAND_PLAN

- **ICP for the paid tier** shifts from "small CEO + manager + platform eng" (Tier 2 in GRAND_PLAN) to the same set, but with the engineering manager as the *primary* buyer rather than the adoption multiplier. The reframe matters for the sales motion: founder-led PLG to free local-first; sales-assisted PLG to mid-market paid orchestrator.
- **Hosted SaaS pulled forward** from Stage 2 to v1, but scoped narrowly to the orchestrator. The org filesystem and analytics surfaces stay local-first.
- **Pricing introduced in v1** (hybrid seat+usage) instead of Stage 2. Free local-first dash remains. The orchestrator is the first metered surface.
- **Multi-user/RBAC pulled forward** from Stage 3 (§5) basic-RBAC scope, because mid-market won't buy without it.

---

*Owner: lead. Edits land through PR per [CLAUDE.md](../../CLAUDE.md) cross-team narrative document rules. Last updated: 2026-05-22.*
