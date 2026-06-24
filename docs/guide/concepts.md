# Concepts

Crawfish runs bulk agent work as a typed pipeline you author as directories. This page is the mental model behind the framework; each section maps to real public API and hands off to a reference page for exact signatures.

On this page:

- [The directory model](#the-directory-model) — an agent is a directory
- [The pipeline](#the-pipeline) — `Source → Batch → Aggregator → Router → Sink`
- [Runtimes](#runtimes-the-swappable-agent-loop) — the swappable agent loop
- [The static-vs-fluid boundary](#the-static-vs-fluid-prompt-injection-boundary) — prompt-injection defence
- [Secrets by reference](#secrets-by-reference) and [safe egress](#safe-egress-the-sink-invariants)
- [Team coordination](#team-coordination), [Store seams](#the-store-and-artifactstore-seams), and [cost & inspection](#cost-budgets-and-inspection)
- [The measurement loop](#the-measurement-loop) and [the control plane](#the-control-plane-refine-and-verify) — Refine & Verify
- [The composition surface](#the-composition-surface-branch-cycle-recurse) — branch, cycle, recurse

## The directory model

An agent is a directory: markdown for instructions and skills, Python for typed I/O, tools, and policies. You write markdown for the instructions and skills, and
Python for the typed inputs and outputs, tools, and policies. The compiler reads the
directory and turns it into a typed `Definition`. Here's what it looks for:

| Path | Becomes |
| --- | --- |
| `instructions.md` | the lead/main agent (front-matter = topology, body = prompt) |
| `agents/*.md` | one subagent each (role = filename stem) |
| `definition.py` | typed `inputs`/`outputs`, `dependencies`, `coordination`, `lead` |
| `tools/*.py` | a tool named after the file stem (a callable of that name) |
| `policies/*.py` | module-level `Policy` instances → `DefinitionAssets.policies` |
| `mcp/*.py` | module-level `MCPConnection` instances |
| `skills/*.md` | skill assets |
| `pyproject.toml` | identity (`name`) + version |

Compile with `Definition.from_package(path)` (or `load_definition(path)`). A Definition's
identity is **content-derived**: a sha over the directory's contents, never its path or a
timestamp. So a directory and its installed package compile to the same thing, byte for
byte. The compiler writes a `definition.lock` for reproducibility. If an agent references
a tool, policy, or delegate that doesn't exist, that broken binding fails at **load
time** — you find out up front, not partway through a run.

A compiled `Definition` is `Freezable`. Call `.freeze()` to seal it into an immutable
artifact; mutating a frozen one raises `FrozenError`.

See the [authoring reference](../reference/authoring.md) and [definition reference](../reference/definition.md) for the full directory contract and `from_package` signature.

## The pipeline

Bulk work is a pipeline of `Node`s. Data fans out into per-item runs, fans back in, branches, then exits through one sink.

```
Source → Filter → Batch(Definition) → Aggregator → Router → Sink
              ├─ fan-out:    one Run per item   (map)
              ├─ Aggregator: N Outputs → one    (reduce)
              └─ Router:      branch by label    (branch)
```

Data flows between stages as an `Output`: a frozen envelope that carries the value, its
schema, and the id of the node that produced it. Nodes never change an Output in place. To
transform one, a node calls `derive` to make a fresh copy, leaving the original intact for
audit. Adjacent stages are **type-checked when you assemble the pipeline** (structural
`parameters_compatible`), so a mistyped wire is caught before any model call.

- **`Source`** is where data enters the pipeline. `fetch()` returns a typed `Output`. A
  *multi* source (`multi = True`) returns a list, and `fan_out` splits that list into one
  `Output` per item — each one seeding its own `Run`. The built-ins are `RepoSource`
  (single) and `PullRequestSource` (multi). Both are deterministic and need no network
  (they read from fixtures).
- **`Filter`** is a pure, synchronous node that narrows a list `Output` by a predicate
  and preserves order. Factories: `title_contains`, `field_equals`, `field_matches`,
  `limit`.
- **`Batch`** is the assembly point. You wire `Source`s and `Output`s into a `Definition`
  with `.add_input(...)`. A multi source fans out to one `Run` per item, and
  `check_wiring()` type-checks at assembly. The batch's cost ceiling carries onto every
  child `Run`.
- **`Aggregator`** is the fan-in counterpart — it does the reverse of fan-out, taking N
  item `Output`s and emitting one. The built-in reducers (`collect`, `concat`, `count`,
  `dedupe`) are pure; a `definition_reducer` runs an agent team to reduce, for example to
  summarize. `fan_in` is the barrier that handles partial success: it drops failed or
  `None` items and supports a `quorum`.
- **`Router`** sends an `Output` down one labelled branch, chosen by a `Classifier`.
  Classifiers come in two flavours: `from_predicates` (pure) and `from_definition`
  (agent-backed). The label set is closed and always includes a `default` (dead-letter)
  label, so every item is routable. Unroutable wiring raises `UnroutableLabelError` at
  **assembly time**.
- **`Sink`** is the only place a pipeline performs an external side effect. The built-ins
  are `LinearSink` and `GitHubPRSink`, both dry-run by default and network-free. Three
  invariants keep egress safe (below).
- **`Workflow`** is the top-level deployable: ordered steps with the `Output` threaded
  from stage to stage, adjacency type-checked at assembly. Orchestration state is
  checkpointed to the `Store` after each stage, so a crash mid-workflow resumes from the
  last completed step.

!!! warning

    `Sink` targets and idempotency keys are **static-only**. A fluid (model-influenced) value can never redirect where a write lands. See [Safe egress](#safe-egress-the-sink-invariants).

For exact node signatures, see the reference pages for [Source & Filter](../reference/nodes-source-filter.md), [Aggregator](../reference/nodes-aggregator.md), [Router & Sink](../reference/nodes-router-sink.md), and [Output & wiring](../reference/output-and-wiring.md).

## Runtimes — the swappable agent loop

Going from dev to prod is a runtime swap, not a code change. `AgentRuntime` is the **only** place the model SDK or CLI is touched. Every run goes
through this one interface, which is what makes the backend swappable:

| Runtime | Backend | Key | Cost | Use |
| --- | --- | --- | --- | --- |
| `MockRuntime` | pure function of the request | no | $0 | dev loop, tests, benchmarks |
| `CommandRuntime` | local `claude -p` subprocess | no | your Claude session | real local runs |
| `RecordReplayRuntime` | wraps any runtime; cassettes | no on replay | $0 on replay | snapshot/replay tests |
| `ClientRuntime` | API client | yes | metered | (stub today) |
| `ManagedRuntime` | hosted CMA | yes | metered | (stub today) |

`get_runtime(name)` resolves a runtime by name from `RUNTIME_FACTORIES`.

- **Dev loop.** `MockRuntime` returns deterministic canned text with no model call.
  Iterating on a Definition or a metric never burns budget, and scores never drift.
- **Replay.** `RecordReplayRuntime(inner, cassette_dir, record=True)` records real
  `RunResult`s once, then replays them at zero cost. If a cassette is missing and
  recording is off, it raises `CassetteMiss`. This is what makes `craw dev` and
  `craw test` fast and deterministic.

See the [runtimes reference](../reference/runtimes.md) for the `AgentRuntime` interface and each backend's exact behaviour.

## The static-vs-fluid prompt-injection boundary

Untrusted data reaches the model as data, never as instructions — this is the rule that stops it from hijacking your agents. Every `Parameter`
carries a `Flow` that marks it trusted or not:

- `Flow.STATIC` is **trusted config**, set once per batch — a repo, a project. It can go
  straight into the agent's instructions.
- `Flow.FLUID` (the default) is **untrusted per-item data**, like a ticket body. It goes
  *only* inside a clearly marked, labelled data block, and the instructions tell the model
  to treat that block as data, never as instructions. Trusted config and untrusted data
  never mix.

The prompt compiler enforces this. `split_inputs` sorts inputs by their declared flow,
and anything unknown defaults to fluid — the safe, untrusted side. This is the
load-bearing defence against prompt injection. A ticket body can't smuggle instructions
into the agent. And because sink targets must be static, a value the model influenced
can't redirect where a write lands.

!!! warning

    `Flow.FLUID` is the default, and any input you don't classify is treated as **untrusted**. Mark a parameter `Flow.STATIC` only when it is trusted config set once per batch — never to admit per-item data into the instructions.

See the [type-system reference](../reference/type-system.md) for `Flow`, `Parameter`, and `split_inputs`.

## Secrets by reference

Credentials never reach a prompt — Crawfish holds them by reference only. Config stores the *name* of an environment
variable, like `"GITHUB_TOKEN"`, never the value itself. The value is resolved at the
egress boundary by `resolve_secret` and injected into a tool's or MCP server's
environment. It never reaches a prompt, the stored config, an `Output`, logs, or
telemetry. An `MCPConnection`'s `auth` field is a secret reference by construction.

!!! warning

    A secret value never enters a prompt, an `Output`, the stored config, logs, or telemetry. Pass the **name** of the env var (`"GITHUB_TOKEN"`), and let `resolve_secret` inject the value at the egress boundary.

See the [secret-broker reference](../reference/secret-broker.md) and [secrets & consent reference](../reference/secrets-and-consent.md) for `resolve_secret` and the consent model.

## Safe egress — the Sink invariants

A `Sink` is the one place a pipeline performs an external side effect. Three invariants keep that safe:

1. **Static-only targets.** Destination slots — repo, project, channel — must be
   `Flow.STATIC`. A fluid target is rejected at construction with `TargetMustBeStaticError`,
   so a prompt can never redirect a write.
2. **Idempotency.** Every write is keyed by a hash of *static config only* plus the batch
   and output identity, never the fluid or model-derived value. Re-running the same batch
   is a no-op, not a duplicate side effect.
3. **Approval gate.** An `always_ask` sink refuses to fire without an explicit approval
   callback, raising `ApprovalRequired`. A run can also suspend durably on approval before
   spending any compute (`requires_approval` → `RunSuspended`).

See the [Router & Sink reference](../reference/nodes-router-sink.md) for the sink built-ins and these invariants in full.

## Team coordination

A `TeamSpec` carries the multi-agent topology — agents delegate in and return a typed result out, rather than sharing a message bus. Coordination leans on Claude's
**hierarchical subagent model** rather than a bespoke message bus:

- **`SINGLE`** is one agent, or several independent agents, with no coordinator.
- **`LEAD`** is a lead that dispatches the roles in its `delegates_to`, then combines
  their typed results. Each subagent result re-enters the lead as **fluid data**
  (`{role}_result`), never as instructions, which preserves both typing and the injection
  boundary.
- **`SEQUENTIAL`** runs agents in declared order; each result threads into the next as
  `prior_result`.

`run_team` executes the topology and returns one `RunResult`. The coordinator is
runtime-agnostic — it works with the mock, so tests stay deterministic.

!!! note "Good to know"

    Each subagent result re-enters the lead as **fluid data** (`{role}_result`), never as instructions. The injection boundary holds inside a team, not just at its edge.

## The Store and ArtifactStore seams

All persistence goes through the `Store` protocol — swap the backend without touching the code that uses it. A `Store` is a *seam*, meaning a clean interface
you can swap the backend behind without touching the code that uses it. The product model
imports the *protocol*, never a concrete backend, so moving from SQLite to Postgres is a
driver swap, and no raw SQL appears at any call site. Every row carries an `org_id`
tenancy key (defaulted to `"local"`), so cloud multi-tenancy is also a driver swap, not a
schema migration. The local default is `SqliteStore`. The `Store` backs typed records, KV
and working memory, idempotency claims, and the append-only event ledger that powers the
inspector.

- **`Memory`** is a thin `Store`-backed KV and dedup handle, scoped to a
  `(namespace, org_id)` pair. It covers working memory (`get`/`set`), cross-run dedup
  (`already_processed`/`mark_processed`), and an atomic `claim` that wins exactly once per
  id. Because state lives in the `Store`, dedup survives across runs.
- **`ArtifactStore`** (with `LocalArtifactStore` and `offload_if_large`) is the blob seam:
  the local filesystem now, S3 later. Large payloads are offloaded by reference instead of
  carried inline.

See the [persistence reference](../reference/persistence.md) for the `Store`, `Memory`, and `ArtifactStore` contracts.

## Cost, budgets, and inspection

You see the bill before a single model call, and you reconstruct any run from the event ledger.

- **`estimate_cost(definition, items=N)`** is a deterministic dry-run preview. It assumes
  one run per agent per item, prices it from a coarse per-model table, and returns a
  `CostEstimate` — so you see the bill before a single model call. The `mock` model is
  free, so dev and replay preview at $0.
- **`CostBudget`** is the hard ceiling the orchestrator can kill a run on, raising
  `BudgetExceeded`. **`Budget`** layers a warn/stop policy on top (`BudgetState` is
  ok/warn/stopped), and **`CostMeter`** is a live accumulator that tracks remaining
  headroom.
- **`inspect_run(store, run_id)`** derives a `RunReport` — status, cost, latency, tool
  calls, transcript — purely from the Store's append-only event ledger, with no live model
  call. `tail_events` is the poll primitive for live streaming, and `format_report`
  renders a report for the CLI. This is the trust and devtools layer that backs
  `craw inspect` and `craw logs`.

See the [context & budgets reference](../reference/context-and-budgets.md) and the [inspector reference](../reference/emission-inspector-visualize.md) for the exact budget and report types.

## The measurement loop

`Metric` → `Rubric` → `Benchmark` make quality measurable and comparable across Definition
versions. The eval data lifecycle (`EvalCase`, `GoldenSet`, `LLMJudge`, `capture_case`,
`grade_output`, and `save_baseline`/`load_baseline`/`gate_against_baseline`) lets you
capture real runs as reusable cases, curate versioned golden sets, grade with an
LLM-as-judge, and gate a candidate against a stored regression baseline. All of it is
deterministic under mock and replay.

See the [evals reference](../reference/evals.md) and [metrics reference](../reference/metrics.md) for the full lifecycle.

## The control plane — Refine and Verify

One primitive in Crawfish is stochastic: a model `Run`. Everything else is
deterministic, typed, versioned, and taint-tracked. The **control plane** is what wraps
that single stochastic primitive in a *loop* without giving up any of those properties —
"keep trying until good enough, but never past N tries or $X, and resume a crash for
free." `Refine` is that loop; `Verifier` is the critic that can stop it.

**`Refine` generalises the bounded/metered/durable loop.** The framework already had
three fixed-bound re-run atoms — `EscalatingRuntime` (2×), `Run._repair` (+1),
`RetryPolicy` (on-exception). `Refine` folds them into one goal-driven operator: run a
producing body `Definition`, check each frozen `Output` against an **external**
`StopCondition`, and iterate until satisfied or a bound is hit (`max_iters`, the shared
`CostBudget`, cooperative cancel, or noise-aware no-progress — **never wall-clock**). It
mutates nothing: every attempt is a fresh frozen `Output`, the body stays frozen. That is
`mutable = False` — **eval mode**.

**The stop signal must be external — and a critic must *earn* the authority to stop you.**
A bare `Verifier` only describes an `Output` (a closed label set with a mandatory
`default`); it is in `WARN`/`SHADOW` and **cannot** stop a loop. `Verifier.gated(...)` is
the only path to a `GatedVerifier` with `BLOCK` authority, and it **fails closed**: a
never-benchmarked critic, or one below `min_precision` against a decision `GoldenSet`,
raises `VerifierNotGated` rather than being trusted. This is the same discipline as a
`Sink`: stopping a loop ships the result, so the authority to stop is conferred by a gate,
not asserted. And a `Refine` whose verifier critic shares the body's `content_sha()` is
rejected outright — the generator may never critique itself.

**$0 crash-resume falls out of the spine, not a special case.** With an `ExecutionLedger`,
each completed iteration's frozen `Output` is checkpointed under a **deterministic** loop
id. On `resume=True` the committed iterations replay through the cassette runtime at zero
cost, and because each iteration's `produced_by` is the deterministic
`body.content_sha()#visit` coordinate, the replayed Output's content sha reproduces the
checkpoint **bit-for-bit** — determinism is *verified*, not trusted. A loop that died at
iteration 3 of 5 restarts at iteration 4 charging `$0`.

See the [Refine & Verify guide](refine-and-verify.md) for the runnable walkthrough.

## The composition surface — branch, cycle, recurse

`Refine` is the control plane for *one* body. The **composition surface** gives the agent
language its *shape*: control flow that branches, cycles, and recurses — while keeping
every property the rest of the framework holds. Control flow here is **deterministic,
versioned, and taint-tracked**, cycles are **bounded and crash-resumable at \$0**, and
recursion re-enters only **frozen** Definitions. It is the structural keystone the Tuner
and the rest of Phase 2 compose onto.

**A `Router` becomes a runnable step.** `branch(classifier, branches)` dispatches each
item through the *same* step machinery as its chosen branch, so a branch may be a
`Sink`/`Batch`/`Filter`/`Aggregator` and inherits the identical budget / taint /
checkpoint guarantees. The label set is closed and totality-checked at construction, and
`check_types` verifies every branch accepts the upstream output — a mistyped or uncovered
branch fails at **assembly**, before any model call.

**A `Program` is a typed graph whose edges may cycle.** It reuses the `Workflow` kernel;
the difference is the *driver* — it walks edges per item rather than running the steps
once. A back-edge re-enters its region while a guard predicate holds, and every traversal
is a **content-addressed version transition** (`Output.derive` mints a fresh sha; the
frozen Output rejects in-place edits — this is eval mode). Cycles are bounded by
iteration / shared budget / cancel / calibrated no-progress — **never wall-clock** — and a
back-edge with no `max_visits` is rejected with `UnboundedCycleError` at assembly. One
shared `CostBudget` meters every iteration, and taint carries across every edge.

**Durable \$0 resume falls out of the same ledger, not a special case.** Each iteration is
checkpointed under a **deterministic** loop id over the F-2 composite-key ledger; on
`resume=True` the committed iterations replay through the cassette runtime at zero cost,
and because each iteration's `produced_by` is the deterministic
`{region_version}#{edge_id}#{visit}` coordinate, the replayed Output's content sha
reproduces the checkpoint **bit-for-bit** — determinism is *verified*, not trusted. Every
ledger row carries `org_id`, so a cross-tenant resume is isolated.

**`recurse` re-enters a frozen Definition under a depth bound.** Recursion is a
depth-guarded `Program` back-edge into the *same* frozen body, pushing a frozen version
onto a per-item depth stack and folding the descent-order children with an existing
reducer. `max_depth` is mandatory (`UnboundedRecursionError` otherwise), the whole-tree
shared budget guards the `O(b^d)` fan-out, and a fold **never launders taint** — the
reduced Output is tainted if any child input was.

See the [Compose guide](compose.md) for the runnable walkthrough.

## Next steps

- [Cookbook](cookbook.md) — copy-paste recipes, including eval-as-test.
- [Getting started](getting-started.md) — build and run your first agent.
- [API reference](api-reference.md) — every public symbol.
- [Reference index](../reference/index.md) — the deep per-topic pages.
