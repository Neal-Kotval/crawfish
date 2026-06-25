# Security-review Definition of Done

The per-PR security sign-off. [SECURITY.md](SECURITY.md)'s review gate mandates a
security-reviewer sign-off before a Linear issue moves to `Done`; **High/Critical
findings block completion.** This checklist is what that reviewer runs. It pairs the
*static* invariant (the taint/non-interference conformance suite, ALG-7) with the
*behavioural* gate (the operator-level prompt-injection red-team, CRA-239).

A PR that touches a **fluid surface** or a **consequential action** cannot be marked
`Done` until every applicable box is checked and the red-team is green.

## When this applies

Any change that touches one of:

- a **fluid surface** — anything that brings `Flow.FLUID` (untrusted session data) into
  the run: a Source, a Refine feedback loop, a Router/Classifier label, a Verifier
  verdict, a Quorum sample, a Rag/Wiki retrieved hit, a learned-guard proposer input, a
  generated artifact;
- a **consequential action** — a Sink, an idempotency key, a corrections-corpus
  admission, a precision/promotion gate, a `declassify`.

The operator tickets that introduce these (CL-1, CL-2, C1, C2, C3, TS-1, TS-7, AL-DV4,
OPT-1, AL-T1) each carry a **security sign-off** acceptance criterion that points here.

## The checklist

### 1. The fluid boundary holds (invariant 1)

- [ ] Every new untrusted input is typed `Flow.FLUID`; it reaches the model as **data**,
      never concatenated into instructions.
- [ ] No fluid value is bound to a `Flow.STATIC` slot at wire time.
- [ ] `craw prove --no-injection` / `assert_no_fluid_to_static_sink` passes on the
      affected Definition (ALG-3 assembly gate, [ADR 0021](decisions/0021-alg3-assembly-time-rejection.md)).

### 2. Consequential targets stay static-only (invariants 2–3)

- [ ] The Sink **destination** comes from `Flow.STATIC` config — never fluid, model- or
      data-derived.
- [ ] The idempotency key derives from static config only.
- [ ] A fluid-derived Router/Classifier label may gate **whether** a consequential action
      fires, never **choose** among distinct consequential Sink targets
      (`assert_classifier_gates_not_chooses`, S3).

### 3. Sink fires only in eval mode (the new consequential-action gate)

- [ ] A consequential Sink runs only against a **frozen / eval-mode** Definition; a Sink
      against an unfrozen (train-mode) Definition raises
      ([ADR 0020](decisions/0020-sink-fires-only-in-eval-mode.md)).
- [ ] Any knowledge artifact summoned for a consequential run is frozen (an eval-mode
      Wiki refuses a mutable handle).

### 4. Taint propagates; aggregates take the union (invariant 5)

- [ ] Any value derived from a fluid input stays `tainted`.
- [ ] Any fold/vote/summary (Verifier verdict, Quorum, aggregate) is tainted if **any**
      input was — aggregate-taint = union ([ADR 0022](decisions/0022-aggregate-taint-union-and-declassify.md)).
- [ ] A tool/MCP-result-derived emission is `tainted=True` (CRA-184).
- [ ] The only fluid→static upgrade is an explicit, audited `declassify`, unreachable from
      a fluid path ([ADR 0022](decisions/0022-aggregate-taint-union-and-declassify.md)).

### 5. Ground-truth corpora are poisoning-resistant (Gap S4)

- [ ] A correction enters the guard/verifier corpus only if `provenance == TRUSTED`
      **AND** `tainted is False` (the AND is load-bearing: taint wins over a mislabel).
- [ ] An un-benchmarked verifier/guard cannot gate a consequential action — the precision
      gate **fails closed** (`VerifierNotGated`).

### 6. Secrets stay by reference (invariant 4)

- [ ] No secret value reaches a prompt, a log, an emission, a transcript, or a Store row.
- [ ] A node receives only the secrets it declares; credentials resolve by reference.

### 7. The red-team is green (CRA-239)

- [ ] `uv run pytest packages/crawfish/tests/test_redteam_security.py -q` passes — every
      injection attempt against the new fluid surfaces is **blocked**.
- [ ] If the PR adds a new fluid surface, it adds **≥1 injection payload** for it to
      `crawfish.testing.redteam_attacks()` and a blocking assertion.
- [ ] The taint/non-interference conformance suite (ALG-7) passes.

## Sign-off

- [ ] No **High/Critical** finding remains open. (A High/Critical finding **blocks**
      `Done`, per SECURITY.md.)
- [ ] The decision log records any fork resolved (`lang_notes/`), and a spine-extending
      fork minted/updated its ADR.

## See also

- [Security spine](SECURITY.md) — the invariants this gate enforces
- [ADR 0020–0022](decisions) — the spine extensions this project added
- [Testing](../reference/testing.md) — the red-team + conformance harness
