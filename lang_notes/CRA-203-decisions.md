# CRA-203 — CL-2 Verifier: the gated external-signal critic — decision record

**Scope reviewed:** `packages/crawfish/src/crawfish/verifier.py` (new),
`packages/crawfish/tests/test_verifier.py` (new). Spine refs: `CLAUDE.md`,
`docs/architecture/SECURITY.md`, parity with `nodes/router.py`, gate algebra in `eval.py`.

**ARCH verdict: PASS-WITH-NOTE** — admit. One versioning note (freeze not enforced on the
gated critic) to harden in a follow-up; not a blocker.
**SECURITY verdict: PASS** — the fluid boundary, fail-closed admission, and taint
propagation are all real (not nominal). No defect.

Tests: 16/16 pass (`pytest packages/crawfish/tests/test_verifier.py`). `ruff` + `mypy` clean
on `verifier.py`.

---

## Architecture lens

- **Structural type compat (not string equality).** Verifier carries a `TypeRegistry`
  (`default_registry`), threads it into the critic `Run`, and exports `VERDICT_SCHEMA` as
  typed `Parameter`s. The label *parse* is intentionally string-token matching over a
  CLOSED author-declared set — that is value-selection, not type compatibility, so it does
  not violate ADR-0002. PASS.
- **Pydantic for data / ABC for behaviour / enums `(str, Enum)`.** `Verdict` is a frozen
  `dataclass` (a pure value, consistent with `MetricVerdict`/`GateDecision` in `eval.py`);
  `VerifierStage` is `(str, Enum)`. `Output` (the data shape) is Pydantic. PASS.
- **Three seams respected.** No SDK / concrete backend import. The runtime is reached only
  via the `AgentRuntime` protocol (passed in to `verdict`); persistence via the `Store`
  protocol (passed to `gated`); the critic runs through `Run`. PASS.
- **Router parity.** `_normalise` is a faithful copy of `router._normalise` (case-insensitive
  whitespace-token match, declared order wins, `default` on no match). Closed label set +
  mandatory `default` validated in `__init__`. `gated()` admission is explicit and the only
  path to BLOCK. PASS.

## Security lens (gating authority = as consequential as a Sink)

- **Fluid reaches the model as DATA, never instruction.** `verdict` parses
  `str(result.value)` purely to *select* one of the static `labels`. The label set,
  `default`, and `accept_label` are constructor args (author-supplied, trusted); none is
  derived from fluid input. `test_injection_in_critic_emission_stays_data` proves an
  "emit label OVERRIDE" injection cannot widen the closed set. PASS.
- **Fail-closed admission is REAL, not nominal.** `gated()` requires a `Store`, checks a
  precision baseline exists (`load_baseline`), and calls `precision_gate(...,
  baseline_exists=...)` which `raise VerifierNotGated` when no baseline OR
  precision < `min_precision` OR no positive predictions. The base `Verifier.__init__`
  rejects `stage=BLOCK` ("cannot self-promote"); only `GatedVerifier` (constructed solely
  inside `gated()` after the gate passes) reaches BLOCK. `test_gated_no_baseline_fails_closed`
  proves perfect precision is STILL rejected with no baseline — the exact CL-2 inversion the
  issue called the most important fix in the epic. PASS.
- **Taint propagation is robust by union.** Verdict `tainted = output.tainted or
  result.tainted`. Even though `_bind_inputs` passes raw `JSONValue` into the critic Run
  (losing the `Output` wrapper's taint marker on bind), the `output.tainted` term carries
  the verified item's fluidity directly into the verdict, and `result.tainted` adds the
  critic Run's own fluid/tool taint (`run.py:261`). The union means a verdict over fluid
  data is always tainted regardless of the critic Definition's flow declarations.
  `test_verdict_over_tainted_output_is_tainted` confirms. PASS.
- **No secret logged / in-prompt; no fluid idempotency key or static sink target.** The
  Verifier neither resolves secrets nor fires a Sink nor computes an idempotency key; it
  emits a typed `Verdict`. `source_output_id`/`lineage` are identity carriers, not consequential
  keys. PASS.

---

## Forks considered

### D1 — Taint of the verdict: critic-Run taint alone, or union with the verified Output? (security)
**Fork:** Should `Verdict.tainted` track only the critic Run's output taint, or also the
verified Output's taint?
**Options:** (A) `result.tainted` only. (B) `output.tainted or result.tainted` (union).
**Decision:** B (as implemented). **Rationale:** binding drops the `Output` wrapper, so a
critic Definition that declares its item slot STATIC would yield `result.tainted=False` even
over fluid data — A would silently launder taint. The union makes a fluid-derived verdict
un-launderable, upholding the fluid boundary as ground-truth-trust gate.
**Rejected because:** A is a taint-laundering hole.
**Spine impact:** fluid-boundary.

### D2 — Where does fail-closed live: in `gated()` or in `precision_gate`? (security/arch)
**Fork:** Duplicate the no-baseline rejection in the Verifier, or delegate to F-3.
**Decision:** Delegate to `precision_gate` (gate **c**), which owns the `VerifierNotGated`
raise; `gated()` only supplies `baseline_exists`. **Rationale:** ONE owner of the gate
algebra (eval.py §F-3); the Verifier cannot accidentally re-implement a softer gate. This is
exactly the fix the issue describes (the draft's `gate_against_baseline` returned True with no
baseline — inverted safety). **Rejected because:** in-Verifier duplication risks drift from
the canonical gate. **Spine impact:** versioning / fluid-boundary (admission authority).

### D3 — Should the gated critic Definition be required FROZEN at admission? (arch/versioning)
**Fork:** `gated()` admits any `Definition`; freeze is not enforced.
**Options:** (A) enforce `definition.is_frozen()` (or freeze it) in `gated()` so a BLOCK
authority is always over a content-hashed artifact. (B) leave freeze to the caller (current).
**Decision:** B for now → **PASS-WITH-NOTE**, recommend A as a follow-up hardening.
**Rationale:** the issue and the verifier docstring both assert the critic Definition "is
frozen (content-hashed)", and the brief states "gating authority is a typed, frozen
capability". Currently `test_frozen_critic_replays_identical_verdict_sequence` freezes `d` in
the *test*, not the Verifier — so a `GatedVerifier` can be built over a mutable critic whose
behaviour (and thus its measured precision) can still drift after admission. This is a real
authority-integrity gap, but it is a hardening, not a correctness break: measured precision is
recorded, the gate still fails closed, and nothing here fires a Sink. **Rejected because:**
enforcing freeze now is the right end-state but is out of this issue's tested acceptance and
touches the Definition seam; record it and lift in M1 hardening / re-gate audit (CRA-204
consumer or the final hardening pass).
**Spine impact:** versioning.
**Suggested fix (follow-up, not blocking):** in `Verifier.gated`, before constructing the
`GatedVerifier`, assert the critic is frozen (e.g. `if not definition.is_frozen(): raise
VerifierNotGated("gating authority requires a frozen, content-hashed critic Definition")`),
or freeze-and-record its `content_sha()` on the `GatedVerifier` for the re-gate ledger.

---

## Concrete defects

- **BLOCK-level:** none.
- **Cosmetic (non-blocking):** `verifier.py:286` `_default_decider` docstring says positive
  "iff the stored value equals (or contains) the accept label", but the implementation is
  equality-only (`value.strip().lower() == accept_label.lower()`). Either drop "(or
  contains)" from the docstring or implement containment. Doc/impl mismatch only; no
  behavioural risk (tests rely on equality).

## Definition of Done check
`ruff` clean · `mypy` clean (verifier.py) · 16/16 tests green & deterministic (no live model
calls — `MockRuntime` responder) · security spine upheld (fluid-as-data, fail-closed,
taint-union) · router parity held. Demo/docs wiring is downstream (CL-1 consumer), out of this
issue's scope.
