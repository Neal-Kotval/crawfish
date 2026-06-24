# Milestone 2 — Composition surface (CRA-205/206/207/208)

Branch `cra/m-2` off `cra/m-1`. Thesis advance: the **cyclic, typed, durable Program graph** —
the structural keystone that Refine (M1) and recurse compose onto. Branch-then-recurse and guarded
loops become representable, typed, and crash-resumable.

## Shared-file resolution (why one owner, not a parallel wave)
The audit hints show all four issues converge on `workflow.py` (+ `executor.py`, `router.py`):
- **CRA-205 C1**: adds a `ROUTER` arm to `Workflow._run_step` (`workflow.py:187`) so Router is a
  runnable branch, not a hand-rolled dispatch that loses budget/taint/checkpoint guarantees.
- **CRA-206 C2a**: cyclic-capable `Program` surface + cyclic `check_types`; `BatchExecutor` currently
  rejects cycles (`executor.py:85-87`). "The structural keystone the durable Refine and recurse
  compose onto."
- **CRA-207 C2b**: per-iteration program-graph versioning + durable resume over the F-2 ledger (the
  durable half of C2; same driver as 206).
- **CRA-208 C3**: `recurse` = a depth-guarded `Program` back-edge re-entering the same frozen
  Definition; "reuses C2's kernel" — a thin delta on the 206 driver (depth bound + per-item depth stack).

Because 205/206/207/208 all edit the same driver, **one owner (`impl-program`)** implements the whole
surface in dependency order: **206 (spine) → 205 (router arm) → 207 (durable resume) → 208 (recurse)**.
This is the correct one-owner-per-file resolution (same as M1's refine.py owning 202+204), not a missed
parallelization. Review (arch+security), docs, and demo remain separate agents/teams.

## Live evidence target (RUNBOOK)
Router branches tickets by type into sub-pipelines; a bounded `recurse` handles multi-part tickets;
back-edges resume durably ($0) after a mid-cycle crash; bit-identical replay.

## Demo extension
`demo/triage-bot`: a Router branches tickets (bug / billing / how-to) into sub-pipelines; a bounded
recurse splits a multi-part ticket and re-enters; a mid-cycle crash resumes at $0.
