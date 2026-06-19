"""Record/replay — deterministic runs from cassettes (CRA-112, basis for CRA-119).

Wrap any runtime. On a cache hit, replay the recorded ``RunResult`` (zero cost, no
model call — `craw dev` and `craw test` iterate without burning budget). On a miss in
``record`` mode, call the inner runtime and persist the cassette; otherwise raise.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.runtime.prompt import pick_agent

__all__ = ["RecordReplayRuntime", "CassetteMiss"]


class CassetteMiss(RuntimeError):
    """Raised when no cassette exists and recording is disabled."""


def _key(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    canonical = json.dumps(
        {
            "id": request.definition.id,
            "version": str(request.definition.version),
            "role": agent.role,
            "model": request.model,
            "inputs": request.inputs,
            "session_id": request.session_id,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class RecordReplayRuntime(AgentRuntime):
    name = "replay"

    def __init__(
        self, inner: AgentRuntime, cassette_dir: str | Path, *, record: bool = False
    ) -> None:
        self._inner = inner
        self._dir = Path(cassette_dir)
        self._record = record

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        path = self._dir / f"{_key(request)}.json"
        if path.exists():
            result = RunResult.model_validate_json(path.read_text())
            self._emit_telemetry(ctx, result, f"replay:{self._inner.name}")
            return result  # zero cost — no budget charge on replay
        if not self._record:
            raise CassetteMiss(f"no cassette for request (key {path.stem}); run with record=True")
        result = await self._inner.run(request, ctx)
        self._dir.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(indent=2))
        return result
