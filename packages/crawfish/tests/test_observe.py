"""CRA-154 acceptance: observer events + run-info surface.

Events and run-info persist via the Store, are queryable by pipeline/time/kind, are
append-only + ordered, and sensitive content is scrubbed before the write.
"""

from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.observe import ObserverEvent, ObserverSurface, RunInfo, Severity, parse_since
from crawfish.secrets import ScrubbingStore
from crawfish.store import SqliteStore


def _surface() -> ObserverSurface:
    return ObserverSurface(SqliteStore())


def test_events_persist_and_query_by_pipeline() -> None:
    s = _surface()
    s.emit(ObserverEvent(pipeline="triage-bot", kind="cost.spike", detail="$2.10 in 5m"))
    s.emit(ObserverEvent(pipeline="other", kind="failure.rate", detail="ignored"))
    events = s.events("triage-bot")
    assert [e.kind for e in events] == ["cost.spike"]
    assert events[0].detail == "$2.10 in 5m"


def test_events_are_append_only_and_ordered() -> None:
    s = _surface()
    for i in range(3):
        s.emit(ObserverEvent(pipeline="p", kind=f"k{i}", ts=float(i)))
    assert [e.kind for e in s.events("p")] == ["k0", "k1", "k2"]


def test_events_filter_by_kind_and_time_window() -> None:
    s = _surface()
    s.emit(ObserverEvent(pipeline="p", kind="cost.spike", ts=100.0))
    s.emit(ObserverEvent(pipeline="p", kind="quality.low", ts=200.0))
    assert [e.kind for e in s.events("p", kind="quality.low")] == ["quality.low"]
    # now=250, since="-1m" → threshold 190 → only the ts=200 event survives
    recent = s.events("p", since="-1m", now=250.0)
    assert [e.ts for e in recent] == [200.0]


def test_run_info_persists_and_queries() -> None:
    s = _surface()
    s.put_run_info(RunInfo(pipeline="triage-bot", run_id="r1", cost_usd=0.42, started_at=10.0))
    # a full-record upsert on the same run_id replaces in place (not append)
    s.put_run_info(
        RunInfo(pipeline="triage-bot", run_id="r1", status="done", cost_usd=0.42, started_at=10.0)
    )
    s.put_run_info(RunInfo(pipeline="other", run_id="r2", started_at=20.0))
    infos = s.run_info("triage-bot")
    assert len(infos) == 1  # upsert on run_id, not append
    assert infos[0].status == "done" and infos[0].cost_usd == 0.42


def test_run_info_newest_first_and_window() -> None:
    s = _surface()
    s.put_run_info(RunInfo(pipeline="p", run_id="a", started_at=100.0))
    s.put_run_info(RunInfo(pipeline="p", run_id="b", started_at=300.0))
    assert [ri.run_id for ri in s.run_info("p")] == ["b", "a"]
    assert [ri.run_id for ri in s.run_info("p", since="-1m", now=320.0)] == ["b"]


def test_sensitive_content_scrubbed_before_write() -> None:
    inner = SqliteStore()
    surface = ObserverSurface(ScrubbingStore(inner, secrets=["hunter2"]))
    surface.emit(
        ObserverEvent(
            pipeline="p",
            kind="quality.low",
            detail="token hunter2 and key sk-abcdefghij0123456789 leaked",
            data={"contact": "alice@example.com"},
        )
    )
    raw = inner.events("observer:p")[0]
    assert "hunter2" not in raw["detail"]
    assert "sk-abcdefghij0123456789" not in raw["detail"]
    assert "alice@example.com" not in str(raw["data"])
    assert "***REDACTED***" in raw["detail"]


def test_ctx_emit_routes_through_store() -> None:
    ctx = RunContext(store=SqliteStore())
    ctx.emit(ObserverEvent(pipeline="p", kind="info", severity=Severity.INFO))
    assert ObserverSurface(ctx.store).events("p")[0].kind == "info"


def test_parse_since_units() -> None:
    assert parse_since(None) == 0.0
    assert parse_since(150.0) == 150.0
    assert parse_since("-2h", now=10_000.0) == 10_000.0 - 7200.0
    assert parse_since("-30s", now=1000.0) == 970.0
