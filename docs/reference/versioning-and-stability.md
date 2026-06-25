# Versioning & stability

Two contracts for change over time. One *pins and seals* a single artifact so a run stays
reproducible. The other lets a *public API surface* declare how much you can depend on it.
The first lives in `crawfish.versioning`, the second in `crawfish.stability`.

`Version` · `FrozenError` · `Freezable` · `Stability` · `stable` · `experimental` ·
`deprecated` · `stability_of` · `is_breaking`

## Two questions, answered separately

You author **artifacts** (definitions, sources, sinks) that you reuse and share. That raises
two questions: which exact copy of an artifact did a run use, and how much can you rely on a
piece of the framework's API not to change under you. The two clusters here answer those
separately.

A **version** stamps an artifact with a `major.minor` number and, optionally, a content
`sha` (a short fingerprint of its contents). As a string it reads `0.2` or `0.1-ab12cd`, the
form a lockfile pins to. A version also carries a **frozen** flag. *Frozen* means sealed: the
artifact becomes an immutable, reproducible unit. You make an artifact freezable by giving it
a `version` field (that is all the `Freezable` mixin does), and you seal it by calling
`freeze()`.

Separately, every public function or class in Crawfish can declare a **stability tier**, a
promise about how much it may change:

- **stable**: you can depend on it; breaking it requires a major version bump.
- **experimental**: usable, but the shape may change without ceremony. This is the
  *default* for anything not explicitly marked.
- **deprecated**: on its way out; still works, but warns on use and names its
  replacement.

You attach a tier with a decorator (`@stable`, `@experimental`, `@deprecated`) and read
it back off any object with `stability_of`. `is_breaking(old, new)` decides whether moving
between two version strings counts as a breaking change. It does when the major number goes
up.

## Why artifacts are versioned and freezable

Reproducibility is the goal: a recorded run must re-run against the *exact* artifacts it
used, not whatever they later became. Pinning a `Version` (number plus content `sha`) gives
a lockfile something stable to reference. Freezing guarantees the referenced copy cannot
drift. Definitions are versioned first, then Source and Sink.

## How freezing blocks mutation

Both `Version` and `Freezable` override `__setattr__` to enforce the seal, but they
guard different things:

- **`Version.__setattr__`** rejects *any* write once `frozen` is `True`. The one
  exception is `freeze()` itself, which flips the flag through `object.__setattr__`,
  bypassing the guard for that single allowed write. So a frozen `Version` is fully
  immutable, including its own `frozen` field.
- **`Freezable.__setattr__`** rejects writes to every field *except* `version` once
  `self.version.frozen` is set. Reassigning `version` stays open; mutating *through* it
  (e.g. `artifact.version.sha = ...`) is blocked by `Version`'s own guard.

`Freezable.freeze()` delegates to `self.version.freeze()`, and the `frozen` property
just reads `self.version.frozen`.

!!! warning "Freezing is one-way"

    There is no unfreeze. Once an artifact is sealed, every write to a frozen `Version` or to
    a frozen `Freezable`'s non-`version` fields raises `FrozenError` (a subclass of
    `RuntimeError`). Seal only when you mean it.

## Stability decorators are behaviour-preserving

A stability decorator never changes what the wrapped object *does*. `@stable` and
`@experimental` set a `__crawfish_stability__` attribute on the object and return it
unchanged. `@deprecated` is a decorator *factory*: it takes keyword arguments and
returns the actual decorator, which wraps the callable in a thin forwarder that emits a
`DeprecationWarning` on each call before delegating. The wrapper preserves the original
signature and metadata via `functools.wraps`. This module makes the policy in
[API-STABILITY.md](../architecture/API-STABILITY.md) machine-readable, so tooling can read
a tier off any symbol uniformly.

!!! note "Good to know"

    `stability_of` returns `Stability.EXPERIMENTAL` for any object that was never tagged.
    Nothing is considered stable until it is *explicitly* promoted with `@stable`. The safe
    default is "this may change."

## What `is_breaking` compares

`is_breaking(old, new)` parses only the **major** component of each version string and
returns `True` when `new`'s major exceeds `old`'s. Parsing is lenient: it strips a
leading `v`, splits on the first `.`, and reads the head as an int, so `"v1.2.3"`,
`"1.2"`, and `"1"` all parse to major `1`. Minor and patch increases are never breaking
by this signal. It is the coarse check tooling uses to decide a migration note is
required.

## Example

Freeze an artifact and watch mutation get rejected, tag a function and read its tier
back, and check two versions for a breaking bump. All pure, no runtime needed.

```python
import warnings
from crawfish.versioning.version import Version, Freezable, FrozenError
from crawfish.stability import experimental, stability_of, is_breaking

# A freezable artifact: mutable until sealed, then locked.
class Definition(Freezable):
    name: str = "triage"

d = Definition()
print(d.frozen)
d.name = "triage-v2"        # allowed while unfrozen
print(d.name)
d.freeze()
print(d.frozen, str(d.version))
try:
    d.name = "nope"         # rejected once frozen
except FrozenError as e:
    print(type(e).__name__)

# Tag a function and read the tier back; untagged defaults to experimental.
@experimental
def fanout(): ...

print(stability_of(fanout).value)
print(stability_of(object()).value)

# Breaking only when the major component increases.
v1, v2, v3 = Version(major=0, minor=4), Version(major=1, minor=0), Version(major=0, minor=9)
print(is_breaking(str(v1), str(v2)))   # 0.4 -> 1.0
print(is_breaking(str(v1), str(v3)))   # 0.4 -> 0.9
```

??? success "▶ Output"

    ```text
    False
    triage-v2
    True 0.1
    FrozenError
    experimental
    experimental
    True
    False
    ```

## API reference

### `Version`

`class Version(BaseModel)`: a semver-ish version with an optional content sha and a
frozen flag.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `major` | `int` | `0` | Major component. |
| `minor` | `int` | `1` | Minor component. |
| `sha` | `str \| None` | `None` | Optional content fingerprint, appended after `-`. |
| `frozen` | `bool` | `False` | When `True`, all writes raise `FrozenError`. |

Methods: `freeze() -> None` seals the version (the one write that bypasses the guard).
`__str__` renders `"{major}.{minor}"`, plus `"-{sha}"` when `sha` is set (e.g. `0.1`,
`0.2-ab12cd`).

### `FrozenError`

`class FrozenError(RuntimeError)`: raised on any attempt to mutate a frozen artifact
(a frozen `Version`, or a frozen `Freezable`'s non-`version` fields).

### `Freezable`

`class Freezable(BaseModel)`: mixin for any customizable artifact carrying a `version`.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `version` | `Version` | `Version()` | The artifact's version; freezing it seals the artifact. |

Members: `freeze() -> None` seals via `self.version.freeze()`; `frozen: bool` (property)
reads `self.version.frozen`. Once frozen, assigning any field other than `version` raises
`FrozenError`.

### `Stability`

`class Stability(str, Enum)`: the stability tier of a public API surface (`str` mix-in
so a tier round-trips through JSON/config).

| Member | Value | Meaning |
| --- | --- | --- |
| `Stability.STABLE` | `"stable"` | Depend on it; breaking requires a major bump. |
| `Stability.EXPERIMENTAL` | `"experimental"` | Usable, may change without ceremony. The default for untagged objects. |
| `Stability.DEPRECATED` | `"deprecated"` | On its way out; warns on use. |

### `stable`

```python
def stable(obj: T) -> T
```

Tag `obj` as `Stability.STABLE` and return it unchanged. Behaviour-preserving.

### `experimental`

```python
def experimental(obj: T) -> T
```

Tag `obj` as `Stability.EXPERIMENTAL` and return it unchanged. Behaviour-preserving.

### `deprecated`

```python
def deprecated(
    *,
    since: str,
    removed_in: str,
    use: str | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]
```

A decorator factory. Returns a decorator that marks a callable `Stability.DEPRECATED`
and emits a `DeprecationWarning` on every call before forwarding to the wrapped callable.
Metadata is preserved via `functools.wraps`.

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `since` | `str` | (required) | Version the deprecation took effect (e.g. `"0.4"`). |
| `removed_in` | `str` | (required) | Version scheduled for removal. |
| `use` | `str \| None` | `None` | Optional replacement API name, surfaced in the warning. |

### `stability_of`

```python
def stability_of(obj: object) -> Stability
```

Read the tier tagged on `obj` (via the `__crawfish_stability__` attribute). Returns
`Stability.EXPERIMENTAL` for any untagged object. Nothing is stable until explicitly
promoted with `stable`.

### `is_breaking`

```python
def is_breaking(old: str, new: str) -> bool
```

`True` when going from `old` to `new` increases the major version component (semver
breaking change). Parsing strips a leading `v` and reads the head before the first `.`,
so `"v1.2.3"`, `"1.2"`, and `"1"` all yield major `1`. Minor/patch bumps return `False`.

## See also

- [Core types](core-types.md): the `Parameter` and `Policy` data shapes artifacts build on.
- [Definition](definition.md): authoring the artifacts you version and freeze.
- [Persistence](persistence.md): how runs reference the exact artifacts they used.
