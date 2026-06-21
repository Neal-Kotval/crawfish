"""CRA-177 — learning agents: eval-gated self-versioning.

The learning loop is the Tuner (CRA-176) pointed at an agent's own Definition, with the
winner promotion-gated + versioned + reversible. These tests pin the load-bearing
guarantees:

* a loop PROMOTES an improved version (beats the baseline) and the promoted Definition is a
  new content-hashed, frozen Version;
* it REFUSES a worse one (regression-gated) and the active version is unchanged;
* rollback to a prior recorded version works (reversibility);
* the autonomy ceiling (budget / cancel / max_trials) halts the loop → no promotion;
* determinism: same base + seed ⇒ same promotion decision.
"""

from __future__ import annotations

import pytest

from crawfish.batch import Task
from crawfish.core.context import CancelToken, CostBudget, RunContext
from crawfish.core.types import Flow, Parameter
from crawfish.definition.types import AgentSpec, Definition, TeamSpec
from crawfish.learning import LearningLoop, PromotionOutcome
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


def _ctx(tmp_path, *, store=None, limit_usd=None, cancel=False) -> RunContext:
    store = store or SqliteStore(str(tmp_path / "t.db"))
    tok = CancelToken()
    if cancel:
        tok.cancel()
    return RunContext(store=store, cost_budget=CostBudget(limit_usd=limit_usd), cancel_token=tok)


# Score depends only on the agent's `model` knob: fast > mid > slow.
def _responder(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    return str({"slow": 1, "mid": 5, "fast": 9}.get(agent.model or "", 0))


# A best model whose name sorts LAST, so the winner is the final candidate in grid order
# (KnobGridMutator sorts each axis). Used by the ceiling tests so the improvement is
# unreachable until the search has run past a 1-trial ceiling.
def _responder_last(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    return str({"a_slow": 1, "b_mid": 5, "z_fast": 9}.get(agent.model or "", 0))


def _benchmark() -> Benchmark:
    return Benchmark(
        Rubric([OutputNumber(name="score")]), [Task(description="a"), Task(description="b")]
    )


def _loop(store, *, mut, name="agent", **tuner_kw) -> LearningLoop:
    return LearningLoop(name, Tuner(_benchmark(), mut, **tuner_kw), store)


# -- promotes an improved version, recorded as a new frozen content-hashed Version --
@pytest.mark.asyncio
async def test_improve_promotes_better_version(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.db"))
    loop = _loop(store, mut=KnobGridMutator(models=["slow", "mid", "fast"]))
    out = await loop.improve(
        _base("slow"), _ctx(tmp_path, store=store), MockRuntime(_responder), seed=0
    )

    assert isinstance(out, PromotionOutcome)
    assert out.promoted and out.reason == "promoted"
    assert out.active.team.agents[0].model == "fast"
    assert out.candidate_scores["score"] == 9.0
    assert out.base_scores["score"] == 1.0

    # the promoted Definition is a new, frozen, content-hashed Version distinct from the base
    assert out.active.frozen
    assert out.active.version.sha is not None
    assert out.candidate_sha != out.base_sha
    active = loop.active()
    assert active is not None and active.sha == out.candidate_sha and active.role == "promoted"
    # lineage edge points back at the recorded base
    assert active.parent_sha == out.base_sha
    assert {r.role for r in loop.history()} == {"base", "promoted"}


# -- refuses a worse candidate (regression-gated); active version unchanged --
@pytest.mark.asyncio
async def test_improve_refuses_regression(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.db"))
    # base is already the BEST model; every candidate is strictly worse.
    loop = _loop(store, mut=KnobGridMutator(models=["slow", "mid"]))
    out = await loop.improve(
        _base("fast"), _ctx(tmp_path, store=store), MockRuntime(_responder), seed=0
    )

    assert not out.promoted
    assert out.reason == "no_improvement"  # Tuner's own regression gate kept the base as winner
    assert out.active.team.agents[0].model == "fast"  # unchanged
    # only the base is in the lineage and it is the active version
    roles = [r.role for r in loop.history()]
    assert roles == ["base"]
    active = loop.active()
    assert active is not None and active.role == "base"


# -- baseline gate refuses a candidate that regresses vs a *stored* baseline --
@pytest.mark.asyncio
async def test_promotion_gated_against_stored_baseline(tmp_path) -> None:
    from crawfish.eval import save_baseline

    store = SqliteStore(str(tmp_path / "t.db"))
    loop = _loop(store, mut=KnobGridMutator(models=["slow", "mid", "fast"]))
    # Pre-seed a baseline the best reachable candidate (score 9) cannot beat.
    save_baseline(store, "learning:agent", {"score": 99.0})
    out = await loop.improve(
        _base("slow"), _ctx(tmp_path, store=store), MockRuntime(_responder), seed=0
    )

    assert not out.promoted and out.reason == "gated"
    assert loop.active() is None or loop.active().role == "base"
    assert not any(r.role == "promoted" for r in loop.history())


# -- rollback re-activates a prior version (reversibility) --
@pytest.mark.asyncio
async def test_rollback_reverses_a_promotion(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.db"))
    loop = _loop(store, mut=KnobGridMutator(models=["slow", "mid", "fast"]))
    out = await loop.improve(
        _base("slow"), _ctx(tmp_path, store=store), MockRuntime(_responder), seed=0
    )
    assert out.promoted
    base_sha = out.base_sha

    rolled = loop.rollback(base_sha)
    assert rolled.team.agents[0].model == "slow"  # back to the pre-tune Definition
    active = loop.active()
    assert active is not None and active.sha == base_sha and active.role == "base"

    # baseline reset to the rolled-back scores, so a re-improve can promote again
    from crawfish.eval import load_baseline

    assert load_baseline(store, "learning:agent") == {"score": 1.0}

    with pytest.raises(KeyError):
        loop.rollback("nonexistent-sha")


# -- autonomy ceiling halts the loop → no promotion --
@pytest.mark.asyncio
async def test_budget_ceiling_blocks_promotion(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.db"))
    # "z_fast" (the winner) is the LAST candidate; a 1-trial budget never reaches it.
    mut = KnobGridMutator(models=["a_slow", "b_mid", "z_fast"])
    loop = _loop(store, mut=mut, max_trials=64, cost_per_trial_usd=1.0)
    ctx = _ctx(tmp_path, store=store, limit_usd=1.0)
    out = await loop.improve(_base("a_slow"), ctx, MockRuntime(_responder_last), seed=0)

    assert not out.promoted
    assert out.reason == "ceiling:budget"
    assert out.tune.stopped_reason == "budget"
    assert not any(r.role == "promoted" for r in loop.history())


@pytest.mark.asyncio
async def test_cancel_ceiling_blocks_promotion(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.db"))
    loop = _loop(store, mut=KnobGridMutator(models=["slow", "mid", "fast"]))
    ctx = _ctx(tmp_path, store=store, cancel=True)
    out = await loop.improve(_base("slow"), ctx, MockRuntime(_responder), seed=0)

    assert not out.promoted and out.reason == "ceiling:cancelled"
    assert out.tune.stopped_reason == "cancelled"
    # no promotion happened; nothing was activated as a promoted version
    assert not any(r.role == "promoted" for r in loop.history())


@pytest.mark.asyncio
async def test_max_trials_ceiling_blocks_promotion(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "t.db"))
    # winner "z_fast" is the last candidate; max_trials=1 stops before reaching it.
    loop = _loop(store, mut=KnobGridMutator(models=["a_slow", "b_mid", "z_fast"]), max_trials=1)
    out = await loop.improve(
        _base("a_slow"), _ctx(tmp_path, store=store), MockRuntime(_responder_last), seed=0
    )

    assert not out.promoted and out.reason == "ceiling:max_trials"
    assert out.tune.stopped_reason == "max_trials"


# -- determinism: same base + seed ⇒ same promotion decision --
@pytest.mark.asyncio
async def test_same_seed_same_promotion(tmp_path) -> None:
    mut = KnobGridMutator(models=["slow", "mid", "fast"])
    base = _base("slow")  # same base object -> the determinism contract is "same base + seed"

    async def run(db: str) -> PromotionOutcome:
        store = SqliteStore(str(tmp_path / db))
        loop = _loop(store, mut=mut)
        return await loop.improve(
            base, _ctx(tmp_path, store=store), MockRuntime(_responder), seed=7
        )

    a = await run("a.db")
    b = await run("b.db")
    assert a.promoted == b.promoted
    assert a.candidate_sha == b.candidate_sha
    assert a.candidate_scores == b.candidate_scores
    assert [t.version for t in a.tune.trials] == [t.version for t in b.tune.trials]
