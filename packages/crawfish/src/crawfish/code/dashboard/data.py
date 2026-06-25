"""Dashboard data layer — the typed read-model over the ledger (CRA-252).

Every dashboard view sits on :class:`DashboardData`, a read facade constructed over an
:class:`~crawfish.observe.ObserverSurface` (never a store *class*). It composes the
already-Store-backed, already-scrubbed surfaces — ``run_info`` / ``events`` (observer),
:class:`~crawfish.deploy.DeployRegistry` + ``manage_list`` (deployed pipelines),
:class:`~crawfish.ledger.ExecutionLedger` (per-item DONE counts), the cost interval
(:mod:`crawfish.cost`), and the ``[budget]`` ceiling (:mod:`crawfish.config`).

The seam (ADR 0011): this module imports **protocols and surfaces only** — the
:class:`~crawfish.store.base.Store` protocol, ``ObserverSurface``, ``DeployRegistry``,
``manage_list`` — and **never** a concrete persistence backend or a raw query string. All
cross-row aggregation (cost rollups, status counts, fan-out progress, the cost-vs-ceiling
gauge) is **pure Python over typed, scrubbed rows**; a source-lint test
(``test_code_dashboard_seam.py``) fails the build if a concrete backend or query verb ever
appears here.

Tainted carriage (UNFILED-XSS): ``RunInfo.version``, ``ObserverEvent.detail``, item ids, and
metric labels are ``Flow.FLUID`` and are carried through this layer **unmodified** so the
render layer's ``encode_field`` (``encoding.py``) is the single output-encoding chokepoint.
This facade never renders; it only projects typed Pydantic view-models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from crawfish.observe import ObserverEvent, RunInfo

if TYPE_CHECKING:
    from crawfish.config import BudgetConfig
    from crawfish.deploy import DeployRegistry
    from crawfish.observe import ObserverSurface
    from crawfish.store.base import Store

__all__ = [
    "DashboardData",
    "FleetRow",
    "FleetSnapshot",
    "RunCard",
    "CostBand",
    "CostGauge",
    "DASHBOARD_SCHEMA",
    "RUNS_SCHEMA",
    "COST_SCHEMA",
]

#: Schema tags for the dashboard ``--json`` snapshots (CRA-269 / spec). Major-only; minor
#: (additive) bumps keep the tag stable. These match the spec's ``craw.code.dashboard.v1`` /
#: ``…runs.v1`` / ``craw.code.cost.v1`` payload identifiers.
DASHBOARD_SCHEMA = "craw.code.dashboard.v1"
RUNS_SCHEMA = "craw.code.dashboard.runs.v1"
COST_SCHEMA = "craw.code.cost.v1"

#: Where a per-run cost interval is stashed for the runs view (CRA-253). The interval is
#: declared at run-start by the writer; the dashboard reads it back through the Store protocol
#: (``get_record``), never reconstructing one from a definition it cannot see.
_RUN_BUDGET_KIND = "run_budget"


class CostBand(BaseModel):
    """A run's cost interval — the band the runs view renders actual spend against.

    Mirrors the three-number cost interval (``crawfish.cost.CostEstimate``): ``total_usd`` is
    the lower bound, ``worst_case_usd`` the upper, ``expected_usd`` the measured-rate band
    between them. The cost invariant ``total <= expected <= worst_case`` is preserved on read.
    """

    total_usd: float = 0.0
    expected_usd: float = 0.0
    worst_case_usd: float = 0.0


class RunCard(BaseModel):
    """One run row in the runs-in-flight view (CRA-253).

    ``version`` is model-derivable and carried tainted (encoded at render). ``done_items`` is
    the count of loop-ledger DONE records for the run (fan-out progress ``done/total``),
    read via the surface/ledger — never a SQL ``COUNT``.
    """

    run_id: str
    pipeline: str
    status: str
    version: str = ""
    items: int = 0
    done_items: int = 0
    cost_usd: float = 0.0
    budget: CostBand = Field(default_factory=CostBand)


class FleetRow(BaseModel):
    """One deployed-pipeline row in the fleet view (composed from ``manage_list``)."""

    pipeline: str
    status: str
    uptime_s: float = 0.0
    next_fire: str | None = None
    cost_today_usd: float = 0.0


class FleetSnapshot(BaseModel):
    """The fleet view: deployed pipelines + today's aggregate spend."""

    org_id: str
    generated_at: float
    rows: list[FleetRow] = Field(default_factory=list)
    cost_today_usd: float = 0.0


class CostGauge(BaseModel):
    """The org-scoped aggregate cost-vs-ceiling gauge (UNFILED-COST).

    ``state`` flips ``ceiling_reached`` when ``spent_today_usd >= ceiling_usd`` — the **same**
    signal the HITL/budget gate reads to halt agent ``--live`` calls. A missing ceiling
    (``None``) is unbounded ("no ceiling") and never reaches ``ceiling_reached``.
    """

    org_id: str
    ceiling_usd: float | None = None
    spent_today_usd: float = 0.0
    projected_today_usd: float = 0.0
    state: str = "ok"  # ok | warn | ceiling_reached


def _today_cost(infos: list[RunInfo], *, today: datetime) -> float:
    """Sum ``RunInfo.cost_usd`` for the UTC day — matches ``craw manage``'s ``$ TODAY``."""
    day = today.date()
    return sum(
        ri.cost_usd for ri in infos if datetime.fromtimestamp(ri.started_at, UTC).date() == day
    )


class DashboardData:
    """Typed read facade over the scrubbed surface (CRA-252).

    Constructed from an :class:`~crawfish.observe.ObserverSurface` and a
    :class:`~crawfish.deploy.DeployRegistry` — the *interfaces*, already org-scoped and
    scrubbed. It never takes a store class and never reconstructs an un-scrubbed surface, so
    the redaction guarantee (ADR 0011) holds structurally.
    """

    def __init__(
        self,
        surface: ObserverSurface,
        registry: DeployRegistry,
        *,
        store: Store,
        org_id: str = "local",
        budget: BudgetConfig | None = None,
    ) -> None:
        self._surface = surface
        self._registry = registry
        self._store = store
        self._org = org_id
        self._budget = budget

    # -- fleet ---------------------------------------------------------------
    def fleet(self, *, now: float | None = None) -> FleetSnapshot:
        """Deployed-pipeline rows + today's aggregate spend (composed from ``manage_list``)."""
        from crawfish.manage import manage_list

        at = datetime.fromtimestamp(now, UTC) if now is not None else datetime.now(UTC)
        rows = manage_list(self._store, org_id=self._org, now=at)
        fleet_rows = [
            FleetRow(
                pipeline=r.name,
                status=r.status,
                uptime_s=r.uptime_s,
                next_fire=r.next_fire,
                cost_today_usd=r.cost_today_usd,
            )
            for r in rows
        ]
        total = sum(r.cost_today_usd for r in fleet_rows)
        return FleetSnapshot(
            org_id=self._org,
            generated_at=at.timestamp(),
            rows=fleet_rows,
            cost_today_usd=round(total, 4),
        )

    # -- runs ----------------------------------------------------------------
    def runs(self, *, since: str = "-1d", pipeline: str | None = None) -> list[RunCard]:
        """Run cards (newest first) with fan-out progress + the per-run cost band."""
        infos = self._surface.run_info(pipeline, since=since)
        return [self._run_card(ri) for ri in infos]

    def running(self, *, since: str = "-1d") -> list[RunCard]:
        """Just the runs in flight (``status == "running"``) — the herding surface."""
        return [c for c in self.runs(since=since) if c.status == "running"]

    def _run_card(self, ri: RunInfo) -> RunCard:
        """Project one :class:`RunInfo` to a :class:`RunCard` with DONE-count + band."""
        return RunCard(
            run_id=ri.run_id,
            pipeline=ri.pipeline,
            status=ri.status,
            version=ri.version,  # tainted; encoded at render
            items=ri.items,
            done_items=self._done_count(ri.run_id),
            cost_usd=ri.cost_usd,
            budget=self._cost_band(ri),
        )

    def _done_count(self, run_id: str) -> int:
        """Count loop-ledger DONE items for a run via the ledger surface (no SQL ``COUNT``)."""
        from crawfish.ledger import ExecutionLedger

        ledger = ExecutionLedger(self._store, org_id=self._org)
        return len(ledger.completed_items(run_id))

    def _cost_band(self, ri: RunInfo) -> CostBand:
        """Read the run's declared cost interval; degrade to a degenerate band on actual spend.

        The interval is read back through the Store protocol (``get_record``). Absent a stored
        interval the band is the degenerate ``[cost, cost, cost]`` so the view never invents a
        budget; the cost invariant ``total <= expected <= worst_case`` is preserved either way.
        """
        rec = self._store.get_record(_RUN_BUDGET_KIND, ri.run_id, org_id=self._org)
        if rec is None:
            c = ri.cost_usd
            return CostBand(total_usd=c, expected_usd=c, worst_case_usd=c)
        total = float(rec.get("total_usd", 0.0))
        worst = float(rec.get("worst_case_usd", total))
        expected = float(rec.get("expected_usd", worst))
        # Clamp to the invariant so a malformed stored interval can never render inverted.
        expected = min(max(expected, total), worst)
        return CostBand(total_usd=total, expected_usd=expected, worst_case_usd=worst)

    # -- events --------------------------------------------------------------
    def events(
        self, *, since: str = "-1h", kind: str | None = None, pipeline: str | None = None
    ) -> list[ObserverEvent]:
        """Observer events across deployed pipelines (newest first), tainted ``detail`` intact.

        ``detail`` is carried unmodified so the renderer's ``encode_field`` is the single
        encoding chokepoint (UNFILED-XSS). Filtered by the static ``kind`` identifier only.
        """
        pipelines = (
            [pipeline] if pipeline is not None else [e.name for e in self._registry.entries()]
        )
        out: list[ObserverEvent] = []
        for name in pipelines:
            out.extend(self._surface.events(name, since=since, kind=kind))
        out.sort(key=lambda e: e.ts, reverse=True)
        return out

    # -- cost gauge ----------------------------------------------------------
    def cost_gauge(self, *, now: float | None = None) -> CostGauge:
        """Org-scoped aggregate spend vs the ``[budget]`` ceiling (UNFILED-COST).

        Sums **only this org's** ``RunInfo.cost_usd`` for the UTC day (the surface is already
        org-scoped, so org-B rows are structurally absent). ``state`` flips ``ceiling_reached``
        at/over the ceiling — the load-bearing handoff to the HITL/budget gate.
        """
        at = datetime.fromtimestamp(now, UTC) if now is not None else datetime.now(UTC)
        infos = self._surface.run_info()  # this org only
        spent = round(_today_cost(infos, today=at), 4)
        ceiling = self._budget.ceiling_usd if self._budget is not None else None
        # Projected end-of-day from the expected band of in-flight runs: actual + the
        # remaining expected of any running run (worst-case-honest, never undercount).
        projected = spent
        for ri in infos:
            if ri.status == "running":
                band = self._cost_band(ri)
                projected += max(0.0, band.expected_usd - ri.cost_usd)
        projected = round(projected, 4)
        state = "ok"
        if ceiling is not None:
            if spent >= ceiling:
                state = "ceiling_reached"
            elif projected >= ceiling or spent >= ceiling * 0.8:
                state = "warn"
        return CostGauge(
            org_id=self._org,
            ceiling_usd=ceiling,
            spent_today_usd=spent,
            projected_today_usd=projected,
            state=state,
        )
