"""``craw manage`` — see & control running pipelines (CRA-152).

A single view over every deployed pipeline, joining three Store-backed sources: the
**deploy registry** (CRA-151, name/pid/session/schedule), the **execution ledger**
(CRA-134, run state), and the **run-info surface** (CRA-154, last run / cost today).
Control verbs (``stop`` / ``restart`` / ``logs``) act through the same registry.

Dead-process detection runs on every read: a registry row whose PID is gone is
reported ``dead`` so the operator sees reality, not a stale ``running``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from crawfish.deploy import DeployRegistry, DeployStatus
from crawfish.observe import ObserverSurface, RunInfo

if TYPE_CHECKING:
    from crawfish.deploy import Spawner
    from crawfish.store.base import Store

__all__ = ["PipelineStatus", "manage_list", "restart_target", "format_table"]


class PipelineStatus(BaseModel):
    """A row in ``craw manage``: a deployed pipeline joined with its run state."""

    name: str
    status: str  # running | stopped | dead
    pid: int
    schedule: str | None = None
    uptime_s: float = 0.0
    last_run_status: str | None = None
    last_run_ago_s: float | None = None
    next_fire: str | None = None
    cost_today_usd: float = 0.0
    log_path: str = ""
    runs: list[RunInfo] = Field(default_factory=list)


def _today_cost(infos: list[RunInfo], *, today: datetime) -> float:
    day = today.date()
    return sum(
        ri.cost_usd for ri in infos if datetime.fromtimestamp(ri.started_at, UTC).date() == day
    )


def manage_list(
    store: Store, *, org_id: str = "local", now: datetime | None = None
) -> list[PipelineStatus]:
    """Build the management view for every deployed pipeline.

    Reconciles liveness first (marks dead PIDs), then joins each registry entry with
    its run-info history for uptime, last run, next fire, and today's spend.
    """
    now = now or datetime.now(UTC)
    registry = DeployRegistry(store, org_id=org_id)
    registry.reconcile_liveness()
    surface = ObserverSurface(store, org_id=org_id)

    rows: list[PipelineStatus] = []
    for entry in registry.entries():
        infos = surface.run_info(entry.name)  # newest first
        last = infos[0] if infos else None
        next_fire: str | None = None
        if entry.schedule and entry.status == DeployStatus.RUNNING:
            from crawfish.triggers import CronSchedule

            next_fire = CronSchedule(entry.schedule).next_after(now).strftime("%H:%M")
        rows.append(
            PipelineStatus(
                name=entry.name,
                status=entry.status.value,
                pid=entry.pid,
                schedule=entry.schedule,
                uptime_s=max(0.0, now.timestamp() - entry.started_at),
                last_run_status=last.status if last else None,
                last_run_ago_s=(now.timestamp() - last.started_at) if last else None,
                next_fire=next_fire,
                cost_today_usd=_today_cost(infos, today=now),
                log_path=entry.log_path,
                runs=infos,
            )
        )
    return rows


def restart_target(
    name: str,
    *,
    store: Store,
    org_id: str = "local",
    spawn: Spawner | None = None,
) -> bool:
    """Stop then re-deploy ``name`` with its recorded dir + schedule. Returns success."""
    from crawfish.deploy import deploy, stop

    registry = DeployRegistry(store, org_id=org_id)
    entry = registry.get(name)
    if entry is None:
        return False
    stop(name, store=store, org_id=org_id)
    deploy(
        entry.dir,
        name=name,
        store=store,
        schedule=entry.schedule,
        backend=entry.backend,
        spawn=spawn,
        org_id=org_id,
    )
    return True


def _fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h{int((seconds % 3600) // 60)}m ago"
    return f"{int(seconds // 86400)}d ago"


def _fmt_uptime(seconds: float) -> str:
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h{int((seconds % 3600) // 60)}m"
    return f"{int(seconds // 86400)}d"


def format_table(rows: list[PipelineStatus]) -> str:
    """Render the management view as a fixed-width table (``craw manage``)."""
    if not rows:
        return "no deployed pipelines (use `craw deploy`)"
    header = f"{'NAME':<14}{'STATUS':<9}{'UPTIME':<8}{'LAST RUN':<12}{'NEXT':<8}{'$TODAY':>7}"
    lines = [header]
    for r in rows:
        last = f"{r.last_run_status or '—'} {_fmt_age(r.last_run_ago_s)}".strip()
        lines.append(
            f"{r.name:<14}{r.status:<9}{_fmt_uptime(r.uptime_s):<8}"
            f"{last:<12}{r.next_fire or '—':<8}{f'${r.cost_today_usd:.2f}':>7}"
        )
    return "\n".join(lines)
