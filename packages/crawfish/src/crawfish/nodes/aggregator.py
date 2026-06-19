"""Aggregator — the fan-in / reduce node (CRA-133).

A fan-out produces N item :class:`~crawfish.output.Output` s (one per item); an
``Aggregator`` is the fan-in counterpart: it consumes that *group* of N Outputs and
emits exactly **one** Output. The reduction is pluggable:

* **built-in reducers** — pure, deterministic functions over the item values
  (:func:`collect`, :func:`concat`, :func:`count`, :func:`dedupe`); and
* a **Definition-backed reducer** (:func:`definition_reducer`) that runs an agent team
  to reduce the N item values into one (e.g. summarise), feeding the values in as
  *fluid* session data (never instructions) and returning the agent's text.

Because :class:`~crawfish.output.Output` is frozen, the Aggregator never mutates its
inputs: :meth:`Aggregator.reduce` builds a fresh Output stamped with ``produced_by``.

The :func:`fan_in` barrier waits for N concurrent runs (or a quorum) and is
**partial-success aware**: failed (exception) or ``None`` results are dropped before
reduction, so one bad item never sinks the whole fan-in. It is deterministic — results
keep their submission order (``asyncio.gather`` preserves order).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from crawfish.core.context import RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Node, NodeKind, Parameter
from crawfish.output import Output

if TYPE_CHECKING:
    from crawfish.definition.types import Definition
    from crawfish.runtime.base import AgentRuntime

__all__ = [
    "Reducer",
    "collect",
    "concat",
    "count",
    "dedupe",
    "definition_reducer",
    "Aggregator",
    "fan_in",
]


@runtime_checkable
class Reducer(Protocol):
    """A reduction over a group of item Outputs into a single value.

    Built-in reducers are pure and synchronous; the Definition-backed reducer is
    asynchronous (it runs an agent team). :meth:`Aggregator.reduce` awaits the result
    either way, so both shapes plug in interchangeably.
    """

    def __call__(
        self, outputs: list[Output[JSONValue]], ctx: RunContext
    ) -> JSONValue | Awaitable[JSONValue]:
        """Reduce ``outputs`` (in order) to one value."""
        ...


# -- built-in reducers ------------------------------------------------------
# Each is a pure function over the item *values* (`Output.value`), order preserved.


def collect(outputs: list[Output[JSONValue]], ctx: RunContext) -> list[JSONValue]:
    """Gather the item values into a list (the identity fan-in)."""
    return [out.value for out in outputs]


def concat(outputs: list[Output[JSONValue]], ctx: RunContext) -> str:
    """Concatenate the item values into one string (str-coerced, no separator)."""
    return "".join(str(out.value) for out in outputs)


def count(outputs: list[Output[JSONValue]], ctx: RunContext) -> int:
    """Count the items."""
    return len(outputs)


def dedupe(outputs: list[Output[JSONValue]], ctx: RunContext) -> list[JSONValue]:
    """List the item values with duplicates removed, first-seen order preserved."""
    seen: list[JSONValue] = []
    for out in outputs:
        if out.value not in seen:
            seen.append(out.value)
    return seen


def definition_reducer(definition: Definition, runtime: AgentRuntime) -> Reducer:
    """A reducer that runs an agent team to reduce N item values into one.

    The N item *values* are fed in as a single fluid input (``{"items": [...]}``), so
    they reach the model as untrusted session data (never as instructions). The
    reduced value is the agent team's text result.
    """

    async def _reduce(outputs: list[Output[JSONValue]], ctx: RunContext) -> str:
        from crawfish.runtime.team import run_team

        items = [out.value for out in outputs]
        result = await run_team(definition, {"items": items}, ctx, runtime)
        return result.text

    return _reduce


class Aggregator(Node):
    """A fan-in node: consumes a group of N Outputs and emits one Output.

    The ``reducer`` is any :class:`Reducer` (a built-in or
    :func:`definition_reducer`). ``output_schema`` declares the shape of the reduced
    value on the emitted Output (default: empty, i.e. undeclared).
    """

    def __init__(
        self,
        reducer: Reducer,
        *,
        output_schema: list[Parameter] | None = None,
        name: str = "aggregator",
    ) -> None:
        self.id = new_id()
        self.name = name
        self.kind = NodeKind.AGGREGATOR
        self.reducer = reducer
        self.output_schema: list[Parameter] = list(output_schema or [])

    async def reduce(self, outputs: list[Output[JSONValue]], ctx: RunContext) -> Output[JSONValue]:
        """Apply the reducer to the N item Outputs and emit one fresh Output."""
        reduced = self.reducer(outputs, ctx)
        if isinstance(reduced, Awaitable):
            reduced = await reduced
        return Output(
            output_schema=list(self.output_schema),
            value=reduced,
            produced_by=self.id,
        )


async def fan_in(
    runs_or_coros: list[Awaitable[Output[JSONValue] | None]],
    *,
    quorum: int | None = None,
) -> list[Output[JSONValue]]:
    """Barrier that waits for N concurrent runs and returns their successful Outputs.

    Partial-success aware: results that raise or resolve to ``None`` are dropped, so a
    single failed item never sinks the fan-in. Order is preserved (submission order).
    If ``quorum`` is given, raise once fewer than ``quorum`` items succeed.
    """
    results = await asyncio.gather(*runs_or_coros, return_exceptions=True)
    collected: list[Output[JSONValue]] = [
        r for r in results if not isinstance(r, BaseException) and r is not None
    ]
    if quorum is not None and len(collected) < quorum:
        raise ValueError(f"fan-in quorum not met: {len(collected)} succeeded < {quorum} required")
    return collected
