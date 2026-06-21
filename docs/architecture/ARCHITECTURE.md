# Crawfish Architecture

How Crawfish turns a directory of files into typed, swappable runtime parts.

## The model

An **agent is a directory**. Write markdown (instructions and skills) and Python (tools,
typed IO); the framework **compiles** the directory into typed runtime objects. The
control-flow model:

```
Source → Filter → Batch(Definition) → Aggregator → Router → Sink
              ├─ fan-out:    one Run per item        (map)
              ├─ Aggregator: N Outputs → one         (reduce)
              └─ Router:      branch by label         (branch)
```

## Three swappable seams

The product model imports **none** of these directly — only their protocols. That is what
makes moving to cloud and scale a driver swap, not a rewrite.

| Seam | Protocol | Local default | Later |
|------|----------|---------------|-------|
| `AgentRuntime` | the agent loop/backend | CommandRuntime (`claude -p`) | ClientRuntime / ManagedRuntime (CMA) |
| `Store` | persistence | `SqliteStore` (WAL) | Postgres |
| `ArtifactStore` | blobs | local filesystem | S3 |

## Foundation (M0, shipped)

- **`crawfish.core`** — typed-IO atoms: `Flow` (STATIC/FLUID), `Parameter`, `Node`,
  `NodeKind`, `Policy`, `RunContext` (with `CostBudget` + `CancelToken`), and
  `parameters_compatible`. `crawfish.core.context.RunContext` carries the `org_id`
  tenancy key, defaulted `"local"`.
- **`crawfish.typesystem`** — a structural `TypeRegistry`: `Parameter.type` resolves
  to a registered type (primitive / record / `list[X]` / `Optional[X]`), with
  covariance, record width-subtyping, and JSON-Schema export.
- **`crawfish.versioning`** — `Version` (`0.1-sha` / `0.2`) + `Freezable`; a frozen
  artifact rejects mutation.
- **`crawfish.store`** — the `Store` protocol + `SqliteStore` (WAL, tenancy key,
  transactional `INSERT OR IGNORE` idempotency, append-only event ledger).
- **`crawfish.engine`** — the bootstrap that runs a pipeline of steps end to end
  under one `RunContext` (a no-op pipeline is valid). The richer typed `Workflow`
  builds on this.
- **`crawfish.config`** — `crawfish.toml` manifest + profile resolution
  (`dev`→command, `prod`→managed).

## Emission stream (Phase 2 observability)

- **`crawfish.emission`** — one typed signal, `Emission`. Every producer writes it onto
  the append-only event ledger, and every consumer (inspector, dashboard, anomaly engine)
  reads it. It rides the existing `Store.append_event` transport, so there is no new
  persistence seam and `ScrubbingStore` redaction still applies on write.
- The envelope and the **closed** `EmissionKind` taxonomy (10 kinds: `run_start`,
  `run_finish`, `model`, `tool`, `sink`, `compaction`, `observer`, `metric`,
  `secret_lease`, `jail_violation`) are a frozen contract — see
  [`emission-taxonomy.md`](emission-taxonomy.md) and
  [ADR 0013](decisions/0013-emission-taxonomy-and-inline-output-value.md). Each kind's
  required `attrs` keys are pinned in `REQUIRED_ATTRS`; `EMISSION_SCHEMA_VERSION` lets
  the ledger evolve.
- `emit(store, e, *, max_per_run=...)` writes an emission (with a lightweight per-run
  volume cap as a flood/DoS guard); `read_emissions(store, run_id)` reads them back.
  `Emission.from_event` is a **back-compat shim**: it lifts both new typed emissions
  *and* the legacy loose telemetry dicts older runs wrote (mapping `runtime.run` →
  `model`, run-lifecycle spans → `run_start`/`run_finish`, `sink.write` → `sink`,
  `context.compaction` → `compaction`, `ObserverEvent` dumps → `observer`; anything
  unrecognized lifts into a generic `metric` carrying the raw payload), so old runs
  stay inspectable.
- **Security:** `tainted` carries the fluid/untrusted marker across the emission
  boundary. Every emit site that holds an Output sets it from the producing
  `Output.tainted`. Emissions never carry secret values — `secret_lease` carries the
  `ref` only, and the ledger is written through `ScrubbingStore`.

## Typed outputs & validation (Phase 2)

- **`crawfish.validation`** turns a Definition's declared `outputs` / `inputs`
  (`list[Parameter]`) into a real type contract. `validate_output(text, outputs, reg)`
  parses the model's text and validates it against the schema; `validate_inputs(values,
  schema, reg)` checks bound input *values* (not just presence, which `run.validate()`
  did); `structural_diff(before, after)` is the order-canonical diff eval scoring and the
  tuner key off of. Validation is **registry-driven** — it walks the resolved `TypeDef`
  (PRIMITIVE / RECORD / LIST / OPTIONAL) from `crawfish.typesystem`, so there is **no new
  runtime dependency** (no `jsonschema`).
- **Extraction (parse-from-text).** `claude -p` (CommandRuntime) has no JSON mode and
  returns free text, so `validate_output` extracts JSON *out of* the text. It strips
  Markdown code fences and isolates the outermost `{...}` / `[...]` span before decoding.
  A single `str`-typed output (or a Definition with **no** declared outputs) is a
  pass-through: the raw text becomes `Output.value`, which keeps back-compat with the
  string-output era. Otherwise the parsed value is **canonicalised** (record keys
  sorted) so golden-set equality and diffs are deterministic under record/replay.
- **`Output.value` is the typed value, not a string.** On completion `run.py` builds
  `Output(value=<typed>, output_schema=definition.outputs, ...)` — a RECORD output yields
  a validated `dict`, a LIST a `list`, etc. (ADR 0013: the value is inline). `Metric`s
  and the inspector read it directly.
- **Failure reasons vs the action policy are distinct.** `ValidationFailure` is the
  **closed set of reasons** (`NOT_JSON`, `MISSING_FIELD`, `TYPE_MISMATCH`, `EXTRA_FIELD`,
  `EMPTY_SCHEMA`, `CONSTRAINT`) carried on each `ValidationError`. `ValidationAction`
  (`RETRY` / `REPAIR` / `DEAD_LETTER`) is the separate *policy* a `Run` applies when an
  output fails: `RETRY` re-runs via the existing `RetryPolicy`; `REPAIR` re-prompts the
  model **once** with the schema error fed back as fluid data (a metered extra call that
  respects `ctx.cost_budget` / `ctx.cancel_token`); `DEAD_LETTER` (default) gives up.
  The value is never silently coerced.
- **Security / taint.** The typed value is untrusted model output → `tainted=True` when
  any input was fluid **or** the run consumed any `tool_result` event (a malicious tool
  output is an injection vector). A wrong-typed input is rejected *before* any model call.
  Callers that deliberately over-bind (the `Router`'s classifier) opt out via
  `validate_input_types=False` / `validate_output_schema=False`.

## Schema migrations (Phase 2)

An older `.crawfish` database must upgrade cleanly when a newer binary opens it. The
schema version lives in SQLite's built-in `PRAGMA user_version`. `SqliteStore.__init__`
runs `crawfish.store.migrations.apply_migrations` under its lock: it applies every forward
migration whose version exceeds the on-disk version (each in its own transaction), then
stamps `user_version`. See ADR 0014.

- **Migration 1 is the baseline** — the original table set, written `CREATE TABLE IF NOT
  EXISTS`. So a brand-new DB and an existing *pre-versioning* DB (tables already present,
  `user_version=0`) both converge. Re-opening a current DB applies nothing (idempotent).
- **Downgrade is refused.** If `user_version` exceeds `CURRENT_SCHEMA_VERSION`, a newer
  binary wrote the DB; `apply_migrations` raises `StoreMigrationError` rather than risk
  corruption.
- **Concurrency** is safe: migrations run under the store lock and SQLite's file lock; a
  second opener sees the bumped `user_version` and applies nothing.

**Migration-authoring contract.** Phase-2 work that persists a new shape does two things:
(1) **append a `Migration`** in `store/migrations.py` with the next ascending `version`
and bump `CURRENT_SCHEMA_VERSION`; keep the body additive/idempotent (`IF NOT EXISTS`,
additive `ALTER TABLE`) so it is safe on a DB at any older version. (2) If the new shape
changes how a stored record *kind* is interpreted, **register a read-path up-converter**
in `RECORD_UPCONVERTERS` (keyed by `kind`); it lifts an individual legacy row's JSON
envelope to the current shape lazily on read in `get_record` / `list_records` — the
record analogue of CRA-171's `Emission.from_event`. A migration fixes the table; the
up-converter fixes a row, without a bulk rewrite. (Emission retention/rotation and
`max_per_run` are a separate concern, deliberately out of scope here.)

## Packaging

- `packages/crawfish` — the OSS framework (the `pip install crawfish` distribution).
- `packages/crawfish-cma` — the CMA/ManagedRuntime backend (later).
- Module discovery reads the `crawfish.sources` / `crawfish.sinks` /
  `crawfish.definitions` / `crawfish.types` entry-point groups.
- A user project is **self-contained** (root = the project); `.crawfish/` is
  generated state only; installed plugins live in site-packages, pinned by
  `crawfish.lock`.

## Conventions

- The product model **never imports the SDK** — all model calls go through
  `AgentRuntime`. No raw SQL escapes the `Store` implementation.
- See [`SECURITY.md`](SECURITY.md) for the security spine and
  [`decisions/`](decisions) for ADRs.

!!! note "Good to know"
    The three seams are the load-bearing rule. As long as the product model imports only
    `AgentRuntime`, `Store`, and `ArtifactStore` protocols — never a concrete backend —
    cloud and scale stay a configuration change. Breaking that rule is what turns a swap
    into a rewrite.

## See also

- [Security](SECURITY.md) — the prompt-injection boundary, secrets, and taint
- [Emission taxonomy](emission-taxonomy.md) — the frozen observability contract
- [API stability](API-STABILITY.md) — semver and deprecation policy
- [ADRs](decisions) — the decisions behind these seams
