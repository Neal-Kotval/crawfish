"""ClientRuntime + ManagedRuntime stubs (CRA-112).

Registered so profile selection resolves them, but not implemented in Phase 1 M1.
ClientRuntime (Anthropic / OpenAI-compatible, API key) and ManagedRuntime (CMA) land
behind the same :class:`AgentRuntime` seam — adding them is additive, no call-site change.
"""

from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult

__all__ = ["ClientRuntime", "ManagedRuntime"]


class ClientRuntime(AgentRuntime):
    name = "client"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key
        self._model = model

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        raise NotImplementedError(
            "ClientRuntime is a stub (CRA-112). Use CommandRuntime (`claude -p`) for the "
            "zero-key dev loop; the API-key backend lands behind this same seam."
        )


class ManagedRuntime(AgentRuntime):
    name = "managed"

    def __init__(self, *, endpoint: str | None = None) -> None:
        self._endpoint = endpoint

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        raise NotImplementedError(
            "ManagedRuntime (CMA) is a stub (CRA-112); ships in the managed/cloud phase "
            "(packages/crawfish-cma)."
        )
