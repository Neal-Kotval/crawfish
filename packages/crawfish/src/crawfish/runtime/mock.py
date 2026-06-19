"""MockRuntime — a deterministic, zero-cost backend for `craw dev` and tests.

No model call: a pure function of the request, so iterating on a Definition never
burns budget and tests stay deterministic.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from crawfish.core.context import RunContext
from crawfish.runtime.base import AgentRuntime, EventKind, RunRequest, RunResult, RuntimeEvent
from crawfish.runtime.prompt import pick_agent, split_inputs

__all__ = ["MockRuntime"]

Responder = Callable[[RunRequest], str]


def _default_responder(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    _, fluid = split_inputs(request.definition, request.inputs)
    return f"[{agent.role}] processed: {json.dumps(fluid, sort_keys=True)}"


class MockRuntime(AgentRuntime):
    name = "mock"

    def __init__(self, responder: Responder | None = None) -> None:
        self._responder = responder or _default_responder

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        text = self._responder(request)
        result = RunResult(
            text=text,
            session_id=f"mock-{ctx.run_id}",
            cost_usd=0.0,
            model="mock",
            events=[RuntimeEvent(kind=EventKind.RESULT, text=text)],
        )
        self._emit_telemetry(ctx, result, self.name)
        return result
