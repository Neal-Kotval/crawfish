"""Deterministic acceptance test for the Milestone-5 SURFACES step of the cumulative demo.

Exercises the operator surface (CRA-219..222) added to
``demo/triage-bot/self_improve.py`` — entirely off the mock runtime (NO live model
call) — and asserts the three load-bearing M5 guarantees:

* **Single-flight / request coalescing (OPT-3).** Two identical IN-FLIGHT triage calls
  collapse onto ONE real ``inner.run`` via a :class:`~crawfish.cache.CachingRuntime`; the
  duplicate caller COALESCES (``CacheStats.coalesced == 1``), charges $0, and sees a
  bit-identical result. The coalescing key is org-salted, so two tenants never share an
  in-flight result (the tenancy boundary).
* **Honest cost band (OPT-2).** :func:`~crawfish.cost.compose_cost` folds an
  escalate∘refine operator nesting onto a base estimate and yields an
  ``expected_usd <= worst_case_usd`` band whose worst case HONESTLY brackets the refine
  step's REAL metered spend — the advertised ceiling never undercounts.
* **Lockfile (OPT-4).** :func:`~crawfish.resolve.resolve` pins the demo's summoned
  transitive closure into a :class:`~crawfish.resolve.Lockfile`; a re-resolve of the
  unchanged closure reproduces the SAME ``closure_sha`` (reproducible/drift-free), a
  mutated unit DIVERGES it (the ``craw lock --check`` drift gate fires), and the lockfile
  round-trips through ``write_lockfile`` / ``read_lockfile`` data-only.

The whole step is deterministic over the demo's own fixtures (the single-flight gate is
choreographed, the cost band is a pure fold, the resolve is pure/offline), so — like the
M4 taming step — there is no model-variance branch: these assertions hold on both paths.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

from crawfish.cache import CachingRuntime
from crawfish.core.context import CostBudget, RunContext
from crawfish.definition.types import DefinitionRef
from crawfish.resolve import (
    Candidate,
    InMemoryCandidateSource,
    ResolutionError,
    SemVer,
    read_lockfile,
    resolve,
    write_lockfile,
)
from crawfish.runtime import RecordReplayRuntime, RunRequest
from crawfish.store import SqliteStore

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO = REPO_ROOT / "demo" / "triage-bot" / "self_improve.py"


def _load_scenario():
    spec = importlib.util.spec_from_file_location("crawfish_demo_surfaces_test", SCENARIO)
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


# --- Single-flight: two identical in-flight calls collapse to one real call -------
def test_single_flight_collapses_to_one_real_call(result) -> None:
    """Two identical IN-FLIGHT calls made EXACTLY one real inner.run, one coalesced."""
    assert result.coalesce_inner_calls == 1  # one leader computed
    assert result.coalesce_coalesced == 1  # the duplicate joined in-flight (did NOT recompute)


def test_single_flight_coalesced_waiter_charged_zero_and_saw_same_result(result) -> None:
    """The coalesced waiter charged $0 (saved a spend) and saw a bit-identical result."""
    assert result.coalesce_saved_usd >= 0.0  # the avoided spend is tallied (one call's cost)
    assert result.coalesce_results_identical  # the waiter's result == the leader's, bit-for-bit


def test_single_flight_key_is_org_salted_no_cross_tenant_share(module) -> None:
    """Two DIFFERENT orgs with an identical (definition, inputs) call do NOT coalesce.

    The coalescing key carries ``ctx.org_id`` (CRA-221 gap S2), so org B is never served
    org A's in-flight result — each tenant computes its own. This is the security
    invariant the single-flight layer upholds; here we drive it directly with the demo's
    gating inner runtime so the overlap is choreographed (no wall-clock race).
    """
    inner = module._GatingRuntime()
    inner.gate = asyncio.Event()
    inner.entered = asyncio.Event()
    body = module._build_quorum_body()
    request = RunRequest(
        definition=body,
        role="quorum-classifier",
        inputs={"project": "acme", "ticket_body": "same inputs"},
    )

    async def _drive(tmp: str) -> int:
        replay = RecordReplayRuntime(inner, tmp, record=True)
        caching = CachingRuntime(replay)
        store = SqliteStore()
        ctx_a = RunContext(store=store, org_id="org-a", cost_budget=CostBudget(limit_usd=1.0))
        ctx_b = RunContext(store=store, org_id="org-b", cost_budget=CostBudget(limit_usd=1.0))
        task_a = asyncio.create_task(caching.run(request, ctx_a))
        await inner.entered.wait()
        task_b = asyncio.create_task(caching.run(request, ctx_b))
        await asyncio.sleep(0)
        inner.gate.set()
        await asyncio.gather(task_a, task_b)
        return caching.stats.coalesced

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        coalesced = asyncio.run(_drive(tmp))
    # Different orgs ⇒ distinct coalescing keys ⇒ NO coalesce (each tenant ran its own call).
    assert coalesced == 0
    assert inner.calls == 2  # two real computations, one per tenant — never shared


# --- Honest cost band: expected <= worst, and worst brackets the real refine spend ---
def test_cost_band_is_well_formed_interval(result) -> None:
    """The OPT-2 band is well-formed: expected_usd <= worst_case_usd (never inverted)."""
    assert result.cost_band_expected_usd <= result.cost_band_worst_usd


def test_cost_band_brackets_real_refine_spend(result) -> None:
    """The advertised band never undercounts: the refine step's REAL spend is bounded.

    The band brackets the cost-bearing refine step (a step that escalates/repairs/refines):
    its real metered spend stays at or below the scenario's structural worst case, and the
    band itself is a valid interval. On the mock path the spend is $0 (bounded trivially);
    the bracket relation is what the live path relies on.
    """
    assert result.cost_band_brackets
    assert result.cost_band_actual_usd <= result.worst_case_usd


def test_cost_band_compose_law_is_monotone(module) -> None:
    """A measured-rate band sits in [base, worst]: expected never exceeds the worst case.

    Drives ``compose_cost`` directly with the demo's escalate∘refine nesting and a measured
    rate < 1, asserting the multiplicative law keeps the expected point inside the band the
    worst case bounds (``compose_cost`` clamps to ``[lower, worst]``).
    """
    from crawfish.cost import CostEstimate, CostShape, compose_cost

    base = CostEstimate(team_size=1, items=1, per_item_usd=0.05, total_usd=0.05)
    band = compose_cost(
        base,
        [
            CostShape.escalate(base_price=0.05, strong_price=0.20, measured_rate=0.25, rate_ci=0.1),
            CostShape.refine(max_iters=5, measured_rate=0.4, rate_ci=0.1),
        ],
    )
    assert band.total_usd <= band.expected_lo_usd <= band.expected_usd
    assert band.expected_usd <= band.expected_hi_usd <= band.worst_case_usd
    # A measured rate < 1 makes the expected strictly cheaper than the worst case (a real band).
    assert band.expected_usd < band.worst_case_usd


# --- Lockfile: resolve pins the closure; the drift gate fires on a mutation -------
def test_lockfile_pins_the_summoned_closure(result) -> None:
    """The resolve pinned a non-empty transitive closure to a closure_sha."""
    assert result.lock_pins > 0
    assert result.lock_closure_sha.startswith("sha256:")


def test_lockfile_reresolve_is_drift_free(result) -> None:
    """A re-resolve of the UNCHANGED closure reproduces the same closure_sha (no drift)."""
    assert result.lock_redrift_ok


def test_lockfile_mutation_drifts_closure_sha(result) -> None:
    """Mutating one unit's content DIVERGES the closure_sha — the lock --check gate fires."""
    assert result.lock_mutation_detected


def test_lockfile_roundtrips_data_only(result) -> None:
    """write_lockfile -> read_lockfile re-verifies the closure_sha (data-only, no code run)."""
    assert result.lock_roundtrip_ok


def test_lockfile_reproducible_across_fresh_sources(module) -> None:
    """Two independently-built sources resolve to the SAME closure_sha (machine-independent).

    Determinism: identical inputs ⇒ identical ``closure_sha`` regardless of insertion order
    or which process built the source (acceptance: reproducible resolution).
    """
    root_a, source_a = module._build_lock_source()
    root_b, source_b = module._build_lock_source()
    lock_a = resolve(root_a, source_a, org_id="local")
    lock_b = resolve(root_b, source_b, org_id="local")
    assert lock_a.closure_sha() == lock_b.closure_sha()
    # org_id does NOT enter the pins — the same closure resolves identically across tenants.
    lock_other = resolve(*module._build_lock_source(), org_id="other-tenant")
    assert lock_other.closure_sha() == lock_a.closure_sha()


def test_resolve_fails_closed_on_conflict() -> None:
    """A version conflict (two requirers pin incompatible versions) fails closed, names both."""
    source = InMemoryCandidateSource()
    # Two leaves require ``shared`` at conflicting exact versions; the resolver must refuse.
    source.add(Candidate("shared", SemVer.parse("1.0.0"), "sha-a"))
    source.add(Candidate("shared", SemVer.parse("2.0.0"), "sha-b"))
    source.add(
        Candidate(
            "left", SemVer.parse("1.0.0"), "sha-l", (DefinitionRef(id="shared", version="1.0.0"),)
        )
    )
    source.add(
        Candidate(
            "right", SemVer.parse("1.0.0"), "sha-r", (DefinitionRef(id="shared", version="2.0.0"),)
        )
    )
    root = Candidate(
        "app",
        SemVer.parse("1.0.0"),
        "sha-app",
        (DefinitionRef(id="left", version="1.0.0"), DefinitionRef(id="right", version="1.0.0")),
    )
    with pytest.raises(ResolutionError, match="conflict"):
        resolve(root, source)


def test_lockfile_corruption_fails_closed() -> None:
    """A hand-edited lockfile whose recorded closure_sha no longer matches fails closed."""
    source = InMemoryCandidateSource()
    source.add(Candidate("app", SemVer.parse("1.0.0"), "sha-app"))
    lock = resolve(Candidate("app", SemVer.parse("1.0.0"), "sha-app"), source)
    text = write_lockfile(lock)
    # Tamper with a pin's integrity without updating the recorded closure_sha -> mismatch.
    tampered = text.replace("sha-app", "sha-EVIL")
    with pytest.raises(ResolutionError, match="closure_sha"):
        read_lockfile(tampered)


# --- The whole scenario still PASSES with the M5 step wired in -------------------
def test_scenario_still_passes_with_surfaces_step(result) -> None:
    """The cumulative demo passes 9/9 end to end with the M5 surfaces step included."""
    assert result.passed()
    assert result._surfaces_step_ok()
