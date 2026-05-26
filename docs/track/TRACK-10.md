# TRACK-10 — Analytics & cost dashboards

**Components:** `PLAT` (primary) · `DASH` (cost-rollup widgets) · `CLI` (the shipped `stats.ts` engine it reuses)
**Source:** ORCHESTRATOR-USER-STORIES.md §10 · ROADMAP O-stages O5.5, O6.10

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the reporting surface, and it sits **orthogonal** to the execution path — it builds
nothing new in the loop, it only reads from the run records and budget data every other surface
already produces. Cost rollups by workspace / repo / craw / ticket; the compounding-factor metric;
per-craw and per-engineer stats; an ROI proxy; a CSV export for finance; and a cycle-time
comparison against human baseline. The work here is *projection and presentation*, not metering.

The single most important architectural fact: there is **one token-spend ledger, and many
projections of it**. The cost a VPE sees on the dashboard (§10.1) must read from the exact same
metered token data the invoice (§10.6, TRACK-12) is built from, or the dashboard and the bill won't
reconcile — and a customer who can't reconcile their bill stops trusting every number you show them.
O5.5 (`usage.ts`) is that ledger. Everything in this track is a view on top of it.

Two reuse facts shape the build. The per-craw stats (§10.3) come straight from the shipped
`cli/projectctl/src/stats.ts` engine — success rate, median tokens, median latency, attempt count
over a 30-day rolling window — so the orchestrator's job is feeding it run records, not re-deriving
metric math. And the cost-rollup widgets already exist (USER-STORIES §17 names the new work as "the
cost-rollup widgets and org-wide aggregation"), so §10.1–10.5 build on those rather than from
scratch. The headline risk is that **four stories have no numbered O-stage at all** (see Gaps).

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Cost by workspace/repo/craw/ticket (§10.1) | `PLAT` | reads O5.5 `cloud/server/src/billing/usage.ts` ledger |
| Compounding-factor metric (§10.2) | `PLAT` + `DASH` | reuses GRAND_PLAN §3.6; widget in dashboard |
| Per-craw stats (§10.3) | `CLI` → `PLAT` | reuses `cli/projectctl/src/stats.ts`; O6.10 trend |
| Per-engineer rollup (§10.4) | `PLAT` + `DASH` | **unnumbered — see Gaps** (privacy-gated query) |
| ROI proxy (§10.5) | `PLAT` | `cloud/server/src/billing/` (O5.5 data) |
| CSV billing export (§10.6) | `PLAT` | reads O5.5 `usage.ts` metered records |
| Cycle-time comparison (§10.7) | `PLAT` + `DASH` | **unnumbered — see Gaps** |
| Bill forecast widget (§10.8) | `PLAT` + `DASH` | **unnumbered, `[v1.5]` — see Gaps** |

---

## User stories

Tags are now **components** (where it gets built), not personas.

10.1 **[PLAT]** See yesterday's cost by workspace, by repo, by craw, by ticket. *AC: refreshes daily; click-through to specific tickets; exportable as CSV.*

10.2 **[PLAT, DASH]** See the org's compounding-factor metric (sub-agent tokens / parent-useful tokens) — reuse GRAND_PLAN §3.6 framing. *AC: weekly trend; top three offending tickets called out.*

10.3 **[CLI]** See per-craw stats: success rate, median tokens per task, median latency, count of tasks attempted. *AC: 30-day rolling window; reuses existing `cli/projectctl/src/stats.ts` agent-stats engine.*

10.4 **[PLAT, DASH]** See per-engineer rollup: which ICs are reviewing the most craw PRs, which are getting most of their tickets handled by craws, which are blocking on craw failures. *AC: aggregates only; no individual transcript surfacing without explicit policy (GRAND_PLAN §4.5 privacy contract).*

10.5 **[PLAT]** See an org-wide ROI proxy: count of craw-merged PRs × estimated time saved (configurable per label) − craw cost = net savings. *AC: estimated time is editable per label; default values shipped; user can override.*

10.6 **[PLAT]** Export the month's billing data (tokens by task, by user, by craw) as CSV for finance reconciliation. *AC: includes timestamps, repo, ticket id, craw id, token type breakdown.*

10.7 **[PLAT, DASH]** See per-ticket cycle time (created → eligible → merged) for craw-handled tickets vs. human-handled baseline. *AC: PM owns the comparison; orchestrator surfaces it but doesn't make a value judgment.*

10.8 **[v1.5]** **[PLAT, DASH]** Dashboard widget: "if this trajectory continues, your monthly bill will be $X." Forecast accuracy improves over 30 days.

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O5.5** — Usage metering above per-seat allowance (`cloud/server/src/billing/{stripe,seats,usage}.ts`, shared with O5.1). This is the **single token-spend ledger** §10.1 and §10.6 read from. `usage.ts` is the source of record; analytics must never compute cost from a second source, or the dashboard and invoice diverge.

  ```ts
  // cloud/server/src/billing/usage.ts — retain the per-task breakdown, do not pre-sum
  type UsageRecord = {
    taskId: string; repoId: string; ticketId: string; crawId: string; userId: string;
    ts: string;
    tokens: { input: number; output: number; cache: number }; // §10.6 needs the split kept
  };
  // §10.1 dashboard and §10.6 CSV are both projections of UsageRecord[]
  ```

- **O6.10** — Regression alert pipeline (`cloud/server/src/quality/regression.ts`, uses the cost-manager pattern). Feeds the per-craw success-rate **trend** behind §10.3 (and the 2σ regression alert in TRACK-15). It consumes the `stats.ts` output rather than recomputing it.

  **Reuses (already shipped — do not rebuild):**
  - `cli/projectctl/src/stats.ts` agent-stats engine — directly cited in §10.3 AC; the 30-day rolling-window source for success rate, median tokens, median latency, attempt count. Feed it run records; do not re-derive these metrics.
  - Existing cost-rollup widgets — USER-STORIES §17 ("new work is the cost-rollup widgets and org-wide aggregation"); §10.1–10.5 build on these.
  - GRAND_PLAN §3.6 compounding-factor framing — directly cited in §10.2.

### DASH — `desktop/dash`

- The compounding-factor widget (§10.2), the per-engineer rollup view (§10.4), the cycle-time comparison (§10.7), and the bill-forecast widget (§10.8) are **dashboard presentation surfaces** over the PLAT ledger and `stats.ts` output. The §10.2 "top three offending tickets" call-out needs the per-task token attribution the SSE stream (O3.2) already records per craw. None of these add metering; they render projections.

  Cross-references: the §10.2 compounding factor only has signal once multi-craw runs exist (TRACK-6 §6.2); in v1's mostly-1-of-1 world the denominator dominates. The §10.6 CSV must match Stripe's metered records exactly (TRACK-12).

---

## Key technical concepts, explained

**One token ledger, many projections.** Every number on this surface — the VPE's daily cost
(§10.1), the finance CSV (§10.6), the ROI proxy (§10.5) — is a *read* of one underlying table,
`usage.ts`'s `UsageRecord[]`. There is no second place where cost is computed. If you ever find
yourself summing tokens outside this ledger to render a chart, stop: that's how the dashboard and
the invoice drift apart. The CSV in particular must keep the input/output/cache split per task and
**not** pre-sum it, because finance reconciles against Stripe's per-type metered records.

**The compounding-factor metric (§10.2, GRAND_PLAN §3.6).** It is a ratio: tokens burned by
sub-agents divided by tokens that did useful parent-level work. A high number means a craw fanned
out into sub-agents that re-did the same work (the "30 sub-agents hitting the same five papers"
disaster from GRAND_PLAN). The "top three offenders" call-out ranks tickets by this ratio:

```ts
// §10.2 — sub-agent spend over parent-useful spend, per ticket
function compoundingFactor(t: TicketUsage): number {
  return t.subAgentTokens / Math.max(t.parentUsefulTokens, 1); // guard divide-by-zero
}
const offenders = tickets.map(compoundingFactor).sort(desc).slice(0, 3);
```

**The GRAND_PLAN §4.5 aggregates-only privacy gate (§10.4).** The per-engineer rollup is governed
by a hard privacy contract: managers see **aggregates**, never individual transcripts, unless an
explicit policy grants access. This is enforced **in code at the query layer**, not in a policy
document — the rollup query must be structurally incapable of drilling from "engineer X handled 12
tickets" down to "here is engineer X's transcript for ticket 7." A query that returns per-row
person-level transcript references is a privacy-contract violation even if no UI exposes it:

```ts
// §10.4 — privacy gate is code: aggregate-only unless an explicit grant exists
function perEngineerRollup(orgId: string, viewer: Member) {
  const q = db.usage.groupBy({ by: ["userId"], where: { orgId }, _count: true, _sum: { tokens: true } });
  if (!hasTranscriptGrant(viewer, orgId)) {
    return q; // counts and sums only — no transcriptId column can be selected
  }
  return q; // grant path may join transcripts; default path must not be able to
}
```

The contract is the product (GRAND_PLAN: "no AI productivity score for employees"). Treat any path
that can reach a single person's transcript by default as a defect.

---

## Gaps — work with no O-stage assigned

§10 has **no dedicated O-stage table** in ROADMAP; the surface is assembled from O5.5 metering +
O6.10 regression + reused `stats.ts` + reused widgets. Four stories have **no numbered deliverable** —
this is the headline of the track and the lead must rule on each before build.

- **§10.4 per-engineer rollup — unnumbered.** Carries the GRAND_PLAN §4.5 privacy contract (aggregates only). *What's needed:* an explicit deliverable for the privacy-gated query layer (above), since "aggregate-only" is a code guarantee, not a widget setting.
- **§10.5 ROI proxy — unnumbered.** `merged PRs × time-saved-per-label − craw cost`. *What's needed:* a source for the **default per-label time-saved values**. Arbitrary defaults invite distrust of the whole ROI number; the values must be editable and their origin defensible.
- **§10.7 cycle-time comparison — unnumbered.** `created → eligible → merged` for craw-handled vs. human baseline. *What's needed:* a deliverable that records the three timestamps on the run record and a human-baseline source. The orchestrator surfaces the comparison "without a value judgment" — so the framing must be neutral.
- **§10.8 bill forecast — unnumbered, `[v1.5]`.** "If this trajectory continues, your bill will be $X." Expected to be v1.5; flagged so it isn't silently dropped.

Lead should confirm whether these fold into the cost-rollup widget work or need explicit O-stage assignment.

---

## Open questions

- **§10.5 default time-saved values:** where do the per-label defaults come from? Not specified. An indefensible default poisons trust in the ROI proxy.
- **§10.6 token-type retention:** confirm the run-record schema keeps input/output/cache *per task* and never pre-sums — the CSV (and Stripe reconciliation) depend on it.
- **§10.4 grant mechanism:** what is the "explicit policy" that lifts the aggregates-only gate, and who can set it? The gate is only as good as the grant path's auth.
