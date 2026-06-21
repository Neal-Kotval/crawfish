"""CRA-186 — Phase 2 integration / end-to-end milestone (the merge-readiness gate).

Per-issue demos don't catch integration breaks at the SEAMS. This module composes the
WHOLE Phase 2 stack end-to-end on deterministic doubles (MockProvider / MockRuntime /
FakeJail / fake SecretBroker / RecordReplay) and asserts the seams hold together:

1. Emission stream E2E — a typed-output Definition run through a runtime writes the
   typed ``Emission`` stream; the dashboard renders it; the anomaly engine acts on it;
   ``cost.spent_today`` reads cost from the SAME typed stream (the CRA-171 guard).
2. Typed output ↔ eval ↔ tuner/learning — a typed ``Output.value`` scored by a metric;
   the Tuner improves a Definition against a Benchmark (regression-gated); the learning
   loop promotes only on a win.
3. Provider routing ↔ cost (no drift) — a ``RoutingPolicy`` routes a cheap step to the
   cheap model; ``estimate_cost(routing=...)`` prices exactly what ``RoutingRuntime`` runs.
4. Security spine E2E — a jailed node denies a folder-escape (JAIL_VIOLATION audited);
   the broker leases a granted secret without the value reaching the child; consent gates
   the grant; a fluid Sink target is rejected (static-only).
5. THE taint-propagation conformance suite — taint survives EVERY boundary (Emission,
   Output.derive, Context artifact, jail) via ``assert_taint_conformance``.

Everything here is 100% deterministic: no subprocess, no network, no live model, no
wall clock. The whole module must pass under ``pytest -q``.
"""

from __future__ import annotations

import pytest

from crawfish.anomaly import AnomalyEngine, CostSpikeRule, Response
from crawfish.batch import Task
from crawfish.core.context import CostBudget, RunContext
from crawfish.core.types import Flow, Parameter
from crawfish.cost import DEFAULT_MODEL_PRICES, estimate_cost, spent_today
from crawfish.definition.types import AgentSpec, Coordination, Definition, TeamSpec
from crawfish.emission import EmissionKind, read_emissions
from crawfish.jail import (
    DenialKind,
    FakeJail,
    JailPath,
    PathMode,
    StaticOnlyError,
    _Probe,
    emit_denials,
)
from crawfish.learning import LearningLoop, PromotionOutcome
from crawfish.metrics import Benchmark, OutputNumber, Rubric
from crawfish.nodes.sink import GitHubPRSink, TargetMustBeStaticError
from crawfish.output import Output
from crawfish.routing import CostTier, RoutingPolicy, RoutingRule, route_model
from crawfish.runtime import MockProvider, ProviderRuntime, RoutingRuntime, RunRequest
from crawfish.runtime.context_artifact import Context
from crawfish.runtime.mock import MockRuntime
from crawfish.runtime.prompt import pick_agent
from crawfish.secrets import (
    AutoConsent,
    Capabilities,
    ConsentDeclined,
    DenyConsent,
    Grant,
    GrantManifest,
    LeaseDenied,
    Outbound,
    SecretBroker,
    SecretRequest,
    consent_install,
)
from crawfish.store import SqliteStore
from crawfish.testing import assert_taint_conformance, taint_conformance_cases
from crawfish.tuner import KnobGridMutator, Tuner
from crawfish.visualize import emission_dashboard_state

CHEAP = "claude-haiku-4-5"
STRONG = "claude-opus-4-8"
SECRET_VALUE = "sk-supersecret-value-0123456789"
REF = "ACME_API_KEY"
DEST = "api.acme.com"
NODE = "sink.acme"
PACKAGE = "crawfish-acme"


def _ctx(tmp_path, *, limit_usd: float | None = None) -> RunContext:
    store = SqliteStore(str(tmp_path / "phase2.db"))
    return RunContext(store=store, cost_budget=CostBudget(limit_usd=limit_usd))


def _typed_definition() -> Definition:
    """A single cheap typed-output step."""
    return Definition(
        team=TeamSpec(agents=[AgentSpec(role="scout", prompt="scan", policies=["tier:cheap"])]),
        inputs=[Parameter(name="task", type="text", flow=Flow.FLUID)],
    )


def _two_step_team() -> Definition:
    return Definition(
        team=TeamSpec(
            agents=[
                AgentSpec(role="scout", prompt="scan", policies=["tier:cheap"]),
                AgentSpec(role="reviewer", prompt="judge", policies=["tier:strong"]),
            ],
            coordination=Coordination.SINGLE,
        )
    )


# =====================================================================================
# SEAM 1 — Emission stream E2E: runtime → typed ledger → dashboard / anomaly / cost
# =====================================================================================


async def test_emission_stream_composes_dashboard_anomaly_and_cost(tmp_path) -> None:
    """A typed-output Definition run through a runtime writes the typed Emission stream;
    every downstream reader (dashboard, anomaly engine, cost) consumes the SAME stream.
    CRA-171 regression guard: cost lives IN the typed stream, not a side channel.
    """
    rt = ProviderRuntime([MockProvider("anthropic", [CHEAP], cost_usd=0.02)], default_model=CHEAP)
    ctx = _ctx(tmp_path)
    result = await rt.run(RunRequest(definition=_typed_definition(), role="scout"), ctx)
    assert result.model == CHEAP and result.cost_usd == pytest.approx(0.02)

    # 1a. The typed Emission stream carries the MODEL kind with cost in attrs.
    ems = read_emissions(ctx.store, ctx.run_id)
    model_ems = [e for e in ems if e.kind is EmissionKind.MODEL]
    assert model_ems and model_ems[0].attrs["cost_usd"] == pytest.approx(0.02)

    # 1b. The dashboard renders the same stream (cost rolls up from model.cost_usd).
    state = emission_dashboard_state(ems)
    assert state["total_cost_usd"] == pytest.approx(0.02)

    # 1c. The anomaly engine acts on the same stream (a cheap spike threshold fires).
    engine = AnomalyEngine(
        [CostSpikeRule(threshold_usd=0.01, window="-1h", response=Response.FLAG)]
    )
    firings = engine.evaluate(ems, now=2.0)
    assert firings, "anomaly engine must see the cost emission in the typed stream"

    # 1d. CRA-171 GUARD: cost.spent_today reads cost from the SAME typed stream.
    spent = spent_today(ctx.store, run_ids=[ctx.run_id])
    assert spent == pytest.approx(0.02), "cost must be discoverable in the typed emission stream"


# =====================================================================================
# SEAM 2 — Typed Output ↔ eval/metric ↔ tuner ↔ learning (regression-gated promotion)
# =====================================================================================


def _benchmark() -> Benchmark:
    return Benchmark(
        Rubric([OutputNumber(name="score")]),
        [Task(description="a"), Task(description="b")],
    )


def _model_scoring_responder(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    return str({"slow": 1, "mid": 5, "fast": 9}.get(agent.model or "", 0))


def test_typed_output_scored_by_metric() -> None:
    """A typed Output.value (dict) is scored by a CRA-175 metric — the eval seam."""
    out: Output[object] = Output(output_schema=[], value={"score": 7.0}, produced_by="scout")
    scores = Rubric([OutputNumber(field="score", name="score")]).score(out)
    assert scores["score"] == 7.0


@pytest.mark.asyncio
async def test_tuner_improves_definition_regression_gated(tmp_path) -> None:
    """The Tuner improves a Definition against a Benchmark; the regression gate keeps the
    base when no candidate beats it."""
    base = Definition(
        team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do it", model="slow")]),
        inputs=[Parameter(name="task", type="text", flow=Flow.FLUID)],
    )
    rt = MockRuntime(_model_scoring_responder)

    # Improvement available -> tuner promotes "fast".
    win = await Tuner(_benchmark(), KnobGridMutator(models=["slow", "mid", "fast"])).tune(
        base, _ctx(tmp_path), rt, seed=0
    )
    assert win.improved and win.best.team.agents[0].model == "fast"
    assert win.best_scores["score"] == 9.0 and win.base_scores["score"] == 1.0

    # Base already best -> regression gate refuses every worse candidate.
    best_base = Definition(
        team=TeamSpec(agents=[AgentSpec(role="worker", model="fast")]),
        inputs=[Parameter(name="task", type="text", flow=Flow.FLUID)],
    )
    held = await Tuner(_benchmark(), KnobGridMutator(models=["slow", "mid"])).tune(
        best_base, _ctx(tmp_path), rt, seed=0
    )
    assert not held.improved and held.best.team.agents[0].model == "fast"


@pytest.mark.asyncio
async def test_learning_loop_promotes_only_on_a_win(tmp_path) -> None:
    """The learning loop is the Tuner pointed at an agent's own Definition; it promotes a
    new frozen content-hashed Version ONLY when it beats the baseline."""
    store = SqliteStore(str(tmp_path / "learn.db"))
    base = Definition(
        team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do it", model="slow")]),
        inputs=[Parameter(name="task", type="text", flow=Flow.FLUID)],
    )
    loop = LearningLoop(
        "agent", Tuner(_benchmark(), KnobGridMutator(models=["slow", "mid", "fast"])), store
    )
    out = await loop.improve(base, _ctx(tmp_path), MockRuntime(_model_scoring_responder), seed=0)
    assert isinstance(out, PromotionOutcome)
    assert out.promoted and out.reason == "promoted"
    active = loop.active()
    assert active is not None and active.sha == out.candidate_sha and active.role == "promoted"


# =====================================================================================
# SEAM 3 — Provider routing ↔ cost estimate (NO DRIFT across the seam)
# =====================================================================================


@pytest.mark.asyncio
async def test_routing_and_cost_estimate_do_not_drift(tmp_path) -> None:
    """estimate_cost(routing=...) prices exactly the models RoutingRuntime actually runs."""
    d = _two_step_team()
    policy = RoutingPolicy(
        rules=(
            RoutingRule(tier=CostTier.CHEAP, model=CHEAP),
            RoutingRule(tier=CostTier.STRONG, model=STRONG),
        )
    )

    # Pure resolver agrees on both steps.
    assert route_model(d, "scout", policy=policy, default=STRONG) == CHEAP
    assert route_model(d, "reviewer", policy=policy, default=STRONG) == STRONG

    # Cost preview prices each step under the SAME policy.
    est = estimate_cost(d, items=1, routing=policy)
    assert est.per_model == {
        CHEAP: pytest.approx(DEFAULT_MODEL_PRICES[CHEAP]),
        STRONG: pytest.approx(DEFAULT_MODEL_PRICES[STRONG]),
    }

    # The runtime routes each step to the exact id the preview priced — NO DRIFT.
    rt = RoutingRuntime(
        ProviderRuntime([MockProvider("p", [CHEAP, STRONG])], default_model=STRONG),
        policy,
        default_model=STRONG,
    )
    ctx = _ctx(tmp_path)
    scout = await rt.run(RunRequest(definition=d, role="scout"), ctx)
    reviewer = await rt.run(RunRequest(definition=d, role="reviewer"), ctx)
    assert scout.model == CHEAP and reviewer.model == STRONG
    assert set(est.per_model) == {scout.model, reviewer.model}


# =====================================================================================
# SEAM 4 — Security spine E2E: jail, broker, consent, static-only sink
# =====================================================================================


def test_jail_denies_folder_escape_and_audits(tmp_path) -> None:
    """A jailed node reading outside its allow_paths is DENIED and AUDITED as JAIL_VIOLATION."""
    jail = FakeJail(lambda cmd: _Probe(reads=["/etc/passwd"]))
    res = jail.run(["node"], allow_paths=[JailPath("/work/project", PathMode.RO)])
    assert len(res.denied) == 1 and res.denied[0].kind is DenialKind.FOLDER_ESCAPE

    store = SqliteStore(str(tmp_path / "jail.db"))
    written = emit_denials(store, res, run_id="run-1", node_id="bad-node", ts=1.0)
    assert written
    rows = read_emissions(store, "run-1")
    assert any(r.kind is EmissionKind.JAIL_VIOLATION for r in rows)
    attempts = {r.attrs["attempt"] for r in rows if r.kind is EmissionKind.JAIL_VIOLATION}
    assert "/etc/passwd" in attempts


def test_jail_rejects_fluid_allow_path() -> None:
    """allow_paths is STATIC-only: a fluid (untrusted) path can never widen the sandbox."""
    jail = FakeJail(lambda cmd: _Probe())
    with pytest.raises(StaticOnlyError):
        jail.run(["x"], allow_paths=[JailPath("/secret", flow=Flow.FLUID)])


def test_broker_leases_granted_secret_value_never_reaches_child() -> None:
    """The broker injects the credential at the egress boundary; the child only ever holds
    a value-free handle."""

    class _Transport:
        def __init__(self) -> None:
            self.sent: list[Outbound] = []

        def send(self, request: Outbound) -> object:
            self.sent.append(request)
            return {"status": "ok"}

    transport = _Transport()
    broker = SecretBroker(secret_values={REF: SECRET_VALUE}, transport=transport)  # type: ignore[arg-type]
    grant = Grant(package="acme", secrets=(REF,), egress=(DEST,))

    handle = broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), grant)
    assert SECRET_VALUE not in str(handle.__dict__) and handle.ref == REF

    resp = broker.send(handle, Outbound(host=DEST, method="POST", path="/v1/things", body={"x": 1}))
    assert resp == {"status": "ok"}
    # Credential reached the wire, never the child.
    assert transport.sent[0].headers["Authorization"] == f"Bearer {SECRET_VALUE}"
    assert SECRET_VALUE not in str(resp)


def test_broker_rejects_fluid_secret_ref_static_only() -> None:
    """A fluid (untrusted) value can never name a secret ref — static-only spine."""
    broker = SecretBroker(secret_values={REF: SECRET_VALUE}, transport=None)  # type: ignore[arg-type]
    grant = Grant(package="acme", secrets=(REF,), egress=(DEST,))
    req = SecretRequest(node_id=NODE, ref=REF, destination=DEST, ref_flow=Flow.FLUID)
    with pytest.raises(LeaseDenied, match="STATIC-only"):
        broker.lease(req, grant)


def test_consent_gates_the_grant() -> None:
    """consent_install records a Grant only on explicit approval; fail-closed otherwise."""
    caps = Capabilities(secrets=[REF], egress=[DEST])

    store = SqliteStore()
    grant = consent_install(PACKAGE, caps, store=store, decider=AutoConsent(), now=123.0)
    assert grant.secrets == (REF,) and grant.egress == (DEST,)
    assert GrantManifest(store).lookup(PACKAGE) == grant

    # Declined -> no grant recorded.
    store2 = SqliteStore()
    with pytest.raises(ConsentDeclined):
        consent_install(PACKAGE, caps, store=store2, decider=DenyConsent())
    assert GrantManifest(store2).lookup(PACKAGE) is None

    # Non-interactive default is fail-closed.
    store3 = SqliteStore()
    with pytest.raises(ConsentDeclined):
        consent_install(PACKAGE, caps, store=store3)


def test_sink_target_is_static_only() -> None:
    """A consequential Sink target must be STATIC; a fluid target is rejected at construction."""
    with pytest.raises(TargetMustBeStaticError):
        GitHubPRSink(target_params=[Parameter(name="repo", type="str", flow=Flow.FLUID)])
    sink = GitHubPRSink(target_params=[Parameter(name="repo", type="str", flow=Flow.STATIC)])
    assert sink.target_params[0].flow is Flow.STATIC


# =====================================================================================
# SEAM 5 — THE taint-propagation conformance suite (across EVERY boundary)
# =====================================================================================


def test_taint_conformance_suite_passes_across_all_boundaries() -> None:
    """The load-bearing cross-cutting check #1/#4/#9 reference: taint survives Emission,
    Output.derive, Context artifact, and jail. This must be green for the gate to pass."""
    assert_taint_conformance()


def test_taint_matrix_covers_the_load_bearing_rows() -> None:
    by_name = {c.name: c for c in taint_conformance_cases()}
    assert by_name["fluid_input"].expected is True
    assert by_name["static_plus_tool"].source_tainted is False
    assert by_name["static_plus_tool"].from_tool is True


def test_taint_propagates_through_output_derive_and_context_artifact() -> None:
    """Boundary check: a fluid Output taints everything derived from it AND any Context
    artifact it is threaded into."""
    fluid: Output[object] = Output(
        output_schema=[], value="untrusted", produced_by="src", tainted=True
    )
    derived = fluid.derive(value={"x": 1}, produced_by="node")
    assert derived.tainted is True

    ctx = Context().add_result(key="scout_result", role="scout", result=fluid)
    assert ctx.tainted is True, "Context artifact must carry taint from a fluid Output"

    clean: Output[object] = Output(output_schema=[], value="cfg", produced_by="src", tainted=False)
    assert Context().add_result(key="cfg", role="scout", result=clean).tainted is False
