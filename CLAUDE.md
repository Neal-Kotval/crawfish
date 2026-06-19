# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Crawfish** — an open-source Python framework for *agents that do bulk work over your
data*: `Source → Batch (fan-out) → Aggregator (reduce) → Router (branch) → Sink`,
authored as directories and run locally via `claude -p`. The build is tracked as Linear
epic **CRA-98** (35 sub-issues, milestones M0–M5). Build in dependency order; the live
plan is mirrored in [`docs/roadmap/README.md`](docs/roadmap/README.md).

## Commands

All commands run through `uv` from the repo root.

```bash
uv sync                                  # install workspace + dev deps (editable)
uv run ruff check .                      # lint
uv run ruff format .                     # format (check: --check)
uv run mypy packages/crawfish/src        # typecheck (strict)
uv run pytest -q                         # full test suite
uv run pytest packages/crawfish/tests/test_store.py -q          # one test file
uv run pytest packages/crawfish/tests/test_store.py::test_kv_roundtrip   # one test
uv run craw run                          # run the engine bootstrap (no-op pipeline)
uv build packages/crawfish               # build the wheel
```

**Definition of Done for any change:** `ruff` + `mypy` clean, `pytest` green and
deterministic (no live model calls — fixtures / record-replay), security spine upheld,
the demo exercises it end to end, docs updated.

## Layout

- `packages/crawfish/src/crawfish/` — the OSS framework (the `pip install crawfish` dist).
  - `core/` — typed-IO atoms: `Flow`, `Parameter`, `Node`, `Policy`, `RunContext`
    (`CostBudget` + `CancelToken`), `parameters_compatible`. **The substrate everything imports.**
  - `typesystem/` — structural `TypeRegistry`; `Parameter.type` resolves here, not by string equality.
  - `versioning/` — `Version` + `Freezable` (frozen artifacts reject mutation).
  - `store/` — the `Store` protocol + `SqliteStore` (WAL, tenancy key, transactional idempotency, event ledger).
  - `engine.py` — pipeline bootstrap behind `craw run`. `config.py` — `crawfish.toml` + profiles. `cli.py` — `craw`.
- `packages/crawfish/tests/` — pytest, one file per issue's acceptance criteria.
- `docs/` — `roadmap/` (live backlog), `architecture/` (ARCHITECTURE, SECURITY, `decisions/` ADRs),
  `product/`, `guide/`.
- `demo/triage-bot/` — the dogfood project; extended and run every milestone.

## Architecture rules (non-negotiable)

These are the seams that keep cloud + scale a driver swap, not a rewrite — see
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) and the ADRs.

- **Three swappable seams**: `AgentRuntime` (loop/backend), `Store` (persistence),
  `ArtifactStore` (blobs). **The product model imports their protocols, never a concrete
  backend.** No SDK import in nodes; no raw SQL outside a `Store` impl.
- **Type compatibility is structural**, via `crawfish.typesystem`, never string equality
  (ADR 0002).
- **Pydantic for data shapes, ABCs for behavioural nodes**; enums are `(str, Enum)` —
  `ruff` `UP042` is intentionally disabled (ADR 0004).
- **Tenancy**: every `Store` row carries `org_id` (defaulted `"local"`).

## Security spine (enforced on every feature, from day one)

See [`docs/architecture/SECURITY.md`](docs/architecture/SECURITY.md). The load-bearing
rule: `Flow.FLUID` inputs are **untrusted session data** (the prompt-injection boundary)
— they reach the model as data, never as instructions. Consequential **Sink targets and
idempotency keys are static-only**; secrets are matched to nodes, resolved by reference,
never logged or in-prompt; host-side node code runs out-of-process with taint propagation
from fluid inputs.

## Working conventions

- One owner per file — don't have two work-streams edit the same module.
- On an architectural/security fork: investigate, decide, and record an ADR in
  `docs/architecture/decisions/` with rationale + rejected alternatives. Keep moving.
- Each Linear issue references its Notion build spec; match its types, deliverables, and
  worked example. Mark an issue `Done` only after QA + security sign-off.
