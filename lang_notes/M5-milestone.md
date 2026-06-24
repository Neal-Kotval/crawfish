# Milestone 5 — Surfaces & accuracy (CRA-219/220/221/222)  [completes the flagship slice]

Branch `cra/m-5` off `cra/m-4`. Thesis advance: the operator-facing surface — `craw
eval/tune/refine/learn/guard` drives the whole language from the CLI; an honest cost interval that
sees escalation/repair/retry/refine; live single-flight caching; a deterministic dependency
resolver + lockfile for summoned units. This lights up the last of the flagship slice (the CLI).

## File ownership (one owner per file) + shared-file resolution
- `cli.py` is touched by BOTH 219 (the 5 optimization subcommands) and 222 (the `craw lock`/resolve
  command) → ONE owner (`impl-cli`) does both CLI surfaces. (Same pattern as refine.py/workflow.py.)
- **impl-cost** → `cost.py`, `escalate.py`, `run.py` : **220 OPT-2** honest cost interval — extend
  `CostEstimate` with additive `expected_usd`/`worst_case_usd` that fold escalation/repair/retry/refine
  fan-out (folds the F-6 cost-owner law). `total_usd` unchanged = the lower bound.
- **impl-cache** → `cache.py` : **221 OPT-3** live single-flight caching — an in-process per-key
  `asyncio.Future` map; concurrent identical in-flight callers await ONE computation (coalesce).
- **impl-resolver** → NEW `resolve.py` + `discovery.py` : **222 OPT-4 core** — a pure deterministic
  `resolve(root, registry, *, constraints)` + a lockfile format for summoned units (references-by-
  version). Avoid `definition/types.py` (import-sensitive); keep resolver types in the new module.

## Waves
- **Wave 1 (parallel, disjoint):** impl-cost (220) ∥ impl-cache (221) ∥ impl-resolver (222-core).
- **Wave 2:** impl-cli (cli.py) — **219 OPT-1** five subcommands (eval/tune/refine/learn/guard, each
  `--budget`→CostBudget) binding the shipped M1–M4 primitives + 220's cost + **222 CLI** (`craw lock`
  calling `resolve()`). After Wave 1.

## Live evidence target (RUNBOOK)
Drive the whole flow from `craw`; show single-flight coalescing two identical in-flight calls; show the
honest cost band; commit a lockfile. (Fold the F-6 cost-owner note into OPT-2.)
