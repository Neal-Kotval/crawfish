"""CRA-109 acceptance: Workflow end-to-end, assembly type-check, crash-resume."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from crawfish.batch import Batch
from crawfish.core.context import RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.definition import Definition
from crawfish.nodes import Filter, GitHubPRSink, Source
from crawfish.output import Output, WireError
from crawfish.runtime import MockRuntime
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.store import SqliteStore
from crawfish.workflow import Workflow

FIXTURES = Path(__file__).parent / "fixtures"


def _minimal(tmp_path: Path) -> Definition:
    dest = tmp_path / "minimal"
    shutil.copytree(FIXTURES / "minimal", dest)
    return Definition.from_package(str(dest))


def _full(tmp_path: Path) -> Definition:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    return Definition.from_package(str(dest))  # inputs: repo (str), pr_body (str)


class _Items(Source[list[dict[str, JSONValue]]]):
    outputs = [Parameter(name="pr_body", type="str")]
    multi = True

    def __init__(self, name: str, config: dict[str, JSONValue] | None = None) -> None:
        super().__init__(name, config)
        self.fetches = 0

    async def fetch(self, ctx: RunContext) -> Output[list[dict[str, JSONValue]]]:
        self.fetches += 1
        return Output(
            output_schema=list(self.outputs), value=self.config["items"], produced_by=self.id
        )


class _BadSource(Source[dict[str, JSONValue]]):
    # provides repo (ok) but pr_body as the wrong type -> adjacency type mismatch
    outputs = [
        Parameter(name="repo", type="str", flow=Flow.STATIC),
        Parameter(name="pr_body", type="list[PR]"),
    ]
    multi = False

    async def fetch(self, ctx: RunContext) -> Output[dict[str, JSONValue]]:
        return Output(output_schema=list(self.outputs), value={"repo": "x"}, produced_by=self.id)


class _FailOnce(AgentRuntime):
    name = "failonce"

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        self.calls += 1
        raise RuntimeError("crash mid-batch")


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


async def test_source_filter_batch_sink_end_to_end(tmp_path: Path) -> None:
    items = [{"pr_body": "keep me"}, {"pr_body": "skip"}, {"pr_body": "keep too"}]
    source = _Items("prs", config={"items": items})
    keep = Filter(lambda v: v.get("pr_body") != "skip", name="drop_skip")
    batch = Batch(_minimal(tmp_path))
    sink = GitHubPRSink(config={"repo": "acme/app"})

    wf = Workflow("triage", steps=[source, keep, batch, sink], runtime=MockRuntime())
    out = await wf.run(ctx=_ctx())
    assert len(out) == 2  # one filtered out
    assert len(sink.writes) == 2  # both survivors written (dry-run)


def test_type_incompatible_adjacency_rejected(tmp_path: Path) -> None:
    wf = Workflow(
        "bad",
        steps=[_BadSource("src"), Batch(_full(tmp_path))],
        runtime=MockRuntime(),
    )
    with pytest.raises(WireError):
        wf.check_types()


async def test_crash_mid_workflow_resumes_from_store(tmp_path: Path) -> None:
    source = _Items("prs", config={"items": [{"pr_body": "a"}, {"pr_body": "b"}]})
    batch = Batch(_minimal(tmp_path))
    sink = GitHubPRSink(config={"repo": "acme/app"})
    wf = Workflow("resumable", steps=[source, batch, sink])
    store = SqliteStore()

    # first attempt crashes at the Batch step (step 1)
    with pytest.raises(RuntimeError):
        await wf.run(ctx=RunContext(store=store), runtime=_FailOnce())
    assert source.fetches == 1

    # resume with a healthy runtime: source step is skipped (no re-fetch), batch+sink finish
    out = await wf.run(ctx=RunContext(store=store), runtime=MockRuntime(), resume=True)
    assert source.fetches == 1  # step 0 not re-run
    assert len(out) == 2
    assert len(sink.writes) == 2
