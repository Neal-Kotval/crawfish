"""ClientRuntime + ManagedRuntime — routed through the unified provider layer.

Both are :class:`AgentRuntime`s; both delegate to :class:`ProviderRuntime`, so they
inherit uniform telemetry, cost capture, and policy-gated failover for free (CRA-173) —
adding a real backend is additive, no call-site change.

Security sequencing (CRA-173): neither performs live egress in this PR. ``ClientRuntime``
backs itself with a :class:`ClientProvider` whose egress ``caller`` is an **injected**
dependency, defaulting to ``None`` — so without an injected caller a run raises rather
than reaching any vendor API, and no credential is ever read from ``.env``/env. Real
credential acquisition lands with the typed Secret schema + sidecar broker — TODO(CRA-178).
``ManagedRuntime`` (CMA) remains a stub until the managed/cloud phase.
"""

from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.provider import ModelsConfig, ProviderPolicy
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.runtime.provider_runtime import ProviderRuntime
from crawfish.runtime.providers import Caller, ClientProvider

__all__ = ["ClientRuntime", "ManagedRuntime"]

# A neutral placeholder default. No vendor default is hardcoded in the provider layer
# (ADR 0005); a configured ModelsConfig.default / agent model overrides this.
_PLACEHOLDER_MODEL = "unset"


class ClientRuntime(AgentRuntime):
    """API-key backend, behind the provider layer. No live egress until CRA-178.

    The ``caller`` is the injected egress dependency; while it is ``None`` (the default
    in this PR) any run raises ``NotImplementedError`` instead of reaching a vendor —
    credential acquisition is deferred to the sidecar broker (TODO(CRA-178)).
    """

    name = "client"

    def __init__(
        self,
        *,
        provider_name: str = "client",
        models: list[str] | None = None,
        caller: Caller | None = None,
        default_model: str = _PLACEHOLDER_MODEL,
        config: ModelsConfig | None = None,
        policy: ProviderPolicy | None = None,
    ) -> None:
        provider = ClientProvider(provider_name, models or [], caller=caller)
        self._runtime = ProviderRuntime(
            [provider], default_model=default_model, config=config, policy=policy
        )

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        return await self._runtime.run(request, ctx)


class ManagedRuntime(AgentRuntime):
    name = "managed"

    def __init__(self, *, endpoint: str | None = None) -> None:
        self._endpoint = endpoint

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        raise NotImplementedError(
            "ManagedRuntime (CMA) is a stub; ships in the managed/cloud phase "
            "(packages/crawfish-cma)."
        )
