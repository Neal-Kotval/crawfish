"""Cost-aware replay caching — CRA-182's second lever, plus CRA-221 single-flight.

:class:`~crawfish.runtime.replay.RecordReplayRuntime` already replays a recorded
``RunResult`` for free on a cache hit (no model call, no budget charge). CRA-182 makes
that *explicit and cost-aware*: a thin :class:`CachingRuntime` wrapper that reports, per
request, whether the call **hit** the cassette (and therefore avoided a spend) or
**missed** it — and totals the dollars the cache saved.

CRA-221 (OPT-3) adds the *in-flight* layer in front of that persistent cache:
**single-flight / request coalescing**. The persistent cache only hits a cassette that
already exists on disk; two identical items in one ``Batch`` therefore both miss and both
spend. Single-flight closes that window — an in-process per-key :class:`asyncio.Future`
map so that when N concurrent callers issue the SAME request, only the FIRST computes the
(real, metered) ``inner.run`` and the rest AWAIT the same in-flight result. Exactly **one**
``inner.run`` per key ⇒ exactly **one** ``CostBudget.charge``; the coalesced waiters
charge $0. This is a strict refinement of the deterministic cassette key, so it can only
change *how many times* a leaf runs, never *what* it returns — replay is bit-for-bit
whether a call was coalesced or not.

The cache key is the same definition-version + inputs hash the replay layer uses
(:func:`crawfish.runtime.replay._key`), surfaced here as :func:`cache_key` so callers can
reason about hit/miss without reaching into the runtime. Identical (definition-version +
inputs) calls collapse onto one cassette: the first records and spends, the rest hit and
cost $0.

**Tenancy (CRA-221 gap S2).** The *coalescing* key includes the run's ``org_id`` (it is
the inner replay runtime's own org-salted cassette key), so two tenants issuing an
identical ``(definition, inputs)`` call in one process get **two** ``inner.run`` calls and
never share a result — org A's computation is never served to org B.

Fully deterministic: the wrapper performs no model call itself; the inner replay runtime
does, only on a miss, and tests drive it with a mock inner runtime so nothing live runs.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.runtime.base import AgentRuntime, RunRequest, RunResult
from crawfish.runtime.replay import RecordReplayRuntime, _key

__all__ = ["cache_key", "CacheStats", "CachingRuntime"]


def cache_key(request: RunRequest) -> str:
    """The cassette key for ``request`` — its definition-version + inputs hash.

    Re-exports the replay layer's :func:`crawfish.runtime.replay._key` so a caller can
    compute hit/miss (two requests share a key iff they would share a cassette) without
    depending on the private name. Pure: definition id + version, role, model, inputs,
    and session id, hashed deterministically.
    """
    return _key(request)


@dataclass
class CacheStats:
    """Running hit/miss + saved-spend accounting for a :class:`CachingRuntime`.

    ``hits``/``misses`` count requests served from / not from the cassette;
    ``coalesced`` counts requests that awaited an in-flight peer (single-flight) instead
    of issuing their own ``inner.run`` — a sub-class of "saved a spend" that is distinct
    from a persistent-cassette ``hit``. ``saved_usd`` totals the spend each hit *or*
    coalesced waiter avoided (the recorded result's ``cost_usd``, which it would otherwise
    have charged). ``spent_usd`` totals what misses actually charged.
    """

    hits: int = 0
    misses: int = 0
    coalesced: int = 0
    saved_usd: float = 0.0
    spent_usd: float = 0.0
    _seen_keys: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        return self.hits + self.misses + self.coalesced

    @property
    def hit_rate(self) -> float:
        """Fraction of requests served without a fresh spend (cassette hit OR coalesced).

        0.0 when nothing ran yet. Both a persistent-cassette ``hit`` and a single-flight
        ``coalesced`` waiter avoided a model call, so both count toward the rate.
        """
        return (self.hits + self.coalesced) / self.total if self.total else 0.0


class CachingRuntime(AgentRuntime):
    """A cost-aware wrapper over :class:`RecordReplayRuntime`.

    Each :meth:`run` reports, via :attr:`stats`, whether the request hit the cassette
    (free, no budget charge — the saved spend is tallied) or missed it (the inner replay
    runtime records + the underlying model spends). A small in-process LRU of recently
    recorded results lets the wrapper price a hit even before the cassette is re-read,
    keeping ``saved_usd`` exact for repeated identical calls within a session.

    In front of that persistent cache sits the CRA-221 **single-flight** layer: an
    in-process per-key :class:`asyncio.Future` map (:attr:`_inflight`). When a request
    arrives while an identical one (same org-salted key) is still computing, this caller
    awaits the in-flight future instead of issuing its own ``inner.run`` — so N concurrent
    identical calls collapse to **one** model call and **one** ``CostBudget.charge``. The
    first (leader) caller resolves the future for every waiter on success, or propagates
    the exception to all of them on failure; either way the key is removed in a ``finally``
    so a later retry recomputes (no poisoned future is ever cached).
    """

    name = "caching"

    def __init__(
        self,
        inner: RecordReplayRuntime,
        *,
        cassette_dir: str | Path | None = None,
        track_capacity: int = 1024,
    ) -> None:
        self._inner = inner
        # Reuse the replay runtime's own cassette dir unless overridden (read-only here).
        self._dir = Path(cassette_dir) if cassette_dir is not None else inner._dir
        self.stats = CacheStats()
        self._capacity = track_capacity
        # key -> recorded cost, so a within-session repeat is priced without re-reading.
        self._costs: OrderedDict[str, float] = OrderedDict()
        # CRA-221 single-flight: org-salted key -> the in-flight leader's Future. A non-None
        # entry means an identical call is mid-compute; concurrent callers await it.
        self._inflight: dict[str, asyncio.Future[RunResult]] = {}

    def _coalesce_key(self, request: RunRequest, ctx: RunContext) -> str:
        """The single-flight coalescing key — the inner replay runtime's own cassette key.

        Built with ``org_id=ctx.org_id`` so it carries the tenant boundary (CRA-221 gap
        S2): two orgs with identical ``(definition, inputs)`` produce **distinct** keys and
        never coalesce onto one another's in-flight result. A fluid/tainted input only ever
        enters via ``inputs`` (already part of the key), never as the org coordinate, so it
        can never widen one tenant's key onto another's.
        """
        return _key(request, org_id=ctx.org_id)

    def _is_hit(self, request: RunRequest) -> bool:
        """True if a cassette already exists for this request (a free replay)."""
        return (self._dir / f"{_key(request)}.json").exists()

    def _remember(self, key: str, cost_usd: float) -> None:
        self._costs[key] = cost_usd
        self._costs.move_to_end(key)
        while len(self._costs) > self._capacity:
            self._costs.popitem(last=False)

    async def run(self, request: RunRequest, ctx: RunContext) -> RunResult:
        # Cancel BEFORE any coalescing decision (CRA-221 AC): a cancelled caller never
        # joins or starts an in-flight computation.
        ctx.cancel_token.raise_if_cancelled()

        coalesce_key = self._coalesce_key(request, ctx)
        existing = self._inflight.get(coalesce_key)
        if existing is not None:
            # A peer with the identical org-salted key is already computing. Await its
            # result instead of issuing our own call — one model call serves N callers.
            # We made no call, so we charge $0. Price the avoided spend from the leader's
            # resolved result (exact, and available only after the await).
            result = await existing
            self.stats.coalesced += 1
            self.stats.saved_usd += result.cost_usd
            self.stats._seen_keys.add(coalesce_key)
            return result

        # We are the leader: register an in-flight future, compute exactly once, and
        # resolve (or fail) it for any waiters that join while we run.
        loop = asyncio.get_running_loop()
        future: asyncio.Future[RunResult] = loop.create_future()
        self._inflight[coalesce_key] = future
        try:
            result = await self._compute(request, ctx)
        except BaseException as exc:
            # Propagate to every awaiter, then re-raise for the leader. The key is cleared
            # in ``finally`` so a retry recomputes (no poisoned future).
            if not future.done():
                future.set_exception(exc)
            raise
        else:
            if not future.done():
                future.set_result(result)
            return result
        finally:
            # Always release the slot. The waiters already hold a reference to ``future``,
            # so dropping it from the map only prevents *new* callers from coalescing onto
            # a finished computation.
            self._inflight.pop(coalesce_key, None)
            # If the future carries an exception and no waiter joined to await it, asyncio
            # would log a spurious "exception never retrieved" warning when it is GC'd.
            # Reading ``.exception()`` here marks it retrieved. (The leader's own raise has
            # already surfaced the error to the caller.)
            if future.done() and not future.cancelled():
                future.exception()

    async def _compute(self, request: RunRequest, ctx: RunContext) -> RunResult:
        """The leader's metered call — the original CRA-182 hit/miss accounting path."""
        key = _key(request)
        hit = self._is_hit(request)
        result = await self._inner.run(request, ctx)

        if hit:
            # Replay charged nothing; tally the spend the cache avoided. Prefer the
            # within-session recorded cost (exact) over the replayed result's own.
            self.stats.hits += 1
            self.stats.saved_usd += self._costs.get(key, result.cost_usd)
        else:
            self.stats.misses += 1
            self.stats.spent_usd += result.cost_usd
            self._remember(key, result.cost_usd)
        self.stats._seen_keys.add(key)
        return result
