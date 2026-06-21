# API Stability, Semver & Migration Policy

What's stable, what isn't, and how Crawfish breaks an API without breaking you.

**Status:** Accepted · **Date:** 2026-06-19

This is the contract that lets you adopt the Crawfish OSS core for serious work. React's
deprecation discipline plus codemods are *why* large codebases trust upgrades. This
document and `crawfish/stability.py` are the Crawfish equivalent.

## Public API surface

The public API is exactly what `crawfish/__init__.py` re-exports. A name not re-exported
from the package root is private — internal modules, `_`-prefixed names, and anything not
listed in `__all__` may change at any time without notice.

Every public name carries a stability tier, declared in code with the decorators in
`crawfish.stability` and readable by tooling via `stability_of(obj)`:

| Tier | Decorator | Meaning |
|------|-----------|---------|
| **STABLE** | `@stable` | Covered by semver. Breaking changes only on a major bump, and only after deprecation. |
| **EXPERIMENTAL** | `@experimental` | May change or break in any minor release. The **default** for untagged names — nothing is stable until explicitly promoted. |
| **DEPRECATED** | `@deprecated(since=…, removed_in=…, use=…)` | Scheduled for removal. Still works, but emits a `DeprecationWarning` naming the replacement. |

```python
from crawfish.stability import stable, experimental, deprecated, stability_of, Stability

@stable
def run(...): ...

stability_of(run) is Stability.STABLE  # True
```

!!! note "Good to know"
    Untagged names are **experimental** by default. Nothing is stable until you promote it
    with `@stable`. Pin to names you can see are `STABLE` via `stability_of(obj)`.

## Semver policy

Crawfish versions follow [SemVer 2.0.0](https://semver.org). The version string is
`MAJOR.MINOR.PATCH`.

**Pre-1.0 (the `0.x` series):**

- **patch** (`0.4.0 → 0.4.1`): bug fixes only. Never breaks any API, stable or experimental.
- **minor** (`0.4.x → 0.5.0`): may break **experimental** APIs. Stable APIs are not broken;
  if a stable API must change, it goes through the deprecation process first.
- There is no `major` axis below 1.0; `0.x` signals the stable surface is still
  consolidating, but the deprecation discipline below already applies to anything tagged
  `@stable`.

**Post-1.0:**

- **major** (`1.x → 2.0`): the only release that may remove or break a **stable** API,
  and only for APIs already deprecated for at least one minor release.
- **minor** (`1.4 → 1.5`): adds APIs and may break **experimental** ones; stable APIs are
  additive-only.
- **patch** (`1.4.0 → 1.4.1`): bug fixes only.

Tooling computes the coarse breaking-change signal with
`crawfish.stability.is_breaking(old, new)` (a major-component bump) and renders a one-line
summary with `migration_note(old, new)`.

## Deprecation process

A stable API is never removed in one step. The lifecycle is:

1. **Mark.** Apply `@deprecated(since="<this-version>", removed_in="<next-major>", use="<replacement>")`.
   The decorator tags the object `Stability.DEPRECATED` and emits a `DeprecationWarning`
   on every call, naming the replacement.
2. **Warn for ≥ 1 minor release.** The deprecated API must remain callable (warning only)
   across at least one full minor release so downstream code has a release to migrate in.
3. **Remove on the next major.** Removal lands only in the major release named by
   `removed_in`, never in a minor or patch.

A breaking change is therefore inseparable from a deprecation plus a migration note:
acceptance for any breaking PR requires both.

## Migration guides + codemods

Every breaking change ships with:

- a **migration guide** from a shared template (what changed, why, the manual before/after,
  and the deprecation timeline), and
- a **codemod** in the codemod harness, so the mechanical part of the upgrade is
  automated rather than hand-applied.

This mirrors the React model: deprecate with a clear replacement, keep it working for a
release, and hand users a codemod so the upgrade is a command, not a chore. The codemod
harness and migration-guide template land alongside the first breaking change that needs
them.

## See also

- [Architecture](ARCHITECTURE.md) — the primitives this policy stabilizes
- [API reference](../guide/api-reference.md) — the public surface, by symbol
- [ADRs](decisions) — the decisions behind the stabilized primitives
