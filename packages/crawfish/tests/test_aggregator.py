"""CRA-133 acceptance: the Aggregator fan-in / reduce node.

Covers the built-in reducers, the Definition-backed (agent-team) reducer, and the
partial-success-aware :func:`fan_in` barrier.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from crawfish.core.context import RunContext
from crawfish.core.types import Parameter
from crawfish.definition import Definition
from crawfish.nodes.aggregator import (
    Aggregator,
    collect,
    concat,
    count,
    dedupe,
    definition_reducer,
    fan_in,
)
from crawfish.output import Output
from crawfish.runtime import MockRuntime
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


def _outputs(*values: object) -> list[Output[object]]:
    return [Output(output_schema=[], value=v, produced_by=f"r{i}") for i, v in enumerate(values)]


# -- built-in reducers ------------------------------------------------------


async def test_collect_fans_in_to_single_list_output() -> None:
    agg = Aggregator(collect)
    out = await agg.reduce(_outputs({"n": 1}, {"n": 2}, {"n": 3}), _ctx())
    assert isinstance(out, Output)
    assert out.value == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert out.produced_by == agg.id


async def test_concat_joins_values_to_string() -> None:
    agg = Aggregator(concat)
    out = await agg.reduce(_outputs("a", "b", "c"), _ctx())
    assert out.value == "abc"


async def test_count_returns_item_count() -> None:
    agg = Aggregator(count)
    out = await agg.reduce(_outputs("x", "y", "z", "w"), _ctx())
    assert out.value == 4


async def test_dedupe_drops_duplicates_preserving_order() -> None:
    agg = Aggregator(dedupe)
    out = await agg.reduce(_outputs("a", "b", "a", "c", "b"), _ctx())
    assert out.value == ["a", "b", "c"]


async def test_declared_output_schema_is_stamped_on_emitted_output() -> None:
    schema = [Parameter(name="items", type="list[str]")]
    agg = Aggregator(collect, output_schema=schema)
    out = await agg.reduce(_outputs("a", "b"), _ctx())
    assert [p.name for p in out.output_schema] == ["items"]


# -- Definition-backed reducer ----------------------------------------------


async def test_definition_reducer_returns_one_string_output(tmp_path: Path) -> None:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    definition = Definition.from_package(str(dest))

    agg = Aggregator(definition_reducer(definition, MockRuntime()))
    out = await agg.reduce(_outputs({"pr": 1}, {"pr": 2}), _ctx())

    assert isinstance(out, Output)
    assert out.produced_by == agg.id
    assert isinstance(out.value, str)
    assert out.value  # non-empty agent text


# -- fan-in barrier ---------------------------------------------------------


async def _ok(value: object) -> Output[object]:
    return Output(output_schema=[], value=value, produced_by="run")


async def _boom() -> Output[object]:
    raise RuntimeError("item failed")


async def _none() -> Output[object] | None:
    return None


async def test_fan_in_waits_for_all_and_excludes_failed_item() -> None:
    collected = await fan_in([_ok({"n": 1}), _boom(), _ok({"n": 2}), _none()])
    assert [o.value for o in collected] == [{"n": 1}, {"n": 2}]


async def test_fan_in_then_reduce_drops_failures() -> None:
    collected = await fan_in([_ok("a"), _boom(), _ok("b")])
    agg = Aggregator(count)
    out = await agg.reduce(collected, _ctx())
    assert out.value == 2


async def test_fan_in_quorum_not_met_raises() -> None:
    with pytest.raises(ValueError):
        await fan_in([_ok("a"), _boom(), _boom()], quorum=2)


async def test_fan_in_quorum_met_returns_successes() -> None:
    collected = await fan_in([_ok("a"), _ok("b"), _boom()], quorum=2)
    assert [o.value for o in collected] == ["a", "b"]
