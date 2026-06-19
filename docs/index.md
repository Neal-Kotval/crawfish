# Crawfish

**Agents for bulk work over your data** — `Source → Batch (fan-out) → Aggregator
(reduce) → Router (branch) → Sink`, authored as directories and run locally via
`claude -p` with zero API key. Measured + trustworthy: typed, versioned, benchmarked.

Think *dbt / Airflow for agents*, not another chatbot SDK.

## Start here

- **[Getting started](guide/getting-started.md)** — install → first run in minutes
- **[Tutorial](guide/tutorial.md)** — build the triage bot end to end
- **[Concepts](guide/concepts.md)** — the directory model, pipelines, runtimes, the security boundary
- **[Cookbook](guide/cookbook.md)** — copy-paste recipes
- **[API reference](guide/api-reference.md)** — the public surface

## Under the hood

- **[Architecture](architecture/ARCHITECTURE.md)** — the three swappable seams · [ADRs](architecture/decisions)
- **[Security spine](architecture/SECURITY.md)** — the prompt-injection boundary, secrets, taint
- **[API stability](architecture/API-STABILITY.md)** — semver + deprecation policy
- **[Product](product/PRODUCT.md)** — positioning, hero use case, personas
- **[Roadmap](roadmap/README.md)** — the Phase-1 plan (CRA-98)

## The 30-second version

```bash
uv sync
craw init my-app && cd my-app
craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"
```
