"""CRA-173 acceptance: unified provider layer — telemetry, failover, policy gating.

All deterministic: no live model calls and no egress. A mock ``Provider`` answers every
turn; failover and policy gating are exercised purely in-memory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from crawfish.core.context import RunContext
from crawfish.definition import Definition
from crawfish.emission import EmissionKind, read_emissions
from crawfish.provider import ModelsConfig, Provider, ProviderPolicy
from crawfish.runtime import (
    ClientProvider,
    ClientRuntime,
    MockProvider,
    ProviderFailover,
    ProviderRuntime,
    RunRequest,
    expand_candidates,
)
from crawfish.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"


def _definition(tmp_path: Path) -> Definition:
    dest = tmp_path / "full"
    shutil.copytree(FIXTURES / "full", dest)
    return Definition.from_package(str(dest))


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore())


# --- the mock Provider satisfies the frozen structural protocol -----------------------


def test_mock_provider_is_a_provider() -> None:
    assert isinstance(MockProvider("p", ["m1"]), Provider)
    assert isinstance(ClientProvider("c", []), Provider)


# --- telemetry + cost capture flow uniformly through the runtime ----------------------


async def test_telemetry_and_cost_capture(tmp_path: Path) -> None:
    rt = ProviderRuntime([MockProvider("anthropic", ["m1"], cost_usd=0.02)], default_model="m1")
    ctx = _ctx()
    result = await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), ctx)

    assert result.model == "m1"
    assert result.cost_usd == pytest.approx(0.02)
    # budget charged + typed MODEL emission written to the ledger (same path as CommandRuntime)
    assert ctx.cost_budget.spent_usd == pytest.approx(0.02)
    ems = read_emissions(ctx.store, ctx.run_id)
    model_ems = [em for em in ems if em.kind is EmissionKind.MODEL]
    assert model_ems and model_ems[0].attrs["runtime"] == "provider:anthropic"


# --- failover across a model list -----------------------------------------------------


async def test_failover_across_model_list(tmp_path: Path) -> None:
    d = _definition(tmp_path)
    # Agent pins a failover list: primary unsupported by the only provider, fallback ok.
    d.agent("scout").model = ["missing", "m2"]
    provider = MockProvider("p", ["m2"])
    rt = ProviderRuntime([provider], default_model="m2")
    result = await rt.run(RunRequest(definition=d, role="scout"), _ctx())
    assert result.model == "m2"  # failed over to the second entry


async def test_failover_when_first_provider_errors(tmp_path: Path) -> None:
    flaky = MockProvider("flaky", ["m1"], fail=True)
    healthy = MockProvider("healthy", ["m1"], cost_usd=0.01)
    rt = ProviderRuntime([flaky, healthy], default_model="m1")
    ctx = _ctx()
    result = await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), ctx)
    assert result.session_id and result.session_id.startswith("healthy-")
    assert ctx.cost_budget.spent_usd == pytest.approx(0.01)


async def test_failover_exhausted_raises(tmp_path: Path) -> None:
    rt = ProviderRuntime([MockProvider("p", ["other"])], default_model="m1")
    with pytest.raises(ProviderFailover):
        await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), _ctx())


# --- alias expansion of EVERY entry (CRA-184 follow-up) -------------------------------


def test_expand_candidates_alias_expands_all_list_entries() -> None:
    config = ModelsConfig(aliases={"fast": "concrete-fast", "smart": "concrete-smart"})
    # Both entries must be expanded, not just the primary model[0].
    assert expand_candidates(["fast", "smart"], default="d", config=config) == [
        "concrete-fast",
        "concrete-smart",
    ]


def test_expand_candidates_str_and_none_match_resolve_model() -> None:
    config = ModelsConfig(default="cfg-default", aliases={"fast": "concrete-fast"})
    assert expand_candidates("fast", default="d", config=config) == ["concrete-fast"]
    assert expand_candidates(None, default="d", config=config) == ["cfg-default"]
    assert expand_candidates([], default="d", config=config) == ["cfg-default"]


def test_expand_candidates_dedups_preserving_order() -> None:
    assert expand_candidates(["a", "b", "a"], default="d") == ["a", "b"]


async def test_failover_list_uses_alias_expanded_fallback(tmp_path: Path) -> None:
    # The alias 'smart' (an aliased non-primary entry) is the only one a provider serves.
    config = ModelsConfig(aliases={"fast": "concrete-fast", "smart": "concrete-smart"})
    d = _definition(tmp_path)
    d.agent("scout").model = ["fast", "smart"]
    rt = ProviderRuntime([MockProvider("p", ["concrete-smart"])], default_model="d", config=config)
    result = await rt.run(RunRequest(definition=d, role="scout"), _ctx())
    assert result.model == "concrete-smart"


# --- ProviderPolicy gating (data-residency / allowed-provider) ------------------------


async def test_policy_denied_provider_refused(tmp_path: Path) -> None:
    # Only 'anthropic' is allowed; the (otherwise capable) 'openai' provider is skipped.
    policy = ProviderPolicy(allowed=("anthropic",))
    denied = MockProvider("openai", ["m1"], cost_usd=0.99)
    allowed = MockProvider("anthropic", ["m1"], cost_usd=0.01)
    rt = ProviderRuntime([denied, allowed], default_model="m1", policy=policy)
    ctx = _ctx()
    result = await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), ctx)
    assert result.session_id and result.session_id.startswith("anthropic-")
    assert ctx.cost_budget.spent_usd == pytest.approx(0.01)  # denied provider never ran


async def test_policy_denies_all_providers_raises(tmp_path: Path) -> None:
    policy = ProviderPolicy(allowed=("nobody",))
    rt = ProviderRuntime([MockProvider("anthropic", ["m1"])], default_model="m1", policy=policy)
    with pytest.raises(ProviderFailover) as exc:
        await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), _ctx())
    assert "denied by policy" in str(exc.value)


def test_policy_from_models_config_is_used(tmp_path: Path) -> None:
    config = ModelsConfig(policy=ProviderPolicy(allowed=("only",)))
    rt = ProviderRuntime([MockProvider("only", ["m1"])], default_model="m1", config=config)
    assert rt._policy.permits("only") and not rt._policy.permits("other")


# --- security sequencing: ClientRuntime never egresses without an injected caller -----


async def test_client_runtime_without_caller_raises_not_egress(tmp_path: Path) -> None:
    # No caller injected -> NotImplementedError (no .env read, no network). CRA-178 gate.
    rt = ClientRuntime()
    with pytest.raises(NotImplementedError):
        await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), _ctx())


async def test_client_runtime_with_injected_caller_runs(tmp_path: Path) -> None:
    # Credential acquisition is an injected dependency (the CRA-178 seam); here a fake
    # caller stands in, proving the layer works without ever touching .env.
    async def fake_caller(request: RunRequest, ctx: RunContext):  # type: ignore[no-untyped-def]
        from crawfish.runtime import RunResult

        return RunResult(text="ok", model=request.model or "", cost_usd=0.03)

    rt = ClientRuntime(models=["m1"], caller=fake_caller, default_model="m1")
    ctx = _ctx()
    result = await rt.run(RunRequest(definition=_definition(tmp_path), role="scout"), ctx)
    assert result.text == "ok"
    assert ctx.cost_budget.spent_usd == pytest.approx(0.03)
