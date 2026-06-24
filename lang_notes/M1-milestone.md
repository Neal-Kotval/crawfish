# Milestone 1 — Control plane (CRA-202, 203, 204)

Branch `cra/m-1` off `main` (F is on main). Thesis advance: the **bounded, metered, durable
loop** becomes the easy path — Refine replaces hand-rolled `while` loops that bypass
`CostBudget`, lose checkpointing, and mis-report `spent=0.0`.

## Wave plan + shared-file resolution
- **Coupling:** CL-1 Refine (202) is *verifier-gated* — it consumes CL-2 Verifier (203). CL-4
  (204) fills the `Refine._checkpoint` stub from 202 → **shares `refine.py` with 202**.
- **Resolution of the shared file `refine.py`:** one owner. A single implementer owns `refine.py`
  and closes BOTH CRA-202 and CRA-204 (CL-1 surface + CL-4 durable checkpoint). This is the
  correct application of one-owner-per-file when two issues touch the same module.
- **Order (sequential — milestone is inherently coupled):**
  - W1: `impl-203` → `verifier.py` (defines the gated critic / stop signal).
  - W2: `impl-refine` → `refine.py` (CRA-202 + CRA-204), consuming Verifier + the F-2 composite
    ledger (`ledger.py`) + `runtime/replay.py` for durable, crash-resumable, $0-resume loops.
- Each issue is reviewed by paired **architecture** + **security** specialist agents before
  integration; their forks land in `CRA-<n>-decisions.md`.

## Live evidence target (RUNBOOK)
Triage agent refines a draft reply until the Verifier passes; kill mid-loop and resume for **$0**;
budget respected; bit-identical replay of freshly recorded cassettes.

## Demo extension
`demo/triage-bot` gains a Refine step: draft → Verifier critic → iterate-until-goal under a
CostBudget, with per-iteration ledger checkpoints. Deterministic test off cassettes + `--live`.
