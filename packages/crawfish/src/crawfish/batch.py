"""Batch — a hand-wired pipeline of Sources, a Definition, and Sinks.

The assembly point: wire Sources/Outputs into a Definition by hand. A multi-item
Source **fans out** to one Run per item, each seeded with that item's fluid values.
Wiring is **type-checked at assembly** (structural ``parameters_compatible``), so a
mistyped wire is rejected before any model call — not at run time. The Batch's token/$
ceiling is carried onto every child Run's ``RunContext``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from crawfish.core.compat import parameters_compatible
from crawfish.core.context import CostBudget, RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Node, NodeKind, Parameter
from crawfish.definition.types import Definition
from crawfish.nodes.source import Source
from crawfish.output import Output, WireError
from crawfish.run import Run, RunStatus
from crawfish.runtime.base import AgentRuntime

__all__ = ["Task", "Anomaly", "Batch"]


class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    description: str = ""
    blocked_by: list[str] = Field(default_factory=list)


class Anomaly(BaseModel):
    task_id: str
    kind: str
    detail: str


class Batch(Node):
    """A set of Runs executed under one Definition, wired from Sources/Outputs."""

    def __init__(
        self,
        definition: Definition,
        name: str = "batch",
        *,
        runtime: AgentRuntime | None = None,
        cost_budget: CostBudget | None = None,
    ) -> None:
        self.id = new_id()
        self.name = name
        self.kind = NodeKind.BATCH
        self.definition = definition
        self.runtime = runtime
        self.cost_budget = cost_budget
        self.tasks: list[Task] = []
        self.runs: list[Run] = []
        self.inputs: list[Source[JSONValue] | Output[JSONValue]] = []
        self.outputs: list[Output[JSONValue]] = []

    # -- assembly -----------------------------------------------------------
    def add_input(self, item: Source[JSONValue] | Output[JSONValue]) -> Batch:
        self.inputs.append(item)
        return self

    def _provided_params(self) -> dict[str, Parameter]:
        """The parameters available from all wired inputs, by name."""
        provided: dict[str, Parameter] = {}
        for item in self.inputs:
            params = item.outputs if isinstance(item, Source) else item.output_schema
            for p in params:
                provided[p.name] = p
        return provided

    def check_wiring(self) -> None:
        """Reject a mistyped/missing wire at assembly (before run time)."""
        provided = self._provided_params()
        for want in self.definition.inputs:
            have = provided.get(want.name)
            if have is None:
                if want.required and want.default is None:
                    raise WireError(
                        f"batch {self.name!r}: no input provides required "
                        f"definition input {want.name!r}"
                    )
                continue
            if not parameters_compatible(have, want):
                raise WireError(
                    f"batch {self.name!r}: input {want.name!r} type {have.type!r} "
                    f"is not compatible with definition input type {want.type!r}"
                )

    # -- execution ----------------------------------------------------------
    async def run(
        self, ctx: RunContext, runtime: AgentRuntime | None = None
    ) -> list[Output[JSONValue]]:
        rt = runtime or self.runtime
        if rt is None:
            raise ValueError("Batch.run requires an AgentRuntime")
        self.check_wiring()  # also enforced at run start, defence in depth

        base_values, item_value_sets = await self._gather_inputs(ctx)
        budget = self.cost_budget or ctx.cost_budget

        self.runs = []
        self.outputs = []
        for item_values in item_value_sets:
            ctx.cancel_token.raise_if_cancelled()
            run_inputs: dict[str, JSONValue] = {**base_values, **item_values}
            task = Task(description=f"item run in batch {self.name}")
            self.tasks.append(task)
            child = RunContext(
                store=ctx.store,
                batch_id=self.id,
                org_id=ctx.org_id,
                cost_budget=budget,  # shared batch ceiling across all runs
                cancel_token=ctx.cancel_token,
            )
            run = Run(self.definition, run_inputs, runtime=rt)
            self.runs.append(run)
            output = await run.execute(child, rt)
            self.outputs.append(output)

        ctx.store.put_record(
            "batch",
            self.id,
            {"id": self.id, "definition": self.definition.id, "runs": len(self.runs)},
            org_id=ctx.org_id,
        )
        return self.outputs

    async def _gather_inputs(
        self, ctx: RunContext
    ) -> tuple[dict[str, JSONValue], list[dict[str, JSONValue]]]:
        """Fetch sources; expand a multi Source into per-item value sets.

        Returns (shared static values, list of per-item fluid value sets). With no
        multi Source there is a single item (one Run); with one there are N.
        """
        base_values: dict[str, JSONValue] = {}
        item_value_sets: list[dict[str, JSONValue]] = [{}]

        for item in self.inputs:
            if isinstance(item, Source):
                output = await item.fetch(ctx)
                if item.multi:
                    items = item.fan_out(output)
                    item_value_sets = [
                        i.value if isinstance(i.value, dict) else {"item": i.value} for i in items
                    ]
                else:
                    if isinstance(output.value, dict):
                        base_values.update(output.value)
            else:  # a direct upstream Output
                if isinstance(item.value, dict):
                    base_values.update(item.value)
        return base_values, item_value_sets

    # -- anomalies ----------------------------------------------------------
    def detect_anomalies(self) -> list[Anomaly]:
        """Surface failed runs as anomalies (richer rules arrive with Metrics)."""
        anomalies = [
            Anomaly(task_id=task.id, kind="run_failed", detail=f"run {run.id} failed")
            for task, run in zip(self.tasks, self.runs, strict=False)
            if run.status is RunStatus.FAILED
        ]
        return anomalies
