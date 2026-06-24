# M3 — Calibration is an irreducible live measurement (replay semantics)

### D — `cw.calibrate` refuses replay; the $0-replay guarantee is for deterministic re-computation only  (arch/thesis)
**Fork (surfaced by the M3 live gate):** the milestone's "bit-identical $0 replay" guarantee
appears to conflict with `cw.calibrate`, which `raise`s `CalibrationError` on a
`RecordReplayRuntime` and therefore makes REAL metered model calls on every `--live` run
(including the "replay" run).

**Decision:** this is CORRECT and load-bearing, not a defect. Calibration MEASURES run-to-run
variance (rubric_std, Brier, ECE, abstention). Replaying canned cassette outputs would report a
fabricated **zero-variance** band — a dishonest measurement that would silently mis-calibrate the
promotion gate (which keys off `rubric_std`). So calibrate refuses replay and re-samples live.

**The precise guarantee:**
- **Replay = $0** for DETERMINISTIC re-computation: scoring, the durable loop, Refine resume,
  recurse resume — these reproduce bit-identical Output shas at $0 on the second run.
- **Calibration is irreducibly live**: it re-measures stochasticity every run. Its cost is folded
  into the demo's structural `worst_case_usd` (132 calls → $7.92 haiku), so the honesty gate holds
  on every run (`total_spend <= worst_case`), and the durable-step resume delta is still exactly $0.

**Why it's thesis-consistent:** the language's determinism guarantee is about *replaying the
deterministic Python around the model call*. The one stochastic primitive (the model call) is only
reproducible when you WANT the recorded value (replay). When the whole point is to QUANTIFY the
stochasticity (calibrate), you must sample it live — recording would defeat the measurement. The
two are not in tension; they are the two halves (eval-replay vs. train-measure).

**Spine impact:** cost/determinism — documents that "$0 replay" is scoped to deterministic
re-computation; calibration is a metered, bounded, honest live measurement. The promotion gate's
variance input is therefore always a real measurement, never a replayed zero.
