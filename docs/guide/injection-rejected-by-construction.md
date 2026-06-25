# Reject injection at build time

Crawfish can refuse to assemble a project where an untrusted value could reach a place that
acts on the world. A *static* value is fixed in your code; a *fluid* value is untrusted
session data that reaches the model as data, never as instructions. A consequential *sink*
target (the address a result is written to) and an idempotency key must be static. The build
gate checks this when you assemble the project: a wiring where a `Flow.FLUID` value can reach
a consequential static-only sink fails before any model call.

This complements [`craw prove --no-injection`](diff-prove-replay.md),
which is a pre-flight certificate you run on demand. The build gate is an earlier check, run
at assembly. It does not replace the runtime checks (`TargetMustBeStaticError`,
`StaticOnlyError`); those still fire at construction and run time. The build gate catches the
mis-wiring earlier, and it fails closed.

Every symbol on this page imports from the top-level `crawfish` package. The check is pure and
deterministic: a structural type check over the wiring, with no model call.

## Check one definition

`assert_no_fluid_to_static_sink(definition)` runs the check over a single `Definition` and
raises `FluidToStaticSinkError` if any obligation fails. An obligation fails when a
`Flow.FLUID` input could reach a consequential static-only slot (a sink target, an idempotency
key, or an instruction slot), or when a consequential output is mis-declared `FLUID`. It is the
assembly-time form of the runtime `TargetMustBeStaticError`.

```python
from crawfish import assert_no_fluid_to_static_sink, FluidToStaticSinkError

# A well-typed wiring: the FLUID ticket body is barred from each static-only egress slot.
assert_no_fluid_to_static_sink(well_typed_definition)   # passes, admitted unchanged

# A mis-wired definition (a FLUID value can reach a static-only Sink) is rejected.
try:
    assert_no_fluid_to_static_sink(mis_wired_definition)
except FluidToStaticSinkError as exc:
    # The error carries the proof, naming every suspected fluid-to-static slot.
    print(exc.result.violations[0].slot)   # e.g. "output:reply"
```

The check is conservative and fails closed. Anything it cannot prove safe is rejected, never
passed silently. It admits exactly the provably-safe project and rejects everything it cannot
certify.

## Fail a whole build closed

`assert_build_safe(definitions)` runs the same check over every `Definition` in a project, so
a project that wires `FLUID` toward a static-only sink fails before the image is produced and
before any model call.

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

The cumulative demo exercises this in its build-fails-closed step: the well-typed variant is
admitted, and a deliberately mis-wired project fails closed at `assert_build_safe`, naming the
slot `output:reply`. The step makes no model call, so it adds nothing to the cost.

## Gate the fluid-widening operators

A few operators can widen the fluid-to-static boundary if left ungated. The build gate closes
each one.

`merge` (the git-style merge of two versions). A two-sided divergence on a `flow` path is
already a typed `MergeConflict`. The gate closes the one-sided gap: if exactly one side widened
a consequential parameter's `flow` from `static` to `fluid`, the merge would silently adopt the
widened boundary. `merge` now surfaces that as a conflict, and the helper
`assert_merge_no_fluid_widen(base, a, b, merged)` raises `FluidWidenError`. A merge can never
quietly turn a consequential static knob fluid.

`Classifier` and `Router`. A fluid-derived (agent-backed) classifier label may gate whether a
consequential action fires (a single target plus a dead-letter or no-op), but it may never
choose among two or more distinct consequential sink targets. That would be a model-influenced
redirection of egress. Routing a fluid-derived classifier to distinct consequential targets
raises `ConsequentialTargetChoiceError` at `Router` construction. A pure-predicate classifier
is exempt: its label is not on the injection boundary, so it may fan out across targets. The
helper is `assert_classifier_gates_not_chooses(branches, classifier)`.

```python
from crawfish import (
    assert_merge_no_fluid_widen, FluidWidenError,
    assert_classifier_gates_not_chooses, ConsequentialTargetChoiceError,
)
```

## Scope

This gate ships the fluid-to-static-sink rejection. Its behaviour matches today's runtime
behaviour by default, with no new grade system. It is the base case of the non-interference
suite for the fluid-to-static-sink class.

A broader capability algebra (a graded type system unifying flow, freezability, cost, and
capability, plus attenuation, mutability borrow, a cost grade, an audited `declassify`, and a
full conformance suite) is deferred. The decision and its rationale are recorded in the
internal changelog, not in the published docs.

## Next steps

- [Diff, prove, and replay](diff-prove-replay.md): the on-demand `craw prove --no-injection`
  pre-flight certificate this build gate complements.
- [Core concepts](concepts.md#static-versus-fluid): the static-versus-fluid boundary this gate
  enforces.
- [Security overview](../architecture/SECURITY.md): how the injection boundary holds across the
  framework.
