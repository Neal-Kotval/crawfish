# Cookbook

Copy-paste recipes for common Crawfish tasks. Each recipe states what it does in one line, then shows the code. Every symbol used here is in the public API (`crawfish.__all__`). The runs use `MockRuntime`, so they need no key and stay deterministic. Swap in `CommandRuntime` to run against real `claude -p`.

## Fan out over N items

Run one agent per item in a collection.

```python
from crawfish import Batch, Definition, MockRuntime, RepoSource, RunContext, SqliteStore

batch = Batch(Definition.from_package("definitions/triage-bot"))
batch.add_input(RepoSource("repo", config={"repo": "acme/app"}))
batch.add_input(my_multi_source)          # multi=True -> one Run per item
outputs = await batch.run(RunContext(store=SqliteStore()), MockRuntime())
```

## Fan in with an aggregator

Combine many outputs into one.

```python
from crawfish import Aggregator, collect

agg = Aggregator(collect)                 # also: concat, count, dedupe
digest = await agg.reduce(outputs, ctx)   # N Outputs -> 1
```

## Branch with a router

Send each output to a different sink based on its content.

```python
from crawfish import Classifier, Router

clf = Classifier.from_predicates(
    {"bug": lambda v: v["kind"] == "bug", "question": lambda v: v["kind"] == "question"},
    default="dead_letter",
)
router = Router({"bug": pr_sink, "question": slack_sink, "dead_letter": dlq}, clf)
label, branch = router.route(output)      # uncovered label -> rejected at assembly
```

!!! warning

    A sink's destination (repo, project, channel) must be `Flow.STATIC`. A fluid target is rejected at construction, so a model-influenced value can never redirect where a write lands.

## Dedup across runs with memory

Process each item only once, even across separate runs.

```python
from crawfish import Memory

mem = Memory.for_run(ctx, "triage")
if mem.claim(ticket_id):                  # True only the first time, persists in the Store
    await process(ticket_id)
```

`claim` wins exactly once per id and persists in the `Store`, so dedup survives across separate runs, not only within one batch.

## Retries and dead-letter at scale

Keep a large batch running when individual items fail, then re-run only the failures.

```python
from crawfish import BatchExecutor, RetryPolicy

ex = BatchExecutor(definition, max_concurrency=8, retry_policy=RetryPolicy(max_attempts=3))
result = await ex.run(batch, ctx, MockRuntime())
# a failing item lands in result.dead_letters; the batch never halts
await ex.replay(batch, ctx, MockRuntime())  # re-runs only the failures (idempotent)
```

## Cost preview before running

Estimate what a batch will cost before you spend anything.

```python
from crawfish import estimate_cost

est = estimate_cost(definition, items=500)
print(est.total_usd)                      # dry-run preview; or `craw dev <path> --estimate`
```

## Eval-as-test

Turn an output-quality rubric into a pass/fail check your CI can run.

```python
from crawfish import Rubric, field_present, assert_rubric

assert_rubric(output, Rubric([field_present("review")]), {"field_present(review)": 1.0})
```

## Snapshot and record/replay testing

Test outputs against a saved snapshot and replay recorded model calls offline.

```python
from crawfish import assert_snapshot, replaying, MockRuntime

assert_snapshot("snapshots/triage.json", output.value)        # fails on drift
runtime = replaying(MockRuntime(), "cassettes", record=False)  # replays, never calls a model
```

## Gate a new version against a baseline

Block a new Definition version if its scores regress against a saved baseline.

```python
from crawfish import gate_against_baseline, save_baseline

save_baseline(store, "triage", baseline_scores)
assert gate_against_baseline(store, "triage", candidate_scores)  # False if it regressed
```

## Next steps

- [Concepts](concepts.md): the model behind these recipes.
- [API reference](api-reference.md): every symbol used above.
- [Reference index](../reference/index.md): deep pages on nodes, evals, persistence, and secrets.
