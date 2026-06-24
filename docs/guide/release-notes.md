# Release notes

Notable, user-facing changes. For the exact public-symbol surface of any release, see the
[API reference](api-reference.md); for the longer arc, see the [Roadmap](../roadmap/README.md).

## Agent language — Milestone 3: the tunable-ML library

The **flagship** half lands: an agent is now a *model with tunable weights*, and `mutable` is
the train/eval switch. Crawfish gains the PyTorch-for-LLMs surface — measure run-to-run noise,
search the knob space under a cost-regularized objective, promote only past that noise, and
transfer the learned weights — without giving up a single determinism, typing, or versioning
guarantee. New, all importable from the top-level `crawfish` package:

- **`train()` / `eval()` / `guard_consequential()`** — the two-axis mode unifier. *Which*
  knobs may move (Axis 1, `tunable`) and *whether* the artifact is sealed (Axis 2, mode) are
  now orthogonal, mirroring PyTorch's `requires_grad` vs `.eval()`. `train(d)` is an unfrozen,
  copy-on-write training copy; `eval(d)` re-freezes via the content hash (so `eval(train(d))`
  is idempotent). `guard_consequential(d)` is the load-bearing gate: **a Sink write or a
  recorded run is eval-only** — a training artifact has no stable identity to key idempotency.
- **`TuneSpec` / `KnobDomain` / `tune_spec_sha`** — the tunable knob space as *data*, authored
  as `tune.toml` and folded into the Definition's content hash. **Changing the search space
  versions the agent** (an empty `tune.toml` stays hash-neutral). Pinned knobs (`tunable=False`)
  are never proposed.
- **`calibrate(...) → CalibrationReport`** — runs each golden case `runs` times under distinct
  derived seeds and reports the **noise band** (`rubric_std`), structural `output_variance`,
  Brier / ECE-with-CI calibration, a reliability curve, and an **evidence-derived**
  `abstention_threshold`. Refuses a replay runtime (it would fabricate zero variance) and
  honours the autonomy ceiling (`partial=True` on a budget/cancel breach). `extract_confidence`
  / `abstention_threshold` (in `crawfish.escalate`) replace the old guessed escalation constant
  with one read off measurements.
- **`Objective` / `ObjectiveForm` / `ObjectiveScore`** — a cost-regularized loss
  (`Σ wᵢ·scoreᵢ − λ·cost − μ·ece`) the Tuner maximizes **only among candidates that already
  pass the hard regression gate**, so cost can break a tie or veto a marginal gain but can
  **never** promote a quality regression. `cost_weight=0` reproduces today's winner; an
  ε-constraint form and a Pareto mode are available.
- **`promote_against_baseline(...) → PromotionVerdict`** — the variance-aware promotion gate:
  promote only when the primary gain **clears the noise band** (`k·std`) *and* no metric
  regresses past its own band. Reduces byte-for-byte to the single-point gate when no `std` is
  recorded, so every existing baseline keeps working. `save_baseline_from_report` /
  `load_baseline_std` carry the band; a `fresh_sample` corrects the winner's curse.
- **`state_dict()` / `load_state()` / `StateDict` / `RoleKnobs`** — the architecture/weights
  split (*Hugging-Face-for-agent-weights*). Extract the tunable knobs as JSON-only weights
  (per-role knobs, coordination choice, few-shots, summons as references-by-version — **no**
  architecture, **no** embedded Definition) and transfer them onto a sibling of the same shape.
  `strict=True` refuses a shape mismatch (`IncompatibleStateError`); `strict=False` loads the
  intersection; `only=[...]` transfers named groups. Copy-on-write — a new frozen artifact.
- **`ServingLoop` / `ExploreSchedule` / `ExploreStrategy`** — the serving-time explore dial.
  Routes `(1-ε)` of live items to the promoted best and `ε` to a trial candidate, choosing
  *which* items explore by a seeded hash of the recorded `item_id` (a replay re-explores
  exactly the same items). Decaying-ε, budget-bounded, and `graduate`s only after a
  **pre-registered sample size** (no peeking) and only through the eval gate. **Only static
  knobs are ever promoted** — the learning loop stays inside the security spine.

Learn it: the [Train, calibrate & promote guide](train-and-tune.md) (runnable, mirrors the
triage demo) and the [Concepts → PyTorch-for-LLMs half](concepts.md#the-pytorch-for-llms-half-train-eval-and-the-tunable-knob).

## Agent language — Milestone 2: the composition surface

The control plane gains *shape*. Agent work that branches, cycles, and recurses is now a
typed, durable graph — bounded, taint-tracked, and crash-resumable for **\$0**. New, all
importable from the top-level `crawfish` package:

- **`branch(classifier, branches)`** — makes a `Router` a first-class, **runnable**
  composition step: each item is classified and dispatched through the same step machinery
  as its branch, so a branch may be a `Sink`/`Batch`/`Filter`/`Aggregator` and inherits
  the identical budget / taint / checkpoint guarantees. The label set is closed and
  totality-checked at construction; `check_types` verifies every branch accepts the
  upstream output.
- **`Program`** — a `Workflow` whose **edges may cycle**. Register nodes with `.step(...)`,
  wire directed edges with `.edge(...)`; a back-edge re-enters its region while a guard
  predicate holds. Every traversal is a content-addressed version transition (no in-place
  mutation), metered into one shared `CostBudget`, with taint carried across every edge.
  Cycles are bounded by `max_visits` / budget / cancel / calibrated no-progress — **never
  wall-clock** — and a back-edge with no `max_visits` raises **`UnboundedCycleError`** at
  assembly. `Edge`, `ProgramResult` (`output`, per-edge `visits`, `stopped` reason).
- **Durable `$0` resume for cycles** — pass a shared `Store` and `resume=True`, and a
  `Program` that crashes mid-iteration re-derives the committed iterations at `$0`. Resume
  is content-hash *verified*: each iteration's `produced_by` is the deterministic
  `{region_version}#{edge_id}#{visit}` coordinate, so the replay reproduces the checkpoint
  bit-for-bit. Every ledger row carries `org_id`.
- **`recurse(body, *, base_case, max_depth, combine)`** — bounded self-referential
  invocation: a depth-guarded back-edge re-entering the same **frozen** `Definition`,
  folding the descent-order children with an existing reducer. `max_depth` is mandatory
  (**`UnboundedRecursionError`** otherwise) and the whole-tree shared budget guards the
  `O(b^d)` fan-out; a fold **never launders taint** (the reduced Output is tainted if any
  child input was). `Recurse`, `RecurseResult` (`output`, `depth_reached`, `stopped`).

Learn it: the [Compose guide](compose.md) (runnable, mirrors the triage demo's
branch-by-type and bounded recurse) and the [Concepts → composition
surface](concepts.md#the-composition-surface-branch-cycle-recurse).

## Agent language — Milestone 1: the control plane

The first headline operators of the [agent language](../roadmap/README.md#milestone-1-the-control-plane-shipped)
land: a bounded, metered, durable **iterate-until-goal** loop, gated by a critic that has
to *earn* the authority to stop it. New, all importable from the top-level `crawfish`
package:

- **`Refine`** — run a producing `Definition`, check each frozen `Output` against an
  external `StopCondition`, and iterate until satisfied or a bound is hit (`max_iters`,
  the shared `CostBudget`, cooperative cancel, or noise-aware no-progress — never
  wall-clock). It mutates nothing and folds the three fixed-bound re-run atoms
  (`EscalatingRuntime`, `Run._repair`, `RetryPolicy`) into one goal-driven operator.
  `RefineResult` reports the real `spent_usd`, the iteration count, and why the loop
  stopped. `feature_loop(...)` is a keyword-only alias.
- **Stop conditions** — `RubricThreshold` (a metric clears `at_least`), `PredicateStop`
  (a typed predicate), and `VerifierStop` (a gated critic accepts). Building a `Refine`
  whose critic shares the body's content hash is rejected: the generator may never
  critique itself.
- **`Verifier`** — a critic over a closed label set with a mandatory `default`. Gating
  authority is **typed**: a bare `Verifier` is in `WARN`/`SHADOW` and cannot stop a loop.
  `Verifier.gated(...)` is the only path to a `GatedVerifier` (stage `BLOCK`), and it
  **fails closed** — a never-benchmarked critic, or one below `min_precision` against a
  decision `GoldenSet`, raises `VerifierNotGated` rather than being trusted to block
  production. `Verdict` carries taint forward; `VerifierStage` is the
  `SHADOW`→`WARN`→`BLOCK` lifecycle.
- **`$0` crash-resume for loops** — pass an `ExecutionLedger` and `resume=True`, and a
  `Refine` loop that crashes mid-iteration restarts at the next iteration re-paying `$0`.
  Resume is content-hash *verified*: each iteration's `produced_by` is the deterministic
  `body.content_sha()#visit` coordinate, so the replayed Output reproduces the checkpoint
  bit-for-bit. Every ledger row carries `org_id`, so a cross-tenant resume is isolated.

Learn it: the [Refine & verify guide](refine-and-verify.md) (runnable, mirrors the triage
demo) and the [control-plane reference](../reference/refine-and-verify.md).
