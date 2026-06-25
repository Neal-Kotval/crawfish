# Compose: branch, cycle, and recurse

A single `Refine` loop iterates one body. Real agent work has shape: tickets branch by type
into different sub-pipelines, some loop back to be re-extracted until they converge, and a
multi-part ticket fans out into a bounded recursion. The composition operators let you author
that shape as a typed, durable graph, and a crash anywhere in it resumes for $0.

You will learn how to:

- Route each item to a different branch with `branch()`.
- Build a graph whose edges may cycle with `Program`.
- Bound a cycle so it always terminates.
- Express recursive work with `recurse()`.

Every symbol on this page imports from the top-level `crawfish` package and runs
deterministically under `MockRuntime`.

## branch(): a runnable router step

A `Router` chooses one labelled branch per item using a `Classifier` (see
[the pipeline](concepts.md#the-pipeline)). `branch()` is a readable constructor that makes a
router a runnable composition step. Each item is classified and dispatched through the same
step machinery as its chosen branch, so a branch may itself be a `Sink`, `Batch`, `Filter`, or
`Aggregator` and inherits the same budget, taint, and checkpoint behaviour.

```python
import crawfish as cw

route = cw.branch(
    classifier,                        # a Classifier: from_predicates (pure) or from_definition
    {
        "bug": bug_pipeline,           # each branch is any Node: Sink/Batch/Filter/Aggregator
        "billing": billing_pipeline,
        "default": dead_letter,        # the closed label set always covers a default
    },
    name="triage-router",
)
```

The label set is closed and checked for totality when you construct the router: an uncovered
label raises `UnroutableLabelError` before any model call. When you wire the router into a
`Workflow` or `Program`, `check_types` verifies that every branch accepts the upstream output;
a branch that cannot raises `WireError` at assembly. Predicate routing is pure (zero model
calls, `spent == 0`); a Definition-backed classifier is one leaf run charged to the shared
budget.

## Program: a typed cyclic graph

A `Workflow` runs its steps once, top to bottom. A `Program` is a `Workflow` whose edges may
cycle. You register graph nodes with `.step(...)` and wire directed edges with `.edge(...)`. A
*back-edge* (a target earlier than its source) re-enters the region between target and source
while a guard predicate holds.

The common shape is extract, then review, with a `review` back to `extract` edge that fires
only while the reviewer reports a mismatch.

```python
import crawfish as cw

prog = cw.Program(name="ap-clerk", version="0.1")

extract = prog.step(extract_fields)        # a Batch over a Definition
review = prog.step(review_fields)          # a Router/Definition emitting a label

prog.edge(extract, review)                 # forward edge
prog.edge(
    review, extract,                       # back-edge: re-enter [extract .. review]
    when=lambda label, out: label == "mismatch",   # loop while the reviewer disagrees
    max_visits=3,                          # REQUIRED on a back-edge (see below)
)

outputs = await prog.run(seed_prompt, ctx=ctx, runtime=cw.MockRuntime())
```

The driver walks edges per item rather than running each step once in order. Each back-edge
traversal mints a new content-addressed version (with `Output.derive`, no in-place mutation;
the frozen `Output` rejects edits) and records its content hash at a deterministic ledger
coordinate `{region_version}#{edge_id}#{visit}`, never a volatile `Run.id`. One shared
`CostBudget` meters every iteration, and taint carries across every cycle edge.

`Program.check_types` runs the linear adjacency check, then per edge verifies that the
back-edge target structurally accepts the source's output (via `crawfish.typesystem`, never
string equality), raising `WireError` otherwise.

## Bound a cycle

Four bounds stop a `Program`. None of them is wall-clock time.

| Bound | What stops the cycle |
| --- | --- |
| `max_visits` | a hard ceiling on back-edge traversals, required at assembly: an unbounded back-edge raises `UnboundedCycleError` when you construct it |
| the shared `CostBudget` | each iteration is checked against `remaining_usd` before it runs; the loop stops at the cap |
| cooperative cancel | the `CancelToken` is checked before each iteration |
| calibrated no-progress | an `Edge.progress` ranking delta within the noise band (`rubric_std`) for `no_progress_patience` iterations counts as stuck |

When a bound trips while the guard is still true, the edge takes its `on_stuck` action:
`"return_last"` (the default) or `"dead_letter"`. The result is a frozen `ProgramResult` that
carries the final output, the per-edge `visits` count, and the `stopped` reason
(`"converged"`, `"max_visits"`, `"budget"`, `"no_progress"`, or `"stuck"`).

!!! warning "A back-edge must declare its ceiling"

    `prog.edge(review, extract, when=...)` without `max_visits` raises `UnboundedCycleError`
    at assembly. A cycle with no ceiling could loop forever, so the bound is the argument that
    it terminates, checked before it can run.

## Resume a crashed cycle for $0

Thread the run through a shared `Store` and pass `resume=True` on the restart. A `Program`
whose cycle crashes mid-iteration re-derives the committed iterations at $0 instead of paying
from scratch. This uses the same ledger substrate as `Refine`, so durable `Refine`, `Program`
loops, and `recurse` all come from one place.

```python
import crawfish as cw

store = cw.SqliteStore()
ctx = cw.RunContext(store=store, cost_budget=cw.CostBudget(usd=0.50))

# First process records and commits some iterations, then crashes mid-cycle.
await prog.run(seed_prompt, ctx=ctx, runtime=runtime)            # ... dies

# Second Program instance, SAME store: replays committed iterations at $0, continues fresh.
ctx2 = cw.RunContext(store=store, cost_budget=cw.CostBudget(usd=0.50))
await prog.run(seed_prompt, ctx=ctx2, runtime=runtime, resume=True)
assert ctx2.cost_budget.spent_usd == 0.0     # replayed iterations charge nothing
```

Resume is checked, not trusted:

- The loop id is deterministic: `compute_loop_id(region_version, item_lineage, edge_id)`,
  never a fresh id, so a second process re-derives the same coordinate. `region_version` folds
  the content hashes of the region's frozen Definitions.
- On resume, completed visits are re-run through the replay runtime, which returns the cached
  `RunResult` at zero cost.
- An iteration's `produced_by` is the deterministic `{region_version}#{edge_id}#{visit}`
  coordinate, so the replayed output's content hash must equal the checkpointed reference,
  bit for bit.

Every `ledger_loop` row carries `org_id`, so a resume in one tenant cannot see another
tenant's committed iterations.

## recurse(): bounded self-referential Definitions

Some work is recursive: a multi-part ticket splits into sub-tickets, each of which may split
again. `recurse()` expresses that as a depth-guarded back-edge that re-enters the same frozen
Definition, pushing a frozen version onto a per-item depth stack, then folding the
descent-order children into one output with a reducer.

```python
import crawfish as cw

rec = cw.recurse(
    body=split_ticket,                     # a FROZEN Definition (the recursive body)
    base_case=lambda out: not out.value["parts"],   # pure predicate: stop descending
    max_depth=4,                           # REQUIRED, distinct from a loop's max_visits
    combine=cw.collect,                    # fold the children: collect / count / dedupe
)
result = await rec.execute(seed, ctx, runtime)        # -> RecurseResult
print(result.depth_reached, result.stopped)
```

Each descent level runs the frozen `body` once, with the prior level fed in as a fluid input
(taint propagates, never an instruction), then derives a fresh content-addressed output with
`produced_by = {body.content_sha()}#{edge_id}#d{depth}`. Descent halts on `base_case`, on
`depth >= max_depth`, on budget, on cancel, or on calibrated no-progress, never on wall-clock
time. The frozen `RecurseResult` reports the folded output, the `depth_reached`, and why it
`stopped` (`"base_case"`, `"max_depth"`, `"budget"`, `"no_progress"`, or `"stuck"`).

Two rules make recursion safe to fund.

- `max_depth` is mandatory. A `None` bound raises `UnboundedRecursionError` when you construct
  it. Tree fan-out is `O(b^d)`, so the whole-tree shared budget is the real guard, checked at
  each descent and stopped on breach (`spent` reflects every level), and `max_depth` plus
  `base_case` are the argument that it terminates.
- A fold never launders taint. The reduced output is tainted if any child input was tainted
  (taint is the union). A vote or summary over fluid children stays fluid.

Resume is the depth version of the loop case: each level checkpoints into the ledger, so
resume at depth *k* replays `1..k-1` at $0, content-hash verified, with `org_id` on every row.

## What stays static

The composition operators hold the [static-versus-fluid
boundary](concepts.md#static-versus-fluid) the same way the rest of Crawfish does. A *static*
value is fixed in your code; a *fluid* value is untrusted session data that reaches the model
as data, never as instructions.

- A classifier label is a control signal, not a target. A fluid-derived label gates which
  static branch fires; the branch set is closed and static at assembly, so a fluid label can
  only select among pre-declared targets, never make a new one. A tainted item routed into a
  static-only `Sink` keeps its taint across the boundary.
- Bounds and coordinates are static. `max_visits`, `max_depth`, `edge_id`, `region_version`,
  and the back-edge `when` predicate are all static, never derived from fluid input. The `when` and `base_case` predicates read the frozen output as data.
- Every cycle and descent carries taint forward. A back-edge feeds the prior output back as
  fluid; a recursion feeds the prior level back as fluid. Taint propagates across every edge,
  and a fold unions it.

## Next steps

- [Refine and verify](refine-and-verify.md): the single-body control loop these operators
  compose onto.
- [Core concepts](concepts.md): the pipeline, the type system, and the static-versus-fluid
  boundary these operators build on.
- [API reference](api-reference.md): every public symbol, including `branch`, `Program`,
  `Edge`, `ProgramResult`, `recurse`, `Recurse`, `RecurseResult`, and the two unbounded
  errors.
