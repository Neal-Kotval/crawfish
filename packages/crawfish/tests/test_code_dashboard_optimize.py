"""CRA-254 — optimize status + version lineage view.

Seeds a learning lineage (base + promoted winner, then a rollback pointer) and asserts the
rendered pass-rate, per-metric deltas vs baseline, winner sha, stopped_reason verbatim, and the
lineage ordering. Two-org isolation on the lineage read. No live optimizer run.
"""

from __future__ import annotations

from crawfish.code.dashboard.optimize import OPTIMIZE_SCHEMA, optimize_status
from crawfish.definition import Definition
from crawfish.learning import VersionRecord
from crawfish.store import SqliteStore


def _record(
    store: SqliteStore,
    *,
    agent: str,
    sha: str,
    role: str,
    scores: dict[str, float],
    parent: str | None = None,
    active: bool = False,
    org: str = "local",
) -> None:
    rec = VersionRecord(
        agent=agent,
        sha=sha,
        version=f"1.0-{sha}",
        definition=Definition(inputs=[], outputs=[]),
        scores=scores,
        role=role,
        parent_sha=parent,
        active=active,
    )
    store.put_record(f"learning:{agent}", sha, rec.model_dump(mode="json"), org_id=org)


def test_pass_rate_and_metric_deltas_vs_baseline() -> None:
    store = SqliteStore()
    _record(
        store,
        agent="triage",
        sha="0000",
        role="base",
        scores={"pass_rate": 0.88, "f1": 0.80, "cost_usd": 0.05},
    )
    _record(
        store,
        agent="triage",
        sha="a1b2c3d",
        role="promoted",
        parent="0000",
        active=True,
        scores={"pass_rate": 0.92, "f1": 0.84, "cost_usd": 0.04},
    )
    status = optimize_status(store, ["triage"], stopped_reasons={"triage": "max_trials"})[0]
    assert status.last_eval.pass_rate == 0.92
    assert status.last_eval.baseline_pass_rate == 0.88
    assert status.last_eval.metric_deltas["f1"] == 0.04
    assert status.last_eval.metric_deltas["cost_usd"] == -0.01
    assert status.winner_sha == "a1b2c3d"
    assert status.stopped_reason == "max_trials"  # verbatim from the audit row
    store.close()


def test_lineage_promote_then_rollback_ordering() -> None:
    store = SqliteStore()
    _record(store, agent="triage", sha="0000", role="base", scores={"pass_rate": 0.88})
    _record(
        store,
        agent="triage",
        sha="aaa",
        role="promoted",
        parent="0000",
        scores={"pass_rate": 0.90},
    )
    # A later candidate was promoted then rolled back: the active pointer sits on the older one.
    _record(
        store,
        agent="triage",
        sha="bbb",
        role="promoted",
        parent="aaa",
        scores={"pass_rate": 0.85},
    )
    _record(
        store,
        agent="triage",
        sha="aaa",
        role="promoted",
        parent="0000",
        active=True,
        scores={"pass_rate": 0.90},
    )
    status = optimize_status(store, ["triage"])[0]
    events = [e.event for e in status.lineage]
    assert "promote" in events
    assert events[-1] == "rollback"  # the pointer-move rollback is the last edge
    rollback = status.lineage[-1]
    assert rollback.to == "aaa"  # rolled back to the active winner
    store.close()


def test_two_org_isolation_on_lineage() -> None:
    store = SqliteStore()
    _record(store, agent="triage", sha="ax", role="base", scores={"pass_rate": 0.9}, org="a")
    _record(store, agent="triage", sha="bx", role="base", scores={"pass_rate": 0.1}, org="b")
    status_a = optimize_status(store, ["triage"], org_id="a")[0]
    assert status_a.winner_sha == "ax"
    assert status_a.last_eval.pass_rate == 0.9  # org B's 0.1 never appears
    store.close()


def test_optimize_schema_tag() -> None:
    assert OPTIMIZE_SCHEMA == "craw.code.dashboard.optimize.v1"
