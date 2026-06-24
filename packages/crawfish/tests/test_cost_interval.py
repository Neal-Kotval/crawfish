"""CRA-220 / OPT-2 acceptance: the honest cost interval, inferred from the runtime.

`test_cost_composition.py` pins the bare composition law (`compose_cost` over a
hand-listed shape chain). This file pins the OPT-2 "Open (resolved)" piece — that
the shape chain can be *inferred from an assembled wrapper chain*
(:meth:`CostShape.from_runtime`) — plus the repair (+1) tail and the named ACs
exercised through the inferred path, so the advertised band cannot drift from what
the runtime would actually spend.
"""

from __future__ import annotations

import pytest

from crawfish.cost import CostEstimate, CostShape, compose_cost
from crawfish.runtime.escalate import EscalatingRuntime, confidence_below
from crawfish.runtime.mock import MockRuntime
from crawfish.runtime.quorum import QuorumRuntime


def _base(usd: float = 1.0) -> CostEstimate:
    return CostEstimate(
        team_size=1, items=1, per_item_usd=usd, total_usd=usd, per_model={"base": usd}
    )


# -- from_runtime: leaf runtime has no re-run wrappers ----------------------
def test_from_runtime_bare_leaf_is_empty() -> None:
    """A plain leaf runtime adds no operator cost -> empty shape chain."""
    shapes = CostShape.from_runtime(MockRuntime())
    assert shapes == []
    # composing the empty chain leaves the lower bound as the whole interval.
    est = compose_cost(_base(3.0), shapes)
    assert est.worst_case_usd == pytest.approx(3.0)
    assert est.expected_usd == pytest.approx(3.0)


# -- from_runtime: escalation re-priced on the strong model -----------------
def test_from_runtime_escalation_repriced_on_strong_model() -> None:
    """`CostShape(escalation=True)` ⇒ worst_case priced on strong_model, ≥ total_usd."""
    rt = EscalatingRuntime(
        MockRuntime(),
        primary_model="claude-haiku-4-5",  # $0.01
        strong_model="claude-opus-4-8",  # $0.30
        should_escalate=confidence_below(0.5),
    )
    shapes = CostShape.from_runtime(rt)
    assert [s.kind for s in shapes] == ["escalate"]
    est = compose_cost(_base(0.01), shapes)
    # worst = base(0.01) + strong(0.30) = 0.31, priced on the strong model, > total.
    assert est.worst_case_usd == pytest.approx(0.31)
    assert est.worst_case_usd >= est.total_usd


def test_from_runtime_escalation_count_fallback_without_prices() -> None:
    """No price table for the models -> count-based 2× (never an undercount)."""
    rt = EscalatingRuntime(
        MockRuntime(),
        primary_model="unknown-a",
        strong_model="unknown-b",
        should_escalate=confidence_below(0.5),
    )
    shapes = CostShape.from_runtime(rt, model_prices={})
    est = compose_cost(_base(4.0), shapes)
    assert est.worst_case_usd == pytest.approx(8.0)  # 2 × base


# -- from_runtime: quorum samples ------------------------------------------
def test_from_runtime_quorum_uses_k() -> None:
    rt = QuorumRuntime(MockRuntime(), k=5)
    shapes = CostShape.from_runtime(rt)
    assert [s.kind for s in shapes] == ["quorum"]
    est = compose_cost(_base(2.0), shapes)
    assert est.worst_case_usd == pytest.approx(10.0)  # 5 samples


def test_from_runtime_quorum_unpinned_k_uses_floor() -> None:
    """An unpinned quorum previews at its min_k floor (the most the test could draw)."""
    rt = QuorumRuntime(MockRuntime(), min_k=3)
    shapes = CostShape.from_runtime(rt)
    est = compose_cost(_base(1.0), shapes)
    assert est.worst_case_usd == pytest.approx(3.0)


# -- from_runtime: nested wrappers fold outermost-first ---------------------
def test_from_runtime_nested_quorum_over_escalate_is_multiplicative() -> None:
    """Quorum(5) wrapping Escalate(2×) over a leaf previews 5 × 2 = 10× (F-6)."""
    leaf = MockRuntime()
    esc = EscalatingRuntime(
        leaf,
        primary_model="m",
        strong_model="m",  # strong == primary -> 2× count factor
        should_escalate=confidence_below(0.5),
    )
    rt = QuorumRuntime(esc, k=5)
    shapes = CostShape.from_runtime(rt, model_prices={"m": 1.0})
    # outermost-first: quorum is the outer wrapper, escalate inner.
    assert [s.kind for s in shapes] == ["quorum", "escalate"]
    est = compose_cost(_base(1.0), shapes)
    assert est.worst_case_usd == pytest.approx(1.0 * 5 * 2)  # == 10


def test_from_runtime_full_refine_escalate_quorum_40x() -> None:
    """The OPT-2 worked example through the inferred path: Refine(4) is a Node the
    caller adds; Escalate(2×) ∘ Quorum(5) is inferred from the runtime -> 4×2×5 = 40×."""
    esc = EscalatingRuntime(
        MockRuntime(),
        primary_model="m",
        strong_model="m",
        should_escalate=confidence_below(0.5),
    )
    rt = QuorumRuntime(esc, k=5)
    inferred = CostShape.from_runtime(rt, model_prices={"m": 1.0})
    # Refine is not a runtime wrapper; the caller folds it in alongside the inferred chain.
    shapes = [CostShape.refine(max_iters=4), *inferred]
    est = compose_cost(_base(1.0), shapes)
    assert est.worst_case_usd == pytest.approx(40.0)


# -- repair (+1) tail -------------------------------------------------------
def test_repair_worst_case_doubles_the_leaf() -> None:
    """Run._repair's one extra re-prompt is a 2× worst case."""
    est = compose_cost(_base(3.0), [CostShape.repair()])
    assert est.worst_case_usd == pytest.approx(6.0)


def test_repair_measured_rate_folds_a_band() -> None:
    """A 10% measured repair rate ⇒ expected strictly between lower and worst."""
    est = compose_cost(_base(1.0), [CostShape.repair(measured_rate=0.1, rate_ci=0.05)])
    # expected = 1 + 0.1 × (2 - 1) = 1.1
    assert est.expected_usd == pytest.approx(1.1)
    assert est.total_usd < est.expected_usd < est.worst_case_usd
    assert est.expected_lo_usd < est.expected_usd < est.expected_hi_usd


# -- measured rate band through the inferred chain --------------------------
def test_measured_escalation_rate_yields_band() -> None:
    """escalation_rate=0.2 ⇒ expected strictly between lower and worst, with a CI."""
    base = _base(1.0)
    # strong attempt priced equal to base -> worst factor 2×.
    shape = CostShape.escalate(base_price=1.0, strong_price=1.0, measured_rate=0.2, rate_ci=0.05)
    est = compose_cost(base, [shape])
    assert est.total_usd == pytest.approx(1.0)
    assert est.worst_case_usd == pytest.approx(2.0)
    assert est.total_usd < est.expected_usd < est.worst_case_usd
    assert est.expected_lo_usd < est.expected_usd < est.expected_hi_usd


def test_no_rates_expected_equals_worst_case_no_undercount() -> None:
    """With no measured rates the inferred band collapses to worst-case (honest)."""
    rt = QuorumRuntime(MockRuntime(), k=4)
    est = compose_cost(_base(1.0), CostShape.from_runtime(rt))
    assert est.expected_usd == pytest.approx(est.worst_case_usd)


# -- determinism ------------------------------------------------------------
def test_from_runtime_is_deterministic_no_model_call() -> None:
    """Same assembled runtime ⇒ identical inferred numbers, twice, no run()."""
    rt = QuorumRuntime(
        EscalatingRuntime(
            MockRuntime(),
            primary_model="claude-haiku-4-5",
            strong_model="claude-opus-4-8",
            should_escalate=confidence_below(0.5),
        ),
        k=3,
    )
    a = compose_cost(_base(1.0), CostShape.from_runtime(rt))
    b = compose_cost(_base(1.0), CostShape.from_runtime(rt))
    assert a.model_dump() == b.model_dump()
