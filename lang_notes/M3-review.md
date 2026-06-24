# M3 — Tunable ML library: combined ARCH + SECURITY review (`cra/m-3`)

Reviewer: `review-m3`. Scope: commits `504af34` (CRA-209/211/213) + `b7f52d8`
(CRA-210/212/214 + 209-tune). Reviewed the **committed tip** `b7f52d8` as the merge
candidate; source files read from the committed blobs (see the working-tree note below —
the working tree is NOT the build under review).

## Verdicts

- **ARCH: PASS-WITH-NOTE.** The committed milestone is sound: the definition↔tuner cycle
  is broken honestly (low-dep `crawfish.tune`), the two-axis mode mirrors PyTorch
  (train=CoW/unfrozen, eval=frozen), state_dict transfers by-reference, and the
  promotion/variance/objective machinery composes the F-3/F-8 substrate without
  re-implementing stats. The single NOTE is a **process/hygiene defect, not a code
  defect**: the working tree carries an uncommitted, **broken** experiment that reverts
  the cycle-break. It must not be committed (see B1).
- **SECURITY: PASS.** train→eval is the consequential-Sink boundary and the demo gates it
  fail-closed; no fluid-derived consequential knob exists anywhere in TuneSpec / StateDict
  / seeds; the promotion gate is deterministic over trusted measurements and org-tagged;
  calibration confidence is measured from fluid output, never trusted as instruction.

## BLOCK-level defect

**None in the committed code.**

### B1 (BLOCK if committed — do NOT commit the working tree) — process

The working tree on `cra/m-3` holds **uncommitted** changes that *delete*
`packages/crawfish/src/crawfish/tune.py` and rewrite the cycle-break to a lazy
compile-time `Definition.model_rebuild` in `definition/compiler.py::_ensure_tune_schema`
(with `definition/types.py` switched to a `crawfish.tuner` forward-ref).

- **This state does not import.** `import crawfish` raises
  `pydantic.errors.PydanticUndefinedAnnotation: name 'TuneSpec' is not defined` — the
  field annotation is never resolved before some other model forces the schema to
  completion. Verified by running the interpreter against the working tree.
- It also contradicts the recorded decision `M3-tune-cycle-decision.md` (Option A: extract
  the light value-types) and the committed docstrings/changelog.

**Fix:** discard the working-tree delta (`git checkout -- packages/crawfish/src/crawfish/tune.py packages/crawfish/src/crawfish/definition/types.py packages/crawfish/src/crawfish/definition/compiler.py`)
and merge the committed tip `b7f52d8` as-is. The committed cycle-break is the correct,
documented, importable design. If a future change wants the lazy-rebuild approach, it must
land green (importable + tests) — it currently is not.

## Per-issue invariant confirmations (committed state)

- **CRA-209 (two-axis mode).** `train()` (`tuner.py:170`) returns an unfrozen copy with a
  fresh `Version` (CoW); `eval()` (`tuner.py:183`) is `_refreeze` to `content_sha`,
  idempotent. `guard_consequential` (`tuner.py:195`) raises `FrozenError` unless frozen.
  Axis-1 `tunable` is data on `KnobDomain`; `named_knobs()` yields only `tunable=True`,
  path-sorted (`tune.py:159`). `is_tunable()` refuses unknown/pinned paths. **Confirmed.**
- **CRA-210 (state_dict).** `StateDict` carries knobs + `injected_prompts` + summons as
  `DefinitionRef` by-version (`learning.py:379`), never embedded Definitions; `sha`
  excludes `structure_sha`; `load_state` is CoW via `_refreeze` (`learning.py:520`);
  `strict=True` raises `IncompatibleStateError` on `structure_sha` mismatch, `strict=False`
  loads the role intersection; `only=[…]` filters knob groups. JSON-only. **Confirmed.**
- **CRA-211 (calibrate).** Refuses `RecordReplayRuntime` (`metrics.py:959`); per-run seed
  is `random.Random(f"{base_seed}:{case_id}:{run_index}")` — pure, static, never fluid
  (`metrics.py:734`); Brier primary, ECE diagnostic with equal-mass bins + bootstrap CI;
  records `determinism_tier` and separates `infra_variance_floor`; bounded by budget/cancel
  with a `partial=True` report on ceiling breach; report is frozen + `org_id`-tagged.
  `CalibrationReport.gate_safe(margin)` enforces F-8 (forbids gating when ECE CI is wider
  than the margin; fails safe to `False` without a CI). **Confirmed.**
- **CRA-212 (variance gate).** `promote_against_baseline` (`eval.py:420`) reads baseline +
  parallel `*_std` record; hard gate via `is_regression_variance_aware`, improvement must
  clear `k·std` (`noise_band(alpha)`); `std=0`/no-std reduces byte-for-byte to
  `is_regression` (back-compat — std lives in a separate `eval_baseline_std` record so old
  baselines are untouched); winner's-curse shrink on the promoted scores before they become
  the new baseline; both records `org_id`-tagged. **Confirmed.**
- **CRA-213 (Objective).** `Objective.value = Σwᵢ·scoreᵢ − λ·cost − μ·ece`
  (`tuner.py:315`), cost normalized by `cost_baseline_usd` (λ unit-free), ε-constraint form
  via `feasible`, `pareto` returns the non-dominated front. The hard regression gate
  (`is_regression` vs base) stays non-negotiable; the objective only re-ranks gate-passers
  (`tuner.py:796,807`) — it can never promote a quality regression. `cost_weight=0`
  preserves the legacy winner. **Confirmed.**
- **CRA-214 (explore-rate).** `ServingLoop` routes `ε` by `_explore_hash(item_id, seed)`
  (seeded SHA-256 over the recorded, trusted `item_id` — never fluid, `learning.py:586`);
  `epsilon=0` is a no-op overlay; decaying-ε schedule with reserved UCB1/Thompson hooks;
  ε bounded by `CostBudget`; `graduate()` returns `decided=False` until the pre-registered
  N (`learning.py:719`) — no-peeking controls Type-I error; graduation still funnels through
  the eval gate; decisions carry `org_id` and `explore` tagging. **Confirmed.**

## Cycle-break soundness (committed)

Sound and the architecturally honest choice. `crawfish/tune.py` imports only
`pydantic/json/hashlib/tomllib/collections.abc` — **no crawfish import**, so
`definition.types` importing it introduces no cycle. `tuner.py:46` imports the value-types
from `crawfish.tune` and re-exports them in `__all__`, so
`crawfish.tuner.TuneSpec is crawfish.tune.TuneSpec` holds **by construction** (single
definition, re-export — no isinstance footgun across the seam). `definition/types.py:301`
binds the type at module bottom (after `Definition` is defined) and calls
`Definition.model_rebuild()`, resolving the field before any downstream
`RunRequest.model_rebuild` forces schema completion. The `TYPE_CHECKING` line
(`def_types.py:26`, `from crawfish.tuner import …`) and the runtime import
(`def_types.py:301`, `from crawfish.tune import …`) resolve to the same object — consistent,
not a defect.

## Required confirmations (brief)

- **tune hash-neutral-when-empty:** CONFIRMED. `content_dict` does `payload.pop("tune", None)`
  then folds `tune_spec_sha` **only** when `self.tune is not None and self.tune.knobs`
  (`def_types.py:222-226`). Demo lock unchanged: `demo/triage-bot/definition.lock` =
  `0.1-7113bfa78543`.
- **single TuneSpec class:** CONFIRMED (committed). One definition in `crawfish.tune`,
  re-exported by `crawfish.tuner`; identity holds by construction. (FALSE in the broken
  working tree, where `crawfish.tune` does not exist — see B1.)
- **train≠eval consequential boundary holds:** CONFIRMED. `guard_consequential` raises on a
  non-frozen Definition; the demo's `_fire_sink` (`self_improve.py:1417`) independently
  refuses to fire on a non-frozen Definition (fail-closed), and only fires after step 8
  freezes the winner. Universal sink-egress wiring of `guard_consequential` is correctly
  deferred to M-S (D-M3-3 / task #14) — the guard exists and the demo gates it.
- **no fluid-derived consequential knob:** CONFIRMED. TuneSpec `KnobValue` is a narrow
  static scalar; StateDict `RoleKnobs` (model/policies/decode) are static author config;
  summons are by-version refs; calibrate + explore seeds derive only from
  `base_seed`/`item_id`/`case_id`/index — all trusted/static, never a fluid value.
- **promotion gate deterministic + org-isolated:** CONFIRMED. `promote_against_baseline`
  and `Tuner` acceptance are pure arithmetic over recorded scores/std (same inputs ⇒ same
  verdict); baseline, std, and lineage records all carry `org_id`.

## Decision

The **committed** M3 (`b7f52d8`) is **mergeable** on both ARCH and SECURITY axes. The only
action required before merge is to **discard the broken, uncommitted working-tree delta
(B1)** and confirm `import crawfish` + `pytest` are green on the clean committed tree (the
working tree currently fails to import). No source edits are needed.
