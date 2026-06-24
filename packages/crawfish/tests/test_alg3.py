"""CRA-231 / ALG-3 (pulled forward): assembly-time fluid→static-sink rejection.

The "injection-by-construction is rejected" gate. These exercise the first-class
assembly check and the three wired fluid-widening operators (build, merge, classifier).
All deterministic — no model calls.
"""

from __future__ import annotations

import pytest

from crawfish.agentdiff import MergeConflict, merge
from crawfish.alg3 import (
    ConsequentialTargetChoiceError,
    FluidToStaticSinkError,
    FluidWidenError,
    assert_classifier_gates_not_chooses,
    assert_merge_no_fluid_widen,
    assert_no_fluid_to_static_sink,
)
from crawfish.build import assert_build_safe
from crawfish.core.types import Flow, Parameter
from crawfish.definition import Definition
from crawfish.nodes.router import Classifier, Router
from crawfish.nodes.sink import LinearSink


def _defn(inputs: list[Parameter], outputs: list[Parameter]) -> Definition:
    return Definition(inputs=inputs, outputs=outputs)


# --- core gate: fluid→static-sink REJECTED at assembly -----------------------------


def test_valid_static_egress_passes() -> None:
    """A fluid input + STATIC-only egress slots passes the assembly gate unchanged."""
    d = _defn(
        inputs=[
            Parameter(name="repo", type="str", flow=Flow.STATIC),
            Parameter(name="ticket", type="str", flow=Flow.FLUID),
        ],
        outputs=[Parameter(name="target", type="str", flow=Flow.STATIC)],
    )
    assert_no_fluid_to_static_sink(d)  # does not raise


def test_fluid_egress_rejected_at_assembly() -> None:
    """A consequential output mis-declared FLUID fails closed with a typed error."""
    d = _defn(
        inputs=[Parameter(name="ticket", type="str", flow=Flow.FLUID)],
        outputs=[Parameter(name="target", type="str", flow=Flow.FLUID)],
    )
    with pytest.raises(FluidToStaticSinkError) as ei:
        assert_no_fluid_to_static_sink(d)
    assert not ei.value.result.proven
    assert any(v.slot == "output:target" for v in ei.value.result.violations)


def test_no_fluid_inputs_passes() -> None:
    """A fully-static wiring is vacuously safe."""
    d = _defn(
        inputs=[Parameter(name="repo", type="str", flow=Flow.STATIC)],
        outputs=[Parameter(name="target", type="str", flow=Flow.STATIC)],
    )
    assert_no_fluid_to_static_sink(d)


# --- build hook: project build fails closed ----------------------------------------


def test_build_safe_passes_clean_project() -> None:
    d = _defn(
        inputs=[Parameter(name="ticket", type="str", flow=Flow.FLUID)],
        outputs=[Parameter(name="target", type="str", flow=Flow.STATIC)],
    )
    assert_build_safe([d, d])  # does not raise


def test_build_fails_closed_on_fluid_sink() -> None:
    """The demo-able 'build fails closed' entry point rejects an unsafe project."""
    bad = _defn(
        inputs=[Parameter(name="ticket", type="str", flow=Flow.FLUID)],
        outputs=[Parameter(name="target", type="str", flow=Flow.FLUID)],
    )
    with pytest.raises(FluidToStaticSinkError):
        assert_build_safe([bad])


# --- merge: one-sided fluid-widen REJECTED (review-m7 S-1) -------------------------


def _frozen(d: Definition) -> Definition:
    from crawfish import derive

    return derive.refreeze(d, d)


def test_merge_one_sided_fluid_widen_rejected() -> None:
    """A one-sided STATIC->FLUID widen of a Parameter flow is a MergeConflict, not silent."""
    base = _frozen(_defn(inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)], outputs=[]))
    # Side ``a`` widens x: static -> fluid; side ``b`` leaves it untouched.
    a = _frozen(_defn(inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)], outputs=[]))
    b = base

    result = merge(base, a, b)
    assert isinstance(result, MergeConflict)
    assert any(p.endswith("x.flow") for p in result.paths)


def test_merge_no_widen_when_static_preserved() -> None:
    """A merge that does not widen any flow succeeds (returns a frozen Definition)."""
    base = _frozen(_defn(inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)], outputs=[]))
    # Side ``a`` adds an output; side ``b`` unchanged. No flow widened.
    a = _frozen(
        _defn(
            inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)],
            outputs=[Parameter(name="t", type="str", flow=Flow.STATIC)],
        )
    )
    b = base
    result = merge(base, a, b)
    assert isinstance(result, Definition)


def test_assert_merge_helper_raises_on_widen() -> None:
    """The standalone helper raises FluidWidenError on a one-sided widen."""
    base = _defn(inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)], outputs=[])
    merged = _defn(inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)], outputs=[])
    with pytest.raises(FluidWidenError):
        assert_merge_no_fluid_widen(base, base, base, merged)


# --- classifier S3: fluid label may gate WHETHER, not CHOOSE targets ---------------


def _agent_classifier() -> Classifier:
    """A Definition-backed (fluid-derived) classifier over two labels + default."""
    d = _defn(inputs=[Parameter(name="item", type="str", flow=Flow.FLUID)], outputs=[])
    return Classifier.from_definition(d, labels=["a", "b", "default"], default="default")


def test_classifier_distinct_consequential_targets_rejected() -> None:
    """A fluid classifier routing to two DISTINCT Sink targets is rejected at assembly."""
    branches = {
        "a": LinearSink(name="sink_a"),
        "b": LinearSink(name="sink_b"),
        "default": LinearSink(name="sink_a"),
    }
    with pytest.raises(ConsequentialTargetChoiceError):
        Router(branches, _agent_classifier())


def test_classifier_single_target_plus_deadletter_passes() -> None:
    """Gating WHETHER one consequential action fires (single target + dead-letter) is OK."""
    deadletter = LinearSink(name="sink_a")  # same target as 'a'
    branches = {
        "a": LinearSink(name="sink_a"),
        "b": LinearSink(name="sink_a"),  # same target -> still one destination
        "default": deadletter,
    }
    Router(branches, _agent_classifier())  # does not raise


def test_predicate_classifier_exempt() -> None:
    """A pure predicate classifier is not on the injection boundary; may fan out."""
    clf = Classifier.from_predicates({"a": lambda v: True, "b": lambda v: False}, default="default")
    branches = {
        "a": LinearSink(name="sink_a"),
        "b": LinearSink(name="sink_b"),
        "default": LinearSink(name="sink_c"),
    }
    Router(branches, clf)  # does not raise


def test_classifier_helper_direct() -> None:
    branches = {"a": LinearSink(name="s1"), "b": LinearSink(name="s2")}
    with pytest.raises(ConsequentialTargetChoiceError):
        assert_classifier_gates_not_chooses(branches, _agent_classifier())
