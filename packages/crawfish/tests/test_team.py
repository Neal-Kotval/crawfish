"""CRA-135 acceptance: TeamSpec coordination topologies execute correctly."""

from __future__ import annotations

import shutil
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.definition import AgentSpec, Coordination, Definition, TeamSpec
from crawfish.runtime import MockRuntime, run_team
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


async def test_single_topology_runs_one_agent() -> None:
    d = Definition(team=TeamSpec(agents=[AgentSpec(role="solo", prompt="Do it")]))
    result = await run_team(d, {"x": "1"}, _ctx(), MockRuntime())
    assert result.text.startswith("[solo]")


async def test_sequential_threads_prior_result() -> None:
    d = Definition(
        team=TeamSpec(
            agents=[AgentSpec(role="first", prompt="A"), AgentSpec(role="second", prompt="B")],
            coordination=Coordination.SEQUENTIAL,
        )
    )
    result = await run_team(d, {"seed": "v"}, _ctx(), MockRuntime())
    # the second (last) agent ran with the first's result threaded in
    assert result.text.startswith("[second]")
    assert "prior_result" in result.text


async def test_lead_delegates_and_combines(tmp_path: Path) -> None:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    d = Definition.from_package(str(dest))  # lead delegates to scout, reviewer
    assert d.team.coordination is Coordination.LEAD

    result = await run_team(d, {"pr_body": "Fix bug"}, _ctx(), MockRuntime())
    # lead's combined view contains both delegates' typed results (delegation-in)
    assert result.text.startswith("[lead]")
    assert "scout_result" in result.text
    assert "reviewer_result" in result.text


async def test_lead_aggregates_cost(tmp_path: Path) -> None:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    d = Definition.from_package(str(dest))

    def responder(_req: object) -> str:
        return "x"

    rt = MockRuntime(responder=responder)
    result = await run_team(d, {"pr_body": "x"}, _ctx(), rt)
    assert result.cost_usd == 0.0  # mock is free; cost is summed across lead+delegates
