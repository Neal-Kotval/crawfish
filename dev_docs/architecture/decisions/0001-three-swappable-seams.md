# ADR 0001 — Three swappable seams

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M0

## Context

The framework must run locally with nothing hosted, yet scale to cloud + multi-tenant
without a rewrite. The risk is that primitives reach for a concrete backend (the
Anthropic SDK, raw SQL, the local filesystem) and ossify around it.

## Decision

Three protocols are the only backend touch-points, and the product model imports
**none** of them concretely:

- `AgentRuntime` — the agent loop/backend (CommandRuntime → ClientRuntime → ManagedRuntime).
- `Store` — persistence (`SqliteStore` → Postgres).
- `ArtifactStore` — blobs (local FS → S3).

`Store` ships first (M0) as a `typing.Protocol` with a SQLite reference impl. No raw
SQL appears at any call site. `AgentRuntime` and `ArtifactStore` land in M1/M3 behind
the same discipline.

## Alternatives rejected

- **Import the SDK directly in nodes** — fastest to write, but couples every primitive
  to one provider and makes the OSS/CMA boundary impossible to draw.
- **One god "Backend" object** — collapses three independent swap axes (loop, storage,
  blobs) into one, forcing all-or-nothing replacement.

## Consequences

Cloud and scale become driver swaps. The cost is protocol discipline: a new primitive
must route persistence through `Store` and model calls through `AgentRuntime`, checked
in review.
