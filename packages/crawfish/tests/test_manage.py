"""CRA-152 acceptance: craw manage — list/control deployed pipelines."""

from __future__ import annotations

from datetime import UTC, datetime

from crawfish.deploy import DeployEntry, DeployRegistry
from crawfish.manage import format_table, manage_list, restart_target
from crawfish.observe import ObserverSurface, RunInfo
from crawfish.store import SqliteStore

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_deployed_pipeline_appears_with_status_and_cost() -> None:
    store = SqliteStore()
    DeployRegistry(store).register(
        DeployEntry(
            name="triage-bot",
            pid=999999,  # not alive → reconciled to dead
            dir="/p",
            session="crawfish/triage-bot",
            schedule="0 8 * * *",
            started_at=NOW.timestamp() - 3600,
        )
    )
    surface = ObserverSurface(store)
    surface.put_run_info(
        RunInfo(
            pipeline="triage-bot",
            run_id="r1",
            status="done",
            cost_usd=0.42,
            started_at=NOW.timestamp() - 180,
        )
    )
    rows = manage_list(store, now=NOW)
    assert len(rows) == 1
    row = rows[0]
    assert row.name == "triage-bot"
    assert row.status == "dead"  # PID gone → reflected, not stale "running"
    assert row.last_run_status == "done"
    assert round(row.cost_today_usd, 2) == 0.42


def test_next_fire_shown_for_running_scheduled_pipeline() -> None:
    store = SqliteStore()
    # use this process's own PID so liveness check sees it as running
    import os

    DeployRegistry(store).register(
        DeployEntry(name="p", pid=os.getpid(), dir="/p", session="crawfish/p", schedule="0 8 * * *")
    )
    rows = manage_list(store, now=NOW)
    assert rows[0].status == "running"
    assert rows[0].next_fire == "08:00"


def test_format_table_renders_rows() -> None:
    store = SqliteStore()
    import os

    DeployRegistry(store).register(
        DeployEntry(name="triage-bot", pid=os.getpid(), dir="/p", session="crawfish/triage-bot")
    )
    out = format_table(manage_list(store, now=NOW))
    assert "triage-bot" in out and "STATUS" in out


def test_format_table_empty() -> None:
    assert "no deployed pipelines" in format_table([])


def test_pipeline_with_no_runs_and_no_schedule() -> None:
    import os

    store = SqliteStore()
    DeployRegistry(store).register(
        DeployEntry(name="fresh", pid=os.getpid(), dir="/p", session="crawfish/fresh")
    )
    row = manage_list(store, now=NOW)[0]
    assert row.last_run_status is None  # no runs yet → no crash
    assert row.last_run_ago_s is None
    assert row.next_fire is None  # no schedule → no next fire
    assert row.cost_today_usd == 0.0
    # the table still renders the row with em-dashes for the empties
    assert "fresh" in format_table([row])


def test_restart_redeploys_with_recorded_schedule() -> None:
    store = SqliteStore()
    captured: dict[str, object] = {}

    def fake_spawn(argv: list[str], cwd: object, log: object) -> int:
        captured["argv"] = argv
        return 4242

    DeployRegistry(store).register(
        DeployEntry(name="p", pid=999999, dir="/proj", session="crawfish/p", schedule="*/5 * * * *")
    )
    assert restart_target("p", store=store, spawn=fake_spawn) is True
    entry = DeployRegistry(store).get("p")
    assert entry is not None and entry.pid == 4242
    assert entry.schedule == "*/5 * * * *"  # schedule preserved across restart


def test_restart_missing_returns_false() -> None:
    store = SqliteStore()
    assert restart_target("missing", store=store) is False
