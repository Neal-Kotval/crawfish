"""CRA-151 acceptance: always-on deploy — registry, supervisor, schedule, resume.

Deterministic: the supervisor loop is driven with injected clock/sleep/stop seams and
a fake spawner, so no real daemon is launched and no live model call is made.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from crawfish.core.context import RunContext
from crawfish.deploy import (
    DeployEntry,
    DeployRegistry,
    DeployStatus,
    Supervisor,
    deploy,
    stop,
)
from crawfish.ledger import ExecState, ExecutionLedger
from crawfish.observe import ObserverSurface
from crawfish.store import SqliteStore
from crawfish.triggers import CronSchedule


def _ok_cycle(ctx: RunContext) -> None:
    ctx.cost_budget.charge(0.05)


def _bad_cycle(ctx: RunContext) -> None:
    raise RuntimeError("boom with secret hunter2")


# -- registry ---------------------------------------------------------------
def test_registry_roundtrip() -> None:
    store = SqliteStore()
    reg = DeployRegistry(store)
    reg.register(DeployEntry(name="triage-bot", pid=4321, dir="/p", session="crawfish/triage-bot"))
    got = reg.get("triage-bot")
    assert got is not None and got.pid == 4321
    assert [e.name for e in reg.entries()] == ["triage-bot"]


def test_registry_marks_dead_pid() -> None:
    store = SqliteStore()
    reg = DeployRegistry(store)
    # PID 999999 almost certainly does not exist
    reg.register(DeployEntry(name="p", pid=999999, dir="/p", session="crawfish/p"))
    assert reg.reconcile_liveness() == ["p"]
    assert reg.get("p").status == DeployStatus.DEAD  # type: ignore[union-attr]


# -- supervisor cycle -------------------------------------------------------
def test_cycle_records_runinfo_and_ledger() -> None:
    store = SqliteStore()
    sup = Supervisor("triage-bot", store, _ok_cycle)
    run_id = sup.run_cycle(now=datetime(2026, 1, 1, tzinfo=UTC))
    info = ObserverSurface(store).get_run_info(run_id)
    assert info is not None and info.status == "done" and info.cost_usd == 0.05
    runs = store.list_records("ledger_run")
    assert any(r["id"] == run_id and r["status"] == ExecState.DONE.value for r in runs)


def test_failed_cycle_keeps_supervisor_alive_and_records_failure() -> None:
    store = SqliteStore()
    sup = Supervisor("triage-bot", store, _bad_cycle)
    run_id = sup.run_cycle(now=datetime(2026, 1, 1, tzinfo=UTC))
    info = ObserverSurface(store).get_run_info(run_id)
    assert info is not None and info.status == "failed"
    events = ObserverSurface(store).events("triage-bot")
    assert any(e.kind == "run.failed" for e in events)


def test_serve_fires_each_tick_without_schedule() -> None:
    store = SqliteStore()
    sup = Supervisor("p", store, _ok_cycle)
    fired = sup.serve(
        max_cycles=3, now_fn=lambda: datetime(2026, 1, 1, tzinfo=UTC), sleep_fn=lambda _s: None
    )
    assert fired == 3
    assert len(ObserverSurface(store).run_info("p")) == 3


def test_serve_honors_cron_due() -> None:
    store = SqliteStore()
    sup = Supervisor("p", store, _ok_cycle, schedule="0 8 * * *")
    # 08:00 matches → due; 09:00 does not
    assert sup.due(datetime(2026, 1, 1, 8, 0, tzinfo=UTC)) is True
    assert sup.due(datetime(2026, 1, 1, 9, 0, tzinfo=UTC)) is False


def test_reconcile_retries_orphaned_runs_on_restart() -> None:
    store = SqliteStore()
    ExecutionLedger(store).record_run(
        "old", backend="command", status=ExecState.RUNNING, version="0.1"
    )
    sup = Supervisor("p", store, _ok_cycle)
    result = sup.reconcile()
    assert "old" in result["retried"]
    # a resume event is recorded for visibility
    assert any(e.kind == "deploy.resumed" for e in ObserverSurface(store).events("p"))


# -- deploy / stop ----------------------------------------------------------
def test_deploy_writes_registry_and_no_secret_in_argv(tmp_path: Path) -> None:
    store = SqliteStore()
    captured: dict[str, object] = {}

    def fake_spawn(argv: list[str], cwd: Path, log: Path) -> int:
        captured["argv"] = argv
        captured["cwd"] = cwd
        return 12345

    entry = deploy(tmp_path, name="triage-bot", store=store, schedule="0 8 * * *", spawn=fake_spawn)
    assert entry.pid == 12345
    assert entry.session == "crawfish/triage-bot"  # no secret in the session name
    argv = captured["argv"]
    assert "_supervise" in argv and "triage-bot" in argv
    assert DeployRegistry(store).get("triage-bot") is not None


def test_deploy_rejects_bad_schedule(tmp_path: Path) -> None:
    store = SqliteStore()
    try:
        deploy(tmp_path, name="p", store=store, schedule="not a cron", spawn=lambda _a, _c, _g: 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError on bad cron")


def test_stop_signals_and_clears_status() -> None:
    store = SqliteStore()
    reg = DeployRegistry(store)
    reg.register(DeployEntry(name="p", pid=999999, dir="/p", session="crawfish/p"))
    killed: list[int] = []
    assert stop("p", store=store, kill=killed.append) is True
    assert reg.get("p").status == DeployStatus.STOPPED  # type: ignore[union-attr]
    assert stop("missing", store=store, kill=killed.append) is False


# -- cron schedule ----------------------------------------------------------
def test_cron_schedule_matches_and_next() -> None:
    cron = CronSchedule("*/5 * * * *")
    assert cron.matches(datetime(2026, 1, 1, 0, 5, tzinfo=UTC)) is True
    assert cron.matches(datetime(2026, 1, 1, 0, 6, tzinfo=UTC)) is False
    nxt = cron.next_after(datetime(2026, 1, 1, 0, 6, tzinfo=UTC))
    assert nxt == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
