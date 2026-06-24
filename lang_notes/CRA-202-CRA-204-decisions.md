# CRA-202 (CL-1 Refine) + CRA-204 (CL-4 durable resume) — decision record

Shared owner of `refine.py` (one file, two issues). DoD green: ruff/format/mypy clean,
15 acceptance tests deterministic (scripted charging runtime + RecordReplayRuntime, no live
calls). Integrated to `cra/m-1` (commit 13a2df6). Full suite 817 passed after integration.

### D1 — NodeKind has no "refine" and `core/types.py` is not this issue's to edit  (CRA-202, arch)
**Fork:** add a `REFINE` member to the core `NodeKind` enum (cross-owner edit) vs. reuse an existing kind.
**Decision:** `Refine.kind = NodeKind.AGGREGATOR` (reduce-shaped: many attempts → one chosen Output)
plus a `node_kind_tag = "refine"` class attr for telemetry/CLI.
**Rationale:** one-owner-per-file — Refine must not reach into the core enum module. AGGREGATOR is
semantically honest (fan-in to a single best Output).
**Follow-up:** a later core-owned change should add `NodeKind.REFINE` and flip `kind`. Tracked.
**Spine impact:** none (telemetry tag only).

### D2 — Deterministic Output identity for content-hash-verified resume  (CRA-204, arch+security)
**Fork:** stamp a Refine iteration's `Output.produced_by` with the volatile `Run.id` vs. a deterministic coordinate.
**Decision:** `produced_by = body.content_sha()#visit` (deterministic), NOT `Run.id`.
**Rationale:** a second-process resume must reproduce a bit-identical Output whose content sha matches
the checkpointed reference — only a deterministic coordinate makes resume-verification sound. (Volatile
Run.id was the root cause of 2 initial test failures.)
**Spine impact:** versioning — NEW invariant; changing the coordinate scheme shifts every iteration
Output sha (a migration). Documented in `docs/_changelog/CRA-204.md`.

### D3 — `spent=0.0` (audit Gap #3) closed by reading the shared budget  (CRA-202, arch)
**Fork:** introduce a parallel per-loop meter vs. read the shared `CostBudget`.
**Decision:** charge in concrete runtimes via `ctx.cost_budget.charge(result.cost_usd)`; Refine reports
`spent = budget.spent_usd - spent_at_entry`. Preflight checks `remaining_usd` before each call.
**Rationale:** a single source of truth for spend; no fresh unbounded budget. Overshoot is bounded to one
worst-case call (matches the softened acceptance criterion).
**Spine impact:** cost — Refine now honors the shared budget law (no bypass).

### D4 — Noise-aware no-progress band before F-8 `cw.calibrate` exists  (CRA-202, arch)
**Fork:** block on F-8 calibration vs. ship a parameterized band now.
**Decision:** constructor param `rubric_std` (default 0.0 = exact-improvement required). When F-8/M3
`cw.calibrate` lands, callers pass the calibrated per-step std; NO API change needed.
**Rationale:** keeps the stack moving; forward-compatible seam for the M3 flagship calibrate work.
**Spine impact:** none.

### $0-resume proof (how the live/det gate is satisfied)
`test_crash_then_resume_zero_recompute`: record cassettes on an uninterrupted reference run → simulate a
crash (checkpoints visits {0,1} then dies) → resume with `resume=True` over the SAME ledger. Asserts
`ctx.cost_budget.spent_usd == 0.0` on resume, resumed final Output sha == reference sha,
`completed_visits == {0,1,2}`. Mechanism = deterministic `compute_loop_id` + F-2
`checkpoint_iteration`/`completed_visits` + replay-charges-nothing.
