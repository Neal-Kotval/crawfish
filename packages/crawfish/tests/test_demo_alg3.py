"""Deterministic acceptance test for the Milestone-8 ALG-3 step of the cumulative demo.

Exercises the assembly-time **fluid->static-sink rejection** (CRA-231 / ALG-3) added to
``demo/triage-bot/self_improve.py`` as the "build fails closed" step — entirely off the mock
runtime (NO live model call) — and asserts the load-bearing M8 guarantees:

* **The build ADMITS the well-typed wiring.** ``assert_no_fluid_to_static_sink`` over the
  well-typed demo variant (all-STATIC consequential egress) passes; the provably-safe project
  is admitted unchanged.
* **The build FAILS CLOSED on injection-by-construction.** ``assert_build_safe`` over a project
  that wires a FLUID value toward a static-only Sink raises ``FluidToStaticSinkError`` and names
  the suspected slot — the misbuild is rejected at build, before any model call.
* **The fluid-widening operators are gated.** A one-sided ``STATIC->FLUID`` merge widen raises
  ``FluidWidenError``; a fluid-derived classifier that would CHOOSE among distinct consequential
  Sink targets raises ``ConsequentialTargetChoiceError`` at ``Router`` construction.

The whole cumulative scenario must still PASS 9/9 with the M8 step wired in, and the M8 step must
add NOTHING to the F-6 cost worst case (the assembly gate is a pure, model-FREE type-discharge).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from crawfish.alg3 import (
    ConsequentialTargetChoiceError,
    FluidToStaticSinkError,
    FluidWidenError,
    assert_merge_no_fluid_widen,
    assert_no_fluid_to_static_sink,
)
from crawfish.build import assert_build_safe
from crawfish.core.types import Flow, Parameter
from crawfish.definition import Definition

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO = REPO_ROOT / "demo" / "triage-bot" / "self_improve.py"


def _load_scenario() -> object:
    """Import the demo scenario module by path (it lives outside the package)."""
    spec = importlib.util.spec_from_file_location("demo_self_improve_m8", SCENARIO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the cumulative scenario still PASSes 9/9 with the M8 step wired in --------------


def test_alg3_step_certifies_and_scenario_passes() -> None:
    si = _load_scenario()
    res = si.run_self_improvement(live=False)  # type: ignore[attr-defined]

    # The M8 certifier holds, and so does the whole 9/9 scenario (deterministic mock path).
    assert res._alg3_step_ok(), res.summary()
    assert res.passed(), res.summary()

    # The well-typed wiring was admitted by the assembly gate.
    assert res.alg3_welltyped_built
    # The mis-wired project FAILED CLOSED at build, naming the fluid->static slot.
    assert res.alg3_build_failed_closed
    assert res.alg3_build_error == "FluidToStaticSinkError"
    assert res.alg3_build_violation_slot == "output:reply"
    # The two fluid-widening operators were both rejected.
    assert res.alg3_merge_widen_rejected
    assert res.alg3_classifier_choice_rejected


def test_m8_step_adds_nothing_to_cost_worst_case() -> None:
    """The M8 assembly gate is a pure, model-FREE type-discharge, so it cannot move the bound."""
    si = _load_scenario()
    res = si.run_self_improvement(live=False)  # type: ignore[attr-defined]
    # Mock path: every call is $0, so the worst case is $0 and total spend honestly bounded by it.
    assert res.worst_case_usd == 0.0
    assert res.total_spend_usd <= res.worst_case_usd


# --- the build-fails-closed guarantee in isolation -----------------------------------


def test_build_admits_well_typed_and_fails_closed_on_miswired() -> None:
    """The demo's two variants: the well-typed one passes; the mis-wired one fails closed."""
    si = _load_scenario()
    welltyped = si._build_provable_variant()  # type: ignore[attr-defined]
    miswired = si._build_miswired_variant()  # type: ignore[attr-defined]

    # Admitted: the provably-safe wiring passes the core gate and the project build.
    assert_no_fluid_to_static_sink(welltyped)  # does not raise
    assert_build_safe([welltyped, welltyped])  # does not raise

    # Fails closed: a project that contains the mis-wired variant is rejected at build, and the
    # typed error names the fluid->static slot it could not discharge.
    with pytest.raises(FluidToStaticSinkError) as ei:
        assert_build_safe([welltyped, miswired])
    assert ei.value.result.violations
    assert ei.value.result.violations[0].slot == "output:reply"


def test_merge_widen_and_classifier_choice_are_gated() -> None:
    """The two fluid-widening operators the demo exercises both fail closed."""
    # A one-sided STATIC->FLUID widen of a consequential slot is rejected.
    base = Definition(
        id="alg3-test-base",
        inputs=[Parameter(name="target", type="str", flow=Flow.STATIC)],
        outputs=[],
    )
    widened = Definition(
        id="alg3-test-merged",
        inputs=[Parameter(name="target", type="str", flow=Flow.FLUID)],
        outputs=[],
    )
    with pytest.raises(FluidWidenError):
        assert_merge_no_fluid_widen(base, base, base, widened)

    # A fluid-derived classifier choosing among distinct consequential targets is rejected at
    # Router construction (covered end-to-end via the demo's _run_alg3_step + the scenario test);
    # we assert the standalone helper here for completeness.
    from crawfish.alg3 import assert_classifier_gates_not_chooses
    from crawfish.nodes.router import Classifier
    from crawfish.nodes.sink import LinearSink

    agent_clf = Classifier.from_definition(
        Definition(
            id="alg3-test-clf",
            inputs=[Parameter(name="ticket_body", type="str", flow=Flow.FLUID)],
            outputs=[],
        ),
        labels=["a", "b", "default"],
        default="default",
    )
    branches = {"a": LinearSink(name="sink_a"), "b": LinearSink(name="sink_b")}
    with pytest.raises(ConsequentialTargetChoiceError):
        assert_classifier_gates_not_chooses(branches, agent_clf)
