"""AgentRuntime backends — the swappable agent loop (CRA-112)."""

from __future__ import annotations

from crawfish.runtime.base import (
    AgentRuntime,
    EventKind,
    RunRequest,
    RunResult,
    RuntimeEvent,
    ToolCall,
)
from crawfish.runtime.command import CommandRuntime, Transport
from crawfish.runtime.mock import MockRuntime
from crawfish.runtime.prompt import compile_prompt, pick_agent, split_inputs
from crawfish.runtime.replay import CassetteMiss, RecordReplayRuntime
from crawfish.runtime.select import RUNTIME_FACTORIES, get_runtime
from crawfish.runtime.stubs import ClientRuntime, ManagedRuntime
from crawfish.runtime.team import run_team

__all__ = [
    "AgentRuntime",
    "run_team",
    "EventKind",
    "RuntimeEvent",
    "ToolCall",
    "RunRequest",
    "RunResult",
    "CommandRuntime",
    "Transport",
    "MockRuntime",
    "ClientRuntime",
    "ManagedRuntime",
    "RecordReplayRuntime",
    "CassetteMiss",
    "get_runtime",
    "RUNTIME_FACTORIES",
    "compile_prompt",
    "pick_agent",
    "split_inputs",
]
