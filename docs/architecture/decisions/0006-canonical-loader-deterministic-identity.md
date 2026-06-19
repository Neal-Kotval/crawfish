# ADR 0006 — One canonical loader; content-derived Definition identity

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M1 (CRA-102)

## Context

A Definition can be loaded two ways: from a local directory (`from_package(path)`) and
as an installed package via a `DefinitionRef@version` (CRA-113). The gap review requires
that both routes materialize an **identical** Definition — otherwise "reproducible
artifact" is a lie and the canvas/registry can disagree with the runtime. A random
`Definition.id` (the type's default `new_id`) or a path-derived identity would break this.

## Decision

- **One canonical loader** (`crawfish.definition.compiler.load_definition`) backs every
  route. `Definition.from_package` and the future installed-package/`DefinitionRef` route
  both call it. CLI discovery (CRA-113) will too.
- **Identity is content-derived, never path- or time-derived.** `Definition.id` is the
  package name (from `pyproject.toml`'s `[project].name`, else the directory name);
  `Version.sha` is a hash of the directory's file contents. `definition.lock`, caches,
  and `.crawfish/` are excluded from the hash so writing the lock doesn't change identity
  on recompile.

A test asserts a directory and a copy at a different path compile byte-identically, and
that recompiling in place is byte-stable.

## Alternatives rejected

- **Random `id` per load** — two loads of the same package differ; defeats reproducibility.
- **Path/mtime-derived identity** — the same package at two paths (dev dir vs.
  site-packages) would diverge.
- **Two separate loaders** (dir vs. installed) — guarantees drift over time.

## Consequences

The lockfile and registry can trust `id@version` as a stable handle. Authors must keep
the package name stable to keep identity stable (renaming is a new identity — correct).
