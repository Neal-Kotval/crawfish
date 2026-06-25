"""UNFILED-COST — org-scoped dashboard + aggregate cost-vs-ceiling gauge.

Two-org Store fixture (org A spends $3.10, org B $9.00, ceiling $5.00): build for org A → gauge
$3.10/ok, and org B's spend never contributes; push org A over $5.00 → ceiling_reached. The
ceiling_reached state is the load-bearing handoff to the HITL/budget gate.
"""

from __future__ import annotations

import time

from crawfish.code.dashboard.data import DashboardData
from crawfish.config import BudgetConfig
from crawfish.deploy import DeployRegistry
from crawfish.observe import ObserverSurface, RunInfo
from crawfish.store import SqliteStore


def _spend(store: SqliteStore, org: str, run_id: str, cost: float) -> None:
    ObserverSurface(store, org_id=org).put_run_info(
        RunInfo(pipeline="p", run_id=run_id, status="done", cost_usd=cost, started_at=time.time())
    )


def _gauge(store: SqliteStore, org: str, ceiling: float | None):
    data = DashboardData(
        ObserverSurface(store, org_id=org),
        DeployRegistry(store, org_id=org),
        store=store,
        org_id=org,
        budget=BudgetConfig(ceiling_usd=ceiling),
    )
    return data.cost_gauge(now=time.time())


def test_org_scoped_gauge_excludes_other_org() -> None:
    store = SqliteStore()
    _spend(store, "a", "ra", 3.10)
    _spend(store, "b", "rb", 9.00)
    gauge = _gauge(store, "a", ceiling=5.00)
    assert gauge.org_id == "a"
    assert gauge.spent_today_usd == 3.10  # org B's $9.00 never contributes
    assert gauge.state == "ok"
    store.close()


def test_ceiling_reached_flips_state() -> None:
    store = SqliteStore()
    _spend(store, "a", "ra", 3.10)
    _spend(store, "a", "rb", 2.50)  # total 5.60 ≥ 5.00
    gauge = _gauge(store, "a", ceiling=5.00)
    assert gauge.spent_today_usd == 5.60
    assert gauge.state == "ceiling_reached"  # the signal the HITL gate reads
    store.close()


def test_missing_ceiling_is_unbounded() -> None:
    store = SqliteStore()
    _spend(store, "a", "ra", 100.0)
    gauge = _gauge(store, "a", ceiling=None)
    assert gauge.ceiling_usd is None
    assert gauge.state == "ok"  # no ceiling → never ceiling_reached
    store.close()


def test_warn_band_before_ceiling() -> None:
    store = SqliteStore()
    _spend(store, "a", "ra", 4.20)  # 84% of 5.00 → warn
    gauge = _gauge(store, "a", ceiling=5.00)
    assert gauge.state == "warn"
    store.close()


def test_gauge_snapshot_schema() -> None:
    store = SqliteStore()
    _spend(store, "a", "ra", 1.0)
    gauge = _gauge(store, "a", ceiling=5.0)
    from crawfish.code.dashboard.data import COST_SCHEMA

    assert COST_SCHEMA == "craw.code.cost.v1"
    assert gauge.model_dump()["state"] == "ok"
    store.close()
