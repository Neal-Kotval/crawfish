"""Concrete :class:`~crawfish.provider.Provider` implementations.

Two providers ship in the layer:

* :class:`MockProvider` — a deterministic, in-memory backend used by ``craw dev`` and
  the whole test suite. No model call, no egress, zero cost: a pure function of the
  request, so failover/telemetry can be exercised deterministically.
* :class:`ClientProvider` — a thin client adapter skeleton. It is **not** wired to a
  live backend in this PR (security sequencing, CRA-173): it performs no network call
  and never reads a credential from ``.env``/env. Credential acquisition is an injected
  dependency that stays ``None`` until the typed Secret schema + sidecar broker land —
  TODO(CRA-178). Calling :meth:`ClientProvider.run` without an injected ``caller``
  raises, so it can never silently egress.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from crawfish.core.context import RunContext
from crawfish.runtime.base import EventKind, RunRequest, RunResult, RuntimeEvent
from crawfish.runtime.prompt import pick_agent, split_inputs

__all__ = ["MockProvider", "ClientProvider"]


class MockProvider:
    """A deterministic, zero-cost :class:`~crawfish.provider.Provider` for tests.

    Satisfies the structural ``Provider`` protocol. Serves a fixed model set; the
    response text is a pure function of the request's fluid inputs (untrusted data is
    echoed as data, never executed). ``fail`` makes :meth:`run` raise to drive failover.
    """

    def __init__(
        self,
        name: str,
        models: list[str],
        *,
        cost_usd: float = 0.0,
        fail: bool = False,
    ) -> None:
        self.name = name
        self._models = list(models)
        self._cost_usd = cost_usd
        self._fail = fail

    def models(self) -> list[str]:
        return list(self._models)

    def supports(self, model: str) -> bool:
        return model in self._models

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        if self._fail:
            raise RuntimeError(f"MockProvider {self.name!r} configured to fail")
        agent = pick_agent(request.definition, request.role)
        _, fluid = split_inputs(request.definition, request.inputs)
        text = f"[{self.name}:{agent.role}] {json.dumps(fluid, sort_keys=True)}"
        model = request.model or (self._models[0] if self._models else "")
        return RunResult(
            text=text,
            session_id=f"{self.name}-{ctx.run_id}",
            cost_usd=self._cost_usd,
            model=model,
            events=[RuntimeEvent(kind=EventKind.RESULT, text=text, cost_usd=self._cost_usd)],
        )


# An injected egress callable. CRA-178 supplies a real implementation whose credential
# is resolved by reference through the sidecar broker — never from .env here.
Caller = Callable[[RunRequest, RunContext], Awaitable[RunResult]]


class ClientProvider:
    """A thin API-client adapter skeleton — credential acquisition deferred to CRA-178.

    Holds *no* secret and performs *no* network I/O in this PR. The ``caller`` (the
    thing that would actually reach a vendor API) is an injected dependency that stays
    ``None`` until the typed Secret schema + sidecar broker land. With no caller,
    :meth:`run` raises ``NotImplementedError`` rather than egressing — onboarding keys
    via ``.env`` now would widen the exact gap CRA-178 closes.
    """

    def __init__(self, name: str, models: list[str], *, caller: Caller | None = None) -> None:
        self.name = name
        self._models = list(models)
        # TODO(CRA-178): credential is injected by reference via the sidecar broker.
        self._caller = caller

    def models(self) -> list[str]:
        return list(self._models)

    def supports(self, model: str) -> bool:
        # An empty model set means "unconfigured stub" — claim support so the call
        # reaches :meth:`run`, which raises NotImplementedError (no silent egress).
        return not self._models or model in self._models

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        if self._caller is None:
            raise NotImplementedError(
                f"ClientProvider {self.name!r} has no injected caller. Live egress and "
                "key onboarding are gated on the typed Secret schema + sidecar broker "
                "(TODO(CRA-178)); credentials are never read from .env here."
            )
        return await self._caller(request, ctx)
