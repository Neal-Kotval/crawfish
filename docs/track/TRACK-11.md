# TRACK-11 — Failure handling & escalation

**Components:** `PLAT` (primary) · `DASH` (the widgets that read failure state)
**Source:** ORCHESTRATOR-USER-STORIES.md §11 · ROADMAP O-stages O3.5, O3.6, O3.7, O3.8, O6.2, O6.3

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is where every execution path that can go wrong lands. A task fails — its plan was
rejected, CI never went green, it blew its token budget, the craw errored, it timed out, a
human cancelled it, or a policy blocked it — and this surface is responsible for making that
failure **visible, categorized, and recoverable**. It cross-cuts the whole product: a TRACK-5
budget stall, a TRACK-7 CI failure, and a TRACK-9 comment-loop halt all converge here as the
same kind of event.

The load-bearing rule is **one failure record, three read-projections**. When a task fails you
write *one* row. From that single row you render three views: a comment on the ticket, a
`stuck` filter entry on the dashboard, and (optionally) an email or Slack ping to the assignee.
You do not generate three independent messages — that drifts, and the customer ends up reading
three slightly different stories about the same failure. Build the record first; the surfaces
are projections over it.

Two stories in this section have no numbered deliverable and must stay visible to the lead: the
**weekly failure digest** (§11.5) and the **capability-gap recommendation** (§11.6). Both are
real acceptance criteria with no O-stage behind them. They are flagged in the Gaps section, not
buried.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Failure surfaces in 3 places (§11.1) | `PLAT` + `DASH` | `cloud/server/src/orchestrator/failure-taxonomy.ts` (record) → dashboard widget reads it |
| Categorize failures + trend lines (§11.2) | `PLAT` + `DASH` | `cloud/server/.../failure-taxonomy.ts` (O3.5) + dashboard widget (O3.6) |
| Manual takeover detection (§11.3) | `PLAT` | `cloud/server/src/orchestrator/takeover-detector.ts` (O3.8) |
| Manual takeover UX (§11.3 human half) | `PLAT` + `DASH` | dashboard + Linear/GitHub comments (O6.3) |
| Auto-disable on failure spike (§11.4) | `PLAT` | `cloud/server/src/orchestrator/craw-health.ts` (O3.7) |
| Weekly digest (§11.5) | `PLAT` + `DASH` | **unmapped — see Gaps** |
| Capability-gap recommendation (§11.6) | `PLAT` + `DASH` | **unmapped — see Gaps** |
| Escalation policy + chain (§11 routing) | `PLAT` + `DASH` | escalation policy UI + backend (O6.2) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

11.1 **[PLAT, DASH]** When a task fails, the failure surfaces in three places: the ticket (as a comment), the dashboard (as a `stuck` filter), and (optionally) email/Slack to the assignee. *AC: same failure record; one source of truth.*

11.2 **[PLAT, DASH]** Categorize failures: `plan-rejected`, `ci-failed-after-fixes`, `budget-exceeded`, `craw-error`, `timeout`, `cancelled-by-user`, `policy-blocked`. *AC: each category surfaced in dashboard filters; trend lines per category.*

11.3 **[PLAT, DASH]** Take over a failed task manually: check out the worktree, fix the issue locally, push, and merge as a normal human PR. *AC: orchestrator detects the human-authored push and gracefully exits its own loop; ticket links the human PR.*

11.4 **[PLAT]** Auto-disable a craw when its failure rate spikes (e.g., >50% failures in last 24h on >5 attempts). *AC: orchestrator pauses new dispatches to that craw and pings the EM; manual re-enable.*

11.5 **[PLAT, DASH]** Receive a weekly digest of which craws had the highest failure rate this week and what category dominated. *AC: digest is opt-in; default off; surfaces in email + dashboard.*

11.6 **[PLAT, DASH]** When a task fails due to a missing capability (e.g., needs a tool the craw doesn't have), the failure message tells me what craw or skill would be needed instead. *AC: failure message includes a recommendation; opens the relevant marketplace entry.*

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O3.5** — Failure categorization taxonomy (`cloud/server/src/orchestrator/failure-taxonomy.ts`). Implements §11.2. This is the **one record** §11.1 depends on. Define the seven categories as an enum and a single `recordFailure()` that every upstream stall calls. The taxonomy is a *normalizer*, not seven new detectors — each category maps to an event that already fires somewhere else (see Key concepts).

  ```ts
  // cloud/server/src/orchestrator/failure-taxonomy.ts
  export type FailureCategory =
    | "plan-rejected" | "ci-failed-after-fixes" | "budget-exceeded"
    | "craw-error" | "timeout" | "cancelled-by-user" | "policy-blocked";

  // ONE write. The ticket comment, dashboard filter, and Slack/email all read this row.
  export async function recordFailure(input: {
    taskId: string; crawId: string; category: FailureCategory; detail: string;
  }) {
    return db.taskFailure.create({ data: { ...input, at: new Date() } });
    // Do NOT also post a comment / send an email here — those are projections, fired by readers.
  }
  ```

- **O3.7** — Auto-disable craw on failure-rate spike (`cloud/server/src/orchestrator/craw-health.ts`). Implements §11.4. Reads the per-craw stats (TRACK-10, `stats.ts`), and when a craw crosses >50% failures over the last 24h on >5 attempts, flips it to a paused state, pings the EM (via O6.4, TRACK-13), and requires a manual re-enable. This is a **reversible workflow state** — the same shape as the budget pause in TRACK-5 §5.6 — not a delete.

  ```ts
  // craw-health.ts — evaluated after each task completes
  const { attempts, failures } = await stats.crawWindow(crawId, hours(24));
  if (attempts > 5 && failures / attempts > 0.5) {
    await db.craw.update({ where: { id: crawId }, data: { status: "disabled-auto" } });
    await notify.em(crawId, "auto-disabled: failure rate >50% over 24h"); // O6.4 delivers
    // Re-enable is a human action that sets status back to "active". Nothing is destroyed.
  }
  ```

- **O3.8** — Manual-takeover detection (`cloud/server/src/orchestrator/takeover-detector.ts`). Implements the machine half of §11.3. Watches for a **human-authored push** to the craw's branch and exits the orchestrator loop gracefully instead of fighting the human. This shares its push-watcher with §16.2 (direct-push conflict halt) — one watcher, two consumers, distinguished by whether the orchestrator was mid-run when the push landed.

- **O6.2** — Escalation policy + UI (fallback reviewer chain). The backend policy and the routing for failed/stuck tasks: who gets pinged, and who is the fallback if the first owner does not respond. Same machinery TRACK-13 §13.6 and TRACK-4 §4.7 reuse — the chain lives here; O6.4 delivers the ping.

- **O6.3** — Manual-takeover UX (hand off worktree gracefully) — backend half. Generates the worktree-checkout instructions and links the resulting human PR back to the ticket once O3.8 sees the push.

**Reuses (already shipped):**
- `budget.ts` `budget_breach` (CLI) — the existing breach event the `budget-exceeded` category (§11.2) and §11.1 surfacing read from. The failure record does not re-detect a budget breach; it ingests the breach event.

### DASH — `desktop/dash`

- **O3.6** — Failure dashboard widget. Implements the dashboard projection of §11.1 (the `stuck` filter) and the §11.2 trend lines. It is a **read view** over the O3.5 failure rows — it queries by category, renders one trend line per category, and never writes failure records itself.

- **O6.2 / O6.3 (UI halves)** — The escalation-chain configuration screen (who escalates to whom, per workspace) and the takeover UX surfaced in the dashboard plus the Linear/GitHub comment. The dashboard proxies to `desktop/lens` for the SSE stream and transcript replay that lets a human see *why* a task failed before taking it over.

**Reuses (already shipped):** lens SSE + replay (DASH) — the live event stream and transcript playback the takeover UX renders.

Cross-refs: O3.5 record is consumed by TRACK-5 (stalls), TRACK-7 (CI failures), TRACK-9 (loop halts). O6.2 escalation chain is shared with TRACK-4 §4.7 and TRACK-13 §13.6. O3.7 pause mirrors TRACK-5 §5.6 budget pause.

---

## Key technical concepts, explained

**One failure record, three read-projections (§11.1).** The temptation is to, at the moment a
task fails, post a comment *and* update the dashboard *and* send a Slack message in three
separate code paths. That guarantees drift: a copy edit to the comment never reaches Slack. The
discipline is a single `taskFailure` row written by `recordFailure()` (O3.5), and three
independent *readers* that each render their own surface from that row — the ticket-comment
writer, the dashboard `stuck` filter (O3.6), and the optional Slack/email sender (O6.4). One
source of truth; the surfaces are downstream.

**The failure taxonomy is a normalizer over existing events (§11.2).** None of the seven
categories is a new detector. Each maps to a signal that already fires elsewhere, and O3.5 just
labels it:

```ts
// Where each category's signal originates — the taxonomy normalizes, it does not detect.
"budget-exceeded"      // ← budget.ts budget_breach (CLI; TRACK-5/12)
"ci-failed-after-fixes"// ← O1.7 CI status (TRACK-7)
"cancelled-by-user"    // ← O1.8 cancel (TRACK-5)
"plan-rejected"        // ← O1.3 plan gate (TRACK-4)
"timeout"              // ← §5.8 idle-halt
```

Build one ingestion point that maps each upstream event onto a `FailureCategory`. Adding a
category later is a new mapping, not a new subsystem.

**Auto-disable is a reversible workflow state (§11.4).** "Disable a craw" must not mean delete
or hard-stop. It means flip a status field (`active` → `disabled-auto`) that the dispatcher
checks before sending new work, while in-flight tasks finish. A human re-enable flips it back.
This is exactly the budget-pause pattern from TRACK-5 §5.6 — the same reversible state, a
different trigger. Do not build a second pause path.

**The push-watcher is shared with §16.2 (§11.3).** Detecting a human push to the craw's branch
serves two stories: graceful takeover (§11.3, exit the loop) and conflict halt (§16.2, stop and
warn). One watcher emits the push event; the consumer decides what it means based on whether the
orchestrator was mid-run. Build the watcher once.

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§11.5 weekly failure digest.** Highest-failure-rate craws + dominant category, opt-in, default off, email + dashboard. No O-stage names it. It overlaps TRACK-13 §13.2 (digest mode, O6.4) and reads the O3.5 taxonomy data, but the *weekly failure digest specifically* is unbuilt. *What's needed:* a scheduled aggregation over the failure-taxonomy time-series + an opt-in flag; ideally one time-series store shared with the §11.2 live trend lines so the emailed digest and the dashboard agree.
- **§11.6 capability-gap recommendation.** "What craw or skill would be needed instead," opening the relevant marketplace entry. No O-stage. It depends on a **capability→craw index** the curated library (TRACK-2) does not yet expose; without it the failure message can only say "missing capability X" generically. *What's needed:* a structured capability declaration in `craw.yaml` (TRACK-2) the recommender can query, plus the recommendation engine itself.

---

## Open questions

- **§11.6 capability declaration:** is there a structured capability field in `craw.yaml` (TRACK-2) the recommender can query? If not, §11.6's marketplace link cannot be built — the message degrades to a generic "missing capability."
- **§11.5 / §11.2 time-series:** confirm one shared time-series store backs both the live dashboard trend lines and the emailed weekly digest, so the two never disagree on the same week's numbers.
