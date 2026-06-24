"""Deterministic acceptance test for the Milestone-1 Refine step of the cumulative demo.

Exercises the verifier-gated, bounded, durable ``Refine`` loop added to
``demo/triage-bot/self_improve.py`` — entirely off the mock runtime (NO live model
call) — and asserts the four load-bearing M1 guarantees:

* the loop **ran** (the triage agent drafted a reply, iterating it);
* a **gated** ``Verifier`` (a critic that earned the right to block by clearing an
  absolute-precision bar) **stopped** the loop — ``refine_stopped == "satisfied"``,
  not the bound;
* spend is **metered** into the one shared ``CostBudget`` and bounded by the worst case;
* a **crash-resume re-charges exactly $0** (proven as a dollar delta) and reproduces the
  accepted draft bit-for-bit (content-sha verified).

Plus the CL-1/CL-2 assembly-safety invariant: a ``VerifierStop`` whose critic is the
SAME version as the body is forbidden (the generator may never critique itself).
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

from crawfish.core.context import CostBudget, RunContext
from crawfish.ledger import ExecutionLedger
from crawfish.output import Output, output_content_sha
from crawfish.refine import Refine, VerifierStop
from crawfish.store import SqliteStore

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO = REPO_ROOT / "demo" / "triage-bot" / "self_improve.py"


def _load_scenario():
    spec = importlib.util.spec_from_file_location("crawfish_demo_refine_test", SCENARIO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # so dataclass forward-refs resolve
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    if not SCENARIO.exists():  # pragma: no cover - demo always present in-repo
        pytest.skip(f"demo scenario not found at {SCENARIO}")
    return _load_scenario()


@pytest.fixture(scope="module")
def result(module):
    return module.run_self_improvement(live=False)  # deterministic mock path only


# --- the step ran and the gated verifier stopped it ------------------------------
def test_refine_step_ran(result) -> None:
    """The Refine step executed at least one drafting iteration."""
    assert result.refine_iters > 0
    assert result.refine_final_sha


def test_verifier_gated_the_loop(result) -> None:
    """The loop stopped on a VERIFIER PASS (not the bound), and the critic was gated.

    The mock draft climbs in quality each iteration; the gated verifier rejects the
    early drafts and accepts at ``_ACCEPT_AT_ITER`` — so a healthy run stops
    ``satisfied`` after exactly ``_ACCEPT_AT_ITER + 1`` body calls.
    """
    assert result.refine_stopped == "satisfied"
    assert result.refine_verifier_precision >= 0.9  # cleared the absolute-precision bar


def test_refine_iter_count_matches_accept_point(module, result) -> None:
    """The loop ran exactly until the verifier accepted — bounded, well under max_iters."""
    assert result.refine_iters == module._ACCEPT_AT_ITER + 1
    assert result.refine_iters < 5  # the max_iters bound was never reached


# --- metered spend, bounded by the worst case ------------------------------------
def test_refine_spend_metered_and_bounded(result) -> None:
    """Spend meters into the shared budget and the worst case honestly bounds it.

    On the mock path every call is $0, so the spend is $0 — and $0 is still a valid,
    honest reading of the *shared* budget delta (Gap #3: read from the budget the
    runtime charges, never a hard-coded 0). It must not exceed the worst case.
    """
    assert result.refine_spent_usd >= 0.0
    assert result.refine_spent_usd <= result.worst_case_usd
    # the loop's spend folds into the scenario total, which the worst case bounds (F-6)
    assert result.total_spend_usd <= result.worst_case_usd


# --- the crash-resume re-charges exactly $0 --------------------------------------
def test_refine_resume_is_zero_dollars(result) -> None:
    """A resume over the same ledger replays every committed draft at $0 (CL-4)."""
    assert result.refine_resume_spent_usd == 0.0


def test_scenario_pass_predicate_requires_refine(result) -> None:
    """The whole-scenario PASS predicate now also gates on the Refine step."""
    assert result.passed(), result.summary()


# --- live acceptance: a JUSTIFIED bounded Refine outcome certifies the operator ---
import dataclasses  # noqa: E402


def _live_pass_template(result, *, recorded=True):
    """A fully-passing scenario result, marked ``live`` — every non-Refine criterion met.

    Derived from a real mock run (so all the structural fields — gate, shas, resume deltas,
    tenancy — are internally consistent) then flipped to the live acceptance mode with
    live-realistic cost fields: a positive worst case (mock prices every call at $0, but a
    live run prices haiku at a few cents) that bounds the Refine spend.

    ``recorded=True`` models a **fresh record** (real calls fired → Refine spent > $0);
    ``recorded=False`` models a **$0 replay** (every cassette hit → Refine spent $0, which
    is correct and must still PASS). Individual tests perturb ONLY the Refine outcome.
    """
    return dataclasses.replace(
        result,
        live=True,
        recorded=recorded,
        worst_case_usd=4.32,  # the live haiku worst case (72 calls × $0.05 × 1.2)
        budget_usd=4.32,  # bound to the worst case on the live path
        total_spend_usd=2.50 if recorded else 0.0,  # fresh record spends; replay re-pays $0
        refine_spent_usd=0.10 if recorded else 0.0,  # fresh > $0; replay $0 (correct)
    )


@pytest.mark.parametrize("stopped", ["satisfied", "no_progress", "exhausted"])
def test_live_accepts_any_justified_bounded_refine_stop(module, result, stopped) -> None:
    """On the LIVE path, a justified bounded Refine stop certifies the operator.

    ``satisfied`` (critic accepted), ``no_progress`` (calibrated stall), and ``exhausted``
    (hit ``max_iters``) are all CORRECT bounded outcomes under real-model variance — the
    same precedent as the F-3 gate accepting a justified reject. All three must PASS.
    """
    live = dataclasses.replace(_live_pass_template(result), refine_stopped=stopped)
    assert live.passed(), live.summary()


@pytest.mark.parametrize("bad", ["stuck", ""])
def test_live_rejects_broken_refine_outcomes(module, result, bad) -> None:
    """A broken Refine still FAILS live: ``stuck`` (dead-letter/abstain) or ``""`` (error).

    An error/exception leaves ``refine_stopped`` at its ``""`` default (``execute`` would
    have raised before recording a verdict); ``stuck`` is a dead-letter/abstain, not a
    justified bounded stop. Neither may certify the operator.
    """
    live = dataclasses.replace(_live_pass_template(result), refine_stopped=bad)
    assert not live.passed()


def test_live_rejects_unbounded_or_overspending_refine(module, result) -> None:
    """A Refine that ran past ``max_iters`` or overspent the worst case FAILS live."""
    base = _live_pass_template(result)
    unbounded = dataclasses.replace(base, refine_iters=module.REFINE_MAX_ITERS + 1)
    assert not unbounded.passed()  # iters > max_iters -> not bounded
    overspend = dataclasses.replace(base, refine_spent_usd=base.worst_case_usd + 1.0)
    assert not overspend.passed()  # spent > worst_case -> overspend


def test_fresh_record_requires_metered_refine_spend(module, result) -> None:
    """On a FRESH RECORD (``recorded=True``) a $0 Refine spend FAILS (Gap-#3 guard).

    A real fresh record always hits the model and charges > $0; a $0 reading on a record
    means nothing actually ran, so the operator was not exercised.
    """
    zero = dataclasses.replace(_live_pass_template(result, recorded=True), refine_spent_usd=0.0)
    assert not zero.passed()


@pytest.mark.parametrize("stopped", ["satisfied", "no_progress", "exhausted"])
def test_zero_dollar_replay_passes(module, result, stopped) -> None:
    """A $0 REPLAY (``recorded=False``, ``refine_spent_usd == 0``) MUST PASS.

    A ``--live`` replay re-pays exactly $0 by design (every cassette hits), so the metering
    lower bound is waived on a replay — the replay-PASS guarantee. The justified bounded
    stop (including a ``no_progress``/``exhausted`` draw recorded earlier) still certifies.
    """
    replay = dataclasses.replace(
        _live_pass_template(result, recorded=False), refine_stopped=stopped
    )
    assert replay.refine_spent_usd == 0.0  # a replay re-pays $0
    assert replay.passed(), replay.summary()


def test_mock_still_requires_satisfied(module, result) -> None:
    """The deterministic (mock) path is UNCHANGED — it still requires ``satisfied``.

    A mock run that stopped on ``no_progress`` / ``exhausted`` would mean the rigged critic
    failed to accept — a real regression — so the mock gate must stay strict.
    """
    assert result.live is False
    assert result.refine_stopped == "satisfied"
    for stopped in ("no_progress", "exhausted", "stuck", ""):
        mutated = dataclasses.replace(result, refine_stopped=stopped)
        assert not mutated.passed(), f"mock must reject refine_stopped={stopped!r}"


# --- determinism: the accepted draft sha is bit-identical across runs ------------
def test_refine_deterministic_across_runs(module) -> None:
    a = module.run_self_improvement(live=False)
    b = module.run_self_improvement(live=False)
    assert a.refine_final_sha == b.refine_final_sha
    assert a.refine_iters == b.refine_iters
    assert a.refine_stopped == b.refine_stopped == "satisfied"


# --- CL-2 assembly safety: the generator may not critique itself -----------------
def test_self_critique_is_rejected(module) -> None:
    """A VerifierStop whose critic Definition == the body is forbidden at assembly."""
    store = SqliteStore()
    body = module._build_drafter_body()
    # Gate the SAME definition as the critic, then try to use it to stop its own loop.
    gated = module._gate_reply_verifier(store, body, org_id="acme")
    with pytest.raises(ValueError, match="external"):
        Refine(body, VerifierStop(gated), max_iters=3, edge_id=module.REFINE_EDGE_ID)
    store.close()


# --- a never-accepting critic exhausts the bound (the bound is real) -------------
def test_unsatisfiable_verifier_hits_the_bound(module) -> None:
    """If the verifier never accepts, the loop is still bounded — it exhausts max_iters.

    This proves the bound is load-bearing independently of the verifier: with the
    accept point pushed past ``max_iters`` the loop cannot satisfy and must stop on
    exhaustion (never wall-clock, never unbounded).
    """
    store = SqliteStore()
    ctx = RunContext(store=store, org_id="acme", cost_budget=CostBudget(limit_usd=3.0))
    backend = module._make_backend(live=False, record=False, model=None)

    body = module._build_drafter_body()
    critic = module._build_reply_critic()
    verifier = module._gate_reply_verifier(store, critic, org_id="acme")
    ticket, _ = module._SEED_TICKETS[0]
    seed = Output(
        value={"reply": "", "_draft_iter": -1},
        produced_by="reply-seed",
        lineage=ticket,
        output_schema=[],
    )
    refine = Refine(
        body,
        VerifierStop(verifier),
        max_iters=2,  # bounded BELOW the accept point (_ACCEPT_AT_ITER == 2)
        no_progress_patience=3,  # > max_iters: disabled, so ONLY the bound can stop it
        edge_id=module.REFINE_EDGE_ID,
        name="reply-refine",
    )
    produce = module._make_reply_producer(backend, body, ticket)
    res = asyncio.run(refine.execute(seed, ctx, backend.runtime, produce=produce))
    assert res.refine_stopped == "exhausted"
    assert res.refine_iters == 2  # ran exactly to the bound, no further
    store.close()


# --- CL-4: the ledger checkpoints each frozen iteration (durability) -------------
def test_refine_checkpoints_each_iteration(module) -> None:
    """Every drafting iteration is checkpointed into the org-scoped ledger."""
    store = SqliteStore()
    ctx = RunContext(store=store, org_id="acme", cost_budget=CostBudget(limit_usd=3.0))
    backend = module._make_backend(live=False, record=False, model=None)

    body = module._build_drafter_body()
    verifier = module._gate_reply_verifier(store, module._build_reply_critic(), org_id="acme")
    ticket, _ = module._SEED_TICKETS[0]
    seed = Output(
        value={"reply": "", "_draft_iter": -1},
        produced_by="reply-seed",
        lineage=ticket,
        output_schema=[],
    )
    refine = Refine(
        body,
        VerifierStop(verifier),
        max_iters=5,
        no_progress_patience=5,
        edge_id=module.REFINE_EDGE_ID,
        name="reply-refine",
    )
    ledger = ExecutionLedger(store, org_id="acme")
    res = asyncio.run(
        refine.execute(
            seed,
            ctx,
            backend.runtime,
            ledger=ledger,
            produce=module._make_reply_producer(backend, body, ticket),
        )
    )
    loop_id = refine._loop_id(ticket)
    completed = ledger.completed_visits(loop_id, ticket, module.REFINE_EDGE_ID)
    assert completed == set(range(res.refine_iters))
    # a different org's ledger sees none of it (tenancy)
    other = ExecutionLedger(store, org_id="other-org")
    assert other.completed_visits(loop_id, ticket, module.REFINE_EDGE_ID) == set()
    # the resume of the SAME loop reproduces the accepted draft bit-for-bit
    resumed = asyncio.run(
        refine.execute(
            seed,
            ctx,
            backend.runtime,
            ledger=ledger,
            resume=True,
            produce=module._make_reply_producer(backend, body, ticket),
        )
    )
    assert output_content_sha(resumed.output) == output_content_sha(res.output)
    store.close()
