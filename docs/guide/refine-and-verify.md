# Refine & Verify — iterate until good enough

Most agent work isn't one shot. A draft reply, a generated patch, a summary — you
want the agent to **keep trying until the result clears a bar**, but never past a few
tries or a dollar ceiling, and you want a crash mid-loop to resume for free instead of
re-running from scratch. That is exactly what `Refine` and `Verifier` give you.

This is the **control plane** of the agent language: a bounded, metered, durable
*iterate-until-goal* loop whose stop signal is an **external critic that had to earn the
authority to stop it**. Everything on this page is real public API, importable from the
top-level package, and runs deterministically under `MockRuntime`.

On this page:

- [The shape of the loop](#the-shape-of-the-loop)
- [Stop conditions](#stop-conditions) — `RubricThreshold`, `PredicateStop`, `VerifierStop`
- [Verifier — a critic that earns the right to stop you](#verifier-a-critic-that-earns-the-right-to-stop-you)
- [Worked example — draft, verify, refine](#worked-example-draft-verify-refine) (mirrors the triage demo)
- [Durable, $0 crash-resume](#durable-0-crash-resume)
- [What stays static (the security spine)](#what-stays-static-the-security-spine)

## The shape of the loop

`Refine` wraps a producing **body** `Definition`, runs it, checks each frozen `Output`
against a `StopCondition` (`until=...`), and repeats — feeding the prior attempt back as
a **fluid** input — until the condition is satisfied **or** a bound is hit:

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

The loop is bounded by four things and **never by wall-clock**:

| Bound | What stops it |
| --- | --- |
| `max_iters` | a hard ceiling on body runs |
| the shared `CostBudget` | each inner run is preflighted against `remaining_usd`; the loop stops without exceeding the cap by more than one worst-case call |
| cooperative cancel | `CancelToken` checked before each iteration |
| no-progress | a `progress()` delta inside the calibrated noise band (`rubric_std`) for `no_progress_patience` iterations counts as stuck |

`Refine` **mutates nothing**. Every attempt is a fresh frozen `Output` (copy-on-write
via `Output.derive`); the body stays frozen — this is eval mode. The result is a frozen
`RefineResult` carrying the accepted (or best-ranked) `output`, `refine_iters`,
`spent_usd` (the true delta charged to the shared budget — not a hard-coded `0.0`), the
`refine_stopped` reason (`"satisfied"`, `"exhausted"`, `"no_progress"`, or `"stuck"`),
and `best_progress`.

!!! note "`feature_loop` reads the same"

    `feature_loop(body, *, until, max_iters, **kwargs)` is a keyword-only alias for
    `Refine(...)` from the vision vocabulary — it reads as "loop this feature body until
    `until`, but never past `max_iters`."

## Stop conditions

The stop signal is **external** to the body by design — the generator can't decide it's
done. Three `StopCondition`s ship:

```python
from crawfish import RubricThreshold, PredicateStop, VerifierStop
```

- **`RubricThreshold(rubric, *, metric, at_least)`** — stop when a `Rubric` metric clears
  a threshold. `progress()` is the metric value, so the loop also tracks improvement for
  no-progress detection.
- **`PredicateStop(predicate, *, progress=None)`** — stop when a typed predicate over the
  `Output` is true. Supply an optional `progress` function to enable no-progress
  detection.
- **`VerifierStop(verifier)`** — delegate the stop decision to a **gated** `Verifier`
  (below). This is the path you reach for when "good enough" is a *judgement*, not a
  numeric threshold.

!!! warning "The generator may never critique itself"

    A `Refine` built with a `VerifierStop` whose critic `Definition` shares the body's
    `content_sha()` is rejected at construction. A model grading its own work is not an
    external signal.

## Verifier — a critic that earns the right to stop you

A `Verifier` is a critic that judges an `Output` against a **closed label set with a
mandatory `default`** (mirroring `Router`/`Classifier`). An unparseable critic emission
maps to `default` — never a silent pass.

The load-bearing idea: **gating authority is typed and must be earned.** A bare
`Verifier` is in `WARN`/`SHADOW` and **cannot stop a loop** (`can_block` is `False`).
Only `Verifier.gated(...)` admits a `GatedVerifier` (stage `BLOCK`, `can_block == True`)
— and only after the critic clears an **absolute-precision** bar against a decision
`GoldenSet`. The gate **fails closed**: a never-benchmarked critic (no baseline) raises
`VerifierNotGated`, and so does one below `min_precision`.

```python
from crawfish import Verifier, VerifierStop

# This RAISES VerifierNotGated unless the critic clears min_precision against `golden`
# AND a precision baseline exists in the store — fail-closed by design.
critic = Verifier.gated(
    critic_definition,
    golden,                            # decision GoldenSet (case.output = critic label,
    labels=["accept", "revise"],       #                     case.label  = ground truth)
    default="revise",                  # unparseable emission -> revise, never accept
    accept_label="accept",
    min_precision=0.9,
    store=store,
)
assert critic.can_block            # only a GatedVerifier reaches here
stop = VerifierStop(critic)        # now usable as a Refine stop signal
```

A `Verdict` is a frozen `(label, tainted, source_output_id, lineage)`. A verdict over
fluid (untrusted) data is itself **tainted**, so a consequential consumer can refuse to
treat a fluid-derived verdict as trusted ground truth.

!!! note "A critic is as consequential as a Sink"

    Stopping a `Refine` loop ships the result downstream — so the authority to stop is
    treated like the authority to write. A critic earns `BLOCK` the way a `Sink` earns
    a static target: by passing a fail-closed gate, not by asserting it.

## Worked example — draft, verify, refine

This mirrors the triage demo end to end: a triage agent **drafts a reply**, a gated
`Verifier` **judges** it, and `Refine` **iterates** until the verifier accepts or a
budget / `max_iters` bound is hit — checkpointing each iteration so a crash resumes for
`$0`.

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

# 1. The critic earns gating authority (fails closed if it can't).
reply_ok = Verifier.gated(
    reply_critic,                      # a DISTINCT Definition from the drafter
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

# 3. One shared budget is threaded into every inner run — the loop stops at the cap.
ctx = RunContext(store=store, cost_budget=CostBudget(usd=0.50))
ledger = ExecutionLedger(store)

result = await loop.execute(seed_ticket, ctx, MockRuntime(), ledger=ledger)

print(result.refine_stopped)   # "satisfied" | "exhausted" | "no_progress" | "stuck"
print(result.refine_iters)     # body runs actually executed this invocation
print(result.spent_usd)        # the true delta charged to the shared budget
```

Because the run uses `MockRuntime`, it needs no key and the iteration count and output
sha are deterministic. Swap in `CommandRuntime` to run against real `claude -p`.

## Durable, $0 crash-resume

Pass an `ExecutionLedger` (and `resume=True` on the restart) and `Refine` checkpoints
**each completed iteration's frozen `Output`** into the F-2 composite-key ledger. A loop
that crashes at iteration 3 of 5 restarts at iteration 4 re-paying **`$0`**:

```python
ledger = ExecutionLedger(store)

# First process: crashes after iterations {0, 1} are checkpointed.
result = await loop.execute(seed, ctx, runtime, ledger=ledger)        # ... dies

# Second process, SAME ledger: replays committed iterations at $0, continues fresh.
result = await loop.execute(seed, ctx, runtime, ledger=ledger, resume=True)
assert ctx.cost_budget.spent_usd == 0.0   # replayed iterations charge nothing
```

How this is sound rather than trusted:

- The **loop id is deterministic** — `compute_loop_id(body.content_sha(), item_lineage,
  edge_id)`, never a fresh id — so two process invocations re-derive the same id.
- On resume, completed visits are **re-run through the replay runtime**, which returns
  the cached `RunResult` at **zero cost**.
- An iteration's `Output.produced_by` is the deterministic `body.content_sha()#visit`
  coordinate (not a volatile `Run.id`), so the replayed Output's content sha reproduces
  the checkpointed reference **bit-for-bit**. Determinism is content-hash *verified*.
- The per-iteration checkpoint is written only after **both** the body `Output` and (for
  a `VerifierStop`) its verdict are in hand — a crash between them re-runs that iteration
  (replaying `$0`) rather than skipping the verifier or double-charging.

Every ledger row carries `org_id`, so a cross-tenant resume cannot see another org's
completed iterations.

## What stays static (the security spine)

`Refine` and `Verifier` hold the prompt-injection boundary the same way the rest of the
framework does — see the [static-vs-fluid boundary](concepts.md#the-static-vs-fluid-prompt-injection-boundary).

- The prior attempt is fed back under a **static** `feedback_key` as a **FLUID** input.
  Taint propagates; it stays in the labelled data block, never an instruction slot.
- The bound (`max_iters`, `$X`), the verifier identity, the `feedback_key`, the
  `accept_label`, and the coordinate keys are **static** — never derived from fluid input.
- A critic's emission is parsed **as data** against the static, trusted label set. An
  injected or undeclared label cannot widen the set; the worst it can do is fall to
  `default`.

## Next steps

- [Concepts → The control plane](concepts.md#the-control-plane-refine-and-verify) — how
  Refine advances the one-stochastic-primitive thesis.
- [API reference](api-reference.md) — every public symbol, including `Refine`,
  `RefineResult`, the `StopCondition`s, `Verifier`, `GatedVerifier`, `Verdict`, and
  `VerifierStage`.
- [Evals](../reference/evals.md) — building the decision `GoldenSet` a gated `Verifier`
  is measured against.
