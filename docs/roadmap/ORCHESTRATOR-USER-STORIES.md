# Crawfish Orchestrator — MVP user stories

Companion to [`ORCHESTRATOR-ONEPAGER.md`](./ORCHESTRATOR-ONEPAGER.md). Every story below is in scope for v1 unless tagged `[v1.5]` or `[deferred]`. Acceptance criteria are included where they sharpen scope; omitted when they're obvious.

**Personas:**

- **VPE** — VP / head of engineering (buyer, sets policy, reads cost rollup)
- **EM** — Engineering manager (installer, day-to-day admin, gates PRs)
- **IC** — Individual contributor developer (reviews craw-authored PRs, files tickets)
- **PM** — Product manager (writes tickets, reads team-velocity rollup)
- **QA** — QA engineer (reviews test diffs, files bugs)
- **PLAT** — Platform / DevOps engineer (configures integrations, RBAC, CI)
- **FIN** — Finance / billing admin (manages subscription, seats, budget alerts)
- **SEC** — Security / compliance contact (reviews audit log, sets allowlists)

A story tagged `[VPE, EM]` is one whose primary value accrues to either persona; pick the most senior reader for prioritization conflicts.

---

## 1 · Onboarding & account setup

1.1 **[VPE]** Sign up via GitHub OAuth and create a workspace in under 90 seconds. *AC: GitHub OAuth, workspace name, billing email → land in the empty dashboard with a "connect your first repo" CTA.*

1.2 **[EM]** Invite teammates by email or by domain auto-match, with a role chosen at invite time (admin, member, viewer). *AC: invitee receives email with magic-link accept; on accept they land in the workspace; OrgMember.role persisted (existing Prisma model).*

1.3 **[PLAT]** Connect Linear via OAuth and select which teams / projects are eligible. *AC: per-team toggle; webhook subscriptions registered; selection persisted.*

1.4 **[PLAT]** Connect GitHub via the existing GitHub App OAuth (already in `cloud/server`); select which repos are eligible for craw activity. *AC: per-repo toggle; PR-write scope confirmed; repos with PR-write disabled appear read-only.*

1.5 **[PLAT]** Connect the CI provider (GitHub Actions detected automatically from connected repos; CircleCI / GitLab CI as v1.5). *AC: orchestrator can read CI status on a PR via the provider's API; failures fetch logs.*

1.6 **[VPE]** Land in a 4-step empty-state walkthrough that ends with a real "boring & bounded" PR opened against a sandbox repo within 10 minutes. *AC: walkthrough uses the customer's own GitHub account; sandbox repo is forked from a Crawfish-provided template; PR is real and merges with one click.*

1.7 **[EM]** Convert a personal workspace to a team workspace and re-route billing to the team admin. *AC: irreversible action; confirms migration of existing PRs to team ownership.*

1.8 **[deferred → v2]** SSO / SAML / OIDC.

---

## 2 · Craw library & configuration

2.1 **[EM]** Browse the curated craw library (8–12 craws at launch) with name, description, what tasks it handles, what languages it supports, and a published benchmark per craw. *AC: each craw card shows: success rate on Crawfish's reference bench, median tokens per task, median latency, last update.*

2.2 **[EM]** Install a craw to the workspace with a single click; uninstall just as easily. *AC: install is idempotent; uninstall doesn't delete historical run data.*

2.3 **[EM]** Pin a craw to a specific version; receive notifications when a newer version is available and review the changelog before bumping. *AC: version is per-workspace, not per-repo; rollback to the previous version available for 30 days.*

2.4 **[EM]** Define routing rules: label `dep-bump` → `dep-bumper-craw v3`; label `test-backfill` → `test-craw v2`. *AC: rules evaluated in order; first match wins; fallback to "no eligible craw" if no rule matches.*

2.5 **[EM]** Restrict a craw to specific repos (e.g., the lint-cleaner runs only on the marketing-site repo). *AC: per-craw allow/deny list; deny takes precedence.*

2.6 **[VPE]** See the full list of craws active across all repos in one screen, with the version each repo is pinned to. *AC: drift indicator if two repos pin different versions of the same craw.*

2.7 **[v1.5]** **[IC]** Fork a curated craw and customize its system prompt + skill set per the customer-authored path.

2.8 **[deferred]** Submit a craw to a public marketplace.

---

## 3 · Issue intake & auto-classification

3.1 **[PM]** When I create a Linear ticket, the orchestrator reads it within 60 seconds and decides whether it's craw-eligible. *AC: webhook latency < 10s; classifier latency < 20s; eligibility decision written to the ticket as a Linear comment + a label.*

3.2 **[EM]** Configure the eligibility classifier per-workspace: which labels imply yes/no, what description shape implies eligibility, what the confidence threshold is. *AC: threshold is a number 0.0–1.0; default 0.7; below threshold = "needs human review" Linear label added.*

3.3 **[IC]** Override the classifier on any individual ticket — force-eligible or force-ineligible — and have my override persist. *AC: manual override is logged with the IC's user id; future runs respect it.*

3.4 **[PM]** When the classifier marks a ticket eligible, the ticket gets a "Craw will attempt this" comment with the chosen craw, the proposed plan, and a "decline" button I can click. *AC: decline halts the run before any code is written; one click; reason field optional.*

3.5 **[PLAT]** See the classifier's confidence distribution over the last 7 days, with explicit calls-out of borderline calls (0.6–0.8 confidence). *AC: histogram + sample list of borderline tickets; click-through to the ticket.*

3.6 **[EM]** Pull GitHub Issues on a 5-minute schedule for repos where webhooks aren't available, with the same classifier flow. *AC: dedup against already-ingested issues; respect rate limits.*

3.7 **[EM]** Configure a label allowlist as the *only* signal for eligibility (skip auto-classification entirely). *AC: when allowlist mode is on, classifier never runs; cost goes to zero per ticket; eligibility is deterministic.*

3.8 **[QA, EM]** Re-run the classifier on a closed/old ticket on demand. *AC: useful when the classifier is updated and the team wants to backfill eligibility on a backlog.*

---

## 4 · Plan checkpoint (gate 1)

4.1 **[IC]** Before any code is written, the orchestrator posts the craw's proposed plan as a comment on the ticket and waits for human approval. *AC: plan is a markdown comment with: what files will change, which tests will run, expected diff size, estimated token cost; status changes to "awaiting plan approval."*

4.2 **[IC]** Approve the plan with a single emoji/reaction or a click in the dashboard. *AC: 👍 reaction in Linear or the "approve" button in the dashboard both work; logged with actor.*

4.3 **[IC]** Reject the plan with a one-line reason; the craw halts and the ticket returns to the backlog. *AC: rejection reason posted as a comment; ticket re-classifiable on next pass.*

4.4 **[IC]** Edit the plan inline (e.g., "also touch `src/billing.ts`") and re-approve. *AC: craw re-runs against the edited plan; original plan archived.*

4.5 **[EM]** Configure auto-approval for specific labels (e.g., `dep-bump` auto-approves the plan because the action is mechanical). *AC: auto-approval logs an "auto-approved" event; reviewer still has the merge gate.*

4.6 **[VPE]** Set a workspace-wide policy: "all plans require human approval" OR "plans auto-approve unless flagged risky." *AC: a craw can flag its own plan as risky (large diff, sensitive file path); risky always requires human review regardless of policy.*

4.7 **[EM]** Receive an in-app + email notification when a plan is awaiting my approval for more than the SLA window (default 4h). *AC: SLA configurable per workspace; escalation to backup reviewer after a second timeout.*

---

## 5 · Orchestration & execution

5.1 **[PLAT]** Tasks queued for execution survive a worker crash or restart without rerunning the side effects (PR creation, comments) twice. *AC: durable workflow engine (Temporal-class); idempotency keys on every external side-effect call.*

5.2 **[PLAT]** Concurrent task limit per workspace and per repo (default: 5 workspace-wide, 1 per repo). *AC: tasks beyond the limit wait in queue with a visible "queued, position N" status.*

5.3 **[EM]** Cancel an in-flight task; the worker stops within 30s and posts a "cancelled by user" comment on the ticket. *AC: worktree is cleaned up; partial PR (if drafted) is closed; token cost up to cancel is still billed.*

5.4 **[PLAT]** Each task runs in an isolated git worktree under the workspace's hosted runner; no two tasks share a checkout. *AC: worktree creation < 5s; cleanup on completion or cancel.*

5.5 **[EM]** Re-run a failed task with one click; the re-run inherits the original plan and budget but starts a fresh worktree. *AC: re-run count visible on the ticket; auto-disable re-run after 3 attempts without manual override.*

5.6 **[VPE]** Set a per-task budget cap (default $5) and a per-org daily cap (default $200); exceeded tasks pause and require human approval to continue. *AC: budgets enforced at token-spend level using existing `budget.ts` / `cost-manager` patterns; pause is reversible in two clicks.*

5.7 **[PLAT]** See the live queue (tasks pending, running, paused, failed) with filters by repo, craw, and age. *AC: filter persistence in URL; auto-refresh.*

5.8 **[IC]** Tasks that idle without progress for > N minutes (no LLM activity, no tool call) auto-halt with a "stuck" label. *AC: N is configurable per craw; default 5 minutes; halt posts the last log entry as a debugging hint.*

---

## 6 · Live team-execution dashboard

6.1 **[IC, EM]** Open a running task and see, in real time, which craw is executing what step, with a streaming log of tool calls and reasoning. *AC: SSE stream; one row per craw in the multi-craw team; collapsed by default, expandable per craw.*

6.2 **[EM]** See the multi-craw "team" view per task: implementer craw + tester craw + reviewer craw, with their parallel progress and which one is currently active. *AC: visible even for v1's mostly-single-craw runs (renders as "1 of 1" rather than 0); pulls forward for v1.5 multi-craw tasks.*

6.3 **[IC]** Replay a completed task end-to-end — every tool call, every diff, every checkpoint — for debugging. *AC: same UI as live view; reads from JSONL transcript; uses existing lens replay primitives.*

6.4 **[EM]** Filter the dashboard by repo, craw, status, or active reviewer. *AC: filters persist in URL.*

6.5 **[VPE]** See an org-wide rollup: how many tasks ran today, how many are queued, how many are stuck. *AC: counts refresh on a 30s timer; click-through to the filtered list.*

6.6 **[IC]** Click on a craw's current step to see why that step was chosen (planning agent's rationale + which past trajectories it consulted). *AC: trajectory hint uses GRAND_PLAN §3.11 cache mechanism; for v1 may be empty if no historical data exists yet.*

6.7 **[PLAT]** Kill any in-flight task from the dashboard with a confirmation modal. *AC: same effect as 5.3 but reachable from any view.*

---

## 7 · CI verification

7.1 **[IC]** When a craw drafts a PR, the customer's existing CI runs against it automatically (GitHub Actions). *AC: PR draft state until CI completes; orchestrator polls CI status.*

7.2 **[EM]** Configure which CI jobs are required (test suite, lint, type-check, security scan); only listed jobs gate the human checkpoint. *AC: required job list editable per repo; missing required job = block.*

7.3 **[IC]** When CI fails, the orchestrator reads the failure log and attempts to fix it (up to N revisions, default 3). *AC: each fix attempt logs as an additional commit; counter visible on the PR.*

7.4 **[EM]** After N failed fix attempts, the task halts and a human is notified with the full failure log + the craw's last attempted fix. *AC: PR stays as draft; ticket labeled `craw-stuck`; notification per §13.*

7.5 **[PLAT]** Configure a regression guard: if CI test count drops on the craw's branch vs. the base, fail the gate. *AC: prevents tests-deleted-to-make-CI-pass class of failure; default on; toggleable per repo.*

7.6 **[PLAT]** Surface the existing test-generator + visual-auditor agents (GRAND_PLAN §3.9) as installable craws that augment any task's CI verification. *AC: optional, off by default; when on, runs as a parallel craw and posts as an additional CI check.*

7.7 **[QA]** When the test-generator craw adds tests, they're marked as agent-authored in the PR description and labeled in the test file's frontmatter. *AC: human reviewer can filter "show me only agent-authored tests."*

---

## 8 · PR submission & merge checkpoint (gate 2)

8.1 **[IC]** When CI passes, the PR is converted from draft to ready-for-review with a structured PR description: what changed, what tests verify it, what was deferred, and the craw's confidence. *AC: description follows a template; review-friendly format; no walls of text.*

8.2 **[EM]** Configure who gets auto-assigned as the reviewer (default: the ticket assignee or owner of the touched files via CODEOWNERS). *AC: respects existing CODEOWNERS; falls back to a configured default reviewer.*

8.3 **[IC]** Review the PR in GitHub exactly as I would a human-authored PR, with no Crawfish-specific UI required. *AC: zero learning curve; the PR is structurally normal.*

8.4 **[IC]** A single GitHub approval merges the PR (when policy permits); the orchestrator does the merge and links the merge commit back to the ticket. *AC: respects branch protection rules; no force-merge.*

8.5 **[VPE]** Require N approvers for craw-authored PRs (configurable per repo; default 1 for boring & bounded labels, 2 for risky). *AC: enforced at the orchestrator level on top of GitHub's own rules.*

8.6 **[EM]** Auto-close the original ticket when the PR merges; post the merge commit + PR link as a Linear comment. *AC: respects existing Linear status-transition rules; uses the GitHub mirror already shipped in `cli/orgctl/src/inbound/github-issues.ts`.*

8.7 **[IC]** Reject the PR with a comment and the craw stops re-engaging; the ticket returns to the backlog. *AC: opposite of auto-respond loop; explicit "halt this craw" path.*

---

## 9 · PR-comment loop (auto-respond with budget)

9.1 **[IC]** When I @-mention `@crawfish-bot` in a PR comment, the craw re-engages to address my feedback. *AC: mention-only is the default mode; bot doesn't react to unmentioned comments.*

9.2 **[EM]** Configure auto-respond mode per repo: `mention-only`, `respond-to-all`, or `off`. *AC: mode is per repo, not per workspace; defaults to mention-only.*

9.3 **[IC]** When the bot re-engages, it posts a "working on it" reply with an estimated cost and ETA. *AC: estimated cost is based on the craw's historical revision cost.*

9.4 **[EM]** Cap the auto-respond loop per PR: max N revisions OR max $M tokens, whichever first; on cap, the bot halts and notifies. *AC: caps editable per repo; defaults: 5 revisions, $10; halt notification uses §13 channels.*

9.5 **[IC]** When the bot detects conflicting feedback across two reviewers, it halts and pings a human instead of guessing which to follow. *AC: detection is a heuristic (semantic similarity check + reviewer count); false negatives are OK; false positives waste tokens.*

9.6 **[IC]** When the bot can't address a comment (out-of-scope, requires architecture decision, ambiguous), it replies with an honest "I can't address this without X" and stops. *AC: explicit fallback path; the bot does not silently give up.*

9.7 **[VPE]** Audit log entry for every bot revision: who asked for it, what was changed, tokens spent. *AC: same audit surface as §14.*

9.8 **[IC]** I can "veto" the bot mid-loop with a comment like `@crawfish-bot halt` and the bot stops within 30s. *AC: keyword commands documented and stable.*

---

## 10 · Analytics & cost dashboards

10.1 **[VPE]** See yesterday's cost by workspace, by repo, by craw, by ticket. *AC: refreshes daily; click-through to specific tickets; exportable as CSV.*

10.2 **[VPE]** See the org's compounding-factor metric (sub-agent tokens / parent-useful tokens) — reuse GRAND_PLAN §3.6 framing. *AC: weekly trend; top three offending tickets called out.*

10.3 **[EM]** See per-craw stats: success rate, median tokens per task, median latency, count of tasks attempted. *AC: 30-day rolling window; reuses existing `cli/projectctl/src/stats.ts` agent-stats engine.*

10.4 **[EM]** See per-engineer rollup: which ICs are reviewing the most craw PRs, which are getting most of their tickets handled by craws, which are blocking on craw failures. *AC: aggregates only; no individual transcript surfacing without explicit policy (GRAND_PLAN §4.5 privacy contract).*

10.5 **[VPE]** See an org-wide ROI proxy: count of craw-merged PRs × estimated time saved (configurable per label) − craw cost = net savings. *AC: estimated time is editable per label; default values shipped; user can override.*

10.6 **[FIN]** Export the month's billing data (tokens by task, by user, by craw) as CSV for finance reconciliation. *AC: includes timestamps, repo, ticket id, craw id, token type breakdown.*

10.7 **[PM]** See per-ticket cycle time (created → eligible → merged) for craw-handled tickets vs. human-handled baseline. *AC: PM owns the comparison; orchestrator surfaces it but doesn't make a value judgment.*

10.8 **[v1.5]** **[VPE]** Dashboard widget: "if this trajectory continues, your monthly bill will be $X." Forecast accuracy improves over 30 days.

---

## 11 · Failure handling & escalation

11.1 **[IC]** When a task fails, the failure surfaces in three places: the ticket (as a comment), the dashboard (as a `stuck` filter), and (optionally) email/Slack to the assignee. *AC: same failure record; one source of truth.*

11.2 **[EM]** Categorize failures: `plan-rejected`, `ci-failed-after-fixes`, `budget-exceeded`, `craw-error`, `timeout`, `cancelled-by-user`, `policy-blocked`. *AC: each category surfaced in dashboard filters; trend lines per category.*

11.3 **[IC]** Take over a failed task manually: check out the worktree, fix the issue locally, push, and merge as a normal human PR. *AC: orchestrator detects the human-authored push and gracefully exits its own loop; ticket links the human PR.*

11.4 **[EM]** Auto-disable a craw when its failure rate spikes (e.g., >50% failures in last 24h on >5 attempts). *AC: orchestrator pauses new dispatches to that craw and pings the EM; manual re-enable.*

11.5 **[VPE]** Receive a weekly digest of which craws had the highest failure rate this week and what category dominated. *AC: digest is opt-in; default off; surfaces in email + dashboard.*

11.6 **[IC]** When a task fails due to a missing capability (e.g., needs a tool the craw doesn't have), the failure message tells me what craw or skill would be needed instead. *AC: failure message includes a recommendation; opens the relevant marketplace entry.*

---

## 12 · Billing & seats

12.1 **[FIN]** Subscribe with a credit card or invoice; per-seat for humans (agents are free per GRAND_PLAN §3.2 Linear convention). *AC: Stripe Connect on `cloud/server`; seat pricing displayed at signup; usage metering disclosed.*

12.2 **[FIN]** See current seat usage vs. plan, with overage warnings before they hit the bill. *AC: warning at 80% and 100% of seats.*

12.3 **[FIN]** Configure the usage allowance per seat (e.g., 100k tokens per seat per month); above this, usage is metered at a per-token rate. *AC: clear rate disclosure; rolls over no; resets monthly.*

12.4 **[FIN]** Set a hard monthly budget cap; when hit, the orchestrator stops dispatching new tasks and emails the admin. *AC: in-flight tasks complete; new tasks queue with "paused for budget" status.*

12.5 **[VPE]** See projected end-of-month cost based on the first N days' burn. *AC: linear projection; updates daily.*

12.6 **[EM]** Add or remove human seats from the org; pro-rate the change on the next invoice. *AC: standard Stripe behavior; no surprise.*

12.7 **[FIN]** Download invoices as PDF; receive each invoice as an email attachment. *AC: invoices comply with standard formats; tax info supported per Stripe.*

12.8 **[v1.5]** **[FIN]** Per-team budget envelopes within the same workspace.

---

## 13 · Notifications

13.1 **[IC]** Receive an in-app + email notification when (a) a plan needs my approval, (b) a PR is ready for my review, (c) a craw is stuck on a ticket I own. *AC: notification settings per-event-type; unsubscribe per type.*

13.2 **[EM]** Configure a digest mode: receive a daily summary instead of individual notifications. *AC: digest is per-user; orchestrator-wide events (e.g., budget cap hit) still send immediately.*

13.3 **[EM]** Mute notifications for a specific repo or ticket. *AC: mute lifts after a configurable window or manually.*

13.4 **[PLAT]** Configure a Slack webhook to receive workspace events (PRs opened, tasks failed, budget hit). *AC: Slack is one-way notification only in v1; no inbound chat to the bot.*

13.5 **[FIN]** Receive a billing-event notification (overage, cap hit, invoice paid) directly. *AC: routes to billing email, not to general user notification stream.*

13.6 **[VPE]** Configure escalation: if a plan-approval notification goes unanswered for 24h, ping a fallback reviewer. *AC: fallback chain configurable per workspace.*

13.7 **[deferred → v2]** Discord, Microsoft Teams, PagerDuty integrations.

---

## 14 · Admin, audit & policy

14.1 **[SEC]** Every governance-relevant action is written to an immutable audit log: member added/removed, role changed, craw installed, policy edited, budget changed, manual task takeover. *AC: log is append-only; exportable as JSONL; uses existing JSONL substrate.*

14.2 **[SEC]** Filter the audit log by actor, action type, time window, and resource. *AC: 90-day retention default; configurable per workspace; older data exported and purged.*

14.3 **[PLAT]** RBAC: assign roles (admin, member, viewer); each role has a documented permission matrix. *AC: matrix shipped as docs; admin can override per-resource.*

14.4 **[VPE]** Set a kill-switch policy: pause all craw activity workspace-wide. *AC: pause is reversible; in-flight tasks complete; new dispatches queue.*

14.5 **[SEC]** Configure a per-craw allow/deny list of file paths (e.g., the lint-craw cannot touch `/secrets/` or `/migrations/`). *AC: enforced at the worktree mount level; violations block before commit.*

14.6 **[SEC]** Configure a per-craw allow list of network egress destinations (default: GitHub + LLM provider only). *AC: matches GRAND_PLAN §3.16 defence-toolcall pattern.*

14.7 **[VPE]** Configure a policy bundle per workspace: required reviewer count, allowed labels, max diff size for auto-approval. *AC: policy bundle is JSON; editable in dashboard; versioned with audit trail.*

14.8 **[deferred → v2]** SSO, SAML, OIDC, custom retention policies, data residency.

---

## 15 · Eval & quality

15.1 **[EM]** See the auto-classifier's accuracy on the last 30 days of decisions (precision, recall, false-positive rate). *AC: dashboard widget; click-through to misclassified tickets.*

15.2 **[EM]** Label individual classifier decisions as correct/incorrect to improve the classifier over time. *AC: labels feed a per-workspace eval set; classifier re-evaluated weekly.*

15.3 **[PLAT]** See per-craw benchmark scores published by Crawfish — what bench the craw was tested against, what score it got, what the failure cases looked like. *AC: bench data is public; per-craw page links to bench fixtures.*

15.4 **[EM]** Run a craw against a custom benchmark suite (the customer's own tickets, replayed in dry-run mode). *AC: dry-run mode opens no PRs, posts no comments; produces a report.*

15.5 **[VPE]** Receive a regression alert when a craw's success rate drops 2σ below its baseline. *AC: same alerting mechanism as GRAND_PLAN §3.11 cost-manager.*

15.6 **[v1.5]** **[EM]** Tournament mode: run two craws on the same task and pick the winner by metric. (Token-expensive; gated behind a flag.)

---

## 16 · Integrations & edge cases

16.1 **[PLAT]** Bypass the orchestrator for emergency: temporarily disable the GitHub App on a repo without losing config. *AC: re-enable restores config; no data loss.*

16.2 **[IC]** If I push directly to a craw's branch while it's working, the orchestrator detects the conflict and halts. *AC: halt posts a comment explaining; ticket returns to backlog with a "human-took-over" label.*

16.3 **[IC]** If GitHub goes down or rate-limits us, queued tasks pause and resume automatically when GitHub recovers. *AC: orchestrator backs off exponentially; no false failures attributed to the craw.*

16.4 **[PLAT]** If a connected LLM provider has an outage, the task halts gracefully (saves state) and resumes when the provider recovers. *AC: durable workflow engine handles this natively (rationale for the §1.2 ADR in the stages doc).*

16.5 **[EM]** Migrate from GitHub Issues to Linear (or vice versa) without losing historical craw activity. *AC: cross-tracker links preserved; reports stitch across both.*

16.6 **[VPE]** Cancel my subscription; data exports for 90 days post-cancel; then deletion. *AC: standard SaaS deletion contract; exportable formats; explicit deletion confirmation.*

---

## 17 · Stories that the codebase already partially satisfies

Cross-referenced against the v0.3 survey. These stories are partially or fully implemented; v1 work is gap-closing rather than greenfield.

- **§1.4 GitHub repo connect** — `cloud/server/prisma/schema.prisma` `Project` model + GitHub OAuth shipped. Gap: per-repo PR-write toggle, CI provider linking.
- **§3.1 Linear ingestion** — `cli/orgctl/src/inbound/github-issues.ts` + `notion-pages.ts` ship; Linear adapter is new but follows the same pattern.
- **§3.4 Classifier comment on ticket** — `triage.ts` ships heuristic normalization; the LLM-based eligibility classifier is new work layered on top.
- **§5.4 Worktree isolation** — pulled forward from GRAND_PLAN §3.3 LATER² weeks 23–24; existing `git worktree` patterns documented.
- **§5.6 Budget cap** — `cli/orgctl/src/budget.ts` ships per-task budget + auto-escalate; v1 work is the org-wide daily cap + the cost-manager agent dispatch.
- **§6.1 Live SSE stream** — existing `desktop/lens` REST+SSE infrastructure; new work is per-task subscription + multi-craw aggregation.
- **§6.3 Replay** — existing lens session replay; new work is replay for orchestrator tasks specifically.
- **§7 CI integration** — `cli/orgctl/src/inbound/github-issues.ts` reads GitHub state; CI status reads + fix loop is new work.
- **§8.4 Auto-merge** — GitHub API call; net-new but trivial.
- **§10.1–10.5 Analytics** — `cli/projectctl/src/stats.ts` ships rolling stats; new work is the cost-rollup widgets and org-wide aggregation.
- **§11 Failure categorization** — `budget.ts` emits `budget_breach`; new work is the wider failure taxonomy + dashboard.
- **§12 Billing** — Stripe-on-`cloud/server` is net-new (existing models cover orgs/seats but not subscriptions or usage metering).
- **§14.1 Audit log** — JSONL substrate is the natural store; new work is the audit-specific projection + UI.

---

*Owner: lead. Edits land through PR. Last updated: 2026-05-22.*
