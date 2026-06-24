"""CRA-205 (C1) acceptance: Router as a runnable Workflow composition step.

Coverage:
  (1) end-to-end Router step — no TypeError; each item is classified + dispatched.
  (2) predicate routing is pure: ``spent == 0`` (zero model calls).
  (3) ``check_types`` raises ``WireError`` at assembly when a branch cannot accept input.
  (4) an uncovered classifier label still fails at construction (``UnroutableLabelError``).
  (5) a tainted item routed through a branch keeps its taint (taint carries across the
      branch boundary); a Sink with a FLUID target still raises at construction.
  (6) replay yields an identical label sequence (deterministic predicate routing).
  (7) divergent non-terminal branch output schemas raise ``WireError`` at assembly.

Deterministic — predicate classifier makes zero model calls (no live runtime needed).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crawfish.core.context import CostBudget, RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.nodes.aggregator import Aggregator, count
from crawfish.nodes.filter import Filter
from crawfish.nodes.router import Classifier, UnroutableLabelError
from crawfish.nodes.sink import LinearSink, TargetMustBeStaticError
from crawfish.nodes.source import Source
from crawfish.output import Output, WireError
from crawfish.store import SqliteStore
from crawfish.workflow import Workflow, branch


# -- fixtures ---------------------------------------------------------------
class _Items(Source[list[dict[str, JSONValue]]]):
    outputs = [Parameter(name="kind", type="str")]
    multi = True

    async def fetch(self, ctx: RunContext) -> Output[list[dict[str, JSONValue]]]:
        return Output(
            output_schema=list(self.outputs), value=self.config["items"], produced_by=self.id
        )


def _items_source(items: list[dict[str, JSONValue]]) -> _Items:
    return _Items("items", config={"items": items})


def _kind_classifier() -> Classifier:
    return Classifier.from_predicates(
        {
            "bug": lambda v: v.get("kind") == "bug",
            "ask": lambda v: v.get("kind") == "ask",
        },
        default="default",
    )


def _ctx(*, limit: float | None = None, org_id: str = "local") -> RunContext:
    return RunContext(store=SqliteStore(), org_id=org_id, cost_budget=CostBudget(limit_usd=limit))


def _items() -> list[dict[str, JSONValue]]:
    return [{"kind": "bug"}, {"kind": "ask"}, {"kind": "other"}]


# -- (1)(2) end-to-end runnable Router --------------------------------------
async def test_router_step_runs_end_to_end_no_typeerror() -> None:
    bug_sink = LinearSink("bug_sink", {"team": "T"})
    ask_sink = LinearSink("ask_sink", {"team": "T"})
    dead = LinearSink("dead", {"team": "T"})
    router = branch(
        _kind_classifier(),
        {"bug": bug_sink, "ask": ask_sink, "default": dead},
    )
    wf = Workflow(steps=[_items_source(_items()), router])
    ctx = _ctx()
    out = await wf.run(ctx=ctx)
    # Every item flowed through its branch Sink (no TypeError, terminal pass-through).
    assert len(out) == 3
    assert len(bug_sink.writes) == 1
    assert len(ask_sink.writes) == 1
    assert len(dead.writes) == 1
    # Predicate routing is pure — zero metered model calls.
    assert ctx.cost_budget.spent_usd == 0.0


# -- (3) branch cannot accept the producer input -> WireError ---------------
async def test_check_types_rejects_incompatible_branch(tmp_path: Path) -> None:
    from crawfish.batch import Batch
    from crawfish.definition import Definition

    # A Batch branch whose Definition requires an input the source never produces.
    defn = Definition(
        id="needs-x",
        inputs=[Parameter(name="x", type="int")],
        outputs=[Parameter(name="y", type="str")],
    )
    batch_branch = Batch(defn, name="needs_x")
    router = branch(
        _kind_classifier(),
        {"bug": batch_branch, "ask": LinearSink("a"), "default": LinearSink("d")},
    )
    wf = Workflow(steps=[_items_source(_items()), router])
    with pytest.raises(WireError):
        wf.check_types()


# -- (4) uncovered label fails at construction ------------------------------
def test_uncovered_label_fails_at_construction() -> None:
    with pytest.raises(UnroutableLabelError):
        branch(
            _kind_classifier(),
            {"bug": LinearSink("b"), "default": LinearSink("d")},  # "ask" uncovered
        )


# -- (5) taint carries across the branch; fluid target rejected at build ----
async def test_taint_carries_through_branch() -> None:
    # A passthrough Filter branch lets us inspect the routed Output's taint.
    keep_all = Filter(lambda v: True, name="keep")
    router = branch(
        _kind_classifier(),
        {"bug": keep_all, "ask": keep_all, "default": keep_all},
    )

    class _Tainted(Source[list[dict[str, JSONValue]]]):
        outputs = [Parameter(name="kind", type="str")]
        multi = True

        async def fetch(self, ctx: RunContext) -> Output[list[dict[str, JSONValue]]]:
            return Output(
                output_schema=list(self.outputs),
                value=[{"kind": "bug"}],
                produced_by=self.id,
                tainted=True,
                lineage="item-1",
            )

    src = _Tainted("t")
    # The lineage the Source fan-out assigns to the single item; the Router must thread
    # this same lineage forward across the branch boundary.
    fanned = src.fan_out(await src.fetch(_ctx()))
    expected_lineage = fanned[0].lineage

    wf = Workflow(steps=[src, router])
    out = await wf.run(ctx=_ctx())
    assert len(out) == 1
    assert out[0].tainted is True  # taint preserved across the branch boundary
    assert out[0].lineage == expected_lineage  # lineage carried across the branch


def test_fluid_sink_target_rejected_at_construction() -> None:
    with pytest.raises(TargetMustBeStaticError):
        LinearSink(
            "leak",
            {"team": "T"},
            target_params=[Parameter(name="team", type="str", flow=Flow.FLUID)],
        )


# -- (6) deterministic label sequence (replay-stable) -----------------------
async def test_label_sequence_is_deterministic() -> None:
    router = branch(
        _kind_classifier(),
        {"bug": LinearSink("b"), "ask": LinearSink("a"), "default": LinearSink("d")},
    )
    labels1 = [router.route(Output(value=it, produced_by="s"))[0] for it in _items()]
    labels2 = [router.route(Output(value=it, produced_by="s"))[0] for it in _items()]
    assert labels1 == labels2 == ["bug", "ask", "default"]


# -- (7) divergent non-terminal branch schemas raise -----------------------
def test_divergent_branch_output_schemas_raise() -> None:
    from crawfish.batch import Batch
    from crawfish.definition import Definition

    a = Batch(
        Definition(id="a", outputs=[Parameter(name="y", type="str")]),
        name="a",
    )
    b = Batch(
        Definition(id="b", outputs=[Parameter(name="z", type="int")]),
        name="b",
    )
    router = branch(
        _kind_classifier(),
        {"bug": a, "ask": b, "default": Aggregator(count)},
    )
    wf = Workflow(steps=[_items_source(_items()), router, Aggregator(count)])
    with pytest.raises(WireError):
        wf.check_types()
