"""Execution-state ledger + durability reconciliation.

Makes runs/pipelines crash-safe and re-runnable regardless of backend. The ledger
lives in the ``Store``: per-pipeline status + **version pin** + fan-out **item cursor**,
and per-run status tagged with its backend. On restart, :meth:`reconcile` resumes
resumable runs and marks orphaned CommandRuntime (`claude -p`) runs failed→retry —
they die with the engine and must never be silently lost. An in-flight pipeline stays
pinned to the version it started; a redeploy applies to new pipelines only.
"""

from __future__ import annotations

from enum import Enum

from crawfish.store.base import Store

__all__ = ["ExecState", "ExecutionLedger"]


class ExecState(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NEEDS_RETRY = "needs_retry"


# Backends whose sessions die with the engine (cannot be resumed after a crash).
_EPHEMERAL_BACKENDS = {"command", "mock"}


class ExecutionLedger:
    """Store-backed execution state for pipelines, runs, and fan-out items."""

    def __init__(self, store: Store, *, org_id: str = "local") -> None:
        self._store = store
        self._org = org_id

    # -- pipelines ----------------------------------------------------------
    def start_pipeline(self, pipeline_id: str, version: str, *, total_items: int = 0) -> None:
        self._store.put_record(
            "ledger_pipeline",
            pipeline_id,
            {
                "id": pipeline_id,
                "version": version,  # pinned for the life of this pipeline
                "status": ExecState.RUNNING.value,
                "total_items": total_items,
                "completed_steps": [],
            },
            org_id=self._org,
        )

    def pinned_version(self, pipeline_id: str) -> str | None:
        """The version this pipeline started on — unchanged by any redeploy."""
        rec = self._store.get_record("ledger_pipeline", pipeline_id, org_id=self._org)
        return None if rec is None else str(rec["version"])

    def checkpoint_step(self, pipeline_id: str, step_index: int) -> None:
        rec = self._store.get_record("ledger_pipeline", pipeline_id, org_id=self._org)
        if rec is None:
            return
        steps = set(rec.get("completed_steps") or [])
        steps.add(step_index)
        rec["completed_steps"] = sorted(steps)
        self._store.put_record("ledger_pipeline", pipeline_id, rec, org_id=self._org)

    def completed_steps(self, pipeline_id: str) -> set[int]:
        rec = self._store.get_record("ledger_pipeline", pipeline_id, org_id=self._org)
        return set(rec.get("completed_steps") or []) if rec else set()

    def finish_pipeline(self, pipeline_id: str, status: ExecState = ExecState.DONE) -> None:
        rec = self._store.get_record("ledger_pipeline", pipeline_id, org_id=self._org)
        if rec is not None:
            rec["status"] = status.value
            self._store.put_record("ledger_pipeline", pipeline_id, rec, org_id=self._org)

    # -- fan-out item cursor -----------------------------------------------
    def mark_item(self, pipeline_id: str, item_id: str, status: ExecState) -> None:
        self._store.put_record(
            "ledger_item",
            f"{pipeline_id}:{item_id}",
            {"pipeline_id": pipeline_id, "item_id": item_id, "status": status.value},
            org_id=self._org,
        )

    def completed_items(self, pipeline_id: str) -> set[str]:
        return {
            str(r["item_id"])
            for r in self._store.list_records("ledger_item", org_id=self._org)
            if r["pipeline_id"] == pipeline_id and r["status"] == ExecState.DONE.value
        }

    # -- per-run state ------------------------------------------------------
    def record_run(self, run_id: str, *, backend: str, status: ExecState, version: str) -> None:
        self._store.put_record(
            "ledger_run",
            run_id,
            {"id": run_id, "backend": backend, "status": status.value, "version": version},
            org_id=self._org,
        )

    # -- restart recovery ---------------------------------------------------
    def reconcile(self) -> dict[str, list[str]]:
        """Reconcile orphaned state after an engine restart.

        Runs still ``RUNNING`` on an ephemeral backend (their subprocess died with
        the engine) are marked ``NEEDS_RETRY``; resumable-backend runs are left for
        resume. Returns the run ids in each bucket.
        """
        retried: list[str] = []
        resumable: list[str] = []
        for rec in self._store.list_records("ledger_run", org_id=self._org):
            if rec["status"] != ExecState.RUNNING.value:
                continue
            run_id = str(rec["id"])
            if rec["backend"] in _EPHEMERAL_BACKENDS:
                rec["status"] = ExecState.NEEDS_RETRY.value
                self._store.put_record("ledger_run", run_id, rec, org_id=self._org)
                retried.append(run_id)
            else:
                resumable.append(run_id)
        return {"retried": retried, "resumable": resumable}
