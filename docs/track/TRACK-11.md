# TRACK-11 — Failure handling & escalation

## Overview
The failure lifecycle: a single failure record surfaced in three places (ticket, dashboard, optional Slack/email), a categorized failure taxonomy with trend lines, graceful manual takeover, auto-disable of a craw whose failure rate spikes, a weekly digest, and capability-gap recommendations. Primary personas: IC (sees failures, takes over, gets recommendations), EM (categorizes, auto-disable, configures), VPE (weekly digest). Cross-cuts every execution surface — it is where TRACK-5 stalls, TRACK-7 CI failures, and TRACK-9 loop halts converge.
Source: ORCHESTRATOR-USER-STORIES.md §11.

---

## User stories

11.1 **[IC]** When a task fails, the failure surfaces in three places: the ticket (as a comment), the dashboard (as a `stuck` filter), and (optionally) email/Slack to the assignee. *AC: same failure record; one source of truth.*

11.2 **[EM]** Categorize failures: `plan-rejected`, `ci-failed-after-fixes`, `budget-exceeded`, `craw-error`, `timeout`, `cancelled-by-user`, `policy-blocked`. *AC: each category surfaced in dashboard filters; trend lines per category.*

11.3 **[IC]** Take over a failed task manually: check out the worktree, fix the issue locally, push, and merge as a normal human PR. *AC: orchestrator detects the human-authored push and gracefully exits its own loop; ticket links the human PR.*

11.4 **[EM]** Auto-disable a craw when its failure rate spikes (e.g., >50% failures in last 24h on >5 attempts). *AC: orchestrator pauses new dispatches to that craw and pings the EM; manual re-enable.*

11.5 **[VPE]** Receive a weekly digest of which craws had the highest failure rate this week and what category dominated. *AC: digest is opt-in; default off; surfaces in email + dashboard.*

11.6 **[IC]** When a task fails due to a missing capability (e.g., needs a tool the craw doesn't have), the failure message tells me what craw or skill would be needed instead. *AC: failure message includes a recommendation; opens the relevant marketplace entry.*

---

## Coding tasks (from ROADMAP.md)

- **O3.5** — Failure categorization taxonomy (`cloud/server/src/orchestrator/failure-taxonomy.ts`) — implements §11.2 (the seven categories, filterable, trend lines).
- **O3.6** — Failure dashboard widget (dashboard) — implements §11.1 dashboard surface (`stuck` filter) and §11.2 trend lines.
- **O3.7** — Auto-disable craw on failure-rate spike (`cloud/server/src/orchestrator/craw-health.ts`) — implements §11.4 (>50%/24h on >5 attempts → pause dispatches + ping EM + manual re-enable).
- **O3.8** — Manual-takeover detection (`cloud/server/src/orchestrator/takeover-detector.ts`) — implements §11.3 (detect human-authored push, graceful exit, link human PR).
- **O6.2** — Escalation policy + UI (fallback reviewer chain) (dashboard) — escalation routing for failed/stuck tasks.
- **O6.3** — Manual-takeover UX (hand off worktree gracefully) (dashboard + Linear/GitHub comments) — the human-facing half of §11.3.
  - Reuses: `budget.ts` `budget_breach` pattern — the existing breach event the `budget-exceeded` category (§11.2) and §11.1 surfacing build on (USER-STORIES §17, §11).

Gap / flag: §11.5 **weekly digest** (highest-failure-rate craws + dominant category, opt-in, email + dashboard) has no numbered deliverable. It is digest-mode work overlapping TRACK-13 §13.2 (digest mode, O6.4) and reads O3.5 taxonomy data — but no O-stage names the weekly failure digest specifically. Lead should assign.

Gap / flag: §11.6 **capability-gap recommendation** ("what craw or skill would be needed instead," opens the marketplace entry) has no numbered deliverable. It depends on a capability-to-craw mapping that the curated library (TRACK-2) would need to expose; the recommendation engine is unbuilt in O0–O7. Flag.

---

## Tech stack considerations

- §11.1's "same failure record; one source of truth" is the load-bearing constraint: the ticket comment, the dashboard `stuck` filter, and the optional Slack/email must all project from one failure row (O3.5), not three independently-generated messages. Build the failure record first; the three surfaces are read-projections.
- §11.2's seven categories map to upstream events that already exist or are built elsewhere: `budget-exceeded` ← `budget.ts` breach (TRACK-5/12), `ci-failed-after-fixes` ← O1.7 (TRACK-7), `cancelled-by-user` ← O1.8 (TRACK-5), `plan-rejected` ← O1.3 (TRACK-4), `timeout` ← §5.8 idle-halt. The taxonomy is a normalizer over existing signals, not a new detector per category.
- §11.3 manual-takeover detection (O3.8) watches for a human-authored push to the craw's branch and exits the orchestrator loop gracefully; this shares its push-detection with §16.2 (direct-push conflict halt). One push-watcher, two consumers (graceful exit vs. conflict halt) — distinguish by whether the orchestrator was mid-run.
- §11.4 auto-disable threshold (>50% failures / 24h / >5 attempts) reads the per-craw stats (TRACK-10, `stats.ts`); the disable pauses dispatch and requires manual re-enable. This is the craw-health analog of the budget pause (TRACK-5 §5.6) — a reversible workflow state, pinging the EM via O6.4.
- §11.6 recommendation needs a capability→craw index the library doesn't yet expose; without it the failure message can only say "missing capability X" generically. Open question: is there a structured capability declaration in `craw.yaml` (TRACK-2) the recommender can query? If not, §11.6's marketplace link can't be built.
- Trend lines per category (§11.2) and the weekly digest (§11.5) both aggregate the same failure-taxonomy data over time; keep one time-series store so the live dashboard trend and the emailed digest agree.
