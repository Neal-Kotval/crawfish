"""CRA-107 acceptance: hand-wired Batch, fan-out, assembly-time type checking."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from crawfish.batch import Batch
from crawfish.core.context import RunContext
from crawfish.core.types import JSONValue, Parameter
from crawfish.definition import Definition
from crawfish.nodes import RepoSource, Source
from crawfish.output import Output, WireError
from crawfish.runtime import MockRuntime
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _definition(tmp_path: Path) -> Definition:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    return Definition.from_package(str(dest))  # inputs: repo (static) + pr_body (fluid)


class _BodySource(Source[list[dict[str, JSONValue]]]):
    outputs = [Parameter(name="pr_body", type="str")]
    multi = True

    async def fetch(self, ctx: RunContext) -> Output[list[dict[str, JSONValue]]]:
        return Output(
            output_schema=list(self.outputs), value=self.config["items"], produced_by=self.id
        )


class _BadBodySource(Source[dict[str, JSONValue]]):
    outputs = [Parameter(name="pr_body", type="list[PR]")]  # wrong type for a str slot
    multi = False

    async def fetch(self, ctx: RunContext) -> Output[dict[str, JSONValue]]:
        return Output(output_schema=list(self.outputs), value={"pr_body": []}, produced_by=self.id)


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


async def test_source_definition_runs_end_to_end_fanned_out(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    batch = Batch(d)
    batch.add_input(RepoSource("repo", config={"repo": "acme/app"}))
    batch.add_input(_BodySource("prs", config={"items": [{"pr_body": "a"}, {"pr_body": "b"}]}))

    outputs = await batch.run(_ctx(), MockRuntime())
    assert len(outputs) == 2  # N items -> N Runs -> N Outputs
    assert len(batch.runs) == 2


async def test_n_items_n_runs(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    items = [{"pr_body": f"body {i}"} for i in range(5)]
    batch = Batch(d)
    batch.add_input(RepoSource("repo", config={"repo": "acme/app"}))
    batch.add_input(_BodySource("prs", config={"items": items}))
    outputs = await batch.run(_ctx(), MockRuntime())
    assert len(outputs) == 5


def test_mistyped_wire_rejected_at_assembly(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    batch = Batch(d)
    batch.add_input(RepoSource("repo", config={"repo": "acme/app"}))
    batch.add_input(_BadBodySource("bad"))
    with pytest.raises(WireError):
        batch.check_wiring()  # rejected at assembly, before any run


def test_missing_required_input_rejected_at_assembly(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    batch = Batch(d)
    batch.add_input(RepoSource("repo", config={"repo": "acme/app"}))  # no pr_body provider
    with pytest.raises(WireError):
        batch.check_wiring()


async def test_no_anomalies_on_success(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    batch = Batch(d)
    batch.add_input(RepoSource("repo", config={"repo": "acme/app"}))
    batch.add_input(_BodySource("prs", config={"items": [{"pr_body": "a"}]}))
    await batch.run(_ctx(), MockRuntime())
    assert batch.detect_anomalies() == []
