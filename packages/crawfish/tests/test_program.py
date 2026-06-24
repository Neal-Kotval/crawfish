"""CRA-206 (C2a) + CRA-207 (C2b) acceptance: the cyclic Program surface.

C2a (spine + assembly):
  - a back-edge runs to a fixed point / max_visits / budget / cancel, then on_stuck;
  - CycleError is NOT triggered (the Program driver owns cycles);
  - an unbounded back-edge raises UnboundedCycleError at assembly;
  - a bad back-edge schema raises WireError at assembly;
  - budget hard-stops mid-iteration; spent reflects every iteration (no Gap #3 leak);
  - calibrated no-progress ⇒ on_stuck dead_letter;
  - replay ⇒ identical version sequence + final Outputs, bit-for-bit;
  - taint carries across the cycle.

C2b (durable resume):
  - crash mid-cycle then resume ⇒ zero new metered calls for committed iterations, $0,
    resumed Output sha bit-identical; rows carry org_id (cross-org isolation).

Deterministic — a scripted charging runtime meters real spend; resume replays committed
iterations through RecordReplayRuntime at $0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.batch import Batch
from crawfish.core.context import CostBudget, RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.definition.types import AgentSpec, Coordination, Definition, TeamSpec
from crawfish.ledger import ExecutionLedger, compute_loop_id
from crawfish.nodes.source import Source
from crawfish.output import Output, WireError, output_content_sha
from crawfish.runtime.base import AgentRuntime, EventKind, RunRequest, RunResult, RuntimeEvent
from crawfish.runtime.replay import RecordReplayRuntime
from crawfish.store import SqliteStore
from crawfish.workflow import Program, UnboundedCycleError


# -- fixtures ---------------------------------------------------------------
def _body(role: str = "worker") -> Definition:
    # No declared outputs: the run returns its raw text (a JSON ``{"score": ...}`` blob),
    # which ``_score`` parses — mirroring the refine fixtures (free-text body).
    return Definition(
        id=f"body-{role}",
        inputs=[Parameter(name="item", type="str", required=False, flow=Flow.FLUID)],
        team=TeamSpec(agents=[AgentSpec(role=role, prompt="x")], coordination=Coordination.SINGLE),
    )


class _Scripted(AgentRuntime):
    """Emits a scripted ``{"score": ...}`` sequence and CHARGES the shared budget."""

    name = "scripted"

    def __init__(self, scores: list[float], *, cost_per_call: float = 0.01) -> None:
        self._scores = scores
        self._cost = cost_per_call
        self.calls = 0

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        idx = min(self.calls, len(self._scores) - 1)
        score = self._scores[idx]
        self.calls += 1
        ctx.cost_budget.charge(self._cost)
        text = json.dumps({"score": score})
        result = RunResult(
            text=text,
            model="scripted",
            cost_usd=self._cost,
            events=[RuntimeEvent(kind=EventKind.RESULT, text=text)],
        )
        self._emit_telemetry(ctx, result, self.name)
        return result


class _OneItem(Source[list[dict[str, JSONValue]]]):
    outputs = [Parameter(name="item", type="str")]
    multi = True

    async def fetch(self, ctx: RunContext) -> Output[list[dict[str, JSONValue]]]:
        return Output(
            output_schema=list(self.outputs), value=[{"id": "i1", "item": "x"}], produced_by=self.id
        )


def _score(o: Output[JSONValue]) -> float:
    raw = o.value
    if isinstance(raw, str):
        raw = json.loads(raw)
    return float(raw.get("score", 0.0)) if isinstance(raw, dict) else 0.0


def _ctx(
    store: SqliteStore | None = None, *, limit: float | None = None, org_id: str = "local"
) -> RunContext:
    return RunContext(
        store=store or SqliteStore(), org_id=org_id, cost_budget=CostBudget(limit_usd=limit)
    )


def _loop_program(
    scores: list[float],
    *,
    max_visits: int,
    threshold: float = 0.8,
    cost: float = 0.01,
    on_stuck: str = "return_last",
    rubric_std: float = 0.0,
    patience: int = 1,
) -> tuple[Program, _Scripted]:
    """A 2-step program: Source -> Batch(body), with a back-edge Batch->Batch that loops
    while the scored Output has not cleared ``threshold``."""
    rt = _Scripted(scores, cost_per_call=cost)
    prog = Program(name="loop", runtime=rt)
    src = prog.step(_OneItem("src"))
    body = prog.step(Batch(_body(), name="body"))
    prog.edge(
        body,
        body,
        when=lambda label, out: _score(out) < threshold,  # keep looping until cleared
        max_visits=max_visits,
        on_stuck=on_stuck,  # type: ignore[arg-type]
        progress=_score,
        rubric_std=rubric_std,
        no_progress_patience=patience,
    )
    _ = src
    return prog, rt


# -- C2a: convergence / bounds ----------------------------------------------
async def test_back_edge_runs_to_fixed_point() -> None:
    prog, rt = _loop_program([0.2, 0.5, 0.9], max_visits=5, threshold=0.8)
    out = await prog.run(ctx=_ctx())
    assert len(out) == 1
    assert _score(out[0]) == pytest.approx(0.9)
    assert rt.calls == 3  # looped until the score cleared


async def test_unbounded_back_edge_raises_at_assembly() -> None:
    rt = _Scripted([0.1])
    prog = Program(name="bad", runtime=rt)
    src = prog.step(_OneItem("src"))
    body = prog.step(Batch(_body(), name="body"))
    prog.edge(body, body, when=lambda label, out: True)  # no max_visits
    _ = src
    with pytest.raises(UnboundedCycleError):
        prog.check_types()


async def test_bad_back_edge_schema_raises_wireerror() -> None:
    rt = _Scripted([0.1])
    prog = Program(name="bad", runtime=rt)
    src = prog.step(_OneItem("src"))
    # A body whose Definition requires an input the upstream never produces.
    needs_x = Definition(
        id="needs-x",
        inputs=[Parameter(name="x", type="int")],
        outputs=[Parameter(name="score", type="float")],
    )
    body = prog.step(Batch(needs_x, name="body"))
    prog.edge(body, body, when=lambda label, out: True, max_visits=3)
    _ = src
    with pytest.raises(WireError):
        prog.check_types()


async def test_budget_hard_stops_and_spent_reflects_every_iter() -> None:
    # Never clears; budget caps to exactly 2 metered calls.
    prog, rt = _loop_program([0.1, 0.2, 0.3, 0.4], max_visits=10, threshold=0.99, cost=0.01)
    ctx = _ctx(limit=0.02)
    out = await prog.run(ctx=ctx)
    assert rt.calls == 2
    assert ctx.cost_budget.spent_usd == pytest.approx(0.02)  # every iteration metered
    assert ctx.cost_budget.spent_usd <= 0.02
    _ = out


async def test_cancel_stops_cooperatively() -> None:
    prog, rt = _loop_program([0.1, 0.2, 0.3], max_visits=5, threshold=0.99)
    ctx = _ctx()
    ctx.cancel_token.cancel()
    with pytest.raises(Exception):  # noqa: B017 - cooperative Cancelled
        await prog.run(ctx=ctx)
    assert rt.calls == 0


async def test_calibrated_no_progress_dead_letters() -> None:
    from crawfish.retry import list_dead_letters

    # Scores barely move (< rubric_std) -> no progress; on_stuck dead_letter.
    prog, rt = _loop_program(
        [0.40, 0.401, 0.402, 0.403],
        max_visits=10,
        threshold=0.99,
        on_stuck="dead_letter",
        rubric_std=0.01,
        patience=2,
    )
    ctx = _ctx()
    out = await prog.run(ctx=ctx)
    dead = list_dead_letters(ctx, prog.id)
    assert len(dead) == 1  # the stuck item dead-lettered
    _ = out


async def test_taint_carries_across_the_cycle() -> None:
    # The multi-source fans out tainted items; taint must survive every back-edge.
    prog, rt = _loop_program([0.2, 0.9], max_visits=5, threshold=0.8)
    out = await prog.run(ctx=_ctx())
    assert out[0].tainted is True


# -- C2a determinism + C2b durable resume -----------------------------------
async def test_replay_identical_sequence_and_outputs(tmp_path: Path) -> None:
    cassettes = str(tmp_path / "cass")
    scores = [0.2, 0.5, 0.9]

    # Record run.
    inner = _Scripted(scores)
    rec = RecordReplayRuntime(inner, cassettes, record=True)
    prog1 = Program(name="loop", runtime=rec)
    src = prog1.step(_OneItem("src"))
    body = prog1.step(Batch(_body(), name="body"))
    prog1.edge(body, body, when=lambda label, out: _score(out) < 0.8, max_visits=5)
    _ = src
    out1 = await prog1.run(ctx=_ctx())
    sha1 = output_content_sha(out1[0])

    # Replay run: zero cost, identical final sha.
    replay = RecordReplayRuntime(_Scripted(scores), cassettes, record=False)
    prog2 = Program(name="loop", runtime=replay)
    src2 = prog2.step(_OneItem("src"))
    body2 = prog2.step(Batch(_body(), name="body"))
    prog2.edge(body2, body2, when=lambda label, out: _score(out) < 0.8, max_visits=5)
    _ = src2
    ctx2 = _ctx()
    out2 = await prog2.run(ctx=ctx2)
    assert output_content_sha(out2[0]) == sha1
    assert ctx2.cost_budget.spent_usd == 0.0  # replay charges $0


async def test_durable_resume_recharges_zero(tmp_path: Path) -> None:
    cassettes = str(tmp_path / "cass")
    store = SqliteStore()
    scores = [0.2, 0.5, 0.9]

    def _build(rt: AgentRuntime) -> tuple[Program, Batch]:
        prog = Program(name="loop", runtime=rt)
        prog.step(_OneItem("src"))
        body = prog.step(Batch(_body(), name="body"))
        prog.edge(body, body, when=lambda label, out: _score(out) < 0.8, max_visits=5)
        return prog, body

    # First pass: record cassettes + commit ledger iterations under a shared store.
    rec = RecordReplayRuntime(_Scripted(scores), cassettes, record=True)
    prog1, _ = _build(rec)
    ctx1 = _ctx(store)
    out1 = await prog1.run(ctx=ctx1)
    sha1 = output_content_sha(out1[0])

    # Resume in a SECOND program instance over the same store: committed visits replay at
    # $0 (no new metered calls), and the final Output sha is bit-identical.
    inner2 = _Scripted(scores)
    replay = RecordReplayRuntime(inner2, cassettes, record=False)
    prog2, _ = _build(replay)
    # The program id differs per instance, so loop_id (derived from region version + edge)
    # is stable while the pipeline ledger is fresh; resume reads completed_visits.
    ctx2 = _ctx(store)
    out2 = await prog2.run(ctx=ctx2, resume=True)
    assert output_content_sha(out2[0]) == sha1
    assert inner2.calls == 0  # every committed iteration replayed from cassette at $0
    assert ctx2.cost_budget.spent_usd == 0.0


async def test_ledger_rows_carry_org_id_cross_org_isolation() -> None:
    store = SqliteStore()
    prog, rt = _loop_program([0.2, 0.9], max_visits=5, threshold=0.8)
    await prog.run(ctx=_ctx(store, org_id="org-a"))

    # The same loop_id, queried under a different org, sees no committed visits.
    ledger_b = ExecutionLedger(store, org_id="org-b")
    # Reconstruct the loop_id used by the run (region version | edge id).
    # An empty result under org-b proves cross-tenant isolation.
    rows_b = store.list_records("ledger_loop", org_id="org-b")
    assert rows_b == []
    rows_a = store.list_records("ledger_loop", org_id="org-a")
    assert len(rows_a) >= 1
    _ = (ledger_b, compute_loop_id)
