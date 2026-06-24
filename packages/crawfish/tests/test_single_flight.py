"""CRA-221 (OPT-3) acceptance — live single-flight / request coalescing.

The persistent ``CachingRuntime`` only hits a cassette that already exists on disk, so two
identical items in one ``Batch`` both miss and both spend. Single-flight closes that
window: an in-process per-key ``asyncio.Future`` map means N concurrent identical callers
collapse onto **one** ``inner.run`` — one ``CostBudget.charge`` — while the rest await the
same in-flight result and charge $0.

Fully deterministic: the only "model" is a :class:`GatingRuntime` that charges a fixed
cost and blocks on an ``asyncio.Event`` so the test choreographs the overlap precisely. No
live call, no egress, no wall-clock sleeps for ordering (the gate is explicit).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from crawfish.cache import CachingRuntime, cache_key
from crawfish.core.context import Cancelled, RunContext
from crawfish.definition.types import AgentSpec, Definition, TeamSpec
from crawfish.runtime import RecordReplayRuntime, RunRequest
from crawfish.runtime.base import AgentRuntime, EventKind, RunResult, RuntimeEvent
from crawfish.store import SqliteStore


class GatingRuntime(AgentRuntime):
    """A controllable inner runtime: counts calls, charges a fixed cost, blocks on a gate.

    Mirrors ``ProviderRuntime`` in the one way that matters here — it charges
    ``ctx.cost_budget`` exactly once per :meth:`run` — so "exactly one inner.run ⇒ exactly
    one charge" is observable on the budget. ``gate`` (when set) holds each call open until
    the test releases it, letting concurrent callers provably overlap. ``fail`` makes the
    call raise after the gate, to exercise the error-propagation path.
    """

    name = "gating"

    def __init__(self, *, cost_usd: float = 0.05, fail: bool = False) -> None:
        self.calls = 0
        self._cost_usd = cost_usd
        self._fail = fail
        self.gate: asyncio.Event | None = None
        self.entered = asyncio.Event()  # set once a call is inside run(), past the count

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        ctx.cancel_token.raise_if_cancelled()
        self.calls += 1
        self.entered.set()
        if self.gate is not None:
            await self.gate.wait()
        if self._fail:
            raise RuntimeError("gating runtime configured to fail")
        text = str(request.inputs)
        ctx.cost_budget.charge(self._cost_usd)
        return RunResult(
            text=text,
            session_id=f"gating-{ctx.run_id}",
            cost_usd=self._cost_usd,
            model="m1",
            events=[RuntimeEvent(kind=EventKind.RESULT, text=text, cost_usd=self._cost_usd)],
        )


def _definition() -> Definition:
    return Definition(team=TeamSpec(agents=[AgentSpec(role="scout", prompt="scan")]))


def _request(d: Definition, body: str) -> RunRequest:
    return RunRequest(definition=d, role="scout", inputs={"pr_body": body})


def _ctx(org_id: str = "local") -> RunContext:
    return RunContext(store=SqliteStore(), org_id=org_id)


def _caching(tmp_path: Path, inner: GatingRuntime) -> CachingRuntime:
    replay = RecordReplayRuntime(inner, tmp_path / "cassettes", record=True)
    return CachingRuntime(replay)


async def test_two_concurrent_identical_calls_collapse_to_one(tmp_path: Path) -> None:
    """The headline AC: two concurrent identical calls ⇒ one inner.run, one charge."""
    inner = GatingRuntime(cost_usd=0.05)
    inner.gate = asyncio.Event()  # hold the leader open so the second caller joins in-flight
    rt = _caching(tmp_path, inner)
    d = _definition()

    ctx_a, ctx_b = _ctx(), _ctx()
    # Start the leader; wait until it is provably inside inner.run (past the call count).
    task_a = asyncio.create_task(rt.run(_request(d, "same"), ctx_a))
    await inner.entered.wait()
    # Now start the second identical caller — it must coalesce onto the in-flight leader.
    task_b = asyncio.create_task(rt.run(_request(d, "same"), ctx_b))
    # Let both proceed and complete.
    await asyncio.sleep(0)  # give task_b a turn to register as a waiter
    inner.gate.set()
    res_a, res_b = await asyncio.gather(task_a, task_b)

    # Exactly ONE computation served BOTH callers.
    assert inner.calls == 1
    assert rt.stats.misses == 1
    assert rt.stats.coalesced == 1
    assert rt.stats.hits == 0
    # The leader charged its budget; the coalesced waiter charged $0.
    assert ctx_a.cost_budget.spent_usd == pytest.approx(0.05)
    assert ctx_b.cost_budget.spent_usd == pytest.approx(0.0)
    # Budget charged exactly once for the pair; the avoided second spend is tallied.
    assert rt.stats.spent_usd == pytest.approx(0.05)
    assert rt.stats.saved_usd == pytest.approx(0.05)
    # Both callers see the identical (bit-for-bit) result.
    assert res_a.text == res_b.text
    assert res_a.cost_usd == res_b.cost_usd == pytest.approx(0.05)


async def test_replay_is_bit_for_bit_whether_coalesced_or_not(tmp_path: Path) -> None:
    """Coalescing is a strict refinement: the result is identical to a non-coalesced run."""
    # Coalesced pair.
    inner1 = GatingRuntime(cost_usd=0.05)
    inner1.gate = asyncio.Event()
    rt1 = _caching(tmp_path / "a", inner1)
    d = _definition()
    t = asyncio.create_task(rt1.run(_request(d, "x"), _ctx()))
    await inner1.entered.wait()
    t2 = asyncio.create_task(rt1.run(_request(d, "x"), _ctx()))
    await asyncio.sleep(0)
    inner1.gate.set()
    coalesced_a, coalesced_b = await asyncio.gather(t, t2)

    # Serial, no coalescing.
    inner2 = GatingRuntime(cost_usd=0.05)
    rt2 = _caching(tmp_path / "b", inner2)
    serial = await rt2.run(_request(d, "x"), _ctx())

    assert coalesced_a.text == coalesced_b.text == serial.text
    assert coalesced_a.model == serial.model


async def test_inflight_exception_propagates_to_all_and_clears_key(tmp_path: Path) -> None:
    """An in-flight error reaches every awaiter; the key clears so a retry recomputes."""
    inner = GatingRuntime(cost_usd=0.05, fail=True)
    inner.gate = asyncio.Event()
    rt = _caching(tmp_path, inner)
    d = _definition()

    task_a = asyncio.create_task(rt.run(_request(d, "boom"), _ctx()))
    await inner.entered.wait()
    task_b = asyncio.create_task(rt.run(_request(d, "boom"), _ctx()))
    await asyncio.sleep(0)
    inner.gate.set()

    results = await asyncio.gather(task_a, task_b, return_exceptions=True)
    # Both awaiters see the SAME error instance (one computation, one exception).
    assert all(isinstance(r, RuntimeError) for r in results)
    assert results[0] is results[1]
    assert inner.calls == 1
    # No poisoned future: the key is cleared, so a fresh retry recomputes (and fails anew).
    with pytest.raises(RuntimeError):
        # Release immediately for the retry — gate is already set.
        await rt.run(_request(d, "boom"), _ctx())
    assert inner.calls == 2


async def test_cancel_raises_before_coalescing(tmp_path: Path) -> None:
    """A cancelled caller never joins or starts an in-flight computation."""
    inner = GatingRuntime(cost_usd=0.05)
    rt = _caching(tmp_path, inner)
    d = _definition()
    ctx = _ctx()
    ctx.cancel_token.cancel()
    with pytest.raises(Cancelled):
        await rt.run(_request(d, "x"), ctx)
    assert inner.calls == 0
    assert rt.stats.coalesced == 0 and rt.stats.misses == 0


async def test_cross_org_identical_inputs_never_coalesce(tmp_path: Path) -> None:
    """CRA-221 gap S2: two orgs, identical inputs ⇒ two inner.run, no shared result."""
    inner = GatingRuntime(cost_usd=0.05)
    inner.gate = asyncio.Event()
    rt = _caching(tmp_path, inner)
    d = _definition()

    ctx_a = _ctx(org_id="org-a")
    ctx_b = _ctx(org_id="org-b")
    # Identical (definition, inputs) but DIFFERENT org_id — must NOT coalesce.
    task_a = asyncio.create_task(rt.run(_request(d, "same"), ctx_a))
    await inner.entered.wait()
    inner.entered.clear()
    task_b = asyncio.create_task(rt.run(_request(d, "same"), ctx_b))
    # org-b is a distinct key, so it must enter inner.run on its own (not await org-a).
    await inner.entered.wait()
    inner.gate.set()
    await asyncio.gather(task_a, task_b)

    assert inner.calls == 2
    assert rt.stats.misses == 2
    assert rt.stats.coalesced == 0
    # Both tenants paid their own way — no cross-org free ride.
    assert ctx_a.cost_budget.spent_usd == pytest.approx(0.05)
    assert ctx_b.cost_budget.spent_usd == pytest.approx(0.05)


def test_cross_org_keys_differ_at_the_cache_key() -> None:
    """The coalescing key embeds org_id, so identical inputs under two orgs differ.

    ``cache_key`` is the legacy (local) key; the coalescing key adds ``org_id`` via the
    replay layer. This asserts the org coordinate genuinely changes the key.
    """
    from crawfish.runtime.replay import _key

    d = _definition()
    req = _request(d, "same")
    assert _key(req, org_id="org-a") != _key(req, org_id="org-b")
    # And the local key is the legacy cache_key (back-compat).
    assert _key(req, org_id="local") == cache_key(req)


async def test_sequential_identical_calls_hit_cassette_not_coalesce(tmp_path: Path) -> None:
    """When calls do not overlap, the second hits the on-disk cassette (CRA-182 path)."""
    inner = GatingRuntime(cost_usd=0.05)  # no gate: each call completes immediately
    rt = _caching(tmp_path, inner)
    d = _definition()

    await rt.run(_request(d, "same"), _ctx())  # miss, records cassette
    await rt.run(_request(d, "same"), _ctx())  # cassette now exists -> hit, not coalesced
    assert inner.calls == 1
    assert rt.stats.misses == 1
    assert rt.stats.hits == 1
    assert rt.stats.coalesced == 0
    assert rt.stats.saved_usd == pytest.approx(0.05)
