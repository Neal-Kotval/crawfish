"""Observer output + run-info surface (CRA-154).

A structured, queryable place for **observer events** and **per-run info** to land,
read by ``craw visualize``, ``craw manage``, and alerting. Everything persists
through the :class:`~crawfish.store.base.Store` seam — no new SQL — so wrapping the
store in :class:`~crawfish.secrets.ScrubbingStore` redacts secrets/PII *before* the
write automatically (the security spine for this surface).

Two shapes:

* :class:`ObserverEvent` — an append-only, ordered finding (cost spike, quality
  drop, failure rate). Stored as an event stream keyed ``observer:<pipeline>`` so
  it reuses ``Store.append_event``/``Store.events`` (poll-friendly, like
  ``tail_events``).
* :class:`RunInfo` — the per-run summary (status, cost, timing) a dashboard renders.
  Stored as a ``run_info`` record keyed by ``run_id``, updated as the run progresses.

The :class:`ObserverSurface` facade is the stable read/write API; ``ctx.emit(event)``
is the one-liner nodes and observers call.

Example::

    surface = ObserverSurface(store)
    surface.emit(ObserverEvent(pipeline="triage-bot", kind="cost.spike", detail="$2.10 in 5m"))
    surface.run_info("triage-bot", since="-1h")  # → [RunInfo(...), ...]
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = [
    "Severity",
    "ObserverEvent",
    "RunInfo",
    "ObserverSurface",
    "parse_since",
]

# Observer events ride the existing event ledger under a synthetic stream id so all
# SQL stays inside the Store impl and scrubbing (if the store is wrapped) applies. The
# `observer:<pipeline>` namespace cannot collide with a real run's event stream: run ids
# come from `new_id()`, which never emits a colon-prefixed value.
_EVENT_STREAM = "observer"
_RUNINFO_KIND = "run_info"
_SINCE_UNITS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}


class Severity(str, Enum):
    """How loudly an observer event should be surfaced."""

    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class ObserverEvent(BaseModel):
    """A structured finding emitted by an observer or a node.

    ``pipeline`` and ``kind`` are stable, static identifiers (safe to render and
    filter on); ``detail``/``data`` are free-form and are scrubbed on write when the
    surface is backed by a :class:`~crawfish.secrets.ScrubbingStore`.
    """

    pipeline: str
    kind: str  # dotted, e.g. "cost.spike", "quality.low", "failure.rate"
    detail: str = ""
    severity: Severity = Severity.INFO
    observer: str | None = None  # which observer produced it
    run_id: str | None = None  # the run it concerns, if any
    ts: float = Field(default_factory=time.time)
    data: dict[str, JSONValue] = Field(default_factory=dict)
    id: str = Field(default_factory=new_id)


class RunInfo(BaseModel):
    """Per-run summary the dashboard and ``craw manage`` read."""

    pipeline: str
    run_id: str
    status: str = "running"  # running | done | failed | needs_retry
    backend: str = "command"
    version: str = ""
    cost_usd: float = 0.0
    items: int = 0
    started_at: float = Field(default_factory=time.time)
    finished_at: float | None = None


def parse_since(since: str | float | int | None = None, *, now: float | None = None) -> float:
    """Resolve a ``since`` argument to an epoch-seconds threshold.

    Accepts ``None`` (epoch 0 — everything), an absolute epoch ``float``/``int``, or a
    relative string like ``"-1h"`` / ``"-30m"`` / ``"-15s"`` / ``"-2d"``.
    """
    if since is None:
        return 0.0
    if isinstance(since, (int, float)):
        return float(since)
    s = since.strip()
    try:
        if s.startswith("-") and s[-1] in _SINCE_UNITS:
            base = time.time() if now is None else now
            return base - float(s[1:-1]) * _SINCE_UNITS[s[-1]]
        return float(s)  # treat any other string as an absolute epoch
    except ValueError:
        # Malformed window (e.g. "-xh", "garbage") must never crash a poll/dashboard;
        # fall back to "everything" rather than raising into a caller's render loop.
        return 0.0


class ObserverSurface:
    """Read/write facade over the run-info surface, scoped to one tenant.

    Persists through whatever :class:`~crawfish.store.base.Store` it is handed — pass
    a :class:`~crawfish.secrets.ScrubbingStore` to redact secrets before the write.
    """

    def __init__(self, store: Store, *, org_id: str = "local") -> None:
        self._store = store
        self._org = org_id

    # -- observer events (append-only, ordered) -----------------------------
    def emit(self, event: ObserverEvent) -> None:
        """Append an observer event to the ``pipeline``'s ordered stream."""
        self._store.append_event(
            f"{_EVENT_STREAM}:{event.pipeline}",
            event.model_dump(mode="json"),
            org_id=self._org,
        )

    def events(
        self,
        pipeline: str,
        *,
        since: str | float | int | None = None,
        kind: str | None = None,
        now: float | None = None,
    ) -> list[ObserverEvent]:
        """Observer events for ``pipeline``, oldest first, filtered by time/kind."""
        threshold = parse_since(since, now=now)
        rows = self._store.events(f"{_EVENT_STREAM}:{pipeline}", org_id=self._org)
        out = [ObserverEvent.model_validate(r) for r in rows]
        return [e for e in out if e.ts >= threshold and (kind is None or e.kind == kind)]

    # -- per-run info -------------------------------------------------------
    def put_run_info(self, info: RunInfo) -> None:
        """Upsert a run's info record (idempotent on ``run_id``)."""
        self._store.put_record(
            _RUNINFO_KIND, info.run_id, info.model_dump(mode="json"), org_id=self._org
        )

    def get_run_info(self, run_id: str) -> RunInfo | None:
        rec = self._store.get_record(_RUNINFO_KIND, run_id, org_id=self._org)
        return None if rec is None else RunInfo.model_validate(rec)

    def run_info(
        self,
        pipeline: str | None = None,
        *,
        since: str | float | int | None = None,
        now: float | None = None,
    ) -> list[RunInfo]:
        """Run-info records, newest first, optionally scoped to one pipeline/window."""
        threshold = parse_since(since, now=now)
        rows = self._store.list_records(_RUNINFO_KIND, org_id=self._org)
        out = [RunInfo.model_validate(r) for r in rows]
        out = [
            ri
            for ri in out
            if (pipeline is None or ri.pipeline == pipeline) and ri.started_at >= threshold
        ]
        out.sort(key=lambda ri: ri.started_at, reverse=True)
        return out
