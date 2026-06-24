# M2 — `metered>$0` Refine check must tolerate a $0 replay  (found by verifier-m2 final cert)

### D — Apply the Refine metering lower-bound only on a fresh record, never on replay  (demo harness, cost)
**Regression (introduced by the prior liveness fix 9768030, caught by the final live cert):**
`_refine_step_ok()` added `metered = refine_spent_usd > 0.0` for ALL live runs. A `--live` REPLAY
re-pays $0 by design, so `refine_spent_usd == 0.0` on replay ⇒ `metered=False` ⇒ the run FAILS — even
though it reproduces bit-identically. A fresh record PASSES but its own $0 replay FAILS, breaking the
"bit-identical $0 replay still PASSES" guarantee. (Exposed by a `no_progress` draw; the satisfied path
was equally broken.)

**Root cause:** the `>$0` clause conflates "the loop exercised real model calls" (a FRESH-RECORD
property) with "spend is positive on every run" — but $0 is the whole point of replay.

**Fork:**
- A: drop the strict-positive lower bound; rely on `refine_iters >= 1` + `refine_spent_usd <= worst_case`.
- B: thread a record-vs-replay flag into `DemoResult`; require `refine_spent_usd > 0` ONLY on a fresh
  record (real calls), and on replay require only `== 0` is acceptable. Always require `<= worst_case`.
- C: gate `metered` on the backend `_is_replay`.

**Decision:** B (precise, no compromise). Thread the record/replay state into `DemoResult` (the backend
already knows via its `record` flag). The Refine step PASSES when: `refine_iters in [1, max_iters]`,
`refine_spent_usd <= worst_case_usd`, `$0 resume`, justified stop ∈ {satisfied,no_progress,exhausted},
AND (fresh record ⇒ `refine_spent_usd > 0`; replay ⇒ no lower bound). This keeps the Gap-#3
"spent=0.0 metering regression" protection on fresh records while letting a $0 replay pass.
**Rejected:** A loses Gap-#3 protection on fresh records (a real metering regression could slip);
C is equivalent to B but less explicit at the result/assertion layer.
**Spine impact:** cost — the live gate distinguishes "metered real calls" (record) from "free
deterministic replay", which is the correct cost semantics; replay must be exactly $0 and still PASS.

**Test added (required):** a REPLAY case in `test_demo_refine.py` — justified `no_progress` with
`refine_spent_usd == 0.0` and the replay flag set MUST PASS the live gate; a FRESH-record run with
`refine_spent_usd == 0.0` MUST still FAIL (Gap-#3 guard intact). The prior "rejects $0-spend live"
assertion was backwards for the replay path and must be split by record-vs-replay.
