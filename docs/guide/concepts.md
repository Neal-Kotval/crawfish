# Concepts

The model behind Crawfish. Each section maps to real public API; see the
[API reference](api-reference.md) for exact signatures.

## The directory model

**An agent is a directory.** You author markdown (instructions/skills) and Python (typed
IO, tools, policies); the compiler turns the directory into a typed `Definition`. The
layout the compiler reads:

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

Compile with `Definition.from_package(path)` (or `load_definition(path)`). Identity is
**content-derived** (a sha over the directory contents), never path- or time-derived, so
a directory and its installed package compile byte-identically. A `definition.lock` is
written for reproducibility. Broken bindings — an agent referencing an unknown tool,
policy, or delegate — fail at **load time**, never at run time.

A compiled `Definition` is `Freezable`: call `.freeze()` to seal it into an immutable,
reproducible artifact (mutating a frozen artifact raises `FrozenError`).

## The pipeline

Bulk work is a pipeline of `Node`s:

```
Source → Filter → Batch(Definition) → Aggregator → Router → Sink
              ├─ fan-out:    one Run per item   (map)
              ├─ Aggregator: N Outputs → one    (reduce)
              └─ Router:      branch by label    (branch)
```

Data flows as `Output` — a frozen, self-describing envelope (value + schema + the id of
the producing node). Nodes never mutate an Output; transforms `derive` a fresh one,
keeping the upstream value intact for audit. Adjacent stages are **type-checked at
assembly** (structural `parameters_compatible`), so a mistyped wire is rejected before
any model call.

- **`Source`** — pipeline ingress. `fetch()` returns a typed `Output`. A *multi* source
  (`multi = True`) returns a list, which `fan_out` explodes into one `Output` per item,
  each seeding its own `Run`. Built-ins: `RepoSource` (single), `PullRequestSource`
  (multi). Both are deterministic and network-free (fixture-driven).
- **`Filter`** — a pure, synchronous node that narrows a list `Output` by a predicate,
  order preserved. Factories: `title_contains`, `field_equals`, `field_matches`, `limit`.
- **`Batch`** — the assembly point: wire `Source`s/`Output`s into a `Definition` with
  `.add_input(...)`. A multi source fans out to one `Run` per item; `check_wiring()`
  type-checks at assembly. The batch's cost ceiling is carried onto every child `Run`.
- **`Aggregator`** — the fan-in/reduce counterpart: consumes N item `Output`s and emits
  one. Built-in reducers (`collect`, `concat`, `count`, `dedupe`) are pure; a
  `definition_reducer` runs an agent team to reduce (e.g. summarize). `fan_in` is the
  partial-success-aware barrier (failed/`None` items are dropped; supports a `quorum`).
- **`Router`** — branches an `Output` down one labelled branch chosen by a `Classifier`.
  Classifiers come in two flavours: `from_predicates` (pure) and `from_definition`
  (agent-backed). The label set is closed and always includes a `default` (dead-letter)
  label, so every item is routable. Unroutable wiring raises `UnroutableLabelError` at
  **assembly time**.
- **`Sink`** — the only place a pipeline performs an external side effect. Built-ins:
  `LinearSink`, `GitHubPRSink` (both dry-run by default — network-free). Three invariants
  make egress safe (below).
- **`Workflow`** — the top-level deployable: ordered steps with the `Output` threaded
  stage to stage, adjacency type-checked at assembly, and orchestration state
  checkpointed to the `Store` after each stage, so a crash mid-workflow resumes from the
  last completed step.

## Runtimes — the swappable agent loop

`AgentRuntime` is the **only** place the model SDK/CLI is touched. The product model
drives every run through this interface, so the backend is swappable:

| Runtime | Backend | Key | Cost | Use |
| --- | --- | --- | --- | --- |
| `MockRuntime` | pure function of the request | no | $0 | dev loop, tests, benchmarks |
| `CommandRuntime` | local `claude -p` subprocess | no | your Claude session | real local runs |
| `RecordReplayRuntime` | wraps any runtime; cassettes | no on replay | $0 on replay | snapshot/replay tests |
| `ClientRuntime` | API client | yes | metered | (stub today) |
| `ManagedRuntime` | hosted CMA | yes | metered | (stub today) |

Switching dev→prod is a **runtime swap, not a code change**. `get_runtime(name)`
resolves a runtime by name from `RUNTIME_FACTORIES`.

- **Dev loop** — `MockRuntime` returns deterministic canned text with no model call, so
  iterating on a Definition or a metric never burns budget and scores never drift.
- **Replay** — `RecordReplayRuntime(inner, cassette_dir, record=True)` records real
  `RunResult`s once; thereafter replays them at zero cost (a `CassetteMiss` is raised if
  a cassette is missing and recording is off). This is the basis for fast, deterministic
  `craw dev`/`craw test`.

## The static-vs-fluid prompt-injection boundary

Every `Parameter` carries a `Flow`:

- `Flow.STATIC` — **trusted config**, set once per batch (e.g. a repo, a project). It may
  be interpolated into the agent's instructions.
- `Flow.FLUID` (the default) — **untrusted per-item data** (e.g. a ticket body). It is
  placed *only* inside a clearly delimited, labelled data block that the instructions are
  told to treat as data, never as instructions. Static config never mixes with fluid data.

The prompt compiler enforces this: `split_inputs` partitions inputs by declared flow, and
unknown inputs default to fluid — the safe (untrusted) side. This is the load-bearing
prompt-injection defence: a ticket body can never smuggle instructions into the agent,
and (because sink targets must be static) a model-influenced value can never redirect
where a write lands.

## Secrets by reference

Credentials are held **by reference only** — config stores the *name* of an environment
variable (e.g. `"GITHUB_TOKEN"`), never the value. The value is resolved at the egress
boundary (`resolve_secret`) and injected into a tool/MCP server's environment, never into
a prompt, the stored config, an `Output`, logs, or telemetry. An `MCPConnection`'s `auth`
field is a secret reference, by construction.

## Safe egress — the Sink invariants

A `Sink` is the one place side effects happen, and three invariants make that safe:

1. **Static-only targets.** Destination slots (repo, project, channel) must be
   `Flow.STATIC`. A fluid target is rejected at construction (`TargetMustBeStaticError`),
   so a prompt can never redirect a write.
2. **Idempotency.** Every write is keyed by a hash of *static config only* plus the
   batch/output identity (never the fluid/model-derived value). Re-running the same batch
   is a no-op, not a duplicate side effect.
3. **Approval gate.** An `always_ask` sink refuses to fire without an explicit approval
   callback (raising `ApprovalRequired`). Runs can also suspend durably on approval before
   spending any compute (`requires_approval` → `RunSuspended`).

## Team coordination

A `TeamSpec` carries the multi-agent topology. Coordination leans on Claude's
**hierarchical subagent model**, not a bespoke message bus — communication is
*delegation-in / typed-result-out*:

- **`SINGLE`** — one agent (or independent agents), no coordinator.
- **`LEAD`** — a lead dispatches the roles in its `delegates_to`, then combines their
  typed results. Each subagent result re-enters the lead as **fluid data**
  (`{role}_result`), never as instructions — preserving typing and the injection boundary.
- **`SEQUENTIAL`** — agents run in declared order; each result threads into the next as
  `prior_result`.

`run_team` executes the topology and returns one `RunResult`. The coordinator is
runtime-agnostic (works with the mock, so tests are deterministic).

## The Store and ArtifactStore seams

All persistence goes through the `Store` protocol — the product model imports the
*protocol*, never a concrete backend, so SQLite → Postgres is a driver swap and no raw
SQL appears at any call site. Every row carries an `org_id` tenancy key (defaulted
`"local"`), so cloud multi-tenancy is a driver swap, not a schema migration. The local
default is `SqliteStore`. The `Store` backs typed records, KV/working memory, idempotency
claims, and the append-only event ledger that powers the inspector.

- **`Memory`** is a thin `Store`-backed KV/dedup handle scoped to a `(namespace, org_id)`
  pair: working memory (`get`/`set`), cross-run dedup (`already_processed`/
  `mark_processed`), and an atomic `claim` that wins exactly once per id. Because state
  lives in the `Store`, dedup survives across runs.
- **`ArtifactStore`** (with `LocalArtifactStore` and `offload_if_large`) is the blob seam
  — local filesystem locally, S3 later — so large payloads are offloaded by reference
  rather than carried inline.

## Cost, budgets, and inspection

- **`estimate_cost(definition, items=N)`** is a deterministic dry-run preview (one run per
  agent per item, priced from a coarse per-model table) returning a `CostEstimate` — see
  the bill before a single model call. The `mock` model is free, so dev/replay preview
  at $0.
- **`CostBudget`** is the hard ceiling the orchestrator can hard-kill on (`BudgetExceeded`).
  **`Budget`** layers a warn/stop policy on top (`BudgetState`: ok/warn/stopped), and
  **`CostMeter`** is a live accumulator with remaining-headroom tracking.
- **`inspect_run(store, run_id)`** derives a `RunReport` (status, cost, latency, tool
  calls, transcript) purely from the Store's append-only event ledger — no live model
  call. `tail_events` is the poll primitive for live streaming; `format_report` renders a
  report for the CLI. This is the trust/devtools layer (the `craw inspect`/`craw logs`
  backing).

## The measurement loop

`Metric` → `Rubric` → `Benchmark` make quality measurable and comparable across Definition
versions. The eval data lifecycle (`EvalCase`, `GoldenSet`, `LLMJudge`, `capture_case`,
`grade_output`, `save_baseline`/`load_baseline`/`gate_against_baseline`) lets you capture
real runs as reusable cases, curate versioned golden sets, grade with an LLM-as-judge, and
gate a candidate against a stored regression baseline. All deterministic under
mock/replay. See the [cookbook](cookbook.md) for eval-as-test.
