"""SEC-4 (CRA-241) acceptance: circuit breaker + audit trail for the self-mod loop.

The autonomous LearningLoop self-modifies production behavior; it needs (a) a circuit
breaker that auto-halts on a runaway promotion/cost/rollback rate (reusing the shipped
AnomalyEngine), and (b) an append-only audit trail on every auto-promotion / halt /
rollback (both shas + org_id). All deterministic — the breaker reads the recorded ledger,
no model call.
"""

from __future__ import annotations

import pytest

from crawfish.anomaly import (
    PROMOTION_AUDIT_KIND,
    PromotionRateRule,
    Response,
    RollbackRateRule,
    emit_promotion_audit,
    promotion_breaker,
)
from crawfish.batch import Task
from crawfish.core.context import CancelToken, CostBudget, RunContext
from crawfish.core.types import Flow, Parameter
from crawfish.definition.types import AgentSpec, Definition, TeamSpec
from crawfish.emission import read_emissions
from crawfish.learning import LearningLoop
from crawfish.metrics import Benchmark, OutputNumber, Rubric
from crawfish.runtime.base import RunRequest
from crawfish.runtime.mock import MockRuntime
from crawfish.runtime.prompt import pick_agent
from crawfish.store import SqliteStore
from crawfish.tuner import KnobGridMutator, Tuner


def _base(model: str = "slow") -> Definition:
    return Definition(
        team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do it", model=model)]),
        inputs=[Parameter(name="task", type="text", flow=Flow.FLUID)],
    )


def _ctx(store, *, run_id="run-1") -> RunContext:
    return RunContext(
        store=store, run_id=run_id, cost_budget=CostBudget(), cancel_token=CancelToken()
    )


def _responder(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    return str({"slow": 1, "mid": 5, "fast": 9}.get(agent.model or "", 0))


def _benchmark() -> Benchmark:
    return Benchmark(
        Rubric([OutputNumber(name="score")]), [Task(description="a"), Task(description="b")]
    )


# -- the audit trail -------------------------------------------------------
def test_promotion_emits_audit_with_both_shas_and_org() -> None:
    """Every auto-promotion writes an append-only audit event (both shas + org_id)."""
    store = SqliteStore()
    emit_promotion_audit(
        store,
        event="promoted",
        agent="agent",
        candidate_sha="cand",
        baseline_sha="base",
        run_id="r",
        org_id="orgA",
    )
    rows = read_emissions(store, "r", org_id="orgA")
    audit = [e for e in rows if e.attrs.get("metric") == PROMOTION_AUDIT_KIND]
    assert len(audit) == 1
    assert audit[0].attrs["candidate_sha"] == "cand"
    assert audit[0].attrs["baseline_sha"] == "base"
    assert audit[0].attrs["org_id"] == "orgA"
    assert audit[0].attrs["event"] == "promoted"


def test_audit_trail_is_org_scoped() -> None:
    """The audit ledger is tenant-isolated — org B cannot read org A's events."""
    store = SqliteStore()
    emit_promotion_audit(
        store,
        event="promoted",
        agent="a",
        candidate_sha="c",
        baseline_sha="b",
        run_id="r",
        org_id="orgA",
    )
    assert read_emissions(store, "r", org_id="orgB") == []


# -- the breaker rules (pure, deterministic over the ledger) ---------------
def test_promotion_rate_rule_halts_over_cap() -> None:
    """A runaway auto-promotion rate trips the breaker (HALT)."""
    store = SqliteStore()
    for _ in range(3):
        emit_promotion_audit(
            store, event="promoted", agent="a", candidate_sha="c", baseline_sha="b", run_id="r"
        )
    emissions = read_emissions(store, "r")
    rule = PromotionRateRule(max_count=3, window="", response=Response.HALT)
    firing = rule.evaluate(emissions, now=1.0)
    assert firing is not None and firing.halts


def test_promotion_rate_rule_quiet_under_cap() -> None:
    """Under the cap the breaker does not fire (no false halt)."""
    store = SqliteStore()
    emit_promotion_audit(
        store, event="promoted", agent="a", candidate_sha="c", baseline_sha="b", run_id="r"
    )
    emissions = read_emissions(store, "r")
    assert PromotionRateRule(max_count=3, window="").evaluate(emissions, now=1.0) is None


def test_rollback_rate_rule_halts_on_churn() -> None:
    """Repeated rollbacks (a churning loop) trip the breaker."""
    store = SqliteStore()
    for _ in range(2):
        emit_promotion_audit(
            store, event="rolled_back", agent="a", candidate_sha="c", baseline_sha="b", run_id="r"
        )
    emissions = read_emissions(store, "r")
    rule = RollbackRateRule(max_count=2, window="")
    assert rule.evaluate(emissions, now=1.0) is not None


def test_cost_spike_only_counts_promotions_not_gated() -> None:
    """A gated (non-promoted) audit event does NOT count toward the promotion cap."""
    store = SqliteStore()
    for _ in range(3):
        emit_promotion_audit(
            store, event="gated", agent="a", candidate_sha="c", baseline_sha="b", run_id="r"
        )
    emissions = read_emissions(store, "r")
    assert PromotionRateRule(max_count=1, window="").evaluate(emissions, now=1.0) is None


# -- end-to-end: a tripped breaker blocks promotion ------------------------
@pytest.mark.asyncio
async def test_breaker_halts_further_promotion() -> None:
    """A pre-tripped promotion cap halts the loop → the candidate is NOT promoted."""
    store = SqliteStore()
    ctx = _ctx(store)
    # Seed the ledger past the cap so the breaker fires this cycle.
    for _ in range(2):
        emit_promotion_audit(
            store,
            event="promoted",
            agent="agent",
            candidate_sha="c",
            baseline_sha="b",
            run_id=ctx.run_id,
        )
    breaker = promotion_breaker(max_promotions_per_window=2, window="")
    loop = LearningLoop(
        "agent",
        Tuner(_benchmark(), KnobGridMutator(models=["slow", "mid", "fast"])),
        store,
        breaker=breaker,
    )
    out = await loop.improve(_base("slow"), ctx, MockRuntime(_responder), seed=0)

    assert not out.promoted
    assert out.reason.startswith("halted:")
    # The run was halted (cancel token tripped) — the kill-switch fired.
    assert ctx.cancel_token.cancelled
    # A "halted" audit event was recorded.
    audit = [
        e
        for e in read_emissions(store, ctx.run_id)
        if e.attrs.get("metric") == PROMOTION_AUDIT_KIND and e.attrs.get("event") == "halted"
    ]
    assert len(audit) == 1


@pytest.mark.asyncio
async def test_no_breaker_promotes_normally() -> None:
    """Without a breaker the loop promotes as before (additive, no behavior change)."""
    store = SqliteStore()
    ctx = _ctx(store)
    loop = LearningLoop(
        "agent", Tuner(_benchmark(), KnobGridMutator(models=["slow", "mid", "fast"])), store
    )
    out = await loop.improve(_base("slow"), ctx, MockRuntime(_responder), seed=0)
    assert out.promoted
    # A "promoted" audit event was recorded even without a breaker.
    audit = [
        e
        for e in read_emissions(store, ctx.run_id)
        if e.attrs.get("metric") == PROMOTION_AUDIT_KIND and e.attrs.get("event") == "promoted"
    ]
    assert len(audit) == 1
