# Release notes

Notable, user-facing changes. For the exact public-symbol surface of any release, see the
[API reference](api-reference.md); for the longer arc, see the [Roadmap](../roadmap/README.md).

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
