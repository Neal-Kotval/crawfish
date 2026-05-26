# TRACK-15 — Eval & quality

## Overview
The quality-measurement surface: classifier accuracy reporting, human labeling of classifier decisions to improve it, published per-craw benchmarks with failure cases, custom dry-run benchmark suites against a customer's own tickets, a 2σ regression alert, and v1.5 tournament mode. Primary personas: EM (classifier accuracy, labeling, custom bench), PLAT (published benchmarks), VPE (regression alert). Sits alongside the classifier (TRACK-3) and the craw library (TRACK-2) — it is how a workspace measures whether its automation is getting better or worse over time.
Source: ORCHESTRATOR-USER-STORIES.md §15.

---

## User stories

15.1 **[EM]** See the auto-classifier's accuracy on the last 30 days of decisions (precision, recall, false-positive rate). *AC: dashboard widget; click-through to misclassified tickets.*

15.2 **[EM]** Label individual classifier decisions as correct/incorrect to improve the classifier over time. *AC: labels feed a per-workspace eval set; classifier re-evaluated weekly.*

15.3 **[PLAT]** See per-craw benchmark scores published by Crawfish — what bench the craw was tested against, what score it got, what the failure cases looked like. *AC: bench data is public; per-craw page links to bench fixtures.*

15.4 **[EM]** Run a craw against a custom benchmark suite (the customer's own tickets, replayed in dry-run mode). *AC: dry-run mode opens no PRs, posts no comments; produces a report.*

15.5 **[VPE]** Receive a regression alert when a craw's success rate drops 2σ below its baseline. *AC: same alerting mechanism as GRAND_PLAN §3.11 cost-manager.*

15.6 **[v1.5]** **[EM]** Tournament mode: run two craws on the same task and pick the winner by metric. (Token-expensive; gated behind a flag.)

---

## Coding tasks (from ROADMAP.md)

- **O2.5** — Per-workspace eval harness (`cloud/server/src/classifier/eval-harness.ts` + dashboard) — implements §15.1 (30-day precision/recall/FP-rate, click-through to misclassified) and §15.2 (label decisions → per-workspace eval set → weekly re-eval).
- **O2.10** — Bench fixtures per craw (`bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/`) — implements §15.3 (published bench data, per-craw page links to fixtures).
- **O6.10** — Regression alert pipeline (2σ drop in success rate) (`cloud/server/src/quality/regression.ts`, uses cost-manager pattern) — implements §15.5 directly.
  - Reuses: GRAND_PLAN §3.11 cost-manager alerting — the alerting mechanism §15.5 AC cites.

Gap / flag: §15.4 **custom dry-run benchmark suite** (replay a customer's own tickets, no PRs/comments, produce a report) has no numbered deliverable. Dry-run mode is a distinct execution path (suppress all external side-effects) that O2.5's eval harness measures classifier accuracy on, but replaying *craw runs* in dry-run against customer tickets is unbuilt in O0–O7. Lead should assign — this is non-trivial (it needs the worker to run with side-effects stubbed).

Note: §15.6 tournament mode is `[v1.5]`, token-expensive, flag-gated — no v1 O-stage. It depends on the multi-craw collab primitive (O3.1) running two craws on one task and comparing by metric. Correctly deferred.

---

## Tech stack considerations

- The eval harness (O2.5) serves two distinct measurements that share one store: classifier accuracy (§15.1, a labeled-decision precision/recall problem) and the per-workspace eval set that human labels (§15.2) feed. The §3.3 manual override (TRACK-3) is also a labeling signal — route overrides into the same eval set rather than maintaining two.
- §15.3 published benchmarks (O2.10) are Crawfish's *reference* bench, public, with failure cases — distinct from the customer's §15.4 custom suite and from live per-craw stats (TRACK-10 §10.3). Three different "how good is this craw" data sources; the per-craw page must label which is which or it implies a customer's craw was tested on Crawfish's bench.
- §15.4 dry-run mode requires the worker to execute with every external side-effect suppressed (no PR, no comment) — this is a first-class worker mode, not a flag on the PR step, because a craw mid-run makes many side-effecting calls. It overlaps the durable-workflow side-effect boundary (TRACK-5 §5.1): the same idempotency-keyed side-effect calls must be intercept-able as no-ops in dry-run.
- §15.5 regression alert (2σ below baseline) reuses the GRAND_PLAN §3.11 cost-manager alerting mechanism (O6.10) — the same pipeline that feeds the per-craw success-rate trend (TRACK-10). Baseline computation needs enough run history per craw to have a meaningful σ; a new craw has no baseline, so the alert must suppress until N runs exist.
- §15.2 weekly re-evaluation cadence implies a scheduled job over the per-workspace eval set; the classifier (O2.4, TRACK-3) is the thing re-evaluated, so a classifier prompt/version change must re-run against the accumulated eval set to detect regressions — tying §15 quality to TRACK-3's classifier versioning.
- §15.6 tournament mode is token-expensive and flag-gated for a reason: running two craws on one task doubles spend and must respect the per-task budget cap (TRACK-5 §5.6). Open question: does tournament spend count once or twice against the org budget? Deferred to v1.5 but the budget interaction should be decided before it ships.
