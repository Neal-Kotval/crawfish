# Injection rejected by construction (ALG-3)

Milestone 8 turns the prompt-injection boundary from a thing you *check* into a thing the
**build refuses to let you violate**. Where [`craw prove --no-injection`](diff-prove-replay.md#prove-no-injection-craw-prove-no-injection)
is a pre-flight *certificate* you run on demand, **ALG-3** makes the same guarantee a first-class
**assembly gate**: a wiring where a `Flow.FLUID` (untrusted) value can reach a consequential
static-only Sink **fails closed at build, before any model call**.

This is *injection-rejected-by-construction*: the unsafe project never assembles. It is
**defense in depth** (the load-bearing rule) — an *additional, earlier* gate that never replaces
the runtime `TargetMustBeStaticError` / `StaticOnlyError`; those still fire at construction/run
time. ALG-3 catches the misbuild at *build* time, fail-closed.

All of it is real public API importable from the top-level `crawfish` package, and all of it is
**pure and deterministic** — a structural type-discharge over the wiring, no model call.

On this page:

- [The fail-closed boundary — `assert_no_fluid_to_static_sink`](#the-fail-closed-boundary)
- [Build fails closed — `assert_build_safe`](#build-fails-closed)
- [The gated fluid-widening operators](#the-gated-fluid-widening-operators)
- [Scope and deferrals](#scope-and-deferrals)

## The fail-closed boundary

`assert_no_fluid_to_static_sink(definition)` runs the conservative ALG-3 check over a
`Definition` and **raises** `FluidToStaticSinkError` if any obligation fails to discharge — i.e.
a `Flow.FLUID` input could reach a consequential static-only slot (a Sink target, an idempotency
key, an instruction slot), or a consequential output is mis-declared `FLUID`. It is the typed,
assembly-time analogue of the runtime `TargetMustBeStaticError`.

```python
from crawfish import assert_no_fluid_to_static_sink, FluidToStaticSinkError

# A well-typed wiring: the FLUID ticket body is barred from each static-only egress slot.
assert_no_fluid_to_static_sink(well_typed_definition)   # passes — admitted unchanged

# A mis-wired definition (a FLUID value can reach a static-only Sink) is rejected.
try:
    assert_no_fluid_to_static_sink(mis_wired_definition)
except FluidToStaticSinkError as exc:
    # The error carries the proof certificate — every suspected fluid->static slot.
    print(exc.result.violations[0].slot)   # e.g. "output:reply"
```

**Conservative and fail-closed.** Anything outside the decidable fragment is **rejected**, never
silently passed. An unprovable wiring is treated as unsafe — the gate admits exactly the
provably-safe project and rejects everything it cannot certify.

## Build fails closed

`assert_build_safe(definitions)` is the demo-able "build fails closed" entry point: it runs the
core gate over every `Definition` in a project, so a project that wires `FLUID` toward a
static-only Sink **fails closed at build** — before the image is produced and before a single
model call.

```python
from crawfish import assert_build_safe, FluidToStaticSinkError

# Admitted: every definition in the project is provably injection-free.
assert_build_safe([triage, router])              # passes

# Fails closed: one mis-wired definition rejects the whole build.
try:
    assert_build_safe([triage, mis_wired])
except FluidToStaticSinkError as exc:
    print("build rejected:", exc.result.violations[0].slot)
```

This is the gate the cumulative demo exercises in its **build-fails-closed** step (the
`build fails closed (ALG-3 assembly gate)` line under step 9): the well-typed variant is admitted,
and a deliberately mis-wired project fails closed at `assert_build_safe`, naming the slot
`output:reply`. The step is model-free, so it adds **nothing** to the cost worst case.

## The gated fluid-widening operators

A few operators introduced across the language can *widen* the fluid/static boundary if left
ungated. ALG-3 closes each one:

- **`merge` (git for agents).** A *two-sided* divergence on a `flow` path is already a typed
  `MergeConflict`. ALG-3 closes the **one-sided** gap: if exactly one side widened a consequential
  Parameter's `flow` from `static` to `fluid`, the merge would silently adopt the widened boundary.
  `merge` now surfaces that as a conflict, and the standalone helper
  `assert_merge_no_fluid_widen(base, a, b, merged)` raises `FluidWidenError`. A merge can never
  quietly turn a consequential static knob fluid.

- **`Classifier` / `Router` (the S3 invariant).** A fluid-derived (agent-backed) classifier label
  may gate **whether** a consequential action fires (a single target plus a dead-letter / no-op),
  but it may never **choose** among two or more *distinct* consequential Sink targets — that is a
  model-influenced redirection of egress by another name. Routing a fluid-derived classifier to
  distinct consequential targets raises `ConsequentialTargetChoiceError` at `Router` construction.
  A *pure predicate* classifier is exempt — its label is not on the injection boundary, so it may
  fan out across targets. The standalone helper is
  `assert_classifier_gates_not_chooses(branches, classifier)`.

```python
from crawfish import (
    assert_merge_no_fluid_widen, FluidWidenError,
    assert_classifier_gates_not_chooses, ConsequentialTargetChoiceError,
)
```

## Scope and deferrals

ALG-3 ships the **2-point** fluid→static-sink rejection (CRA-231), **default-equivalent to today's
runtime behavior** — no new `Grade` lattice. It is the base case of the non-interference suite for
the fluid→static-sink class.

The full **Property / Capability algebra** is **deferred behind a spike** (reviewers judged it the
most over-scoped area — it would rebuild four working enforced mechanisms atop a new semiring with
high regression risk and no near-term user capability):

- **`Grade` product-graded type** (CRA-232 / ALG-1) — the north-star unification of
  Flow / Freezable / cost / capability into one graded discipline.
- **`narrow()` / attenuation** (CRA-233 / ALG-2) — capability-passing borrow semantics over a `Grade`.
- **Mutability borrow** (CRA-234 / ALG-4) — train/eval via copy-on-write, dynamic exclusive borrow.
- **Cost coeffect grade** (CRA-235 / ALG-5).
- **`declassify`** (CRA-236 / ALG-6) — the sole audited `FLUID→STATIC` upgrade.
- **Non-interference conformance suite** (CRA-237 / ALG-7) — **not dropped**; ALG-3 here is its base
  case, and the executable taint-conformance suite follows when ALG-1/6 land.

See `docs/_changelog/CRA-231.md` in the repository for the full deferral rationale.
