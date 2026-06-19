"""CRA-131 acceptance: the engine bootstrap runs a (no-op) pipeline end to end."""

from __future__ import annotations

from crawfish.core import RunContext
from crawfish.engine import Engine
from crawfish.store import SqliteStore


async def test_noop_pipeline_runs_end_to_end() -> None:
    outputs = await Engine().run_pipeline([])
    assert outputs == []


async def test_pipeline_threads_outputs_and_records_telemetry() -> None:
    store = SqliteStore()
    ctx = RunContext(store=store)

    async def double(_ctx: RunContext, inputs: list[object]) -> list[object]:
        return [*inputs, "x"]

    outputs = await Engine(store).run_pipeline([double, double], ctx=ctx, seed=[])
    assert outputs == ["x", "x"]
    events = [e["event"] for e in store.events(ctx.run_id)]
    assert events[0] == "pipeline.start"
    assert events[-1] == "pipeline.done"
