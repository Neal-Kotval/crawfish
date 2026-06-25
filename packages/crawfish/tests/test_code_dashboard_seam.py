"""UNFILED-SEAM — the dashboard reads through the ObserverSurface/Store seam, never a backend.

(a) A source-grep lint over the whole dashboard package fails if any module names a concrete
backend or SQL. (b) A run-against-a-non-Sqlite ``MemoryStore`` (a Store-protocol impl that is
NOT ``SqliteStore``) produces a well-formed snapshot — proving the SQLite→Postgres swap is a
driver swap (ADR 0011).
"""

from __future__ import annotations

from pathlib import Path

from crawfish.code.dashboard.data import DashboardData
from crawfish.code.dashboard.server import render_snapshot
from crawfish.core.types import JSONValue
from crawfish.deploy import DeployRegistry
from crawfish.observe import ObserverEvent, ObserverSurface, RunInfo

# The forbidden tokens: a concrete backend / a raw SQL verb must never appear in the package.
FORBIDDEN = (
    "crawfish.store.sqlite",
    "SqliteStore",
    "import sqlite3",
    "sqlite3",
    "SELECT ",
    "INSERT ",
    "UPDATE ",
    "DELETE FROM",
    " COUNT(",
)

_DASHBOARD_PKG = Path(__file__).parents[1] / "src" / "crawfish" / "code" / "dashboard"


def test_no_backend_or_sql_in_dashboard_package() -> None:
    offenders: list[str] = []
    for py in sorted(_DASHBOARD_PKG.rglob("*.py")):
        text = py.read_text()
        for token in FORBIDDEN:
            if token in text:
                offenders.append(f"{py.name}: {token!r}")
    assert not offenders, f"dashboard package names a concrete backend or SQL: {offenders}"


# --------------------------------------------------------------------------
# A minimal in-memory Store protocol impl — explicitly NOT SqliteStore — so the
# run-against-a-non-Sqlite-backend test proves the seam is a driver swap.
# --------------------------------------------------------------------------
class MemoryStore:
    """A dict-backed :class:`~crawfish.store.base.Store` impl (no SQL, no SQLite)."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], dict[str, JSONValue]] = {}
        self._kv: dict[tuple[str, str, str], JSONValue] = {}
        self._events: dict[tuple[str, str], list[dict[str, JSONValue]]] = {}
        self._claims: set[tuple[str, str]] = set()

    def put_record(
        self, kind: str, id: str, data: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None:
        self._records[(org_id, kind, id)] = dict(data)

    def get_record(
        self, kind: str, id: str, *, org_id: str = "local"
    ) -> dict[str, JSONValue] | None:
        return self._records.get((org_id, kind, id))

    def list_records(self, kind: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]:
        return [v for (o, k, _), v in self._records.items() if o == org_id and k == kind]

    def delete_record(self, kind: str, id: str, *, org_id: str = "local") -> None:
        self._records.pop((org_id, kind, id), None)

    def kv_get(self, namespace: str, key: str, *, org_id: str = "local") -> JSONValue | None:
        return self._kv.get((org_id, namespace, key))

    def kv_set(self, namespace: str, key: str, value: JSONValue, *, org_id: str = "local") -> None:
        self._kv[(org_id, namespace, key)] = value

    def claim_idempotency(self, key: str, *, org_id: str = "local") -> bool:
        if (org_id, key) in self._claims:
            return False
        self._claims.add((org_id, key))
        return True

    def append_event(
        self, run_id: str, event: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None:
        self._events.setdefault((org_id, run_id), []).append(dict(event))

    def events(self, run_id: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]:
        return list(self._events.get((org_id, run_id), []))

    def close(self) -> None:
        return None


def test_dashboard_runs_against_non_sqlite_store() -> None:
    from crawfish.store.base import Store

    store = MemoryStore()
    assert isinstance(store, Store)  # it satisfies the protocol
    assert type(store).__name__ != "SqliteStore"

    ObserverSurface(store, org_id="local").put_run_info(
        RunInfo(pipeline="p", run_id="r1", status="running", items=2, cost_usd=0.1)
    )
    ObserverSurface(store, org_id="local").emit(
        ObserverEvent(pipeline="p", kind="cost.spike", detail="hi")
    )
    data = DashboardData(
        ObserverSurface(store, org_id="local"),
        DeployRegistry(store, org_id="local"),
        store=store,
        org_id="local",
    )
    snap = render_snapshot(data, now=1_750_000_000.0)
    assert snap["schema"] == "craw.code.dashboard.v1"
    assert snap["org_id"] == "local"
    assert any(r["run_id"] == "r1" for r in snap["runs"])  # the swap works unchanged
    store.close()
