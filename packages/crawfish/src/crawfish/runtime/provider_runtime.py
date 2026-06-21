"""ProviderRuntime — the unified model construct behind ``AgentRuntime``.

One :class:`AgentRuntime` that wraps one or more :class:`~crawfish.provider.Provider`
backends and gives them uniform observability + cost capture (the same
``_emit_telemetry`` / ``Emission`` path :class:`CommandRuntime` uses) plus
**policy-gated failover** across a model list. Adding a new backend (Anthropic API,
OpenAI, Gemini, local) means writing a ``Provider``, not re-inventing telemetry,
cost charging, or failover (#3, #13).

Security sequencing (CRA-173): this is the provider *layer* only. No live egress is
performed here and no credentials are read from ``.env``/env — a real client adapter
acquires its credential as an **injected dependency** once the typed Secret schema +
sidecar broker land (TODO(CRA-178)). Tests drive this construct with an in-memory
mock :class:`Provider`. Failover egress is a data-residency decision gated by
:class:`~crawfish.provider.ProviderPolicy` (allowed-provider), enforced per candidate.
"""

from __future__ import annotations

from collections.abc import Mapping

from crawfish.core.context import RunContext
from crawfish.provider import ModelsConfig, Provider, ProviderPolicy, resolve_model
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.runtime.prompt import pick_agent

__all__ = [
    "ProviderRuntime",
    "ProviderFailover",
    "expand_candidates",
]


class ProviderFailover(RuntimeError):
    """Raised when no permitted provider could serve any candidate model.

    Carries the attempted ``(model, reason)`` pairs so the caller can see why each
    candidate was skipped (policy-denied / unsupported) or failed (provider error).
    """

    def __init__(self, attempts: list[tuple[str, str]]) -> None:
        self.attempts = attempts
        detail = "; ".join(f"{m}: {why}" for m, why in attempts) or "no candidates"
        super().__init__(f"provider failover exhausted ({detail})")


def expand_candidates(
    model: str | list[str] | None,
    *,
    default: str,
    config: ModelsConfig | None = None,
) -> list[str]:
    """Alias-expand a ``model`` field into an ordered failover candidate list.

    CRA-184 follow-up: when ``model`` is a LIST, **every** entry is alias-expanded
    (not just the primary ``model[0]``), so a failover list of friendly names all
    resolve to concrete ids. ``str``/``None`` collapse to the single resolution from
    the shared :func:`resolve_model` (behaviour-identical). Order is preserved and
    duplicates are dropped (first occurrence wins), keeping resolution deterministic.
    """
    aliases: Mapping[str, str] = config.aliases if config is not None else {}

    if isinstance(model, list) and model:
        # Alias-expand EVERY entry (single hop), not just model[0].
        expanded = [aliases.get(entry, entry) for entry in model]
    else:
        # str / None / empty-list: the single shared resolver owns the fallback rule.
        expanded = [resolve_model(model, default=default, config=config)]

    # Stable de-dup (preserve first occurrence) so a model isn't retried needlessly.
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in expanded:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


class ProviderRuntime(AgentRuntime):
    """An :class:`AgentRuntime` that fails over across providers, policy-gated.

    Providers are tried in registration order; for each failover candidate model the
    first provider that (a) is *permitted* by the active :class:`ProviderPolicy` and
    (b) ``supports`` that model is asked to ``run``. Telemetry + cost capture are
    applied uniformly to whichever provider answers — observability written once.
    """

    name = "provider"

    def __init__(
        self,
        providers: list[Provider],
        *,
        default_model: str,
        config: ModelsConfig | None = None,
        policy: ProviderPolicy | None = None,
    ) -> None:
        if not providers:
            raise ValueError("ProviderRuntime requires at least one Provider")
        self._providers = list(providers)
        self._default_model = default_model
        self._config = config
        # Per-runtime policy override; else the project ModelsConfig policy; else open.
        self._policy = policy or (config.policy if config is not None else ProviderPolicy())

    def _candidates(self, request: RunRequest) -> list[str]:
        """The ordered, alias-expanded failover list for this request."""
        if request.model:  # per-run override pins a single model
            field: str | list[str] | None = request.model
        else:
            field = pick_agent(request.definition, request.role).model
        return expand_candidates(field, default=self._default_model, config=self._config)

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        attempts: list[tuple[str, str]] = []

        for model in self._candidates(request):
            for provider in self._providers:
                if not self._policy.permits(provider.name):
                    attempts.append((model, f"provider {provider.name!r} denied by policy"))
                    continue
                if not provider.supports(model):
                    attempts.append((model, f"provider {provider.name!r} does not support model"))
                    continue

                ctx.cancel_token.raise_if_cancelled()
                pinned = request.model_copy(update={"model": model})
                try:
                    result = await provider.run(pinned, ctx)
                except NotImplementedError:
                    # An unwired stub (e.g. ClientProvider w/o injected caller) is a
                    # configuration error, not a transient backend failure — surface it
                    # rather than silently failing over.
                    raise
                except Exception as exc:  # noqa: BLE001 — failover swallows to try next
                    attempts.append((model, f"provider {provider.name!r} errored: {exc}"))
                    continue

                # Uniform observability for whichever provider answered.
                ctx.cost_budget.charge(result.cost_usd)
                self._emit_telemetry(ctx, result, f"{self.name}:{provider.name}")
                return result

        raise ProviderFailover(attempts)
