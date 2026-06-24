# Refine & Verify — the control plane

`Refine` is a bounded, metered, durable **iterate-until-goal** loop over a producing
`Definition`. `Verifier` is the critic that can stop it — but only after it has *earned*
the authority to. Together they are the control plane of the agent language: a loop that
wraps the one stochastic primitive (a model `Run`) without giving up determinism,
typing, metering, or durability.

`StopCondition` · `RubricThreshold` · `PredicateStop` · `VerifierStop` · `RefineResult` ·
`Refine` · `feature_loop` · `VerifierStage` · `Verdict` · `Verifier` · `GatedVerifier`

These live in `crawfish.refine` and `crawfish.verifier`, and all re-export from the
top-level `crawfish` package.

## Refine — the loop

`Refine(body, until, *, max_iters, ...)` runs the `body` `Definition`, checks each frozen
`Output` against `until` (a `StopCondition`), and repeats — feeding the prior attempt back
as a **fluid** input under a static `feedback_key` — until satisfied or a bound is hit.

It generalises the three fixed-bound re-run atoms (`EscalatingRuntime` = 2×,
`Run._repair` = +1, `RetryPolicy` = on-exception) into one goal-driven operator. It
mutates nothing: every attempt is a fresh frozen `Output` via copy-on-write `derive`, and
the body stays frozen (eval mode).

```python
from crawfish import Refine, RubricThreshold

loop = Refine(
    body=draft_reply,
    until=RubricThreshold(quality_rubric, metric="helpfulness", at_least=0.8),
    max_iters=4,
)
result = await loop.execute(seed, ctx, runtime)
```

### Bounds

The loop is bounded by `max_iters`, the shared `CostBudget`, cooperative cancel, and
noise-aware no-progress — **never** by wall-clock.

- **Metering.** The **one shared** `CostBudget` is threaded into every inner `Run` (never
  a fresh `RunContext`); each call is preflighted against `remaining_usd`, so the loop
  stops without exceeding the cap by more than one worst-case call. `spent_usd` is the
  true delta charged to the shared budget over the invocation.
- **No-progress.** A `progress()` delta within the calibrated band (`rubric_std`) counts
  as no progress — compared on the ranking delta, never a byte-identical sha — and the
  loop stops after `no_progress_patience` such iterations.

### Determinism

Exactly one stochastic leaf per iteration: the body `Run` (plus the verifier's own leaf
for a `VerifierStop`). The loop counter, stop check, no-progress, and best-tracking are
pure. An iteration's `Output.produced_by` is the **deterministic** `body.content_sha()#visit`
coordinate, not a volatile `Run.id`, so a second-process resume reproduces a bit-identical
Output.

### `RefineResult`

A frozen result carrying:

| Field | Meaning |
| --- | --- |
| `output` | the accepted attempt, or the best-ranked one on exhaustion |
| `refine_iters` | body runs actually executed this invocation (replayed-on-resume iterations are not re-counted) |
| `spent_usd` | the true delta charged to the shared budget this invocation |
| `refine_stopped` | `"satisfied"` · `"exhausted"` · `"no_progress"` · `"stuck"` |
| `best_progress` | the best `progress()` value seen |

## Stop conditions

A `StopCondition` is the **external** stop signal — `async satisfied(output, ctx, runtime)
-> bool` plus a pure `progress(output) -> float`. Three ship:

- **`RubricThreshold(rubric, *, metric, at_least)`** — satisfied when a `Rubric` metric
  clears `at_least`; `progress()` is that metric.
- **`PredicateStop(predicate, *, progress=None)`** — satisfied when a typed predicate over
  the `Output` is true; supply `progress` to enable no-progress detection.
- **`VerifierStop(verifier)`** — satisfied when a **gated** `Verifier` accepts the Output.
  Constructing a `Refine` whose `VerifierStop` critic shares the body's `content_sha()`
  raises at assembly — self-critique is forbidden.

## Verifier — the gated critic

A `Verifier` wraps a critic `Definition` (own version/knobs, optional `Rubric`) and emits
a `verdict(output)` over a **closed label set with a mandatory `default`** (mirrors
`Router`/`Classifier`). An unparseable critic emission yields `default`, never a silent
pass.

Gating authority is **typed**. A bare `Verifier` is in `WARN`/`SHADOW`; `can_block` is
`False` and it **cannot** stop a loop. It cannot even start in `BLOCK` — that raises.

```python
from crawfish import Verifier

bare = Verifier(
    critic_definition,
    labels=["accept", "revise"],
    default="revise",
    accept_label="accept",
)            # stage WARN; bare.can_block is False
```

### Earning the gate — `Verifier.gated`

`Verifier.gated(definition, golden, *, labels, default, accept_label, min_precision, ...)`
is the only path to a `GatedVerifier` (stage `BLOCK`, `can_block == True`,
`measured_precision` recorded). It measures the critic's **absolute precision**
`TP / (TP + FP)` against a decision `GoldenSet` and admits **only if** precision clears
`min_precision` **and** a precision baseline exists.

It **fails closed** — this closes the CL-2 safety inversion (a never-benchmarked critic
must not be admitted to *block* production):

- no `Store` / no baseline stored ⇒ raises `VerifierNotGated`
- precision below `min_precision` ⇒ raises `VerifierNotGated`

The golden cases carry the critic's label as `output` and ground truth as `label`; the
computation is pure given the golden set (the cases were already labelled under replay).

### `Verdict`

A frozen `(label, tainted, source_output_id, lineage)`. A verdict over fluid (untrusted)
data is itself **tainted**, so a consequential consumer can refuse to treat a fluid-derived
verdict as trusted ground truth.

### `VerifierStage`

`SHADOW` (observed only) · `WARN` (surfaced, still cannot stop) · `BLOCK` (gated; may stop
a `Refine` loop, as consequential as a `Sink`).

## Durable, $0 crash-resume

Pass an `ExecutionLedger` and, on restart, `resume=True`:

```python
await loop.execute(seed, ctx, runtime, ledger=ledger)               # crashes mid-loop
await loop.execute(seed, ctx, runtime, ledger=ledger, resume=True)  # resumes at $0
```

Each completed iteration's frozen `Output` is checkpointed via
`ExecutionLedger.checkpoint_iteration(...)`. The `loop_id` is deterministic
(`compute_loop_id(body.content_sha(), item_lineage, edge_id)`), so two process invocations
re-derive it. On resume, committed visits re-run through the replay runtime and return the
cached `RunResult` at **zero cost**; the replayed Output's content sha reproduces the
checkpoint bit-for-bit, so determinism is content-hash *verified*, not trusted.

The checkpoint is written only after both the body `Output` and (for a `VerifierStop`) its
verdict are in hand — atomic, so a crash between them re-runs that iteration rather than
skipping the verifier or double-charging. Every ledger row carries `org_id`; a cross-tenant
resume cannot see another org's iterations.

## Security spine

- The prior attempt feeds back under a **static** `feedback_key` as a **FLUID** input;
  taint propagates, and it stays in the labelled data block, never an instruction slot.
- The bound (`max_iters`, `$X`), the verifier identity, the `feedback_key`, the
  `accept_label`, and the coordinate keys are static — never derived from fluid input.
- A critic's emission is parsed **as data** against the static, trusted label set; an
  injected/undeclared label cannot widen the set (worst case: `default`). A verdict over a
  tainted Output is itself tainted.

## API reference

| Symbol | Kind | Purpose |
| --- | --- | --- |
| `StopCondition` | ABC | External stop signal: `async satisfied(output, ctx, runtime) -> bool`, `progress(output) -> float`. |
| `RubricThreshold(rubric, *, metric, at_least)` | class | Stop when a `Rubric` metric clears `at_least`. |
| `PredicateStop(predicate, *, progress=None)` | class | Stop when a typed predicate over the Output is true. |
| `VerifierStop(verifier)` | class | Stop when a **gated** `Verifier` accepts the Output. |
| `RefineResult` | frozen dataclass | `output`, `refine_iters`, `spent_usd`, `refine_stopped`, `best_progress`. |
| `Refine(body, until, *, max_iters, feedback_key="_refine_feedback", no_progress_patience=1, rubric_std=0.0, on_stuck="return_best", edge_id="refine", name="refine")` | class | The bounded/metered/durable iterate-until-goal loop. |
| `Refine.execute(seed, ctx, runtime, *, ledger=None, resume=False, produce=None)` | method | Run the loop; `ledger` enables durable checkpointing, `resume=True` replays committed iterations at `$0`. |
| `feature_loop(body, *, until, max_iters, **kwargs)` | function | Keyword-only alias for `Refine(...)`. |
| `VerifierStage` | enum | `SHADOW` · `WARN` · `BLOCK`. |
| `Verdict` | frozen dataclass | `label`, `tainted`, `source_output_id`, `lineage`. |
| `Verifier(definition, *, labels, default, accept_label, rubric=None, stage=WARN, name, registry=None)` | class | A bare critic; `verdict(...)`, `accepts(...)`, `can_block == False`. |
| `Verifier.gated(definition, golden, *, labels, default, accept_label, min_precision, decide=None, store=None, baseline_name=None, rubric=None, name, registry=None)` | classmethod | Admit a `GatedVerifier` — fails closed without a baseline or below `min_precision`. |
| `GatedVerifier` | class | A `Verifier` at stage `BLOCK`; `can_block == True`, carries `measured_precision`. |

## See also

- [Refine & Verify guide](../guide/refine-and-verify.md) — runnable walkthrough mirroring
  the triage demo.
- [Concepts → The control plane](../guide/concepts.md#the-control-plane-refine-and-verify).
- [Evals](evals.md) — the decision `GoldenSet` a gated `Verifier` is measured against.
- [Persistence](persistence.md) — the `ExecutionLedger` that backs `$0` resume.
