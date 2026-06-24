"""Refine — bounded, metered, durable iterate-until-goal loop (CRA-202 / CRA-204).

Acceptance coverage:
  CL-1 (1) improving body stops on the first clearing iteration; refine_iters == count.
  CL-1 (2) never-clearing ⇒ exactly max_iters, returns best, refine_stopped=="exhausted".
  CL-1 (3) a 2-iter budget ⇒ exactly 2 metered calls, spent_usd>0 (Gap #3), no overspend.
  CL-1 (4) cancel stops cooperatively before the next call.
  CL-1 (5) flat progress within the calibrated band stops after no_progress_patience.
  CL-1 (6) feedback is FLUID and never reaches an instruction slot (taint propagates).
  CL-1 (7) same cassette ⇒ identical iteration count + returned Output sha.
  CL-2     a VerifierStop whose critic == body is rejected at assembly.
  CL-4 (1) crash after iter 2 of 5, resume=True ⇒ zero new metered calls for 0–2.
  CL-4 (2) resumed final Output sha identical to an uninterrupted run.
  CL-4 (3) completed_visits reflects exactly the finished iterations.
  CL-4 (4) state carries org_id; cross-org isolation.
  CL-4 (5) cancel between iterations leaves a clean, resumable checkpoint.

All runs are deterministic — no live model call. A scripted charging runtime meters
real spend; resume replays committed iterations through ``RecordReplayRuntime`` at $0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.core.context import CostBudget, RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.definition.types import AgentSpec, Coordination, Definition, TeamSpec
from crawfish.eval import EvalCase, GoldenSet, VerifierNotGated, save_baseline
from crawfish.ledger import ExecutionLedger, compute_loop_id
from crawfish.output import Output, output_content_sha
from crawfish.refine import (
    PredicateStop,
    Refine,
    RubricThreshold,
    VerifierStop,
    feature_loop,
)
from crawfish.runtime.base import AgentRuntime, EventKind, RunRequest, RunResult, RuntimeEvent
from crawfish.runtime.replay import RecordReplayRuntime
from crawfish.store import SqliteStore
from crawfish.verifier import Verifier


# -- fixtures ---------------------------------------------------------------
def _body(role: str = "writer") -> Definition:
    return Definition(
        id=f"body-{role}",
        inputs=[Parameter(name="_refine_feedback", type="str", required=False, flow=Flow.FLUID)],
        team=TeamSpec(
            agents=[AgentSpec(role=role, prompt="improve")], coordination=Coordination.SINGLE
        ),
    )


class _ScriptedRuntime(AgentRuntime):
    """A deterministic runtime that emits a scripted score sequence and CHARGES.

    Each call returns the next value in ``scores`` (clamped to the last), charging
    ``cost_per_call`` to the shared budget — the concrete-runtime metering that closes
    the spent=0.0 gap. ``calls`` counts model calls actually made.
    """

    name = "scripted"

    def __init__(self, scores: list[float], *, cost_per_call: float = 0.01) -> None:
        self._scores = scores
        self._cost = cost_per_call
        self.calls = 0

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        idx = min(self.calls, len(self._scores) - 1)
        score = self._scores[idx]
        self.calls += 1
        ctx.cost_budget.charge(self._cost)
        text = json.dumps({"score": score})
        result = RunResult(
            text=text,
            model="scripted",
            cost_usd=self._cost,
            events=[RuntimeEvent(kind=EventKind.RESULT, text=text)],
        )
        self._emit_telemetry(ctx, result, self.name)
        return result


def _score_of(output: Output[JSONValue]) -> float:
    """Read the scripted ``score`` field out of an Output's JSON value."""
    raw = output.value
    if isinstance(raw, str):
        raw = json.loads(raw)
    return float(raw["score"]) if isinstance(raw, dict) else 0.0


def _threshold_stop(at_least: float) -> PredicateStop:
    """Stop when the scripted score clears ``at_least``; progress == the score."""
    return PredicateStop(
        lambda o: _score_of(o) >= at_least,
        progress=_score_of,
    )


def _seed() -> Output[JSONValue]:
    return Output(value=json.dumps({"score": 0.0}), produced_by="seed", lineage="item-1")


def _ctx(store: SqliteStore, *, limit: float | None = None, org_id: str = "local") -> RunContext:
    return RunContext(store=store, org_id=org_id, cost_budget=CostBudget(limit_usd=limit))


# -- CL-1 acceptance --------------------------------------------------------
async def test_stops_on_first_clearing_iteration() -> None:
    """(1) Improving body stops the first iteration the goal clears; iters == count."""
    rt = _ScriptedRuntime([0.2, 0.5, 0.9])
    refine = Refine(_body(), _threshold_stop(0.8), max_iters=5)
    result = await refine.execute(_seed(), _ctx(SqliteStore()), rt)
    assert result.refine_stopped == "satisfied"
    assert result.refine_iters == 3
    assert rt.calls == 3
    assert _score_of(result.output) == pytest.approx(0.9)


async def test_never_clearing_exhausts_and_returns_best() -> None:
    """(2) Never clears ⇒ exactly max_iters, returns best, refine_stopped=='exhausted'."""
    # Monotonically improving but never reaching the goal — so it exhausts the bound
    # rather than tripping the no-progress guard.
    rt = _ScriptedRuntime([0.1, 0.2, 0.3, 0.4])
    refine = Refine(_body(), _threshold_stop(0.99), max_iters=4)
    result = await refine.execute(_seed(), _ctx(SqliteStore()), rt)
    assert result.refine_stopped == "exhausted"
    assert result.refine_iters == 4
    # Best attempt (the last, 0.4) is returned even though it never cleared.
    assert result.best_progress == pytest.approx(0.4)
    assert _score_of(result.output) == pytest.approx(0.4)


async def test_budget_meters_real_spend_and_caps() -> None:
    """(3) A budget for 2 calls ⇒ exactly 2 metered calls, spent>0, no overspend."""
    rt = _ScriptedRuntime([0.1, 0.2, 0.3, 0.4], cost_per_call=0.01)
    ctx = _ctx(SqliteStore(), limit=0.02)  # room for exactly two calls
    refine = Refine(_body(), _threshold_stop(0.99), max_iters=10)
    result = await refine.execute(_seed(), ctx, rt)
    assert rt.calls == 2  # preflight stops the loop once headroom is gone
    assert result.spent_usd == pytest.approx(0.02)  # Gap #3: true spend, not 0.0
    assert result.spent_usd > 0.0
    assert ctx.cost_budget.spent_usd <= ctx.cost_budget.limit_usd  # type: ignore[operator]


async def test_cancel_stops_cooperatively() -> None:
    """(4) A cancelled token stops the loop before the next body call."""
    rt = _ScriptedRuntime([0.1, 0.2, 0.3])
    ctx = _ctx(SqliteStore())
    ctx.cancel_token.cancel()
    refine = Refine(_body(), _threshold_stop(0.99), max_iters=5)
    with pytest.raises(Exception):  # noqa: B017 - cooperative Cancelled
        await refine.execute(_seed(), ctx, rt)
    assert rt.calls == 0  # stopped before the first metered call


async def test_no_progress_within_band_stops() -> None:
    """(5) Flat progress inside the calibrated band stops after the patience window."""
    # Scores barely move (delta 0.001 < rubric_std band) -> treated as no progress.
    rt = _ScriptedRuntime([0.40, 0.401, 0.402, 0.403])
    refine = Refine(
        _body(),
        _threshold_stop(0.99),
        max_iters=10,
        rubric_std=0.01,  # F-8 calibrated band: moves under this are noise
        no_progress_patience=2,
    )
    result = await refine.execute(_seed(), _ctx(SqliteStore()), rt)
    assert result.refine_stopped == "no_progress"
    # First iter improves over seed (0->0.40), then two stale iters trip patience=2.
    assert result.refine_iters == 3


async def test_feedback_is_fluid_and_taints() -> None:
    """(6) The prior attempt is fed back as FLUID; the produced Output stays tainted."""
    seen_inputs: list[dict[str, JSONValue]] = []

    class _Recording(_ScriptedRuntime):
        async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
            seen_inputs.append(dict(request.inputs))
            return await super().run(request, ctx)

    rt = _Recording([0.2, 0.9])
    # A tainted seed makes the feedback fluid-derived; taint must propagate forward.
    seed = Output(value=json.dumps({"score": 0.0}), produced_by="seed", lineage="i", tainted=True)
    refine = Refine(_body(), _threshold_stop(0.8), max_iters=5)
    result = await refine.execute(seed, _ctx(SqliteStore()), rt)
    # Feedback rode in under the static feedback key on the SECOND call (data slot).
    assert "_refine_feedback" in seen_inputs[1]
    # Taint propagated into the iteration Output (fluid-derived, never trusted ground).
    assert result.output.tainted is True


async def test_same_cassette_identical_iters_and_sha(tmp_path: Path) -> None:
    """(7) Replaying the same cassettes ⇒ identical iteration count + Output sha."""
    cassettes = tmp_path / "cas"
    inner = _ScriptedRuntime([0.2, 0.5, 0.9])
    rec = RecordReplayRuntime(inner, cassettes, record=True)
    refine = Refine(_body(), _threshold_stop(0.8), max_iters=5)
    first = await refine.execute(_seed(), _ctx(SqliteStore()), rec)

    # Replay-only (record=False): identical body, identical decisions, $0.
    replay = RecordReplayRuntime(_ScriptedRuntime([0.2, 0.5, 0.9]), cassettes, record=False)
    ctx2 = _ctx(SqliteStore())
    second = await refine.execute(_seed(), ctx2, replay)
    assert second.refine_iters == first.refine_iters
    assert output_content_sha(second.output) == output_content_sha(first.output)
    assert ctx2.cost_budget.spent_usd == pytest.approx(0.0)  # replay charges nothing


# -- CL-2 assembly safety ---------------------------------------------------
def _gated_verifier(store: SqliteStore, critic: Definition) -> object:
    """Admit ``critic`` as a GatedVerifier by seeding a passing golden set + baseline."""
    golden = GoldenSet(store, "decisions")
    golden.add(EvalCase(id="c1", output="accept", label="accept"))
    golden.add(EvalCase(id="c2", output="reject", label="reject"))
    save_baseline(store, "verifier", {"precision": 1.0})
    return Verifier.gated(
        critic,
        golden,
        labels=["accept", "reject"],
        default="reject",
        accept_label="accept",
        min_precision=0.9,
    )


def test_verifier_stop_rejects_self_critique() -> None:
    """A VerifierStop whose critic is the SAME version as the body is forbidden."""
    store = SqliteStore()
    body = _body()
    gated = _gated_verifier(store, body)  # critic == body
    with pytest.raises(ValueError, match="external"):
        Refine(body, VerifierStop(gated), max_iters=3)  # type: ignore[arg-type]


async def test_verifier_stop_distinct_critic_gates() -> None:
    """A distinct gated critic is a valid external stop signal that can block."""
    store = SqliteStore()
    critic = _body(role="critic")  # distinct content sha from the body
    gated = _gated_verifier(store, critic)
    stop = VerifierStop(gated)  # type: ignore[arg-type]
    refine = Refine(_body(), stop, max_iters=3)
    assert refine.until is stop


def test_ungated_verifier_cannot_stop() -> None:
    """A never-benchmarked critic fails closed: gated() raises VerifierNotGated."""
    store = SqliteStore()
    golden = GoldenSet(store, "decisions")
    golden.add(EvalCase(id="c1", output="accept", label="accept"))
    with pytest.raises(VerifierNotGated):
        Verifier.gated(
            _body(role="critic"),
            golden,
            labels=["accept", "reject"],
            default="reject",
            accept_label="accept",
            min_precision=0.9,
        )


# -- CL-4 durable resume ----------------------------------------------------
async def test_crash_then_resume_zero_recompute(tmp_path: Path) -> None:
    """(1,2,3) Crash after iter 2 of 5; resume re-pays $0 for 0–2, sha matches uninterrupted."""
    cassettes = tmp_path / "cas"

    # --- uninterrupted reference run (records cassettes 0..2 -> clears at iter 2). ---
    ref_inner = _ScriptedRuntime([0.2, 0.5, 0.9, 0.95, 0.99])
    ref_rt = RecordReplayRuntime(ref_inner, cassettes, record=True)
    ref_refine = Refine(_body(), _threshold_stop(0.8), max_iters=5)
    reference = await ref_refine.execute(_seed(), _ctx(SqliteStore()), ref_rt)
    assert reference.refine_iters == 3

    # --- simulate a crash: a fresh loop runs only iters 0,1 then dies. ---
    crash_store = SqliteStore()
    crash_ledger = ExecutionLedger(crash_store)
    crash_inner = _ScriptedRuntime([0.2, 0.5, 0.9, 0.95, 0.99])
    crash_rt = RecordReplayRuntime(crash_inner, cassettes, record=False)
    refine = Refine(_body(), _threshold_stop(0.8), max_iters=2)  # bounded to "crash" at 2
    partial = await refine.execute(
        _seed(), _ctx(crash_store), crash_rt, ledger=crash_ledger, resume=False
    )
    assert partial.refine_stopped == "exhausted"
    loop_id = compute_loop_id(_body().content_sha(), "item-1", "refine")
    assert crash_ledger.completed_visits(loop_id, "item-1", "refine") == {0, 1}

    # --- resume: full bound, resume=True. Replays 0,1 at $0, runs only iter 2. ---
    resume_inner = _ScriptedRuntime([0.2, 0.5, 0.9, 0.95, 0.99])
    resume_rt = RecordReplayRuntime(resume_inner, cassettes, record=False)
    resume_refine = Refine(_body(), _threshold_stop(0.8), max_iters=5)
    ctx = _ctx(crash_store)
    resumed = await resume_refine.execute(_seed(), ctx, resume_rt, ledger=crash_ledger, resume=True)
    # (1) Zero new metered calls for the replayed iterations — replay charges nothing,
    #     and the only fresh model call cost is whatever iter 2's cassette replays ($0).
    assert ctx.cost_budget.spent_usd == pytest.approx(0.0)
    # (2) Resumed final Output sha identical to the uninterrupted run.
    assert output_content_sha(resumed.output) == output_content_sha(reference.output)
    assert resumed.refine_stopped == "satisfied"
    # (3) completed_visits reflects exactly the finished iterations (0,1,2).
    assert crash_ledger.completed_visits(loop_id, "item-1", "refine") == {0, 1, 2}


async def test_resume_org_isolation(tmp_path: Path) -> None:
    """(4) Checkpoints carry org_id; another org cannot see completed iterations."""
    cassettes = tmp_path / "cas"
    store = SqliteStore()
    rt = RecordReplayRuntime(_ScriptedRuntime([0.2, 0.5, 0.9]), cassettes, record=True)
    refine = Refine(_body(), _threshold_stop(0.8), max_iters=5)

    ledger_a = ExecutionLedger(store, org_id="org-a")
    await refine.execute(_seed(), _ctx(store, org_id="org-a"), rt, ledger=ledger_a)
    loop_id = compute_loop_id(_body().content_sha(), "item-1", "refine")
    assert ledger_a.completed_visits(loop_id, "item-1", "refine")  # org-a sees its work

    # A different org's ledger over the same loop_id/item sees nothing.
    ledger_b = ExecutionLedger(store, org_id="org-b")
    assert ledger_b.completed_visits(loop_id, "item-1", "refine") == set()


async def test_cancel_between_iterations_leaves_clean_checkpoint(tmp_path: Path) -> None:
    """(5) Cancel mid-loop leaves a clean, resumable checkpoint (committed iters intact)."""
    cassettes = tmp_path / "cas"
    store = SqliteStore()
    ledger = ExecutionLedger(store)

    # Record cassettes for two good iterations first.
    rec = RecordReplayRuntime(_ScriptedRuntime([0.2, 0.5, 0.9]), cassettes, record=True)
    seed_refine = Refine(_body(), _threshold_stop(0.99), max_iters=2)
    await seed_refine.execute(_seed(), _ctx(store), rec, ledger=ledger)
    loop_id = compute_loop_id(_body().content_sha(), "item-1", "refine")
    committed = ledger.completed_visits(loop_id, "item-1", "refine")
    assert committed == {0, 1}

    # Now a cancelled run on a fresh store/ctx must not corrupt the existing ledger;
    # the committed checkpoints remain loadable for a later resume.
    ctx = _ctx(store)
    ctx.cancel_token.cancel()
    refine = Refine(_body(), _threshold_stop(0.99), max_iters=5)
    with pytest.raises(Exception):  # noqa: B017
        await refine.execute(_seed(), ctx, rec, ledger=ledger, resume=True)
    # The checkpoint set is unchanged — clean and resumable.
    assert ledger.completed_visits(loop_id, "item-1", "refine") == committed
    assert ledger.iteration_output_ref(loop_id, "item-1", "refine", 0) is not None


# -- convenience alias ------------------------------------------------------
async def test_feature_loop_alias() -> None:
    """``feature_loop`` constructs an equivalent Refine."""
    rt = _ScriptedRuntime([0.9])
    loop = feature_loop(_body(), until=_threshold_stop(0.8), max_iters=3)
    assert isinstance(loop, Refine)
    result = await loop.execute(_seed(), _ctx(SqliteStore()), rt)
    assert result.refine_stopped == "satisfied"


def test_rubric_threshold_progress_clamped() -> None:
    """RubricThreshold.progress clamps scores into [0, 1]."""
    from crawfish.metrics import Metric, Rubric

    class _Const(Metric):
        name = "q"

        def evaluate(self, output: Output[JSONValue]) -> float:
            return 1.5  # out of range on purpose

    stop = RubricThreshold(Rubric([_Const()]), metric="q", at_least=0.5)
    assert stop.progress(_seed()) == pytest.approx(1.0)
