"""Batch Executor & scheduling — rule-based (CRA-108).

Orders tasks into parallel layers (Kahn's algorithm over ``blocked_by``, cycles
rejected), then runs a Batch through a **work-queue** backbone: a fixed pool of
workers drains the queue, so a 10k-item fan-out is rate-limited (backpressure), not
exploded. The cost ceiling is a hard-kill; failed items retry then dead-letter
(never halt the batch); progress is checkpointed to the execution ledger. The queue
is an abstraction (local impl now) so a future multi-worker/cloud executor is a
consumer swap, not a rewrite.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from crawfish.batch import Batch, Task
from crawfish.core.context import BudgetExceeded, RunContext
from crawfish.core.types import JSONValue
from crawfish.definition.types import Definition
from crawfish.ledger import ExecState, ExecutionLedger
from crawfish.output import Output
from crawfish.retry import (
    ItemResult,
    ItemStatus,
    RetryPolicy,
    dead_letter,
    list_dead_letters,
    run_with_retry,
)
from crawfish.run import Run
from crawfish.runtime.base import AgentRuntime

__all__ = [
    "CycleError",
    "DependencyGraph",
    "Roadmap",
    "ExecutionPlan",
    "BatchExecutor",
    "BatchRunResult",
]


class CycleError(ValueError):
    """Raised when a dependency graph contains a cycle."""


class DependencyGraph:
    """Edges ``(blocker, blocked)``; ``topo_layers`` returns parallelizable layers."""

    def __init__(self) -> None:
        self.edges: list[tuple[str, str]] = []
        self.nodes: set[str] = set()

    def add_node(self, node: str) -> None:
        self.nodes.add(node)

    def add_edge(self, blocker: str, blocked: str) -> None:
        self.edges.append((blocker, blocked))
        self.nodes.update((blocker, blocked))

    def topo_layers(self) -> list[list[str]]:
        indeg: dict[str, int] = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = defaultdict(list)
        for blocker, blocked in self.edges:
            adj[blocker].append(blocked)
            indeg[blocked] += 1

        layers: list[list[str]] = []
        frontier = sorted(n for n in self.nodes if indeg[n] == 0)
        seen = 0
        while frontier:
            layers.append(frontier)
            nxt: list[str] = []
            for n in frontier:
                seen += 1
                for m in adj[n]:
                    indeg[m] -= 1
                    if indeg[m] == 0:
                        nxt.append(m)
            frontier = sorted(nxt)
        if seen != len(self.nodes):
            raise CycleError("dependency graph has a cycle")
        return layers


class Roadmap(BaseModel):
    milestones: list[dict[str, JSONValue]] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    layers: list[list[str]] = Field(default_factory=list)


@dataclass
class BatchRunResult:
    outputs: list[Output[JSONValue]] = field(default_factory=list)
    items: list[ItemResult] = field(default_factory=list)
    dead_letters: list[dict[str, JSONValue]] = field(default_factory=list)


class BatchExecutor:
    """Schedules + runs a Batch. Rule-based; leaves a seam for an agentic executor."""

    def __init__(
        self,
        definition: Definition,
        *,
        max_concurrency: int = 8,
        retry_policy: RetryPolicy | None = None,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self.definition = definition
        self.max_concurrency = max_concurrency
        # Production-grade default: real exponential backoff. Tests that exercise the
        # failure path pass max_attempts=1 to stay fast.
        self.retry_policy = retry_policy or RetryPolicy(base_delay=0.5)
        self.runtime = runtime
        self.roadmap = Roadmap()

    # -- scheduling ---------------------------------------------------------
    def schedule(self, tasks: list[Task]) -> ExecutionPlan:
        graph = DependencyGraph()
        ids = {t.id for t in tasks}
        for t in tasks:
            graph.add_node(t.id)
            for blocker in t.blocked_by:
                if blocker in ids:
                    graph.add_edge(blocker, t.id)
        return ExecutionPlan(layers=graph.topo_layers())

    # -- execution ----------------------------------------------------------
    async def run(
        self,
        batch: Batch,
        ctx: RunContext,
        runtime: AgentRuntime | None = None,
        *,
        only_items: set[str] | None = None,
    ) -> BatchRunResult:
        rt = runtime or self.runtime or batch.runtime
        if rt is None:
            raise ValueError("BatchExecutor.run requires an AgentRuntime")
        batch.check_wiring()

        base_values, item_value_sets = await batch._gather_inputs(ctx)
        ledger = ExecutionLedger(ctx.store, org_id=ctx.org_id)
        ledger.start_pipeline(
            batch.id, str(self.definition.version), total_items=len(item_value_sets)
        )
        budget = batch.cost_budget or ctx.cost_budget

        # Build the work queue (the dispatch backbone). Skip already-done items
        # (resume / replay): only_items, when given, limits to a work-list.
        queue: asyncio.Queue[tuple[str, dict[str, JSONValue]]] = asyncio.Queue()
        for idx, item_values in enumerate(item_value_sets):
            item_id = str(idx)
            if only_items is not None and item_id not in only_items:
                continue
            queue.put_nowait((item_id, item_values))

        results: dict[str, ItemResult] = {}
        kill: list[BaseException] = []

        async def process(item_id: str, item_values: dict[str, JSONValue]) -> ItemResult:
            child = RunContext(
                store=ctx.store,
                batch_id=batch.id,
                org_id=ctx.org_id,
                cost_budget=budget,
                cancel_token=ctx.cancel_token,
            )

            async def factory() -> Output[JSONValue]:
                run = Run(self.definition, {**base_values, **item_values}, runtime=rt)
                ledger.record_run(
                    run.id,
                    backend=rt.name,
                    status=ExecState.RUNNING,
                    version=str(self.definition.version),
                )
                out = await run.execute(child, rt)
                ledger.record_run(
                    run.id,
                    backend=rt.name,
                    status=ExecState.DONE,
                    version=str(self.definition.version),
                )
                return out

            try:
                out = await run_with_retry(factory, self.retry_policy)
            except Exception as exc:  # noqa: BLE001 - classify below
                if isinstance(exc, BudgetExceeded):
                    raise
                dead_letter(
                    ctx, batch_id=batch.id, item_id=item_id, error=str(exc), payload=item_values
                )
                ledger.mark_item(batch.id, item_id, ExecState.FAILED)
                return ItemResult(item_id=item_id, status=ItemStatus.DEAD, error=str(exc))
            ledger.mark_item(batch.id, item_id, ExecState.DONE)
            return ItemResult(item_id=item_id, status=ItemStatus.OK, value=out.value)

        async def worker() -> None:
            while True:
                try:
                    item_id, item_values = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    results[item_id] = await process(item_id, item_values)
                except BudgetExceeded as exc:  # runaway hard-kill: drain + stop
                    kill.append(exc)
                    while not queue.empty():
                        queue.get_nowait()
                    return

        await asyncio.gather(*(worker() for _ in range(self.max_concurrency)))

        if kill:
            ledger.finish_pipeline(batch.id, ExecState.FAILED)
            raise kill[0]

        ledger.finish_pipeline(batch.id, ExecState.DONE)
        items = [results[k] for k in sorted(results)]
        outputs = [
            Output(value=r.value, produced_by=batch.id) for r in items if r.status is ItemStatus.OK
        ]
        return BatchRunResult(
            outputs=outputs, items=items, dead_letters=list_dead_letters(ctx, batch.id)
        )

    async def replay(
        self, batch: Batch, ctx: RunContext, runtime: AgentRuntime | None = None
    ) -> BatchRunResult:
        """Re-run only dead-lettered items (idempotency makes this safe, CRA-104)."""
        dead = list_dead_letters(ctx, batch.id)
        only = {str(d["item_id"]) for d in dead}
        for d in dead:  # clear before re-running; success won't re-dead-letter
            ctx.store.delete_record("dead_letter", f"{batch.id}:{d['item_id']}", org_id=ctx.org_id)
        return await self.run(batch, ctx, runtime, only_items=only)
