# M2 — Demo pass-criterion must accept a justified Refine no_progress/exhausted (live variance)

### D — `passed()` accepts a justified bounded Refine outcome, not only "satisfied"  (demo harness, cost/control-flow)
**Fork (found by verifier-m2 while certifying the recurse fix):** `DemoResult.passed()`
(`self_improve.py:174`) requires `refine_stopped == "satisfied"`. Under real-model variance the
verifier-gated Refine can legitimately stop on `no_progress`/`exhausted` within budget (the real
haiku critic didn't accept within `max_iters`). That is the operator behaving CORRECTLY, yet the
demo failed the whole live run — so `craw demo --live` PASS was non-deterministic (passed on some
fresh records, failed on others purely by critic draw). Recurse is NOT affected (deterministic
base_case on authoritative depth).

**Options:**
- A: accept a JUSTIFIED Refine stop — `refine_stopped ∈ {satisfied, no_progress, exhausted}` AND the
  bound held (`iters <= max_iters`) AND spend was metered and within budget. A crash / unbounded /
  budget-blown outcome still FAILS.
- B: tune the seed ticket / rubric so a real haiku critic reliably accepts within the bound.
- C: leave it (live PASS stays flaky).

**Decision:** A. The demo proves the *operator* is a bounded, metered, durable loop — not that a
stochastic critic always accepts. Whether the critic accepts within N tries is model-dependent; the
operator's correctness is that it stops for a legitimate reason within its bound. This is EXACTLY
the precedent already set for the F-3 gate step (the live gate accepts a justified *reject* under
real variance as a valid outcome). Making the criterion outcome-shape-based (not "the model
succeeded") is the honest, deterministic choice.
**Rejected:** B is brittle (re-flakes if the model drifts) and hides the real property; C abandons a
reproducible live gate.
**Spine impact:** cost/control-flow — the live gate now certifies the OPERATOR's correctness
(bound + honest metering + legitimate stop), consistent across gate/refine; it does not conflate
"operator worked" with "model happened to satisfy the critic."

**Guardrail:** the deterministic demo still yields `satisfied` (mock critic accepts), so the
deterministic test is unchanged; only live variance now lands a deterministic PASS. A genuinely
broken Refine (error / unbounded / overspend) still FAILS.
