# TRACK-15 — Eval & quality

**Components:** `PLAT` (primary) · `DASH` (accuracy + benchmark widgets) · `CLI` (bench fixtures)
**Source:** ORCHESTRATOR-USER-STORIES.md §15 · ROADMAP.md O-stages O2.5, O2.10, O6.10

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).
> - **OPS** — operational/docs work (runbooks, status page, on-call, published reference docs). Not a code submodule; the deliverable is a written artifact or a process, not a build target.

---

## What this surface is

This is how a workspace measures whether its automation is getting better or worse. It has four
shipping mechanisms — classifier accuracy reporting, human labeling of classifier decisions to
improve it, published per-craw benchmarks with failure cases, and a 2σ regression alert — plus one
unbuilt mechanism (custom dry-run benchmark suites) and one deferred mode (tournament).

The center of gravity is the **eval harness** (O2.5): one per-workspace store that holds labeled
classifier decisions, fed from two directions — explicit human labels (§15.2) and manual overrides
already happening in the classifier flow (TRACK-3 §3.3). From that one store the harness computes
30-day precision/recall/false-positive-rate (§15.1) and re-evaluates the classifier weekly. Keeping
both signals in one eval set is the load-bearing design decision: maintaining two would let them
disagree.

By component: most of this is PLAT — the eval harness, the regression pipeline, the classifier
re-evaluation all live in `cloud/server`. The accuracy widget and the published-benchmark page are
PLAT-backed but render in DASH. The bench *fixtures* themselves — the reference tickets each curated
craw is scored against — are versioned alongside the craws in CLI (`bench/craws/...`). The 2σ
regression alert reuses the GRAND_PLAN §3.11 cost-manager alerting pipeline rather than inventing a
new one.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Classifier accuracy report (§15.1) | `PLAT` + `DASH` | `cloud/server/src/classifier/eval-harness.ts` + dashboard widget (O2.5) |
| Label decisions → eval set (§15.2) | `PLAT` | `cloud/server/src/classifier/eval-harness.ts` (O2.5) |
| Published per-craw benchmarks (§15.3) | `PLAT` + `DASH` + `CLI` | `bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/` (O2.10) + per-craw page |
| Custom dry-run benchmark suite (§15.4) | `PLAT` | **unmapped — see Gaps** |
| 2σ regression alert (§15.5) | `PLAT` | `cloud/server/src/quality/regression.ts` (O6.10) |
| Tournament mode (§15.6) | `PLAT` | `[v1.5]` — depends on O3.1; no v1 O-stage |

---

## User stories

Tags are now **components** (where it gets built), not personas.

15.1 **[PLAT, DASH]** See the auto-classifier's accuracy on the last 30 days of decisions (precision, recall, false-positive rate). *AC: dashboard widget; click-through to misclassified tickets.*

15.2 **[PLAT]** Label individual classifier decisions as correct/incorrect to improve the classifier over time. *AC: labels feed a per-workspace eval set; classifier re-evaluated weekly.*

15.3 **[PLAT, DASH, CLI]** See per-craw benchmark scores published by Crawfish — what bench the craw was tested against, what score it got, what the failure cases looked like. *AC: bench data is public; per-craw page links to bench fixtures.*

15.4 **[PLAT]** Run a craw against a custom benchmark suite (the customer's own tickets, replayed in dry-run mode). *AC: dry-run mode opens no PRs, posts no comments; produces a report.*

15.5 **[PLAT]** Receive a regression alert when a craw's success rate drops 2σ below its baseline. *AC: same alerting mechanism as GRAND_PLAN §3.11 cost-manager.*

15.6 **[v1.5]** **[PLAT]** Tournament mode: run two craws on the same task and pick the winner by metric. (Token-expensive; gated behind a flag.)

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O2.5** — Per-workspace eval harness (`cloud/server/src/classifier/eval-harness.ts` + dashboard). Implements §15.1 and §15.2. One store, two feeds: explicit labels (§15.2) and manual overrides routed in from TRACK-3 §3.3. From it, compute the standard classification metrics over the last 30 days and re-run the classifier against the accumulated eval set weekly.

  ```ts
  // cloud/server/src/classifier/eval-harness.ts
  type EvalEntry = {
    ticketId: string;
    predicted: Label;          // what the classifier decided
    truth: Label;              // from a human label OR a manual override
    source: "label" | "override";
    ts: string;
  };

  function metrics(entries: EvalEntry[]) {
    const tp = entries.filter(e => e.predicted === e.truth && positive(e.truth)).length;
    const fp = entries.filter(e => e.predicted !== e.truth && positive(e.predicted)).length;
    const fn = entries.filter(e => e.predicted !== e.truth && positive(e.truth)).length;
    return {
      precision: tp / (tp + fp),
      recall:    tp / (tp + fn),
      fpRate:    fp / (fp + entries.filter(e => !positive(e.predicted)).length),
    };
  }
  ```

  Weekly re-eval implies a scheduled job replaying the eval set against the current classifier (O2.4, TRACK-3) so a classifier prompt/version change is caught as a regression — this ties §15 quality to TRACK-3 classifier versioning.

- **O6.10** — Regression alert pipeline (`cloud/server/src/quality/regression.ts`). Implements §15.5. A craw's per-run success rate is tracked; when it drops 2σ below its rolling baseline, fire an alert through the **same** mechanism as the GRAND_PLAN §3.11 cost-manager (§15.5 AC names it explicitly). Reuse the cost-manager's alert sink and threshold-crossing logic rather than building a parallel one; this is the same pipeline that feeds the per-craw success-rate trend (TRACK-10).

  ```ts
  // cloud/server/src/quality/regression.ts
  function regressed(history: number[], latest: number, minRuns = 20): boolean {
    if (history.length < minRuns) return false;     // no baseline yet — suppress
    const mean = avg(history);
    const sigma = stddev(history);
    return latest < mean - 2 * sigma;               // 2σ below baseline
  }
  ```

### DASH — `desktop/dash`

- **O2.5 (widget)** — Classifier-accuracy widget. Renders the 30-day precision / recall / FP-rate from the eval harness, with click-through to the misclassified tickets so a human can label them (closing the §15.2 loop). PLAT computes; DASH displays and links.

- **O2.10 (page)** — Per-craw benchmark page. Shows the published score, the bench it was tested against, and the failure cases, linking to the fixtures. It must **label which data source it is showing**: Crawfish's public reference bench (§15.3), the customer's own custom suite (§15.4), and live per-craw stats (TRACK-10 §10.3) are three different "how good is this craw" sources — unlabeled, the page implies a customer's craw was scored on Crawfish's bench.

### CLI — bench fixtures

- **O2.10 (fixtures)** — Bench fixtures per craw (`bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/`). Implements §15.3. The reference tickets and expected outcomes each curated craw is scored against, versioned next to the craw definitions. Public data; the per-craw page (DASH) links straight to these fixtures.

**Reuses (already shipped — do not rebuild):**
- GRAND_PLAN §3.11 cost-manager alerting (`PLAT`) — the alerting mechanism §15.5 AC cites; O6.10 reuses its sink and threshold logic.
- The classifier (O2.4, TRACK-3) — the thing re-evaluated weekly; the harness does not reimplement classification, only scores it.

---

## Key technical concepts, explained

**One eval-set store, two feeds (§15.1, §15.2).** The eval harness measures two things that look
distinct — current classifier accuracy, and the labeled set used to improve it — but they read from
one store. The store's ground truth comes from two sources: explicit human labels (§15.2) and the
manual overrides already produced in the classifier flow (TRACK-3 §3.3). An override is a label: when
a human re-files a ticket the classifier mis-filed, that correction is truth. Route overrides into the
same eval set rather than keeping a second one — two stores would drift and disagree on the same
ticket.

**Dry-run mode = a worker with every external side-effect intercepted as a no-op (§15.4).** This is
not a flag on the PR step. A craw mid-run makes many side-effecting calls — open PR, post comment,
push branch, set CI status. Dry-run means *every* one of those is intercepted and returns a synthetic
success without touching the outside world, so the craw runs end-to-end producing a report and nothing
external happens. Wrap the side-effecting tools:

```ts
// Wrap each external effect; in dry-run it records intent and returns a fake result.
function sideEffect<T>(real: () => Promise<T>, fake: () => T, dryRun: boolean): Promise<T> {
  if (dryRun) {
    report.record("would-have-called", fake);   // appears in the §15.4 report
    return Promise.resolve(fake());              // no PR, no comment, no push
  }
  return real();
}
```

This overlaps the durable-workflow side-effect boundary (TRACK-5 §5.1): the same idempotency-keyed
side-effect calls are exactly the ones that must become interceptable no-ops in dry-run. Build the
side-effect wrapper once and let both durability and dry-run use it.

**A 2σ regression alert needs N baseline runs before it can fire (§15.5).** "2σ below baseline" is
undefined without a baseline, and a baseline is meaningless with two data points. A new craw has no
history, so the alert must **suppress** until at least N runs exist (see `minRuns` above). Without the
guard, every new craw fires a spurious regression alert on its second run. The threshold is statistical,
so the minimum-sample rule is not optional — it is what makes the 2σ figure mean anything.

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§15.4 custom dry-run benchmark suite.** No numbered deliverable. O2.5's eval harness measures
  *classifier* accuracy, but replaying a customer's own tickets through actual *craw runs* in dry-run
  is a different, unbuilt path. *What's needed:* a first-class **side-effect-suppressed worker mode**
  (the `sideEffect` wrapper above), wired so every external call a craw makes is interceptable as a
  no-op, plus a report aggregator. This is non-trivial — it touches the worker's execution loop, not
  just the PR step — and shares its side-effect boundary with the durable workflow engine (TRACK-5
  §5.1), so it should be built on that boundary rather than parallel to it.

- **§15.6 tournament mode.** `[v1.5]`, token-expensive, flag-gated. No v1 O-stage. Depends on the
  multi-craw collab primitive (O3.1, TRACK-11) to run two craws on one task and compare by metric.
  Correctly deferred. *What's needed before it ships:* decide the budget interaction (below).

---

## Open questions

- **§15.6 budget accounting:** running two craws on one task doubles spend and must respect the
  per-task budget cap (TRACK-5 §5.6). Does tournament spend count once or twice against the org
  budget? Deferred to v1.5, but decide before it ships — the answer changes the budget-guard logic.
- **§15.4 vs §15.3 labeling:** the per-craw page surfaces three "how good is this" sources (public
  reference bench, customer custom suite, live stats). Confirm the page schema carries an explicit
  source label per score so a customer's dry-run result is never confused with Crawfish's published
  bench.
- **§15.5 baseline window:** is the 2σ baseline a fixed-N rolling window or a time window (e.g., last
  30 days)? A time window with sparse runs reintroduces the small-sample problem; pick the window
  semantics with the `minRuns` guard in mind.
