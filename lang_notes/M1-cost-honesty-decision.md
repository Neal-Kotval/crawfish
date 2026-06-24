# M1 — Cost-honesty gate fix (F-6 cost-owner law)  (found by verifier-m1 live gate)

### D — Bind the demo hard-kill to the honest worst-case  (demo harness, cost/spine)
**Fork (real defect, caught live, not papered over):** the demo's honesty invariant
`total_spend_usd <= worst_case_usd` ($2.70) diverged from the `CostBudget.limit_usd` hard-kill
($3.00). Once the Refine step was added, the true worst case rose (~49 metered calls ≈ $2.46;
a high-variance live run exceeded $2.70 while still under $3.00). That `($2.70, $3.00]` window
made the gate **flaky under real-model variance** — under budget yet asserting FAIL.

**Options:**
- A: raise `worst_case_usd` to a true upper bound (incl. Refine `max_iters` drafts + critic call
  per iteration + step-7 sweep) AND set `CostBudget(limit_usd=worst_case_usd)` so kill==assertion.
- B: just raise `worst_case_usd` to the full $3.00 budget (loosens the honesty claim).
- C: relax the assertion to `<= limit_usd` (abandons the honest worst-case claim entirely).

**Decision:** A. The honest worst case IS the budget; a complete run must finish ≤ worst_case by
construction, and the hard-kill at the same value is belt-and-suspenders that only fires on a
cost-model bug. Eliminates the flake window without weakening the honesty claim.
**Rejected:** B/C weaken the thesis's cost-honesty story (the whole point of F-6 is that the
advertised worst case is a real, enforced upper bound, not a loose budget).
**Spine impact:** cost — reasserts the F-6 cost-owner law: advertised worst_case is enforced,
and the bound is composition-aware (it now includes the Refine operator's fan-out).
**Live evidence (verifier-m1):** core M1 items all ✅ — refined reply real; verifier gated the
loop (accept point varied iter1↔iter4 under real variance); $0 resume; tenant isolation;
bit-identical replay (shas 9dfc8be045b2 / d9b59d63c276 / f34b4de5990a). Only the cost-honesty
assertion was flaky; fixed by D above.
