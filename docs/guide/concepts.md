# Core concepts

This page is the mental model behind Crawfish. Read it once and the rest of the docs will make
sense. Each section maps to real public API and links to a reference page for the exact
signatures, and to a guide when there is a deeper walkthrough.

The idea in one line: Crawfish is a programming language for agents. An agent is a typed value
you author in a directory, compose with other agents, version like a git commit, and run
through a swappable backend. The only stochastic part is the model call itself. Everything
around it (types, control flow, cost, storage, effects) is ordinary deterministic code.

On this page:

- [The directory model](#the-directory-model): an agent is a directory
- [The pipeline](#the-pipeline): `Source → Batch → Aggregator → Router → Sink`
- [Runtimes](#runtimes): the swappable model backend
- [Static versus fluid](#static-versus-fluid): the prompt-injection boundary
- [Secrets and safe egress](#secrets-and-safe-egress)
- [Team coordination](#team-coordination)
- [Storage](#storage): the Store and ArtifactStore
- [Cost and inspection](#cost-and-inspection)
- [Measuring quality](#measuring-quality)
- [The rest of the language](#the-rest-of-the-language): control flow, tuning, and versioning

## The directory model

An agent is a directory. You write markdown for the instructions and skills, and Python for the
typed inputs and outputs, tools, and policies. The compiler reads the directory and turns it
into a typed `Definition`. Here is what it looks for:

| Path | Becomes |
| --- | --- |
| `instructions.md` | the lead agent (front-matter is topology, body is the prompt) |
| `agents/*.md` | one subagent each (role is the filename stem) |
| `definition.py` | typed `inputs` and `outputs`, `dependencies`, `coordination`, `lead` |
| `tools/*.py` | a tool named after the file stem (a callable of that name) |
| `policies/*.py` | module-level `Policy` instances |
| `mcp/*.py` | module-level `MCPConnection` instances |
| `skills/*.md` | skill assets |
| `pyproject.toml` | identity (`name`) and version |

Compile with `Definition.from_package(path)` (or `load_definition(path)`). A Definition's
identity is content-derived: a sha over the directory's contents, never its path or a timestamp.
So a directory and its installed package compile to the same thing, byte for byte. The compiler
writes a `definition.lock` for reproducibility. If an agent references a tool, policy, or
delegate that does not exist, that broken binding fails at load time, so you find out up front
rather than partway through a run.

A compiled `Definition` is freezable. Call `.freeze()` to seal it into an immutable artifact.
Mutating a frozen one raises `FrozenError`.

See the [authoring reference](../reference/authoring.md) and
[definition reference](../reference/definition.md) for the full directory contract.

## The pipeline

Bulk work is a pipeline of nodes. Data fans out into per-item runs, fans back in, branches, then
exits through one sink.

```text
Source → Filter → Batch(Definition) → Aggregator → Router → Sink
              ├─ fan-out:    one Run per item   (map)
              ├─ Aggregator: N Outputs → one    (reduce)
              └─ Router:      branch by label    (branch)
```

Data flows between stages as an `Output`: a frozen envelope that carries the value, its schema,
and the id of the node that produced it. Nodes never change an Output in place. To transform
one, a node calls `derive` to make a fresh copy, leaving the original intact for audit. Adjacent
stages are type-checked when you assemble the pipeline, so a mistyped wire is caught before any
model call.

Here is what each node does:

- **`Source`** is where data enters. `fetch()` returns a typed `Output`. A multi source
  (`multi = True`) returns a list, and `fan_out` splits that list into one `Output` per item,
  each seeding its own run. The built-ins are `RepoSource` (single) and `PullRequestSource`
  (multi). Both are deterministic and read from fixtures, so they need no network.
- **`Filter`** is a pure, synchronous node that narrows a list by a predicate and keeps the
  order. The factories are `title_contains`, `field_equals`, `field_matches`, and `limit`.
- **`Batch`** is the assembly point. You wire sources and outputs into a Definition with
  `.add_input(...)`. A multi source produces one run per item, and `check_wiring()` type-checks
  at assembly. The batch's cost ceiling carries onto every child run.
- **`Aggregator`** is the fan-in counterpart, taking N item outputs and emitting one. The
  built-in reducers (`collect`, `concat`, `count`, `dedupe`) are pure. A `definition_reducer`
  runs an agent team to reduce, for example to summarize. `fan_in` is the barrier that handles
  partial success: it drops failed or `None` items and supports a `quorum`.
- **`Router`** sends an `Output` down one labelled branch, chosen by a `Classifier`. Classifiers
  come in two kinds: `from_predicates` (pure) and `from_definition` (agent-backed). The label
  set is closed and always includes a `default` (dead-letter) label, so every item is routable.
  Unroutable wiring raises `UnroutableLabelError` at assembly time.
- **`Sink`** is the only place a pipeline performs an external side effect. The built-ins are
  `LinearSink` and `GitHubPRSink`, both dry-run by default and network-free. Three rules keep
  egress safe (below).
- **`Workflow`** is the top-level deployable: ordered steps with the `Output` threaded from stage
  to stage, adjacency type-checked at assembly. Orchestration state is checkpointed to the Store
  after each stage, so a crash mid-workflow resumes from the last completed step.

!!! warning "Sink targets are static-only"

    Sink targets and idempotency keys are static-only. A fluid, model-influenced value can never
    redirect where a write lands. See [Secrets and safe egress](#secrets-and-safe-egress).

For exact signatures, see the reference pages for
[Source and Filter](../reference/nodes-source-filter.md),
[Aggregator](../reference/nodes-aggregator.md),
[Router and Sink](../reference/nodes-router-sink.md), and
[Output and wiring](../reference/output-and-wiring.md).

## Runtimes

A runtime is the model backend. `AgentRuntime` is the only place the model SDK or CLI is
touched, and every run goes through it. That is what makes the backend swappable, and why moving
from dev to prod is a runtime swap and not a code change.

| Runtime | Backend | Key | Cost | Use |
| --- | --- | --- | --- | --- |
| `MockRuntime` | a pure function of the request | no | $0 | dev loop, tests, benchmarks |
| `CommandRuntime` | local `claude -p` subprocess | no | your Claude session | real local runs |
| `RecordReplayRuntime` | wraps any runtime with cassettes | no on replay | $0 on replay | snapshot and replay tests |
| `ClientRuntime` | API client | yes | metered | stub today |
| `ManagedRuntime` | hosted backend | yes | metered | stub today |

`get_runtime(name)` resolves a runtime by name from `RUNTIME_FACTORIES`.

`MockRuntime` returns deterministic canned text with no model call, so iterating on a Definition
or a metric never burns budget and scores never drift. `RecordReplayRuntime(inner, cassette_dir,
record=True)` records real results once, then replays them at zero cost. If a cassette is
missing and recording is off, it raises `CassetteMiss`. This is what makes `craw dev` and
`craw test` fast and deterministic.

See the [runtimes reference](../reference/runtimes.md) for the `AgentRuntime` interface and each
backend's exact behavior.

## Static versus fluid

This is the rule that stops untrusted data from hijacking your agents. Every `Parameter` carries
a `Flow` that marks it trusted or not:

- `Flow.STATIC` is trusted config, set once per batch, like a repo or a project. It can go
  straight into the agent's instructions.
- `Flow.FLUID` (the default) is untrusted per-item data, like a ticket body. It goes only inside
  a clearly marked data block, and the instructions tell the model to treat that block as data,
  never as instructions.

The prompt compiler enforces this. `split_inputs` sorts inputs by their declared flow, and
anything unknown defaults to fluid, which is the safe, untrusted side. A ticket body cannot
smuggle instructions into the agent. And because sink targets must be static, a value the model
influenced cannot redirect where a write lands.

!!! warning "Fluid is the default"

    Any input you do not classify is treated as untrusted. Mark a parameter `Flow.STATIC` only
    when it is trusted config set once per batch. Never use static to admit per-item data into
    the instructions.

See the [type-system reference](../reference/type-system.md) for `Flow`, `Parameter`, and
`split_inputs`, and the [injection boundary guide](injection-rejected-by-construction.md) for how
to prove it holds.

## Secrets and safe egress

**Secrets are held by reference, never by value.** Config stores the name of an environment
variable, like `"GITHUB_TOKEN"`, never the value. The value is resolved at the egress boundary by
`resolve_secret` and injected into a tool's or MCP server's environment. It never reaches a
prompt, the stored config, an `Output`, logs, or telemetry. An `MCPConnection`'s `auth` field is
a secret reference by construction.

A sink is the one place a pipeline writes to the outside world. Three rules keep that safe:

1. **Static-only targets.** Destination slots (repo, project, channel) must be `Flow.STATIC`. A
   fluid target is rejected at construction with `TargetMustBeStaticError`, so a prompt can never
   redirect a write.
2. **Idempotency.** Every write is keyed by a hash of static config only, plus the batch and
   output identity, never the fluid or model-derived value. Re-running the same batch is a no-op,
   not a duplicate write.
3. **Approval gate.** An `always_ask` sink refuses to fire without an explicit approval callback,
   raising `ApprovalRequired`. A run can also suspend durably on approval before spending any
   compute (`requires_approval` leads to `RunSuspended`).

See the [secret-broker reference](../reference/secret-broker.md),
[secrets and consent reference](../reference/secrets-and-consent.md), and
[Router and Sink reference](../reference/nodes-router-sink.md).

## Team coordination

A `TeamSpec` carries the multi-agent topology. Agents delegate in and return a typed result out,
rather than sharing a message bus. Coordination uses Claude's hierarchical subagent model:

- **`SINGLE`** is one agent, or several independent agents, with no coordinator.
- **`LEAD`** is a lead that dispatches the roles in its `delegates_to`, then combines their typed
  results. Each subagent result re-enters the lead as fluid data (`{role}_result`), never as
  instructions, which preserves both the typing and the injection boundary.
- **`SEQUENTIAL`** runs agents in declared order, and each result threads into the next as
  `prior_result`.

`run_team` executes the topology and returns one `RunResult`. The coordinator is
runtime-agnostic, so it works with the mock and tests stay deterministic.

## Storage

All persistence goes through the `Store` interface, so you can swap the backend without touching
the code that uses it. The product model imports the protocol, never a concrete backend, so
moving from SQLite to Postgres is a driver swap, and no raw SQL appears at any call site. Every
row carries an `org_id` tenancy key (defaulted to `"local"`), so cloud multi-tenancy is also a
driver swap, not a schema migration. The local default is `SqliteStore`. The Store backs typed
records, key-value and working memory, idempotency claims, and the append-only event ledger that
powers the inspector.

- **`Memory`** is a thin Store-backed key-value and dedup handle, scoped to a
  `(namespace, org_id)` pair. It covers working memory (`get`/`set`), cross-run dedup
  (`already_processed`/`mark_processed`), and an atomic `claim` that wins exactly once per id.
  Because state lives in the Store, dedup survives across runs.
- **`ArtifactStore`** (with `LocalArtifactStore` and `offload_if_large`) is the blob store: the
  local filesystem now, S3 later. Large payloads are offloaded by reference instead of carried
  inline.

See the [persistence reference](../reference/persistence.md) for the `Store`, `Memory`, and
`ArtifactStore` contracts.

## Cost and inspection

You can see the bill before a single model call, and reconstruct any run from the event ledger.

- **`estimate_cost(definition, items=N)`** is a deterministic dry-run preview. It assumes one run
  per agent per item, prices it from a coarse per-model table, and returns a `CostEstimate`. The
  `mock` model is free, so dev and replay preview at $0.
- **`CostBudget`** is a hard ceiling the orchestrator can kill a run on, raising `BudgetExceeded`.
  `Budget` layers a warn-or-stop policy on top, and `CostMeter` is a live accumulator that tracks
  remaining headroom.
- **`inspect_run(store, run_id)`** derives a `RunReport` (status, cost, latency, tool calls,
  transcript) purely from the event ledger, with no live model call. `tail_events` is the poll
  primitive for live streaming, and `format_report` renders a report for the CLI. This backs
  `craw inspect` and `craw logs`.

See the [context and budgets reference](../reference/context-and-budgets.md) and the
[inspector reference](../reference/emission-inspector-visualize.md).

## Measuring quality

`Metric`, `Rubric`, and `Benchmark` make quality measurable and comparable across Definition
versions. A `Metric` scores one `Output`. A `Rubric` bundles metrics into a score vector. A
`Benchmark` runs a rubric over a fixed task set and averages the results.

The eval data lifecycle (`EvalCase`, `GoldenSet`, `LLMJudge`, `capture_case`, `grade_output`, and
`save_baseline`/`load_baseline`/`gate_against_baseline`) lets you capture real runs as reusable
cases, curate versioned golden sets, grade with an LLM as judge, and gate a candidate against a
stored regression baseline. All of it is deterministic under mock and replay.

See the [evals reference](../reference/evals.md) and [metrics reference](../reference/metrics.md).

## The rest of the language

Everything above is the core. The features below build on it, and each has its own guide. They
share one property: the stochastic model call stays contained, and the deterministic program
around it stays deterministic, versioned, and taint-tracked.

**Refine and verify** wraps a model run in a bounded loop: keep trying until the result is good
enough, but never past N tries or a budget, and resume a crashed loop for free. A `Verifier`
decides when to stop, and a verifier must be benchmarked and gated before it can stop a loop, so
an untested critic fails closed. See [Refine and verify](refine-and-verify.md).

**Compose: branch, cycle, recurse** gives control flow its shape. A `Router` becomes a runnable
step, a `Program` is a typed graph whose edges may cycle, and `recurse` re-enters a frozen
Definition under a depth bound. Cycles are bounded and resume at $0. See [Compose](compose.md).

**Train, calibrate, and promote** treats an agent like a model with tunable weights. A frozen
Definition is in eval mode (reproducible, the only mode that may act on the world). An unfrozen
copy is in train mode (its knobs may move). The tuner searches the knobs, `calibrate` measures
run-to-run variance, and promotion only happens when a candidate clears the noise band without
regressing. See [Train, calibrate, and promote](train-and-tune.md).

**Tame stochasticity** bounds the model call itself with four techniques: quorum (sample N, take
the consensus), abstention (decline instead of guessing), a learned guard distilled into a pure
rule, and constrained decoding (make a malformed output impossible). See
[Tame stochasticity](tameness.md).

**Agents as variables** makes a Definition a content-addressed value you compose, name, and move
through a version log, which is git for agents. `with_*` operators compose copy-on-write,
`DefinitionStore` is the name registry, and knowledge is summoned by reference as data. See
[Agents as variables](variables-and-knowledge.md).

**Diff, prove, and replay** are the verbs the content-addressed substrate unlocks: `diff` and
`merge` two versions, `craw prove --no-injection` as a pre-flight gate, and `craw replay --swap`
to re-run a historical run against a candidate model change, paying only for what changed. See
[Diff, prove, and replay](diff-prove-replay.md).

**Drive Crawfish from the CLI** exposes the optimization plane (`craw eval`, `tune`, `refine`,
`learn`, `guard`) so a long-running app can drive Crawfish through the same shell you do. See
[Drive Crawfish from the CLI](optimize-from-the-cli.md).

## Next steps

- [Cookbook](cookbook.md): copy-paste recipes, including eval-as-test.
- [API reference](api-reference.md): every public symbol.
- [Reference overview](../reference/index.md): the deep per-topic pages.
