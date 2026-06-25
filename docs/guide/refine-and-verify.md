# Refine and verify

You can run an agent step in a loop until the result is good enough, with a hard cap on
tries and spend, and a crash mid-loop resumes for free. This page shows how to build that
loop with `Refine` and `Verifier`.

A *refine loop* runs a producing step, checks the result against a stop condition, and runs
again if the result falls short. The stop signal comes from outside the step, so the model
that produces the work does not get to decide that it is done.

You will learn how to:

- Build a loop with `Refine` and bound it so it always terminates.
- Choose a stop condition: a rubric threshold, a predicate, or a verifier.
- Gate a `Verifier` so only a benchmarked critic can stop a loop.
- Resume a crashed loop for $0.

Every symbol on this page imports from the top-level `crawfish` package and runs
deterministically under `MockRuntime`.

## Build the loop

`Refine` wraps a producing *body* (a `Definition`), runs it, and checks each frozen `Output`
against a stop condition passed as `until=`. If the condition is not met, it feeds the prior
attempt back in and runs the body again, until the condition holds or a bound is hit.

```python
from crawfish import Refine, RubricThreshold

loop = Refine(
    body=draft_reply,                 # a producing Definition
    until=RubricThreshold(quality_rubric, metric="helpfulness", at_least=0.8),
    max_iters=4,                      # never more than 4 body runs
)
result = await loop.execute(seed, ctx, runtime)   # -> RefineResult
print(result.refine_stopped, result.refine_iters, result.spent_usd)
```

Four bounds stop the loop. None of them is wall-clock time.

| Bound | What stops it |
| --- | --- |
| `max_iters` | a hard ceiling on body runs |
| the shared `CostBudget` | each inner run is checked against `remaining_usd` before it runs; the loop stops without exceeding the cap by more than one worst-case call |
| cooperative cancel | the `CancelToken` is checked before each iteration |
| no progress | a `progress()` delta inside the calibrated noise band (`rubric_std`) for `no_progress_patience` iterations counts as stuck |

`Refine` changes nothing in place. Each attempt is a fresh frozen `Output` (a copy made with
`Output.derive`), and the body stays frozen. The result is a frozen `RefineResult` that
carries the accepted output, `refine_iters`, `spent_usd` (the real amount charged to the
shared budget, not a hard-coded zero), a `refine_stopped` reason (`"satisfied"`,
`"exhausted"`, `"no_progress"`, or `"stuck"`), and `best_progress`.

`feature_loop(body, *, until, max_iters, **kwargs)` is a keyword-only alias for `Refine(...)`
that reads as "loop this body until `until`, but never past `max_iters`."

## Choose a stop condition

The stop signal is external to the body, so the generator cannot decide it is done. Three
stop conditions ship.

```python
from crawfish import RubricThreshold, PredicateStop, VerifierStop
```

- `RubricThreshold(rubric, *, metric, at_least)` stops when a `Rubric` metric clears a
  threshold. The metric value is `progress()`, so the loop also tracks improvement for
  no-progress detection.
- `PredicateStop(predicate, *, progress=None)` stops when a typed predicate over the `Output`
  is true. Supply an optional `progress` function to enable no-progress detection.
- `VerifierStop(verifier)` hands the stop decision to a gated `Verifier` (below). Reach for
  this when "good enough" is a judgement, not a number.

!!! warning "The generator may never grade itself"

    A `Refine` built with a `VerifierStop` whose critic shares the body's `content_sha()` is
    rejected when you construct it. A model grading its own work is not an external signal.

## Gate a verifier

A `Verifier` is a critic that judges an `Output` against a closed set of labels with a
required `default` (the same shape as `Router` and `Classifier`). An emission the critic
cannot parse maps to `default`, never to a silent pass.

A verifier must earn the authority to stop a loop. A bare `Verifier` is in `WARN` or `SHADOW`
stage and cannot stop a loop (`can_block` is `False`). Only `Verifier.gated(...)` returns a
`GatedVerifier` (stage `BLOCK`, `can_block == True`), and only after the critic clears a
precision bar against a decision `GoldenSet`. The gate fails closed: a critic that was never
benchmarked (no baseline) raises `VerifierNotGated`, and so does one below `min_precision`.

```python
from crawfish import Verifier, VerifierStop

# Raises VerifierNotGated unless the critic clears min_precision against `golden`
# AND a precision baseline exists in the store. This fails closed by default.
critic = Verifier.gated(
    critic_definition,
    golden,                            # decision GoldenSet (case.output = critic label,
    labels=["accept", "revise"],       #                     case.label  = ground truth)
    default="revise",                  # an unparseable emission becomes revise, never accept
    accept_label="accept",
    min_precision=0.9,
    store=store,
)
assert critic.can_block            # only a GatedVerifier reaches here
stop = VerifierStop(critic)        # now usable as a Refine stop signal
```

A `Verdict` is a frozen `(label, tainted, source_output_id, lineage)`. A verdict over fluid
(untrusted) data is itself tainted, so a downstream consumer can refuse to treat a
fluid-derived verdict as trusted ground truth.

Stopping a loop ships the result downstream, so the authority to stop is treated like the
authority to write. A critic earns `BLOCK` the way a sink earns a static target: by passing a
fail-closed gate, not by asserting it.

## Worked example: draft, verify, refine

This mirrors the triage demo. A triage agent drafts a reply, a gated `Verifier` judges it,
and `Refine` iterates until the verifier accepts or a budget or `max_iters` bound is hit. Each
iteration is checkpointed, so a crash resumes for $0.

```python
from crawfish import (
    CostBudget,
    ExecutionLedger,
    MockRuntime,
    Refine,
    RunContext,
    SqliteStore,
    Verifier,
    VerifierStop,
)

store = SqliteStore()

# 1. The critic earns gating authority (fails closed if it cannot).
reply_ok = Verifier.gated(
    reply_critic,                      # a distinct Definition from the drafter
    reply_golden,
    labels=["accept", "revise"],
    default="revise",
    accept_label="accept",
    min_precision=0.9,
    store=store,
)

# 2. Refine: draft -> verify -> refine, bounded by budget AND max_iters.
loop = Refine(
    body=draft_reply,                  # the triage drafter Definition
    until=VerifierStop(reply_ok),
    max_iters=5,
)

# 3. One shared budget is threaded into every inner run. The loop stops at the cap.
ctx = RunContext(store=store, cost_budget=CostBudget(usd=0.50))
ledger = ExecutionLedger(store)

result = await loop.execute(seed_ticket, ctx, MockRuntime(), ledger=ledger)

print(result.refine_stopped)   # "satisfied" | "exhausted" | "no_progress" | "stuck"
print(result.refine_iters)     # body runs actually executed this invocation
print(result.spent_usd)        # the real amount charged to the shared budget
```

Because the run uses `MockRuntime`, it needs no API key, and the iteration count and output
hash are deterministic. Swap in `CommandRuntime` to run against real `claude -p`.

## Resume a crashed loop for $0

Pass an `ExecutionLedger` (and `resume=True` on the restart), and `Refine` checkpoints each
completed iteration's frozen `Output` into the ledger. A loop that crashes at iteration 3 of 5
restarts at iteration 4 and pays $0 for the work already done.

```python
ledger = ExecutionLedger(store)

# First process: crashes after iterations {0, 1} are checkpointed.
result = await loop.execute(seed, ctx, runtime, ledger=ledger)        # ... dies

# Second process, SAME ledger: replays committed iterations at $0, continues fresh.
result = await loop.execute(seed, ctx, runtime, ledger=ledger, resume=True)
assert ctx.cost_budget.spent_usd == 0.0   # replayed iterations charge nothing
```

Resume is checked, not trusted, in four ways:

- The loop id is deterministic: `compute_loop_id(body.content_sha(), item_lineage, edge_id)`,
  never a fresh id, so two process invocations re-derive the same id.
- On resume, completed iterations are re-run through the replay runtime, which returns the
  cached `RunResult` at zero cost.
- An iteration's `Output.produced_by` is the deterministic `body.content_sha()#visit`
  coordinate, not a volatile `Run.id`, so the replayed output's content hash reproduces the
  checkpointed reference exactly.
- The per-iteration checkpoint is written only after both the body `Output` and (for a
  `VerifierStop`) its verdict are in hand. A crash between them re-runs that iteration
  (replaying for $0) rather than skipping the verifier or charging twice.

Every ledger row carries `org_id`, so a resume in one tenant cannot see another tenant's
completed iterations.

## What stays static

`Refine` and `Verifier` hold the prompt-injection boundary the same way the rest of Crawfish
does. See [the static-versus-fluid boundary](concepts.md#static-versus-fluid). A *static*
value is fixed in your code; a *fluid* value is untrusted session data that reaches the model
as data, never as instructions.

- The prior attempt is fed back under a static `feedback_key` as a fluid input. Taint
  propagates with it; it stays in the labelled data block, never in an instruction slot.
- The bound (`max_iters`, the dollar cap), the verifier identity, the `feedback_key`, the
  `accept_label`, and the coordinate keys are all static. None is derived from fluid input.
- A critic's emission is parsed as data against the static, trusted label set. An injected or
  undeclared label cannot widen the set; the worst it can do is fall to `default`.

## Next steps

- [Compose](compose.md): branch, cycle, and recurse over the loop these operators build on.
- [API reference](api-reference.md): every public symbol, including `Refine`, `RefineResult`,
  the stop conditions, `Verifier`, `GatedVerifier`, `Verdict`, and `VerifierStage`.
- [Evals](../reference/evals.md): building the decision `GoldenSet` a gated `Verifier` is
  measured against.
