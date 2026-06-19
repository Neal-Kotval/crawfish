"""Profile → runtime selection (CRA-112).

``dev`` → CommandRuntime, ``prod`` → ManagedRuntime; switching profile is a runtime
swap with no code change. Per-agent model overrides are honoured inside each runtime.
"""

from __future__ import annotations

from crawfish.config import ProfileConfig
from crawfish.runtime.base import AgentRuntime
from crawfish.runtime.command import CommandRuntime
from crawfish.runtime.mock import MockRuntime
from crawfish.runtime.stubs import ClientRuntime, ManagedRuntime

__all__ = ["get_runtime", "RUNTIME_FACTORIES"]

RUNTIME_FACTORIES: dict[str, type[AgentRuntime]] = {
    "command": CommandRuntime,
    "mock": MockRuntime,
    "client": ClientRuntime,
    "managed": ManagedRuntime,
}


def get_runtime(profile: ProfileConfig) -> AgentRuntime:
    """Instantiate the runtime named by a resolved profile."""
    name = profile.runtime
    factory = RUNTIME_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"unknown runtime {name!r} (known: {sorted(RUNTIME_FACTORIES)})")
    return factory()
