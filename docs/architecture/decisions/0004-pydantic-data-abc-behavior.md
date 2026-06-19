# ADR 0004 — Pydantic for data shapes, ABC for behavioural nodes; `str`-Enums

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M0 (CRA-99)

## Context

The spec mixes Pydantic models and plain/ABC classes and flags an open question:
unify everything on Pydantic, or keep a split?

## Decision

- **Data/config shapes** (`Parameter`, `Policy`, `Version`, `TypeDef`, later `Output`,
  `Definition`) are **Pydantic** models — free validation, coercion, JSON-Schema export.
- **Behavioural nodes** (`Node`, `Source`, `Sink`, runtimes) are **ABCs** — they carry
  behaviour and lifecycle, not just serialisable state.
- Enums are `class X(str, Enum)` (not `StrEnum`) so Pydantic coerces string values
  cleanly and JSON round-trips are stable. Ruff's `UP042` is disabled for this reason.

## Alternatives rejected

- **Everything Pydantic** — forces serialisation semantics onto stateful runtime objects
  (open connections, cancel tokens) that aren't meaningfully serialisable.
- **`enum.StrEnum`** — equivalent at runtime but the spec mandates the `(str, Enum)`
  form and it interacts most predictably with Pydantic v2 coercion.

## Consequences

`Node` subclasses set `id`/`name`/`kind` in `__init__`. A future need for runtime
validation on a node can still wrap it in a Pydantic config object without reclassifying
the node itself.
