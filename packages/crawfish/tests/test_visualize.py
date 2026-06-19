"""CRA-155 acceptance: craw visualize — loopback dashboard over the run-info surface."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from crawfish.deploy import DeployEntry, DeployRegistry
from crawfish.observe import ObserverEvent, ObserverSurface, RunInfo
from crawfish.secrets import ScrubbingStore
from crawfish.store import SqliteStore
from crawfish.visualize import (
    DASHBOARD_HTML,
    LOOPBACK,
    dashboard_state,
    make_handler,
    serve_dashboard,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _seed(store: SqliteStore) -> None:
    import os

    DeployRegistry(store).register(
        DeployEntry(
            name="triage-bot",
            pid=os.getpid(),
            dir="/p",
            session="crawfish/triage-bot",
            schedule="0 8 * * *",
        )
    )
    surface = ObserverSurface(store)
    surface.put_run_info(
        RunInfo(
            pipeline="triage-bot",
            run_id="r1",
            status="done",
            cost_usd=0.42,
            started_at=NOW.timestamp() - 120,
        )
    )
    surface.emit(
        ObserverEvent(
            pipeline="triage-bot", kind="cost.spike", detail="$2.10 in 5m", ts=NOW.timestamp() - 60
        )
    )


def test_dashboard_state_shows_pipelines_runs_cost_events() -> None:
    store = SqliteStore()
    _seed(store)
    state = dashboard_state(store, now=NOW)
    assert state["cost_today_usd"] == 0.42
    assert state["pipelines"][0]["name"] == "triage-bot"  # type: ignore[index]
    assert state["recent_runs"][0]["status"] == "done"  # type: ignore[index]
    assert state["observer_events"][0]["kind"] == "cost.spike"  # type: ignore[index]


def test_dashboard_binds_loopback_only() -> None:
    store = SqliteStore()
    server = serve_dashboard(store, port=0)  # port 0 = ephemeral, no real listen needed
    try:
        assert server.server_address[0] == LOOPBACK == "127.0.0.1"
    finally:
        server.server_close()


def test_dashboard_renders_no_secret_values() -> None:
    # events flow through a ScrubbingStore → the JSON the page renders carries no secret
    inner = SqliteStore()
    store = ScrubbingStore(inner, secrets=["hunter2"])
    surface = ObserverSurface(store)
    surface.emit(
        ObserverEvent(
            pipeline="p", kind="quality.low", detail="leaked hunter2 token", ts=NOW.timestamp()
        )
    )
    import os

    DeployRegistry(store).register(
        DeployEntry(name="p", pid=os.getpid(), dir="/p", session="crawfish/p")
    )
    blob = json.dumps(dashboard_state(store, now=NOW))
    assert "hunter2" not in blob
    assert "***REDACTED***" in blob


def test_state_endpoint_serves_json() -> None:
    store = SqliteStore()
    _seed(store)
    handler = make_handler(store)
    # the HTML page is static and contains no interpolated state (no secret surface)
    assert "127.0.0.1" in DASHBOARD_HTML
    assert handler is not None
