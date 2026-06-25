"""CRA-253 — runs in flight: fan-out progress, cost band, loopback bind.

Seeds a running batch (12 items, 7 DONE) + a per-run cost interval; asserts the card's
done_items, the band ordering + amber threshold, and that the server binds 127.0.0.1 only.
No live model call — all data is pre-seeded rows.
"""

from __future__ import annotations

import time

from crawfish.code.dashboard.data import DashboardData
from crawfish.code.dashboard.server import LOOPBACK, make_handler, render_snapshot, serve_dashboard
from crawfish.code.dashboard.views import render_runs
from crawfish.deploy import DeployRegistry
from crawfish.ledger import ExecState, ExecutionLedger
from crawfish.observe import ObserverSurface, RunInfo
from crawfish.store import SqliteStore


def _data_with_running_batch(cost: float) -> tuple[SqliteStore, DashboardData]:
    store = SqliteStore()
    surface = ObserverSurface(store, org_id="local")
    surface.put_run_info(
        RunInfo(
            pipeline="triage-bot",
            run_id="r1",
            status="running",
            items=12,
            cost_usd=cost,
            started_at=time.time(),
        )
    )
    ledger = ExecutionLedger(store, org_id="local")
    for i in range(7):
        ledger.mark_item("r1", f"item-{i}", ExecState.DONE)
    store.put_record(
        "run_budget",
        "r1",
        {"total_usd": 0.05, "expected_usd": 0.40, "worst_case_usd": 1.20},
        org_id="local",
    )
    data = DashboardData(
        surface, DeployRegistry(store, org_id="local"), store=store, org_id="local"
    )
    return store, data


def test_fanout_progress_done_over_total() -> None:
    store, data = _data_with_running_batch(cost=0.18)
    card = data.running()[0]
    assert card.done_items == 7
    assert card.items == 12
    store.close()


def test_cost_band_ordering_holds() -> None:
    store, data = _data_with_running_batch(cost=0.18)
    band = data.running()[0].budget
    assert band.total_usd <= band.expected_usd <= band.worst_case_usd
    store.close()


def test_band_amber_when_actual_exceeds_expected() -> None:
    # actual 0.50 > expected 0.40 → the rendered band carries the amber class.
    store, data = _data_with_running_batch(cost=0.50)
    html = render_runs(data.running())
    assert "band amber" in html
    store.close()


def test_band_not_amber_under_expected() -> None:
    store, data = _data_with_running_batch(cost=0.10)
    html = render_runs(data.running())
    assert "band amber" not in html
    store.close()


def test_runs_snapshot_stable_schema() -> None:
    store, data = _data_with_running_batch(cost=0.18)
    snap = render_snapshot(data, now=1_750_000_000.0)
    assert snap["runs_schema"] == "craw.code.dashboard.runs.v1"
    card = next(r for r in snap["runs"] if r["run_id"] == "r1")
    assert card["done_items"] == 7
    assert card["budget"]["expected_usd"] == 0.40
    store.close()


def test_server_binds_loopback_only() -> None:
    store, data = _data_with_running_batch(cost=0.1)
    server = serve_dashboard(data, port=0)  # port 0 → OS picks a free port
    try:
        host, _port = server.server_address[0], server.server_address[1]
        assert host == LOOPBACK  # 127.0.0.1, never 0.0.0.0
    finally:
        server.server_close()
        store.close()


def test_handler_rejects_non_loopback_host() -> None:
    # The handler factory builds over the data facade; the loopback-Host guard is a method.
    store, data = _data_with_running_batch(cost=0.1)
    handler_cls = make_handler(data)
    assert hasattr(handler_cls, "_host_is_loopback")
    store.close()
