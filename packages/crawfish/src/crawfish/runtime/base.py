"""The ``AgentRuntime`` seam.

The **only** place the model SDK/CLI is touched. The product model drives runs
through this interface, so the agent loop is swappable: CommandRuntime (`claude -p`,
zero key) → ClientRuntime (API key) → ManagedRuntime (CMA). Switching profile
dev→prod is a runtime swap, not a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue
from crawfish.definition.types import Definition

if TYPE_CHECKING:
    from crawfish.core.context import RunContext

__all__ = [
    "EventKind",
    "ToolCall",
    "RuntimeEvent",
    "RunRequest",
    "RunResult",
    "AgentRuntime",
]


class EventKind(str, Enum):
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    RESULT = "result"
    ERROR = "error"


class ToolCall(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    input: dict[str, JSONValue] = Field(default_factory=dict)


class RuntimeEvent(BaseModel):
    kind: EventKind
    text: str = ""
    tool: ToolCall | None = None
    cost_usd: float = 0.0
    session_id: str | None = None


class RunRequest(BaseModel):
    """One agent's turn: a compiled Definition + the inputs bound for this run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    definition: Definition
    inputs: dict[str, JSONValue] = Field(default_factory=dict)
    role: str | None = None  # which agent (default: lead, else first)
    model: str | None = None  # per-agent/per-run override
    session_id: str | None = None  # resume an existing session


class RunResult(BaseModel):
    text: str = ""
    session_id: str | None = None
    cost_usd: float = 0.0
    model: str = ""
    events: list[RuntimeEvent] = Field(default_factory=list)


# Definition is a concrete import (no cycle: crawfish.definition never imports runtime),
# so the RunRequest forward reference resolves at runtime.
RunRequest.model_rebuild()


class AgentRuntime(ABC):
    """Swappable agent-loop backend."""

    name: str = "abstract"

    @abstractmethod
    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        """Execute one agent turn to completion and return the typed result."""

    async def stream(self, request: RunRequest, ctx: RunContext) -> AsyncIterator[RuntimeEvent]:
        """Stream events. Default: run to completion, then replay its events."""
        result = await self.run(request, ctx)
        for event in result.events:
            yield event

    @staticmethod
    def _emit_telemetry(ctx: RunContext, result: RunResult, runtime: str) -> None:
        """Persist a compact run summary to the Store's event ledger.

        Routed through the typed :class:`~crawfish.emission.Emission` substrate
        (``MODEL`` kind) and written via ``emit`` → ``Store.append_event``, so the
        transport and any ``ScrubbingStore`` redaction are unchanged. Pure runtime
        telemetry has no ``Output`` in hand, so ``tainted`` defaults False; ``ts`` is
        left at the contract default (no wall-clock read on this path).
        """
        # Local import keeps the runtime substrate free of an emission import cycle.
        from crawfish.emission import Emission, EmissionKind, emit

        emit(
            ctx.store,
            Emission(
                kind=EmissionKind.MODEL,
                run_id=ctx.run_id,
                org_id=ctx.org_id,
                attrs={
                    "model": result.model,
                    "cost_usd": result.cost_usd,
                    "events": len(result.events),
                    "session_id": result.session_id,
                    "runtime": runtime,
                },
            ),
            org_id=ctx.org_id,
        )
