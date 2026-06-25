# Architecture

Crawfish is a programming language for agents. You write an agent as a directory of files
and Crawfish compiles that directory into typed runtime objects you can run, test, and
version. This page explains how the system is built and which parts you can swap.

## The model

An agent is a directory. You write markdown for instructions and skills, and Python for
tools and typed inputs and outputs. Crawfish compiles the directory into typed runtime
objects and runs them as a pipeline:

```text
Source → Filter → Batch(Definition) → Aggregator → Router → Sink
              ├─ fan-out:    one Run per item   (map)
              ├─ Aggregator: N Outputs → one     (reduce)
              └─ Router:      branch by label    (branch)
```

A *source* reads data in. A *batch* fans the data out to one run per item. An
*aggregator* reduces many outputs to one. A *router* branches on a label. A *sink* writes
the result to the outside world.

## Three swappable seams

Crawfish has three parts you can replace without touching pipeline code. The product
model imports their protocols, never a concrete backend. That is what keeps the move to
cloud and scale a configuration change rather than a rewrite.

| Seam | What it does | Local default | Later |
|------|--------------|---------------|-------|
| `AgentRuntime` | runs the agent loop against a backend | `CommandRuntime` (`claude -p`) | `ClientRuntime` / `ManagedRuntime` |
| `Store` | persistence | `SqliteStore` (WAL) | Postgres |
| `ArtifactStore` | blob storage | local filesystem | S3 |

As long as the product model imports only these protocols, moving from your machine to a
managed backend is a runtime swap. Breaking that rule is what turns a swap into a rewrite.

## Core types

`crawfish.core` holds the typed atoms everything else builds on: `Flow` (`STATIC` or
`FLUID`), `Parameter`, `Node`, `NodeKind`, `Policy`, `RunContext` (with `CostBudget` and
`CancelToken`), and `parameters_compatible`. `RunContext` carries the `org_id` tenancy
key, which defaults to `"local"`. Every `Store` row carries an `org_id`, so the same
database can hold more than one tenant.

`crawfish.typesystem` is a structural type registry. A `Parameter.type` resolves to a
registered type (a primitive, a record, `list[X]`, or `Optional[X]`), with covariance,
record width-subtyping, and JSON-Schema export. Two nodes wire together when their shapes
match, not when their type names are equal.

`crawfish.versioning` gives every agent a content-addressed `Version` (such as `0.1-sha`
or `0.2`) and a `Freezable` base. A frozen artifact rejects mutation, so a side effect is
always attributable to one reproducible hash.

`crawfish.store` defines the `Store` protocol and `SqliteStore`. The store uses WAL mode,
carries the tenancy key, runs check-then-write idempotency as a single transaction
(`INSERT OR IGNORE`), and keeps an append-only event ledger.

`crawfish.engine` runs a pipeline of steps end to end under one `RunContext`. An empty
pipeline is valid. `crawfish.config` reads the `crawfish.toml` manifest and resolves
profiles (`dev` maps to the command runtime, `prod` to the managed runtime).

## Observability

Every producer writes one typed signal, an `Emission`, onto the append-only event ledger,
and every consumer (the inspector, the dashboard, the anomaly engine) reads it back.
Emissions ride the existing `Store.append_event` transport, so there is no separate
persistence path and the same redaction applies on write.

The set of emission kinds is closed: `run_start`, `run_finish`, `model`, `tool`, `sink`,
`compaction`, `observer`, `metric`, `secret_lease`, and `jail_violation`. Each kind pins
the attributes it must carry. A schema version lets the ledger evolve, and a back-compat
shim lifts older loose telemetry into the typed shape so old runs stay inspectable.

Two safety rules hold across the ledger. Every emission carries a `tainted` marker that
follows untrusted (fluid) data across the boundary, and emissions never carry secret
values. A `secret_lease` carries only the reference, and the ledger is written through a
scrubbing layer.

## Typed outputs

`crawfish.validation` turns a Definition's declared `outputs` and `inputs` into a real
type contract. `validate_output(text, outputs, reg)` parses the model's text and checks
it against the schema. `validate_inputs(values, schema, reg)` checks bound input values,
not only that they are present. `structural_diff(before, after)` produces the
order-canonical diff that scoring and the tuner key off of. Validation walks the resolved
type from `crawfish.typesystem`, so it adds no new runtime dependency.

`claude -p` returns free text rather than JSON, so `validate_output` extracts JSON out of
the text: it strips Markdown code fences and isolates the outermost `{...}` or `[...]`
span before decoding. A single `str`-typed output, or a Definition with no declared
outputs, passes the raw text straight through, which keeps back-compat with the
string-output era. Otherwise the parsed value is canonicalised (record keys sorted) so
equality and diffs are deterministic under record and replay.

`Output.value` is the typed value, not a string. A record output yields a validated
`dict`, a list yields a `list`. When an output fails validation, a `Run` applies one
policy: `RETRY` re-runs, `REPAIR` re-prompts the model once with the schema error fed
back as fluid data (a metered call that respects the cost budget and cancel token), and
`DEAD_LETTER` (the default) gives up. The value is never silently coerced. A wrong-typed
input is rejected before any model call.

The typed value is untrusted model output, so it is tainted when any input was fluid or
the run consumed any tool result. A malicious tool output is an injection vector, so it
taints the same way.

## Schema migrations

An older `.crawfish` database upgrades cleanly when a newer binary opens it. The schema
version lives in SQLite's `PRAGMA user_version`. On open, `SqliteStore` applies every
forward migration whose version exceeds the on-disk version, each in its own transaction,
then stamps the new version.

Migration 1 is the baseline, written with `CREATE TABLE IF NOT EXISTS`, so a brand-new
database and an existing pre-versioning one both converge. Re-opening a current database
applies nothing. Downgrade is refused: if the on-disk version is higher than the binary's
current version, a newer binary wrote the database and the open raises rather than risk
corruption. Migrations run under the store lock and SQLite's file lock, so concurrent
opens are safe.

A migration fixes a table. A read-path up-converter fixes one row lazily on read, without
a bulk rewrite, when a stored record's shape changes meaning.

## Cost model

`cost.py` is the single owner of the cost model. No other module re-implements estimation
or re-defines an operator's cost multiplier. A `CostEstimate` carries an expected value, a
worst case, and a confidence band. The scalar `total_usd` is the lower bound, where every
cost-bearing operator fires once.

Composition is multiplicative along operator nesting:
`worst_case_usd = total_usd × Π shape.worst_case_factor()`. Per-operator worst-case
factors are `Refine` to `max_iters`, `Escalate` to `1 + strong_price/base_price`, `Quorum`
to `k`, `Retry` to `n`, and `recurse` to `branching ** max_depth`. For example,
`Refine(4) ∘ Escalate(2×) ∘ Quorum(5)` previews 40 times the lower bound. The expected
band uses each operator's measured escalation or retry rate; with no measured rate, the
expected value equals the worst case, so the estimate never undercounts.

## Run identity and determinism

Every decode parameter enters run identity exactly once, so two distinct decode settings
can never replay the same cassette. The tunable knobs (`temperature`, `top_p`, `sample_k`)
live on the Definition's `AgentSpec` and enter its content hash. Per-call knobs live on the
`RunRequest`: `grammar` for constrained decode, and `decode_seed`, which is folded into the
replay cassette key.

The replay cassette key is the execution coordinate. Beyond the core fields (id, version,
role, model, inputs, session id) it folds an execution coordinate, the `org_id` (when it is
not `"local"`), and the decode seed, but only when each is non-default. With none of them
set, the key reproduces the legacy key exactly, so old cassettes still resolve. Every
operator that re-runs a leaf stamps its coordinate axis, so each re-run gets a distinct
cassette instead of colliding.

An `AgentRuntime` advertises a determinism tier: `HONORS_SEED`, `BEST_EFFORT`, or `NONE`.
This separates model stochasticity from infrastructure nondeterminism, so calibration can
attribute a backend's residual variance to infrastructure rather than to the Definition.

## The gate algebra

`crawfish.experiment` is the shared, pure, stdlib-only statistical substrate: paired
bootstrap confidence intervals, Holm correction, power helpers, and anytime-valid bounds.
It uses no numpy or scipy, and bootstraps are seeded so identical inputs reproduce
byte-for-byte.

The gate algebra reconciles the gate notions and names which consumer uses which. None of
them re-implement statistics.

| Gate | Consumer |
|------|----------|
| relative-regression | cheap mean-only callers |
| variance-aware aggregate | callers retaining a per-metric `std` |
| variance-aware paired | the tuner, calibration, the promotion gate |
| absolute-precision (fails closed) | verifiers, guards, consequential sinks |

The paired gate analyses per-case deltas over identical golden-set cases: a confidence
interval strictly above zero promotes, one straddling zero rejects. The precision gate is
absolute and fails closed, so no baseline means reject. See [Security](SECURITY.md).

## Train mode

`crawfish/borrow.py` provides an exclusive borrow that switches a `Definition` into
train mode. `mutable(target, store, *, org_id=...)` is a context manager that acquires the
borrow on enter and releases it on exit, even on exception. Enforcement lives in the
Store, reusing the idempotency claim, never an in-process registry, so exclusivity holds
across processes and survives the SQLite-to-Postgres swap. Concurrent borrows are rejected
at acquire, and the borrow is keyed on `org_id`, so a borrow held by one org never blocks
another.

## Packaging

`packages/crawfish` is the OSS framework, the `pip install crawfish` distribution.
`packages/crawfish-cma` is the managed-runtime backend, which lands later. Module
discovery reads the `crawfish.sources`, `crawfish.sinks`, `crawfish.definitions`, and
`crawfish.types` entry-point groups. A user project is self-contained: the project root is
the project, `.crawfish/` is generated state only, and installed plugins live in
site-packages, pinned by `crawfish.lock`.

## Conventions

The product model never imports the SDK. Every model call goes through `AgentRuntime`, and
no raw SQL escapes a `Store` implementation. Two nodes wire together only when their types
match, checked when you assemble the pipeline, before any model call.

## Next steps

- [Security](SECURITY.md) covers the prompt-injection boundary, secrets, and taint.
- [API stability](API-STABILITY.md) covers semver and the deprecation policy.
- [Concepts](../guide/concepts.md) covers the boundary in the directory model.
