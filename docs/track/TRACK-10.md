# TRACK-10 — Analytics & cost dashboards

## Overview
The reporting surface: cost rollups by workspace/repo/craw/ticket, the compounding-factor metric, per-craw and per-engineer stats, an ROI proxy, CSV export for finance, and cycle-time comparison. Primary personas: VPE (cost, compounding factor, ROI), EM (per-craw, per-engineer stats), FIN (billing export), PM (cycle time). Sits orthogonal to the execution path — it reads from the run record and budget data every other surface produces. Reuses the shipped agent-stats engine and cost-rollup widgets rather than building metering anew.
Source: ORCHESTRATOR-USER-STORIES.md §10.

---

## User stories

10.1 **[VPE]** See yesterday's cost by workspace, by repo, by craw, by ticket. *AC: refreshes daily; click-through to specific tickets; exportable as CSV.*

10.2 **[VPE]** See the org's compounding-factor metric (sub-agent tokens / parent-useful tokens) — reuse GRAND_PLAN §3.6 framing. *AC: weekly trend; top three offending tickets called out.*

10.3 **[EM]** See per-craw stats: success rate, median tokens per task, median latency, count of tasks attempted. *AC: 30-day rolling window; reuses existing `cli/projectctl/src/stats.ts` agent-stats engine.*

10.4 **[EM]** See per-engineer rollup: which ICs are reviewing the most craw PRs, which are getting most of their tickets handled by craws, which are blocking on craw failures. *AC: aggregates only; no individual transcript surfacing without explicit policy (GRAND_PLAN §4.5 privacy contract).*

10.5 **[VPE]** See an org-wide ROI proxy: count of craw-merged PRs × estimated time saved (configurable per label) − craw cost = net savings. *AC: estimated time is editable per label; default values shipped; user can override.*

10.6 **[FIN]** Export the month's billing data (tokens by task, by user, by craw) as CSV for finance reconciliation. *AC: includes timestamps, repo, ticket id, craw id, token type breakdown.*

10.7 **[PM]** See per-ticket cycle time (created → eligible → merged) for craw-handled tickets vs. human-handled baseline. *AC: PM owns the comparison; orchestrator surfaces it but doesn't make a value judgment.*

10.8 **[v1.5]** **[VPE]** Dashboard widget: "if this trajectory continues, your monthly bill will be $X." Forecast accuracy improves over 30 days.

---

## Coding tasks (from ROADMAP.md)

- **O5.5** — Usage metering above per-seat allowance (`cloud/server/src/billing/{stripe,seats,usage}.ts`, shared with O5.1) — the metering source §10.1, §10.6 read from.
- **O6.10** — Regression alert pipeline (`cloud/server/src/quality/regression.ts`, uses cost-manager pattern) — feeds the per-craw success-rate trend behind §10.3 (and the 2σ alert in TRACK-15).
  - Reuses: `cli/projectctl/src/stats.ts` agent-stats engine — directly cited in §10.3 AC; 30-day rolling window source.
  - Reuses: existing cost-rollup widgets — USER-STORIES §17 ("new work is the cost-rollup widgets and org-wide aggregation"); §10.1–10.5 build on these.
  - Reuses: GRAND_PLAN §3.6 compounding-factor metric — directly cited in §10.2.

Gap / flag: §10 has no dedicated O-stage table of its own in ROADMAP; the analytics surface is assembled from O5.5 metering + O6.10 regression + reused `stats.ts` + reused widgets. Several stories have **no numbered deliverable**:
- §10.4 per-engineer rollup (with the GRAND_PLAN §4.5 privacy contract constraint — aggregates only) — unnumbered.
- §10.5 ROI proxy (configurable per-label time-saved) — unnumbered.
- §10.7 cycle-time comparison (created→eligible→merged vs. human baseline) — unnumbered.
- §10.8 `[v1.5]` bill forecast — unnumbered (v1.5, expected).
Lead should confirm whether these are folded into the cost-rollup widget work or need explicit O-stage assignment.

---

## Tech stack considerations

- The metering source of record is O5.5 (`usage.ts`); analytics must read from the same metered token data billing uses, or the cost a VPE sees (§10.1) won't reconcile with the invoice (§10.6, TRACK-12). One token-spend ledger, multiple projections.
- §10.3 reuses `cli/projectctl/src/stats.ts` directly — success rate, median tokens, median latency, attempt count over a 30-day rolling window. This engine already computes agent stats; the orchestrator work is feeding it run records and surfacing the output, not new metric math.
- §10.2 compounding factor (sub-agent tokens / parent-useful tokens, GRAND_PLAN §3.6) only has signal once multi-craw runs exist (TRACK-6 §6.2 team view); in v1's mostly-1-of-1 world the denominator dominates. The "top three offending tickets" call-out needs the per-task token attribution the SSE stream (O3.2) already records per craw.
- §10.4 per-engineer rollup is governed by the GRAND_PLAN §4.5 privacy contract: aggregates only, no individual transcript surfacing without explicit policy. This is a hard constraint on the query layer — the rollup must not be able to drill to a single person's transcript by default. Privacy gate is code, not policy doc.
- §10.6 CSV export (timestamps, repo, ticket id, craw id, token-type breakdown) is FIN's reconciliation artifact and must match Stripe's metered records exactly; token-type breakdown (input/output/cache) must be retained per task, not summed — retention decision affects the run-record schema.
- §10.5 ROI proxy and §10.7 cycle time are both editable/comparative surfaces the orchestrator presents "without a value judgment" (§10.7) — default per-label time-saved values ship but are user-overridable. Open question: where do default time-saved-per-label values come from? Not specified; arbitrary defaults invite distrust of the ROI number.
