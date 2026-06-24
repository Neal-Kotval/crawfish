"""ALG-3 (CRA-231, pulled forward) — assembly-time fluid→static-sink rejection.

The "injection-by-construction is rejected" gate. Invariant 4 keeps consequential Sink
targets and idempotency keys ``Flow.STATIC``, enforced at *runtime* by
``TargetMustBeStaticError`` / ``StaticOnlyError`` (``nodes/sink.py``, ``jail.py``). The
new fluid surfaces (Refine feedback, Router labels, Rag hits, a three-way ``merge`` that
could widen a knob) add ways a ``Flow.FLUID``-tainted value could *reach* such a slot.
The cheapest durable defense is to reject that wiring at **assembly time**, before any
model call.

This module lifts the R2/CRA-229 conservative check (:mod:`crawfish.prove`) from a CLI
certificate to a **first-class assembly gate**:

    :func:`assert_no_fluid_to_static_sink` — fail-closed. Any wiring where a FLUID value
    can reach a consequential static-only slot (Sink target / idempotency key /
    instruction slot) RAISES :class:`FluidToStaticSinkError`, never assumed safe.

**Defense in depth (invariant 11).** This is an *additional, earlier* gate. It never
replaces the runtime ``StaticOnlyError`` / ``TargetMustBeStaticError`` — those still fire
at construction/run time. ALG-3 is the pre-flight that catches a fluid→static-slot wiring
*before* a run, so a misbuilt project fails closed at build.

**Determinism.** Pure, structural, no model call, no I/O. Anything outside the decidable
fragment fails closed (is rejected), never silently passed.

**Scope (per CRA-231).** This is the **2-point** fluid→static-sink rejection, default-
equivalent to today's runtime behavior (no new ``Grade`` lattice). The full property
algebra — ``Grade`` (ALG-1/CRA-232), ``narrow``/attenuation (ALG-2/CRA-233), the
mutability borrow (ALG-4/CRA-234), the cost coeffect (ALG-5/CRA-235), ``declassify``
(ALG-6/CRA-236), and the ``Grade``-dependent formalism of the non-interference suite
(ALG-7/CRA-237) — is **deferred behind a spike** (issue §7 note). See
``docs/_changelog/CRA-231.md``.
"""

from __future__ import annotations

from crawfish.core.types import Flow
from crawfish.prove import ProofResult, prove_no_injection

__all__ = [
    "FluidToStaticSinkError",
    "FluidWidenError",
    "ConsequentialTargetChoiceError",
    "assert_no_fluid_to_static_sink",
    "assert_merge_no_fluid_widen",
    "assert_classifier_gates_not_chooses",
]


class FluidToStaticSinkError(ValueError):
    """Raised at assembly when a FLUID value can reach a consequential static-only slot.

    The typed assembly-time analogue of the runtime ``TargetMustBeStaticError`` /
    ``StaticOnlyError``: a wiring where a ``Flow.FLUID`` input could reach a Sink target,
    an idempotency key, or any other static-only consequential slot is rejected *before*
    any model call. Carries the :class:`~crawfish.prove.ProofResult` so the caller can
    surface every suspected path.
    """

    def __init__(self, result: ProofResult) -> None:
        self.result = result
        super().__init__(result.summary())


class FluidWidenError(ValueError):
    """Raised when a merge would one-sidedly widen a consequential slot STATIC→FLUID.

    The ``merge`` (R1 / agentdiff) gate: a *one-sided* change that turns a Parameter's
    ``flow`` from ``static`` to ``fluid`` (or pins a static knob fluid) is a silent
    widening of the prompt-injection boundary. Two-sided divergence is already a
    :class:`~crawfish.agentdiff.MergeConflict`; this closes the one-sided gap (review-m7
    S-1) so a merge can never quietly turn a consequential static knob fluid.
    """


class ConsequentialTargetChoiceError(ValueError):
    """Raised when a fluid-derived label would CHOOSE among distinct consequential targets.

    The S3 Classifier/Router invariant: a fluid-derived label may gate *whether* a
    consequential action fires (a branch to a Sink vs. a dead-letter / no-op), but it may
    never *choose* among two or more **distinct consequential** Sink targets — that is a
    model-influenced redirection of egress by another name. Rejected at assembly.
    """


def assert_no_fluid_to_static_sink(definition: object) -> None:
    """Fail-closed assembly gate: reject any fluid→static-only-sink wiring.

    Runs the conservative ALG-3 check (:func:`crawfish.prove.prove_no_injection`) over
    ``definition`` and RAISES :class:`FluidToStaticSinkError` if any obligation fails to
    discharge — i.e. a ``Flow.FLUID`` input could reach a consequential static-only slot
    (Sink target / idempotency key), or a consequential output is mis-declared FLUID.

    Pure and deterministic. This is the "build fails closed" entry point: a project that
    wires FLUID toward a static-only Sink raises here, before a single model call. It is
    an *additional* gate, never a replacement for the runtime ``StaticOnlyError`` /
    ``TargetMustBeStaticError`` (defense in depth, invariant 11).
    """
    result = prove_no_injection(definition)
    if not result.proven:
        raise FluidToStaticSinkError(result)


def assert_merge_no_fluid_widen(base: object, a: object, b: object, merged: object) -> None:
    """Reject a merge that one-sidedly widens a consequential slot STATIC→FLUID.

    Three-way safety check over the four content payloads (common ancestor ``base``, the
    two descendants ``a`` / ``b``, and the proposed ``merged`` result). A two-sided
    divergence on a ``flow`` path is already surfaced as a
    :class:`~crawfish.agentdiff.MergeConflict`; this closes the **one-sided** gap: if
    exactly one side changed a Parameter's ``flow`` from ``static`` to ``fluid`` and the
    merge would therefore silently adopt the widened (fluid) flow, that is a silent
    widening of the prompt-injection boundary and is REJECTED with
    :class:`FluidWidenError`.

    Pure; operates on ``content_dict`` flow leaves only (the security-relevant axis).
    """
    from crawfish.agentdiff import _flat_payload, _is_flow_path

    fbase = _flat_payload(base)  # type: ignore[arg-type]
    fmerged = _flat_payload(merged)  # type: ignore[arg-type]

    widened: list[str] = []
    for path, merged_flow in fmerged.items():
        if not _is_flow_path(path):
            continue
        if merged_flow != Flow.FLUID.value:
            continue
        # The merged result is fluid here. If the base was static (or absent), the merge
        # widened the boundary. Two-sided divergence would already be a MergeConflict, so
        # reaching here with a fluid result means a one-sided widen was about to be
        # silently adopted — reject it.
        base_flow = fbase.get(path)
        if base_flow != Flow.FLUID.value:
            widened.append(path)

    if widened:
        raise FluidWidenError(
            "merge would silently widen the fluid/static boundary STATIC->FLUID on "
            f"consequential slot(s) {sorted(widened)}; a one-sided widen of a "
            "consequential knob must be resolved explicitly, never auto-applied "
            "(review-m7 S-1 / ALG-3)"
        )


def assert_classifier_gates_not_chooses(branches: object, classifier: object) -> None:
    """Enforce S3: a fluid label may gate WHETHER, not CHOOSE among consequential targets.

    A Router driven by a Definition-backed (agent / fluid-derived) classifier may route
    to **at most one** distinct consequential Sink target; every other branch must be a
    non-consequential continuation (a further node) or a dead-letter / no-op. If two or
    more branches lead to *distinct* consequential Sink targets, a fluid label would be
    choosing the egress destination — REJECTED with
    :class:`ConsequentialTargetChoiceError`.

    A predicate (pure, non-fluid) classifier is exempt: its label is not fluid-derived,
    so it may fan out across targets. Pure structural check over the branch map.
    """
    from crawfish.nodes.sink import Sink

    # Only a fluid-derived (Definition-backed) classifier can launder a fluid label into
    # the branch choice; a pure predicate classifier is not on the injection boundary.
    if getattr(classifier, "_definition", None) is None:
        return

    if not isinstance(branches, dict):
        return

    sink_targets: set[str] = set()
    for node in branches.values():
        if isinstance(node, Sink):
            # Identity of the consequential destination: the static sink name. Two
            # branches to the SAME sink name are the same target (gating whether), so we
            # key on name, not node id.
            sink_targets.add(node.name)

    if len(sink_targets) > 1:
        raise ConsequentialTargetChoiceError(
            "a fluid-derived (agent-backed) classifier routes to distinct consequential "
            f"Sink targets {sorted(sink_targets)}; a fluid label may gate WHETHER a "
            "consequential action fires but must never CHOOSE among distinct egress "
            "targets (S3 / ALG-3). Gate on a single target + dead-letter instead."
        )
