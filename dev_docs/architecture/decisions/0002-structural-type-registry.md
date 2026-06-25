# ADR 0002 — Structural type registry over stringly-typed parameters

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M0

## Context

The spec left an open question: is `Parameter.type` a free string (`"list[PR]"`), or
does it resolve to a registered type so compatibility is structural? The framework's
core promise — typed pipeline wiring and canvas safety — is illusory if compatibility
is string equality (`"list[PR]" == "list[PR]"`), which can't express covariance,
optionality, or record subtyping.

## Decision

`Parameter.type` stays a **string on the wire** (language-neutral, JSON-friendly) but
**resolves through a `TypeRegistry`** for all compatibility checks. Compatibility is
structural:

- primitives match by name (unknown bare names are nominal primitives — ergonomic);
- `list[A] → list[B]` iff `A → B` (covariant);
- non-optional `A` may feed `Optional[A]`; `Optional[A] → Optional[B]` iff `A → B`;
- records use **width subtyping**: a producer must supply every field the consumer needs.

Every type exports JSON-Schema so the console & registry read it without Python.

## Alternatives rejected

- **Free-string equality** — simplest, but no covariance/records; rejects valid wires
  and accepts invalid ones.
- **Reuse Pydantic models as the type identity** — ties the language-neutral wire
  format to Python classes; the console (TypeScript) can't consume it.

## Consequences

A mistyped wire is rejected with a *structural* reason (`TypeRegistry.explain`). Records
must be registered to unlock field rules; bare names fall back to nominal matching so
quick authoring still works.
