"""Engine bootstrap — load a project, build a pipeline, run it (CRA-131).

This is the shared core behind ``craw run`` (and a future daemon). M0 ships the
minimal honest version: a pipeline is an ordered list of *steps*, each an async
callable ``(ctx, inputs) -> outputs`` that threads its predecessor's outputs
forward. An empty pipeline is a valid no-op that runs end to end. The richer
typed ``Workflow`` (CRA-109) and node primitives build on this contract.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING

from crawfish.core.context import RunContext
from crawfish.store.sqlite import SqliteStore

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = ["Step", "Engine", "run_pipeline"]

# A pipeline step: consumes the running list of outputs, returns the next.
Step = Callable[[RunContext, list[object]], Awaitable[list[object]]]


class Engine:
    """Runs a pipeline of steps under a single :class:`RunContext`."""

    def __init__(self, store: Store | None = None) -> None:
        self._store: Store = store or SqliteStore()

    async def run_pipeline(
        self,
        steps: Sequence[Step],
        *,
        ctx: RunContext | None = None,
        seed: list[object] | None = None,
    ) -> list[object]:
        ctx = ctx or RunContext(store=self._store)
        ctx.store.append_event(ctx.run_id, {"event": "pipeline.start", "steps": len(steps)})
        outputs: list[object] = list(seed or [])
        for i, step in enumerate(steps):
            ctx.cancel_token.raise_if_cancelled()
            ctx.store.append_event(ctx.run_id, {"event": "step.start", "index": i})
            outputs = await step(ctx, outputs)
            ctx.store.append_event(ctx.run_id, {"event": "step.done", "index": i})
        ctx.store.append_event(ctx.run_id, {"event": "pipeline.done", "outputs": len(outputs)})
        return outputs


async def run_pipeline(steps: Sequence[Step], **kwargs: object) -> list[object]:
    """Convenience wrapper that builds a default :class:`Engine`."""
    return await Engine().run_pipeline(steps, **kwargs)  # type: ignore[arg-type]
