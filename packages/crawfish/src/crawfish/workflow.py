"""Workflow / Pipeline — the first-class deployable (CRA-109).

The top-level composition: ordered ``steps`` (Source / Filter / Batch / Aggregator /
Sink), Output threaded stage to stage, fan-out across steps. Adjacent steps are
**type-checked at assembly** (stage N's output schema ↔ stage N+1's inputs). Cross-node
orchestration state is checkpointed to the ``Store`` after each stage, so a crash
mid-workflow resumes from the last completed stage (durable by default).
"""

from __future__ import annotations

from crawfish.core.compat import parameters_compatible
from crawfish.core.context import RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Node, Parameter
from crawfish.ledger import ExecutionLedger
from crawfish.nodes.aggregator import Aggregator
from crawfish.nodes.filter import Filter
from crawfish.nodes.sink import Sink
from crawfish.nodes.source import Source
from crawfish.output import Output, WireError
from crawfish.run import Run
from crawfish.runtime.base import AgentRuntime

# Batch imported lazily inside methods to avoid a heavy import at module load.

__all__ = ["Workflow"]


class Workflow:
    """A versioned pipeline of steps, run from a prompt and deployable as a unit."""

    def __init__(
        self,
        prompt: str = "",
        steps: list[Node] | None = None,
        *,
        name: str = "workflow",
        runtime: AgentRuntime | None = None,
        version: str = "0.1",
    ) -> None:
        self.id = new_id()
        self.prompt = prompt
        self.name = name
        self.steps: list[Node] = list(steps or [])
        self.runtime = runtime
        self.version = version

    # -- assembly type-check ------------------------------------------------
    def _producer_out(self, step: Node) -> list[Parameter] | None:
        from crawfish.batch import Batch

        if isinstance(step, Source):
            return step.outputs
        if isinstance(step, Batch):
            return step.definition.outputs
        if isinstance(step, Aggregator):
            return step.output_schema or None
        return None  # Filter passthrough / Sink terminal

    def _consumer_in(self, step: Node) -> list[Parameter] | None:
        from crawfish.batch import Batch

        if isinstance(step, Batch):
            return step.definition.inputs
        return None

    def check_types(self) -> None:
        """Reject a type-incompatible adjacency at assembly."""
        for a, b in zip(self.steps, self.steps[1:], strict=False):
            out = self._producer_out(a)
            inp = self._consumer_in(b)
            if out is None or inp is None:
                continue
            provided = {p.name: p for p in out}
            for want in inp:
                have = provided.get(want.name)
                if have is None:
                    if want.required and want.default is None:
                        raise WireError(
                            f"workflow {self.name!r}: step {b.name!r} needs input "
                            f"{want.name!r} not produced by {a.name!r}"
                        )
                    continue
                if not parameters_compatible(have, want):
                    raise WireError(
                        f"workflow {self.name!r}: {a.name!r}->{b.name!r} type mismatch on "
                        f"{want.name!r} ({have.type!r} vs {want.type!r})"
                    )

    # -- checkpoint state ---------------------------------------------------
    def _save_state(self, ctx: RunContext, current: list[Output[JSONValue]]) -> None:
        ctx.store.put_record(
            "workflow_state",
            self.id,
            {"current": [o.model_dump(mode="json") for o in current]},
            org_id=ctx.org_id,
        )

    def _load_state(self, ctx: RunContext) -> list[Output[JSONValue]]:
        rec = ctx.store.get_record("workflow_state", self.id, org_id=ctx.org_id)
        if rec is None:
            return []
        return [Output.model_validate(o) for o in rec["current"]]

    # -- execution ----------------------------------------------------------
    async def run(
        self,
        prompt: str | None = None,
        *,
        ctx: RunContext | None = None,
        runtime: AgentRuntime | None = None,
        resume: bool = False,
    ) -> list[Output[JSONValue]]:
        if prompt is not None:
            self.prompt = prompt
        rt = runtime or self.runtime
        if ctx is None:
            from crawfish.store.sqlite import SqliteStore

            ctx = RunContext(store=SqliteStore())
        self.check_types()

        ledger = ExecutionLedger(ctx.store, org_id=ctx.org_id)
        if resume:
            done = ledger.completed_steps(self.id)
            current = self._load_state(ctx)
        else:
            ledger.start_pipeline(self.id, self.version, total_items=len(self.steps))
            done = set()
            current = []

        for i, step in enumerate(self.steps):
            if i in done:
                continue
            ctx.cancel_token.raise_if_cancelled()
            current = await self._run_step(step, current, ctx, rt)
            ledger.checkpoint_step(self.id, i)
            self._save_state(ctx, current)

        ledger.finish_pipeline(self.id)
        return current

    async def _run_step(
        self,
        step: Node,
        current: list[Output[JSONValue]],
        ctx: RunContext,
        rt: AgentRuntime | None,
    ) -> list[Output[JSONValue]]:
        from crawfish.batch import Batch

        if isinstance(step, Source):
            out = await step.fetch(ctx)
            return step.fan_out(out) if step.multi else [out]

        if isinstance(step, Filter):
            # Filter the item Outputs directly so lineage + taint are preserved.
            return [o for o in current if step.predicate(o.value)]

        if isinstance(step, Batch):
            if rt is None:
                raise ValueError("workflow with a Batch step requires a runtime")
            outputs: list[Output[JSONValue]] = []
            for item in current:
                inputs = item.value if isinstance(item.value, dict) else {"item": item.value}
                child = RunContext(
                    store=ctx.store,
                    batch_id=step.id,
                    org_id=ctx.org_id,
                    cost_budget=ctx.cost_budget,
                )
                run = Run(step.definition, inputs, runtime=rt)
                out = await run.execute(child, rt)
                # Carry the source item's stable lineage forward for idempotency.
                outputs.append(out.model_copy(update={"lineage": item.lineage}))
            return outputs

        if isinstance(step, Aggregator):
            return [await step.reduce(current, ctx)]

        if isinstance(step, Sink):
            for item in current:
                await step.write(item, ctx)
            return current  # terminal: pass through unchanged

        raise TypeError(f"unsupported workflow step kind: {step.kind}")
