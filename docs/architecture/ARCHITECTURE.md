# Crawfish Architecture

## The model

An **agent is a directory**. Author markdown (instructions/skills) + Python (tools,
typed IO); the framework **compiles** the directory into typed runtime objects. The
control-flow model:

```
Source → Filter → Batch(Definition) → Aggregator → Router → Sink
              ├─ fan-out:    one Run per item        (map)
              ├─ Aggregator: N Outputs → one         (reduce)
              └─ Router:      branch by label         (branch)
```

## Three swappable seams

The product model imports **none** of these directly — only their protocols. That is
the whole reason cloud + scale are driver swaps, not rewrites.

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

- **`crawfish.emission`** — one typed signal, `Emission`, that every producer writes
  onto the append-only event ledger and every consumer (inspector, dashboard, anomaly
  engine) reads. It rides the existing `Store.append_event` transport — no new
  persistence seam — so `ScrubbingStore` redaction still applies on write.
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
- **Security:** `tainted` propagates the fluid/untrusted marker across the emission
  boundary (set from the producing `Output.tainted` at every emit site that holds an
  Output). Emissions never carry secret values — `secret_lease` carries the `ref`
  only, and the ledger is written through `ScrubbingStore`.

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
