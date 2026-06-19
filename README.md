# crawfish-framework

**Agents for bulk work over your data** — `Source → Batch (fan-out) → Aggregator
(reduce) → Router (branch) → Sink`, authored as directories and run locally via
`claude -p` with zero API key. Measured + trustworthy: typed, versioned, benchmarked.

Think *dbt / Airflow for agents*, not another chatbot SDK.

## Quick start

```bash
uv sync
uv run craw run        # runs the engine bootstrap end to end
uv run pytest -q       # the test suite
```

## Docs

- [Product](docs/product/PRODUCT.md) — positioning, hero use case, personas
- [Architecture](docs/architecture/ARCHITECTURE.md) — the three seams · [ADRs](docs/architecture/decisions)
- [Security spine](docs/architecture/SECURITY.md)
- [Roadmap](docs/roadmap/README.md) — the live Phase 1 plan (CRA-98, M0–M5)
- [Getting started](docs/guide/getting-started.md)

Status: **M0 (foundation) complete** — core types, structural type registry, versioning,
the `Store` seam, the engine bootstrap, packaging + CI. M1–M5 in progress.

See [CLAUDE.md](CLAUDE.md) for development guidance.
