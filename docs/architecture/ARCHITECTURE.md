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
