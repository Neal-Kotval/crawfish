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

## Operate & observe

From runs-once to always-on — deploy, watch, and control pipelines locally.

- **[Operations overview](guide/operations.md)** — the deploy → observe → visualize → manage loop, end to end
- **[Deploy](guide/deploy.md)** — `craw deploy`: a detached, scheduled, self-restarting supervisor
- **[Manage](guide/manage.md)** — `craw manage`: list/stop/restart/logs deployed pipelines
- **[Observers](guide/observers.md)** — `crawfish.observe`: rule- and LLM-based watchers over the run-info surface
- **[Visualize](guide/visualize.md)** — `craw visualize`: a loopback-only localhost dashboard
- **[Project structure](guide/project-structure.md)** — the canonical layout, `[project.paths]`, and `craw doctor`
- **[Export to Claude Code](guide/claude-code-export.md)** — `craw export --claude-code`: a Definition as a subagent

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
