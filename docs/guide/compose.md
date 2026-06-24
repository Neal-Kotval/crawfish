# Compose — branch, cycle, and recurse

A single `Refine` loop is the control plane for *one* body. Real agent work has
**shape**: tickets branch by type into different sub-pipelines, some loop back to be
re-extracted until they converge, and a multi-part ticket fans into a bounded recursion.
The **composition surface** lets you author that shape as a typed, durable graph — and a
crash anywhere in it resumes for **\$0**.

This is the structural keystone of the agent language: control flow that is
**deterministic, versioned, and taint-tracked**. Cycles are *bounded and crash-resumable*;
recursion re-enters only **frozen** Definitions. Everything on this page is real public
API, importable from the top-level `crawfish` package, and runs deterministically under
`MockRuntime`.

On this page:

- [`branch()` — a runnable Router step](#branch-a-runnable-router-step)
- [`Program` — a typed cyclic graph](#program-a-typed-cyclic-graph)
- [Bounding a cycle](#bounding-a-cycle) — `max_visits`, budget, cancel, no-progress
- [Durable \$0 resume](#durable-0-resume)
- [`recurse()` — bounded self-referential Definitions](#recurse-bounded-self-referential-definitions)
- [What stays static (the security spine)](#what-stays-static-the-security-spine)

## `branch()` — a runnable Router step

A `Router` chooses one labelled branch per item with a `Classifier` (see
[Concepts → the pipeline](concepts.md#the-pipeline)). `branch()` is a thin, readable
constructor that makes a Router a **first-class, runnable composition step**: each item is
classified and dispatched through the **same** step machinery as its chosen branch, so a
branch may itself be a `Sink`, `Batch`, `Filter`, or `Aggregator` and inherits the
identical budget / taint / checkpoint guarantees.

```python
import crawfish as cw

route = cw.branch(
    classifier,                        # a Classifier: from_predicates (pure) or from_definition
    {
        "bug": bug_pipeline,           # each branch is any Node — Sink/Batch/Filter/Aggregator
        "billing": billing_pipeline,
        "default": dead_letter,        # the closed label set always covers a default
    },
    name="triage-router",
)
```

The label set is **closed and totality-checked at construction** — an uncovered label
raises `UnroutableLabelError` before any model call. When you wire the router into a
`Workflow` or `Program`, `check_types` verifies that **every** branch accepts the upstream
output; a branch that cannot raises `WireError` at assembly. Predicate routing is pure
(zero model calls, `spent == 0`); a Definition-backed classifier is one leaf run charged
to the shared budget.

## `Program` — a typed cyclic graph

A `Workflow` runs its steps once, top to bottom. A **`Program`** is a `Workflow` whose
**edges may cycle**: you register graph nodes with `.step(...)` and wire directed edges
with `.edge(...)`. A *back-edge* (`target` earlier than `source`) re-enters the region
`[target .. source]` while a guard predicate holds.

The canonical shape is **extract → review, with a `review → extract` back-edge** that
fires only while the reviewer reports a mismatch:

```python
import crawfish as cw

prog = cw.Program(name="ap-clerk", version="0.1")

extract = prog.step(extract_fields)        # a Batch over a Definition
review = prog.step(review_fields)          # a Router/Definition emitting a label

prog.edge(extract, review)                 # forward edge
prog.edge(
    review, extract,                       # BACK-edge: re-enter [extract .. review]
    when=lambda label, out: label == "mismatch",   # loop while the reviewer disagrees
    max_visits=3,                          # REQUIRED on a back-edge (see below)
)

outputs = await prog.run(seed_prompt, ctx=ctx, runtime=cw.MockRuntime())
```

The driver walks edges **per item** rather than running `for step in steps` once. Each
back-edge traversal mints a **new content-addressed version** (`Output.derive` — no
in-place mutation; the frozen Output rejects edits) and records its content sha at a
**deterministic** ledger coordinate `{region_version}#{edge_id}#{visit}`, never a volatile
`Run.id`. One shared `CostBudget` meters every iteration, and taint carries across every
cycle edge.

`Program.check_types` runs the linear adjacency check, then per edge verifies the
back-edge target structurally accepts the source's output (via `crawfish.typesystem`,
never string equality) — `WireError` otherwise.

## Bounding a cycle

A `Program` is bounded by four things and **never by wall-clock**:

| Bound | What stops the cycle |
| --- | --- |
| `max_visits` | a hard ceiling on back-edge traversals — **assembly-required**: an unbounded back-edge raises `UnboundedCycleError` at construction |
| the shared `CostBudget` | each iteration is preflighted against `remaining_usd`; the loop stops at the cap |
| cooperative cancel | the `CancelToken` is checked before each iteration |
| calibrated no-progress | an `Edge.progress` ranking delta within the noise band (`rubric_std`) for `no_progress_patience` iterations counts as stuck |

When a bound trips without the guard going false, the edge takes its `on_stuck` action —
`"return_last"` (the default) or `"dead_letter"`. The result is a frozen `ProgramResult`
carrying the final `output`, the per-edge `visits` count, and the `stopped` reason
(`"converged"`, `"max_visits"`, `"budget"`, `"no_progress"`, or `"stuck"`).

!!! warning "A back-edge must declare its ceiling"

    `prog.edge(review, extract, when=...)` **without** `max_visits` raises
    `UnboundedCycleError` at assembly. A cycle that can iterate without a ceiling could
    loop forever; the bound is the termination argument, checked before it can run.

## Durable \$0 resume

Thread the run through a shared `Store` and pass `resume=True` on the restart, and a
`Program` whose cycle crashes mid-iteration **re-derives the committed iterations at \$0**
instead of re-paying from scratch. This shares the same F-2 composite-key ledger substrate
as `Refine` — funded once, durable `Refine`, `Program` loops, and `recurse` all fall out
of it.

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

Why this is **sound, not trusted**:

- The **loop id is deterministic** — `compute_loop_id(region_version, item_lineage,
  edge_id)`, never a fresh id — so a second process re-derives the same coordinate.
  `region_version` folds the content shas of the region's frozen Definitions.
- On resume, completed visits are **re-run through the replay runtime**, which returns the
  cached `RunResult` at **zero cost**.
- An iteration's `produced_by` is the deterministic `{region_version}#{edge_id}#{visit}`
  coordinate, so the replayed Output's content sha must equal the checkpointed reference —
  determinism is **content-hash verified**, bit-for-bit.

Every `ledger_loop` row carries `org_id`, so a cross-tenant resume cannot see another
org's committed iterations.

## `recurse()` — bounded self-referential Definitions

Some work is *recursive*: a multi-part ticket splits into sub-tickets, each of which may
split again. `recurse()` expresses that as a **depth-guarded back-edge re-entering the
same FROZEN Definition**, pushing a frozen version onto a per-item depth stack, then
folding the descent-order children into one Output with an existing reducer.

```python
import crawfish as cw

rec = cw.recurse(
    body=split_ticket,                     # a FROZEN Definition (the recursive body)
    base_case=lambda out: not out.value["parts"],   # pure predicate: stop descending
    max_depth=4,                           # REQUIRED — distinct from a loop's max_visits
    combine=cw.collect,                    # fold the children: collect / count / dedupe
)
result = await rec.execute(seed, ctx, runtime)        # -> RecurseResult
print(result.depth_reached, result.stopped)
```

Each descent level runs the frozen `body` once — the prior level feeds in as a **fluid**
input (taint propagates, never an instruction) — then derives a fresh content-addressed
Output with `produced_by = {body.content_sha()}#{edge_id}#d{depth}`. Descent halts on
`base_case` / `depth >= max_depth` / budget / cancel / calibrated no-progress — **never
wall-clock**. The frozen `RecurseResult` reports the folded `output`, the `depth_reached`,
and why it `stopped` (`"base_case"`, `"max_depth"`, `"budget"`, `"no_progress"`, or
`"stuck"`).

Two invariants make recursion safe to fund:

- **`max_depth` is mandatory.** A `None` bound raises `UnboundedRecursionError` at
  construction. Tree fan-out is `O(b^d)`; the **whole-tree shared budget** is the real
  guard, preflighted at each descent and hard-killed on breach (`spent` reflects every
  level), and `max_depth` + `base_case` are the termination argument.
- **A fold never launders taint.** The reduced Output is tainted if **any** child input
  was tainted (taint = union). A vote or summary over fluid children stays fluid.

Resume is the depth-variant of the loop case: each level checkpoints into the F-2 ledger,
so resume at depth *k* replays `1..k-1` at \$0, content-hash verified, with `org_id` on
every row.

## What stays static (the security spine)

The composition surface holds the [static-vs-fluid
boundary](concepts.md#the-static-vs-fluid-prompt-injection-boundary) the same way the rest
of the framework does:

- **A classifier label is a control signal, not a target.** A fluid-derived label gates
  *which* static branch fires; the branch set is closed and static at assembly, so a fluid
  label can only select among pre-declared targets, never synthesize a new one. A tainted
  item routed into a static-only `Sink` keeps its taint across the boundary.
- **Bounds and coordinates are static.** `max_visits`, `max_depth`, `edge_id`,
  `region_version`, and the back-edge `when` predicate are static by construction — never
  derived from fluid input. The `when`/`base_case` predicates read the frozen Output as
  data.
- **Every cycle and descent carries taint forward.** A back-edge feeds the prior Output
  back as fluid; a recursion feeds the prior level back as fluid. Taint propagates across
  every edge, and a fold unions it.

## Next steps

- [Refine & verify](refine-and-verify.md) — the single-body control loop these operators
  compose onto.
- [Concepts → the composition surface](concepts.md#the-composition-surface-branch-cycle-recurse)
  — how the typed cyclic durable graph advances the thesis.
- [API reference](api-reference.md) — every public symbol, including `branch`, `Program`,
  `Edge`, `ProgramResult`, `recurse`, `Recurse`, `RecurseResult`, and the two unbounded
  errors.
