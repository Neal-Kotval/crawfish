# API stability

This page tells you what is stable, what is not, and how Crawfish changes an API without
breaking your code. Use it to decide which names you can build on. The policy lives in
code in `crawfish/stability.py`.

## Public API surface

The public API is exactly what `crawfish/__init__.py` re-exports. A name not re-exported
from the package root is private: internal modules, `_`-prefixed names, and anything not
listed in `__all__` may change at any time without notice.

Every public name carries a stability tier, declared with the decorators in
`crawfish.stability` and readable by tooling through `stability_of(obj)`.

| Tier | Decorator | Meaning |
|------|-----------|---------|
| STABLE | `@stable` | Covered by semver. Breaks only on a major bump, and only after deprecation. |
| EXPERIMENTAL | `@experimental` | May change or break in any minor release. This is the default for untagged names. |
| DEPRECATED | `@deprecated(since=…, removed_in=…, use=…)` | Scheduled for removal. Still works, but emits a `DeprecationWarning` naming the replacement. |

```python
from crawfish.stability import stable, experimental, deprecated, stability_of, Stability

@stable
def run(...): ...

stability_of(run) is Stability.STABLE  # True
```

Untagged names are experimental by default. Nothing is stable until you promote it with
`@stable`, so pin to names you can confirm are `STABLE` through `stability_of(obj)`.

## Semver policy

Crawfish versions follow [SemVer 2.0.0](https://semver.org). The version string is
`MAJOR.MINOR.PATCH`.

In the pre-1.0 series (`0.x`):

- A patch (`0.4.0 → 0.4.1`) is bug fixes only. It never breaks any API, stable or
  experimental.
- A minor (`0.4.x → 0.5.0`) may break experimental APIs. Stable APIs are not broken; a
  stable API that must change goes through the deprecation process first.
- There is no major axis below 1.0. The `0.x` series signals that the stable surface is
  still consolidating, but the deprecation discipline below already applies to anything
  tagged `@stable`.

After 1.0:

- A major (`1.x → 2.0`) is the only release that may remove or break a stable API, and
  only for an API already deprecated for at least one minor release.
- A minor (`1.4 → 1.5`) adds APIs and may break experimental ones. Stable APIs are
  additive only.
- A patch (`1.4.0 → 1.4.1`) is bug fixes only.

Tooling computes the coarse breaking-change signal with `is_breaking(old, new)` (a
major-component bump) and renders a one-line summary with `migration_note(old, new)`.

## Deprecation process

A stable API is never removed in one step. The lifecycle is:

1. Mark. Apply `@deprecated(since="<this-version>", removed_in="<next-major>",
   use="<replacement>")`. The decorator tags the object `Stability.DEPRECATED` and emits a
   `DeprecationWarning` on every call, naming the replacement.
2. Warn for at least one minor release. The deprecated API stays callable (warning only)
   across at least one full minor release, so downstream code has a release to migrate in.
3. Remove on the next major. Removal lands only in the major release named by
   `removed_in`, never in a minor or patch.

A breaking change is therefore inseparable from a deprecation plus a migration note.
Acceptance for any breaking change requires both.

## Migration guides and codemods

Every breaking change ships with two things: a migration guide (what changed, why, the
manual before and after, and the deprecation timeline) and a codemod in the codemod
harness, so the mechanical part of the upgrade runs as a command rather than by hand. The
codemod harness and migration-guide template land alongside the first breaking change that
needs them.

## Next steps

- [Architecture](ARCHITECTURE.md) covers the primitives this policy stabilizes.
- [API reference](../guide/api-reference.md) lists the public surface, by symbol.
- [Security](SECURITY.md) covers the prompt-injection boundary and secrets.
