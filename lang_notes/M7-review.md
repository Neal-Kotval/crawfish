# M7 Review — Revolutionary capabilities (CRA-228 / 229 / 230)

Reviewer: `review-m7` (combined ARCH + SECURITY). Branch `cra/m-7`, commit `a2fae9d`.
Scope: `agentdiff.py`, `prove.py`, `replay_swap.py`, `cli.py` (replay/prove), test files.

---

## Verdicts

| Axis | Verdict |
|------|---------|
| **ARCH** | **PASS-WITH-NOTE** |
| **SECURITY** | **PASS-WITH-NOTE** (one BLOCK-candidate downgraded to NOTE — see S-1) |

No hard BLOCK. The ALG-3 prove check **fails closed** as required, the merge boundary is
**not silently widened in the two-sided case**, and replay `--swap` is **budget-bounded**
(over-budget refused before any spend). One genuine semantic gap (S-1) on the *one-sided*
fluid-widening merge case is flagged below and should be tracked into M8/S, not a stack blocker.

---

## CRA-228 — git-for-agents diff/merge (`agentdiff.py`)

**Invariant:** diff/merge pure & deterministic over content-addressed Definitions; conflicts
typed, never silent; clean merge → new frozen sha; fluid/static boundary never silently widened.

**ARCH — PASS.**
- `diff` / `merge` are pure: they read `content_dict()` only, no I/O, no clock, no model call
  (`agentdiff.py:219`, `:250`). Diff is non-empty **iff** the sha moved — it diffs the exact
  canonical hash payload (`_flat_payload` over `content_dict`), so the iff-claim holds.
- Determinism: every iteration is over `sorted(...)` keys; `_member_order` rebuild order is
  deterministic (longest-side spine + first-seen union). One latent non-determinism risk:
  `_member_order` uses `max(sides, key=len)` (`agentdiff.py:421`) — on a length tie `max`
  returns the *first* max, and the side order is fixed `(base, a, b)`, so it is deterministic.
  OK, but the determinism rests on that fixed tuple order; worth a one-line comment pin.
- Conflicts are typed and returned (not raised), carrying the **full** path-sorted conflict set
  (`MergeConflict.conflicts`), never the first-only — matches "all of it at once."
- Clean merge re-validates through `Definition.model_validate` then `derive.refreeze` off
  `base` (`_rebuild`, `:317`), so the result is a freshly-frozen, content-addressed, on-lineage
  Definition. No in-place mutation path exists. PASS.

**SECURITY — PASS-WITH-NOTE.**
- Two-sided divergence on a `flow` leaf → `FieldConflict`, never auto-resolved
  (`merge` else-arm `:291`; test `test_merge_surfaces_a_flow_collision_rather_than_auto_applying`).
  The fluid/static boundary cannot be quietly flipped when both sides touch it. Good.
- **S-1 (NOTE, track to M8/S — do not block).** A **one-sided** `static → fluid` widen is
  applied silently with no conflict and no special-casing. `merge`'s "changed on exactly one
  side ⇒ that side wins" rule (`:285`) treats a flow widen like any other field, and the test
  `test_merge_flow_widen_applies_only_one_sided` (`test_agentdiff.py:260`) **asserts** the
  widened `Flow.FLUID` lands. The team-lead invariant "merge never widens fluid/static" is only
  upheld for the *contested* case. `_is_flow_path` (`agentdiff.py:213`) is defined as "the
  explicit security pin" but is **dead code** — it is never called by `merge`, so the pin it
  documents (surface a flow move even when one-sided) is not actually wired.
  - Why it is a NOTE not a BLOCK: the merged artifact is re-frozen and must still pass the
    runtime spine + `prove --no-injection` before it can wire a fluid value into a static sink,
    so the widen is caught downstream (defense-in-depth invariant 11). But a *merge* that widens
    the injection boundary without surfacing it defeats the "PR-reviewable diff" thesis — a
    reviewer merging "B's unrelated change" silently inherits A's boundary widen.
  - **Fix:** call `_is_flow_path(path)` in the one-sided arms of `merge`; when a one-sided change
    moves a `.flow` leaf toward `fluid` (widen), surface it as a `FieldConflict` (or a distinct
    `BoundaryWiden` advisory) rather than auto-applying. Narrowing (fluid→static) stays clean.
    Update `test_merge_flow_widen_applies_only_one_sided` to expect the surfaced conflict.

---

## CRA-229 — `craw prove --no-injection` (`prove.py`)

**Invariant:** ships the ALG-3 **conservative fail-closed** static rejection; the sound proof is
correctly deferred; the check must FAIL CLOSED, never assume safe.

**SECURITY — PASS.** This is the load-bearing M7 security item and it is honest.
- Module docstring and `GUARANTEE = "alg3-conservative-static-rejection"` (`prove.py:49`) name
  exactly which guarantee shipped; the sound full-graph proof is explicitly deferred/flagged
  (HARD-BLOCKERS.md, CRA-229.md). No overstatement — `ProofResult.guarantee` is carried into the
  CLI JSON so no downstream caller can mistake it for the sound proof.
- **Fails closed.** A consequential output mis-declared `Flow.FLUID` is recorded as an
  **undischarged** obligation + a `violation` (`prove.py:190`), forcing `proven=False` and a
  non-zero CLI exit (`cli.py` `_cmd_prove` returns `1` when not proven). The docstring's claim
  "anything it cannot prove safe ... is reported, never assumed safe" matches the code: the only
  path to `proven=True` is an **empty violation set**, and a fluid output cannot be proven
  non-consequential, so it is flagged. Test `test_fluid_output_slot_fails_closed` confirms.
- Defense-in-depth: docstring is explicit it never replaces `StaticOnlyError` /
  `TargetMustBeStaticError`; it is a pre-flight gate. Correct framing per invariant 11.

**ARCH — PASS-WITH-NOTE.**
- The check is sound for the fragment it covers (declared `Flow.STATIC` slots cannot, by type,
  carry a fluid value — the wire-time gate enforces it) and incomplete by construction, which is
  the honest framing the issue demands.
- **N-1 (minor).** `prove_no_injection` takes `definition: object` and reads fields via
  `getattr(..., None)` (`prove.py:98`, `:107`, `:158`). This is duck-typed rather than typed
  against `Definition`; a Definition whose `inputs`/`outputs` attribute were renamed would
  silently range over an **empty** surface and vacuously "prove." Low risk (the type is stable
  and tests pin the real `Definition`), but tightening the annotation to `Definition` would make
  the fail-closed property robust against a future field rename. Not a blocker.

---

## CRA-230 — `craw replay --swap` (`replay_swap.py`)

**Invariant:** clean leaves replay $0 bit-identical; only swapped leaf differs; cost-bounded
cascade refuses over-budget; org-isolated; no surprise live spend.

**ARCH — PASS.**
- Clean leaf ⇒ `counterfactual == original` byte-for-byte, `cost_usd=0.0`, no model call
  (`replay_swap.py:188`). Test `test_clean_leaves_replay_bit_for_bit`. A leaf is dirtied **iff**
  recorded `RunResult.model == swap.frm` (`plan_swap:142`) — pure, offline change detection.
- Determinism: counterfactual is sourced from `alt_cassette_dir` (a recorded `to` run) or a
  deterministic `model_copy(update={"model": swap.to})` re-stamp (`:208`); no live call on the
  test path. `test_swap_is_deterministic` covers it.
- CLI orchestrates, does not reimplement: `_cmd_replay` parses, calls `run_swap`, formats
  (`cli.py`). The cost/dirty logic lives entirely in `replay_swap.py`. Good seam.

**SECURITY — PASS-WITH-NOTE.**
- **Budget bound — PASS.** Projected live spend (`dirtied * live_cost_usd`) is computed and
  compared to `budget_usd` **before** spending; over-budget returns `over_budget=True`,
  `spent_usd=0.0`, `deltas=()` — **no counterfactuals computed, no live call**
  (`run_swap:172`). CLI exits non-zero on refusal (`_cmd_replay`). Tests
  `test_over_budget_cascade_is_refused` + `test_cli_replay_over_budget_exits_nonzero` confirm.
  No surprise live spend: live cost is only ever incurred on the no-alt re-stamp path, and even
  that is `live_cost_usd`-gated and budget-checked first. Boundary is strict `>` (exactly-at-
  budget passes) — acceptable and conventional.
- **N-2 (NOTE) — org isolation is by convention, not enforced.** The docstring claims
  `org_id` is folded onto every cassette key (F-1) so "a counterfactual never reads another
  org's leaves." But `run_swap` / `_load_cassettes` (`:127`) glob **every** `*.json` in the
  passed `cassette_dir` with no org filter, and the CLI `--org` is only stamped onto the report
  header (`cli.py` payload `"org"`) — it does **not** scope which directory is read. Isolation
  therefore depends entirely on the caller pointing `--cassettes` at an already-org-scoped dir.
  Within the F-1 layout (org folds into the on-disk key/path) this holds, but nothing in this
  module *enforces* it — a caller pointing at a cross-org dir would happily swap foreign leaves.
  - **Fix (track, non-blocking):** either filter `_load_cassettes` by an `org_id` parameter
    derived from the RunContext, or assert the cassette dir's org-scope prefix matches `--org`.
    At minimum add a test that a cassette whose key carries a different org is excluded.

---

## Summary of actionable items

| ID | Axis | Severity | Item | Fix |
|----|------|----------|------|-----|
| S-1 | SEC/ARCH | NOTE (track M8/S) | One-sided `static→fluid` merge widen applied silently; `_is_flow_path` is dead code | Wire `_is_flow_path` into `merge`'s one-sided arms; surface widen as conflict; narrowing stays clean (`agentdiff.py:213`,`:285`) |
| N-2 | SEC | NOTE | replay `--swap` org isolation is by-convention; `--org` not used to scope reads | Filter `_load_cassettes` by org / assert dir org-scope; add cross-org exclusion test (`replay_swap.py:127`) |
| N-1 | ARCH | minor | `prove_no_injection` duck-types `definition: object` via getattr | Annotate as `Definition` so a field rename can't vacuously "prove" (`prove.py:125`) |
| (note) | ARCH | trivial | `_member_order` determinism rests on fixed `(base,a,b)` tuple + `max` first-wins | One-line comment pin (`agentdiff.py:421`) |

**Confirmations requested by team-lead:**
- prove **fails closed**: YES — only an empty violation set yields `proven=True`; a fluid
  consequential output is flagged, non-zero exit. The sound proof is correctly deferred/flagged.
- merge **boundary-safe**: YES for the two-sided contested case (typed conflict, never silent);
  **NOTE** for the one-sided widen (S-1) — caught downstream by the spine + prove, but not
  surfaced at merge time.
- swap **budget-bounded**: YES — over-budget refused before any spend, no surprise live call.
