# Crawfish — Product

## Positioning (the wedge)

Most agent frameworks are **conversation-centric** (one chat, one task). Crawfish is
**agents for bulk work over your data** — `Source → Batch (fan-out) → Aggregator
(reduce) → Router (branch) → Sink` — with a built-in **measurement loop**. Think
**dbt / Airflow for agents**, not another chatbot SDK. Measured + trustworthy:
runs are typed, versioned, benchmarked against golden sets, and cost-previewed.

## Hero use case

> Run an agent team over thousands of tickets / PRs / rows, measure the quality, and
> ship the good output — **locally, with no hosted dependency**.

The trust loop, end to end: a multi-item Source fans out → a Definition team runs per
item via `claude -p` → an Aggregator reduces → a Router branches by classification → a
Sink opens real PRs (dry-run → real).

## Personas

- **The automator** — wants thousands of items triaged/processed without babysitting a
  chat. Cares about fan-out, retries/dead-letter, and cost caps.
- **The quality owner** — wants to *trust* agent output before it ships. Cares about
  rubrics, benchmarks vs. golden sets, and catching regressions across Definition versions.
- **The framework author** — builds reusable Definitions (agent-team directories) and
  shares them. Cares about typed IO, versioning/freezing, and a stable API.

## Why local-first matters

`pip install crawfish` + `craw init` + `craw dev` gives a working loop in minutes with
**zero API key** (uses the user's Claude subscription via `claude -p`). Adoption lever #1:
minutes from install to an impressive, useful result.
