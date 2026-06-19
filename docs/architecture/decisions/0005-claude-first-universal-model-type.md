# ADR 0005 — Claude-first runtime, model-universal type

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M1 (CRA-102, CRA-112)

## Context

The Definition spec flags an unresolved tension: `AgentSpec.model` is typed
`str | list[str] | None` (model-universal — `None` lets the platform pick), but the
Phase 1 roadmap resolves the MVP to **Claude-first**. The spec says to settle this
before coding `AgentRuntime`.

## Decision

Keep the **type universal**, ship the **runtime Claude-first**:

- `AgentSpec.model` stays `str | list[str] | None` so universality is expressible from
  day one and Definitions authored now don't need migration later.
- The reference runtime is `CommandRuntime` (`claude -p`). When an agent is unpinned
  (`model is None`), the Claude-first runtime selects a default Claude model
  (`claude-opus-4-8`); a pin restricts that agent. Multi-provider routing is deferred
  to the Smart-Routing phase, behind the same `AgentRuntime` seam.

## Alternatives rejected

- **Type the field Claude-only** (`model: str | None` meaning a Claude id) — would force
  a breaking type change when universality ships.
- **Implement multi-provider routing now** — scope creep against the Claude-first MVP;
  the seam already makes it a later additive change.

## Consequences

A Definition is portable to a future universal runtime without edits. The runtime must
document that `None` means "default Claude model" today, not "any provider" yet.
