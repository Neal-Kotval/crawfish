"""CRA-134 acceptance: execution ledger — checkpoints, version pin, reconciliation."""

from __future__ import annotations

from crawfish.ledger import ExecState, ExecutionLedger
from crawfish.store import SqliteStore


def _ledger() -> ExecutionLedger:
    return ExecutionLedger(SqliteStore())


def test_version_pin_survives_redeploy() -> None:
    led = _ledger()
    led.start_pipeline("p1", "0.1")
    # a "redeploy" would create new pipelines on 0.2; the in-flight one stays 0.1
    assert led.pinned_version("p1") == "0.1"


def test_step_checkpoints() -> None:
    led = _ledger()
    led.start_pipeline("p1", "0.1", total_items=3)
    led.checkpoint_step("p1", 0)
    led.checkpoint_step("p1", 2)
    assert led.completed_steps("p1") == {0, 2}


def test_item_cursor() -> None:
    led = _ledger()
    led.mark_item("p1", "a", ExecState.DONE)
    led.mark_item("p1", "b", ExecState.FAILED)
    assert led.completed_items("p1") == {"a"}  # only DONE items count as completed


def test_reconcile_retries_ephemeral_resumes_managed() -> None:
    led = _ledger()
    led.record_run("r1", backend="command", status=ExecState.RUNNING, version="0.1")
    led.record_run("r2", backend="managed", status=ExecState.RUNNING, version="0.1")
    led.record_run("r3", backend="command", status=ExecState.DONE, version="0.1")  # not in-flight

    result = led.reconcile()
    assert result["retried"] == ["r1"]  # claude -p subprocess died with the engine
    assert result["resumable"] == ["r2"]  # managed session can resume
    assert "r3" not in result["retried"] + result["resumable"]
