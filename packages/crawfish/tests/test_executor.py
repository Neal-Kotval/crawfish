"""CRA-108 + CRA-122 acceptance: scheduling, concurrency, cost-kill, dead-letter, replay."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from crawfish.batch import Batch, Task
from crawfish.core.context import BudgetExceeded, CostBudget, RunContext
from crawfish.core.types import JSONValue, Parameter
from crawfish.definition import Definition
from crawfish.executor import BatchExecutor, CycleError, DependencyGraph
from crawfish.nodes import Source
from crawfish.output import Output
from crawfish.retry import RetryPolicy, list_dead_letters
from crawfish.runtime import CommandRuntime, MockRuntime
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _minimal(tmp_path: Path) -> Definition:
    dest = tmp_path / "minimal"
    shutil.copytree(FIXTURES / "minimal", dest, dirs_exist_ok=True)
    return Definition.from_package(str(dest))  # single agent, no declared inputs


class _Items(Source[list[dict[str, JSONValue]]]):
    outputs = [Parameter(name="pr_body", type="str")]
    multi = True

    async def fetch(self, ctx: RunContext) -> Output[list[dict[str, JSONValue]]]:
        return Output(
            output_schema=list(self.outputs), value=self.config["items"], produced_by=self.id
        )


class _Tracking(AgentRuntime):
    name = "tracking"

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return RunResult(text="ok", model="tracking", cost_usd=0.0)


class _Flaky(AgentRuntime):
    name = "flaky"

    def __init__(self, fail_on: str) -> None:
        self.fail_on = fail_on

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        if self.fail_on in str(request.inputs.get("pr_body", "")):
            raise RuntimeError("item boom")
        return RunResult(text="ok", model="flaky", cost_usd=0.0)


def _ctx(**kw: object) -> RunContext:
    return RunContext(store=SqliteStore(), **kw)  # type: ignore[arg-type]


def _batch(tmp_path: Path, items: list[dict[str, JSONValue]]) -> Batch:
    b = Batch(_minimal(tmp_path))
    b.add_input(_Items("prs", config={"items": items}))
    return b


# -- scheduling ---------------------------------------------------------------
def test_topo_layers_parallel_and_dependent() -> None:
    g = DependencyGraph()
    g.add_node("I3")
    g.add_edge("I1", "I2")  # I1 blocks I2
    assert g.topo_layers() == [["I1", "I3"], ["I2"]]


def test_cycle_rejected() -> None:
    g = DependencyGraph()
    g.add_edge("A", "B")
    g.add_edge("B", "A")
    with pytest.raises(CycleError):
        g.topo_layers()


def test_schedule_from_tasks(tmp_path: Path) -> None:
    ex = BatchExecutor(_minimal(tmp_path))
    t1, t3 = Task(description="1"), Task(description="3")
    t2 = Task(description="2", blocked_by=[t1.id])
    plan = ex.schedule([t1, t2, t3])
    assert plan.layers[0] == sorted([t1.id, t3.id])
    assert plan.layers[1] == [t2.id]


# -- execution ----------------------------------------------------------------
async def test_runs_all_items(tmp_path: Path) -> None:
    items = [{"pr_body": f"b{i}"} for i in range(4)]
    ex = BatchExecutor(_minimal(tmp_path))
    result = await ex.run(_batch(tmp_path, items), _ctx(), MockRuntime())
    assert len(result.outputs) == 4
    assert all(r.status.value == "ok" for r in result.items)


async def test_concurrency_capped(tmp_path: Path) -> None:
    items = [{"pr_body": f"b{i}"} for i in range(6)]
    rt = _Tracking()
    ex = BatchExecutor(_minimal(tmp_path), max_concurrency=2)
    await ex.run(_batch(tmp_path, items), _ctx(), rt)
    assert rt.peak <= 2  # backpressure: never more than the cap in flight


async def test_failing_item_dead_lettered_not_halting(tmp_path: Path) -> None:
    items = [{"pr_body": "ok-1"}, {"pr_body": "FAIL"}, {"pr_body": "ok-2"}]
    ex = BatchExecutor(
        _minimal(tmp_path), max_concurrency=1, retry_policy=RetryPolicy(max_attempts=1)
    )
    ctx = _ctx()
    batch = _batch(tmp_path, items)
    result = await ex.run(batch, ctx, _Flaky("FAIL"))
    statuses = sorted(r.status.value for r in result.items)
    assert statuses == ["dead", "ok", "ok"]  # one dead, batch did not halt
    assert len(list_dead_letters(ctx, batch.id)) == 1


async def test_runaway_killed_at_cost_cap(tmp_path: Path) -> None:
    async def expensive(args: list[str], prompt: str) -> str:
        return json.dumps(
            {"type": "result", "total_cost_usd": 5.0, "result": "x", "session_id": "s"}
        )

    items = [{"pr_body": "a"}, {"pr_body": "b"}]
    ex = BatchExecutor(_minimal(tmp_path), max_concurrency=1)
    ctx = _ctx(cost_budget=CostBudget(limit_usd=0.01))
    with pytest.raises(BudgetExceeded):
        await ex.run(_batch(tmp_path, items), ctx, CommandRuntime(transport=expensive))


async def test_replay_reruns_only_failures(tmp_path: Path) -> None:
    items = [{"pr_body": "ok-1"}, {"pr_body": "FAIL"}]
    ex = BatchExecutor(
        _minimal(tmp_path), max_concurrency=1, retry_policy=RetryPolicy(max_attempts=1)
    )
    ctx = _ctx()
    batch = _batch(tmp_path, items)
    await ex.run(batch, ctx, _Flaky("FAIL"))
    assert len(list_dead_letters(ctx, batch.id)) == 1

    # replay with a runtime that no longer fails -> the dead-lettered item succeeds
    replayed = await ex.replay(batch, ctx, MockRuntime())
    assert len(replayed.outputs) == 1  # only the previously-failed item re-ran
    assert list_dead_letters(ctx, batch.id) == []
