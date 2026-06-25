"""CRA-252 — dashboard data layer over the ObserverSurface/Store seam.

Seeds a temp Store with RunInfo / ObserverEvent / ledger-DONE / run-budget rows and asserts the
typed read-model: FleetSnapshot / RunCard shapes, fan-out done-count, the cost band, and the
two-org isolation invariant. No live model call — all data is pre-seeded rows.
"""

from __future__ import annotations

import time

from crawfish.code.dashboard import build_data
from crawfish.code.dashboard.data import DashboardData
from crawfish.deploy import DeployRegistry
from crawfish.ledger import ExecState, ExecutionLedger
from crawfish.observe import ObserverEvent, ObserverSurface, RunInfo
from crawfish.store import SqliteStore


def _seed_run(
    store: SqliteStore,
    *,
    org: str,
    run_id: str,
    pipeline: str,
    status: str = "running",
    items: int = 0,
    done: int = 0,
    cost: float = 0.0,
    version: str = "0.3.1",
    budget: tuple[float, float, float] | None = None,
) -> None:
    surface = ObserverSurface(store, org_id=org)
    surface.put_run_info(
        RunInfo(
            pipeline=pipeline,
            run_id=run_id,
            status=status,
            items=items,
            cost_usd=cost,
            version=version,
            started_at=time.time(),
        )
    )
    ledger = ExecutionLedger(store, org_id=org)
    for i in range(done):
        ledger.mark_item(run_id, f"item-{i}", ExecState.DONE)
    if budget is not None:
        total, expected, worst = budget
        store.put_record(
            "run_budget",
            run_id,
            {"total_usd": total, "expected_usd": expected, "worst_case_usd": worst},
            org_id=org,
        )


def _data(store: SqliteStore, org: str = "local") -> DashboardData:
    return DashboardData(
        ObserverSurface(store, org_id=org),
        DeployRegistry(store, org_id=org),
        store=store,
        org_id=org,
    )


def test_run_card_shape_and_fanout_and_band() -> None:
    store = SqliteStore()
    _seed_run(
        store,
        org="local",
        run_id="r1",
        pipeline="triage-bot",
        items=12,
        done=7,
        cost=0.18,
        budget=(0.05, 0.40, 1.20),
    )
    cards = _data(store).runs()
    assert len(cards) == 1
    card = cards[0]
    assert card.run_id == "r1"
    assert card.pipeline == "triage-bot"
    assert card.items == 12
    assert card.done_items == 7  # ledger DONE count via the surface, not SQL
    assert card.budget.total_usd == 0.05
    assert card.budget.expected_usd == 0.40
    assert card.budget.worst_case_usd == 1.20
    # cost invariant on the rendered band.
    assert card.budget.total_usd <= card.budget.expected_usd <= card.budget.worst_case_usd
    store.close()


def test_missing_budget_degrades_to_degenerate_band() -> None:
    store = SqliteStore()
    _seed_run(store, org="local", run_id="r1", pipeline="p", cost=0.31)
    card = _data(store).runs()[0]
    assert card.budget.total_usd == card.budget.expected_usd == card.budget.worst_case_usd == 0.31
    store.close()


def test_running_filters_to_in_flight() -> None:
    store = SqliteStore()
    _seed_run(store, org="local", run_id="r1", pipeline="p", status="running")
    _seed_run(store, org="local", run_id="r2", pipeline="p", status="done")
    running = _data(store).running()
    assert [c.run_id for c in running] == ["r1"]
    store.close()


def test_two_org_isolation_runs() -> None:
    store = SqliteStore()
    _seed_run(store, org="a", run_id="ra", pipeline="pa", cost=1.0)
    _seed_run(store, org="b", run_id="rb", pipeline="pb", cost=9.0)
    cards_a = _data(store, org="a").runs()
    assert [c.run_id for c in cards_a] == ["ra"]
    assert all(c.run_id != "rb" for c in cards_a)
    store.close()


def test_events_carry_tainted_detail_unmodified() -> None:
    # The data layer must carry detail through UNENCODED so the renderer is the single
    # encoding chokepoint (UNFILED-XSS). Register a deployed pipeline so events() scans it.
    store = SqliteStore()
    from crawfish.deploy import DeployEntry, DeployStatus

    DeployRegistry(store, org_id="local").register(
        DeployEntry(name="triage-bot", pid=1, dir=".", session="t", status=DeployStatus.RUNNING)
    )
    payload = "<script>alert(1)</script>"
    ObserverSurface(store, org_id="local").emit(
        ObserverEvent(pipeline="triage-bot", kind="quality.flag", detail=payload)
    )
    events = _data(store).events()
    assert any(e.detail == payload for e in events)  # raw, unencoded — encoding happens at render
    store.close()


def test_build_data_wraps_in_scrubbing(tmp_path) -> None:
    # build_data resolves the project store and wraps it scrubbed; the facade never sees a class.
    (tmp_path / ".crawfish").mkdir()
    data = build_data(tmp_path, org_id="local")
    from crawfish.secrets import ScrubbingStore

    assert isinstance(data._store, ScrubbingStore)
    data._store.close()
