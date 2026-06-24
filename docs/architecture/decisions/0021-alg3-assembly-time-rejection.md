# ADR 0021 — Fluid→static-sink injection is rejected at assembly time (the generator as a trust boundary)

**Status:** Accepted · **Date:** 2026-06-24 · **Milestone:** S (Security of the generator boundary)

> Issue CRA-240 / SEC-3, ratifying ALG-3 (CRA-231, pulled forward) and the generator
> threat boundary (CRA-238 / SEC-1). This is **0021**. Cross-linked from
> [SECURITY.md](../SECURITY.md) (invariant 8) and `crawfish.alg3` / `crawfish.prove`.

## Context

The original spine enforces "consequential Sink targets and idempotency keys are
static-only" (invariants 2–4) at **runtime**: `TargetMustBeStaticError` / `StaticOnlyError`
fire when a fluid value is bound to a static slot (`nodes/sink.py`, `jail.py`).

The Agent Language adds two pressures the runtime-only gate does not fully address:

1. **New fluid surfaces multiply the wiring paths.** Refine feedback, Router/Classifier
   labels, Rag/Wiki hits, and a three-way `merge` that could widen a knob all create new
   ways a `Flow.FLUID` value could *reach* a consequential static-only slot.
2. **A generator now writes the Definition.** `craw code` (the self-improving loop)
   produces Definitions from possibly-fluid context. The generator's output is therefore an
   **untrusted artifact** until checked: a misbuilt or maliciously-influenced wiring could
   route fluid toward a sink, and a runtime-only gate would not catch it until a run — after
   the unsafe artifact already shipped.

The cheapest durable defense is to reject an unsafe wiring **before any model call** —
to treat assembly (build) as a trust boundary the generated artifact must pass.

## Decision

**Lift the conservative fluid→static-sink non-interference check from a CLI certificate to
a first-class, fail-closed assembly gate. Any wiring where a `Flow.FLUID` value can reach a
consequential static-only slot (Sink target / idempotency key / instruction slot) is
REJECTED at assembly, before a run — and the generated artifact must pass this gate to
ship.**

- `assert_no_fluid_to_static_sink(definition)` runs the conservative ALG-3 check
  (`prove_no_injection`) and raises `FluidToStaticSinkError` if any obligation fails to
  discharge. A consequential output mis-declared `Flow.FLUID` fails closed.
- `assert_classifier_gates_not_chooses` (S3): a fluid-derived label may gate *whether* a
  consequential action fires, never *choose* among distinct consequential Sink targets.
- `assert_merge_no_fluid_widen` (review-m7 S-1): a three-way `merge` that one-sidedly
  widens a consequential slot `STATIC→FLUID` is rejected, never silently adopted.

**Defense in depth.** This is an *additional, earlier* gate; it never replaces the runtime
`StaticOnlyError` / `TargetMustBeStaticError`. A project (or a generated artifact) that wires
fluid toward a static-only sink fails closed at **build**.

**Honest scope.** This is the *conservative static rejection*, not a sound-and-complete
dataflow proof. The timeboxed spike (CRA-229 §8.2) found a sound proof needs a first-class
serialized dataflow graph the Definition does not yet expose. The check is **sound for the
fluid→static-slot fragment it covers** and **incomplete** (it does not certify the absence
of *every* injection path) — and it **fails closed**: anything outside the decidable
fragment is rejected, never assumed safe. The full property algebra (Grade lattice, narrow,
declassify, the cost coeffect) is deferred behind a spike.

## Alternatives rejected

- **Runtime-only enforcement (the pre-ALG-3 state).** Catches the violation only on a run,
  after the unsafe (possibly generated) artifact already exists. An assembly gate fails the
  build instead — the generator boundary needs a pre-flight.
- **A sound-and-complete dataflow proof now.** Blocked on a serialized graph the Definition
  does not expose; would stall the stack on a research frontier. We ship the conservative
  fail-closed check and flag the sound proof as a follow-on.
- **Pass-unless-proven-unsafe.** Inverts the safety default. The gate is **fail-closed**:
  reject unless proven safe within the covered fragment.

## Consequences

A misbuilt or maliciously-influenced wiring fails closed at build, before a model call — the
generated artifact must clear the gate to ship, closing the generator threat boundary
(CRA-238). The gate is pure, deterministic, and structural (no model call, no I/O), so it is
a free CI step and a `craw prove --no-injection` certificate. It composes with the runtime
gate as defense in depth. Recorded as **SECURITY.md invariant 8**; the deferred sound proof
is tracked in `docs/_changelog/CRA-229.md`.
