# M4 — Taming Stochasticity: ARCH + SECURITY review

**Branch** `cra/m-4` · **Commit** `f8cae5a` · **Reviewer** `review-m4` (combined architecture + security)
**Issues** CRA-215 (TS-1 Quorum), CRA-216 (TS-4 Abstention), CRA-217 (TS-7/R4 House-guard), CRA-218 (TS-8 Constrained decode)
**Scope read** `runtime/quorum.py`, `abstain.py`, `guard.py`, `grammar.py`, `escalate.py`, `run.py`, four test files, plus `runtime/base.py` (`RunRequest`), `runtime/replay.py` (`_key`/`ExecutionCoordinate`), `definition/types.py` (`content_dict`).

---

## Verdicts

| Lens | Verdict |
|---|---|
| **ARCHITECTURE** | **PASS** |
| **SECURITY** | **PASS** |

No BLOCK defects. Two PASS-WITH-NOTE observations recorded below; neither changes a load-bearing invariant.

---

## Per-issue invariant confirmation

### CRA-215 — Typed Quorum / self-consistency (`runtime/quorum.py`)

- **k metered stochastic leaves + pure vote — CONFIRMED.** Each of the k samples charges the shared budget (`ctx.cost_budget.charge`, quorum.py:374) and emits through `inner` exactly as a normal call; the consensus reduction (`ConsensusFn.consensus`) is pure over recorded `RunResult.text` with no model call / I/O / wall-clock. `ConsensusFn` is an ABC; the modal estimand (`MajorityVote`) canonicalises before tallying (quorum.py:185) so `{"a":1,"b":2}` and `{"b":2,"a":1}` collapse to one candidate.
- **Ties / no-majority → declared default (Router parity) — CONFIRMED.** `_resolve` (quorum.py:395) resolves to `default_text` on `winner_text is None`, and raises `QuorumAbstention` only when no default is declared — never a silent arbitrary pick. First-seen deterministic tie-break (quorum.py:207).
- **Ill-defined plurality → abstain — CONFIRMED.** High-cardinality / all-distinct guard (quorum.py:200-203) abstains rather than crowning a singleton (TS-4 fallback).
- **Sequential-test early-stop (F-8, not fixed 0.8) — CONFIRMED.** Wilson lower bound on the leader's share > 0.5 (quorum.py:385-390); bounded by k + budget + cancel, never wall-clock. Budget preflight (`_can_afford`, quorum.py:432) stops cleanly before a breach.
- **F-1 cassette distinctness — CONFIRMED (resolved, not the spec's interim refusal).** CRA-215's "refuse to run over RecordReplayRuntime *until F-1 lands*" was conditional; F-1 has landed (`ExecutionCoordinate(sample_index=...)` threaded at quorum.py:370 → replay.py:98). Each sample gets a distinct `sample_index` coordinate **and** a distinct derived `decode_seed`, so k samples land in k cassettes (no unanimous-no-op collision). Correct resolution.

**SECURITY — quorum does not launder taint — CONFIRMED.** `sample_tainted = bool(fluid)` is derived per the `team._result_output` discipline (quorum.py:350); aggregate taint is the **union** `any(s.tainted for s in samples)` (quorum.py:407) and is carried onto the wrapped Output (`quorum_output`, quorum.py:487). The vote tally and the declared default are static/trusted — never fluid-derived. ALG-7 conformance holds.

### CRA-216 — Abstention as a typed Output (`abstain.py`, `escalate.py`)

- **Typed Output value, not exception/magic-string — CONFIRMED.** `Abstention` is a frozen pydantic model; `as_value()` (abstain.py:86) serialises to a JSON dict tagged with the stable `ABSTENTION_MARKER = "_abstention"` discriminator, so it survives persist/replay as plain JSON and `is_abstention` (abstain.py:120) recognises it for `Router` branching. Routable marker confirmed.
- **Confidence measured, never trusted — CONFIRMED.** `extract_confidence` (escalate.py:61) reads a `[0,1]` self-report as *data*, clamped to the unit interval; a fluid self-report is never an instruction.
- **Calibration-derived threshold — CONFIRMED.** `abstain_below_calibrated` (abstain.py:188) reads `CalibrationReport.abstention_threshold` off the reliability curve, differing from a naive constant on a mis-calibrated fixture.
- **abstain↔escalate import cycle broken — CONFIRMED.** `extract_confidence` is imported lazily *inside* `discipline` (abstain.py:161), not at module top; `escalate.py` re-exports the abstention surface at file-bottom (escalate.py:145). No top-level edge either way.

**SECURITY — abstention is fail-safe — CONFIRMED.** A *missing* confidence abstains (abstain.py:171: "declining is the fail-safe action and is always allowed"). Taint propagates: `Abstention.tainted = output.tainted` and the new Output is built via `output.derive(...)` (abstain.py:183), carrying taint + lineage. An abstaining Output carries the marker dict as its value, so it cannot type-check as a consequential Sink target / idempotency key (those are static-only; an abstention value is a tagged fluid-lineage dict).

### CRA-217 — House-guard: learned→distilled→earned (`guard.py`)

- **Model proposal is the ONLY stochastic leaf — CONFIRMED.** `propose_rule` (guard.py:452) is the single model call; its emission is FLUID and parsed *as data*.
- **Distilled predicate is PURE / deterministic — CONFIRMED.** `distill` (guard.py:503) parses the FLUID proposal into the closed grammar (`Comparison | SetMembership | NumericBound | BoolCombination | Always`) via a hand-written recursive descent — **no `eval`/`exec` anywhere**; an out-of-grammar `kind`/op raises `GuardGrammarError` (guard.py:570) and cannot widen the grammar. `_resolve_field` / `matches` are total (never raise on data). `PredicateMetric.evaluate` (guard.py:324) is a pure 0/1, zero model calls.
- **EARNS enforcement at a precision bar, fail-closed — CONFIRMED.** `synthesize_guard` (guard.py:596) gates on the **joint** criterion `precision_lb >= precision_floor AND coverage.lo >= min_coverage AND has_corpus` (guard.py:660-663). Precision is the Wilson **lower** bound (guard.py:341), never the optimistic point; a 99%-precision / 2%-coverage rule cannot earn `BLOCK`. No corpus ⇒ stays in `WARN` (fail-closed). `HouseGuard.blocks` (guard.py:761) enforces only when `can_block` (stage is `BLOCK`) AND the predicate matches.
- **Versioned / content-hashed / reversible — CONFIRMED.** `_predicate_content_sha` (guard.py:297) over canonical JSON; a structurally-different predicate mints a new sha; a fresh synthesis never edits a frozen prior rule.

**SECURITY — house-guard is a consequential authority that earns against TRUSTED corrections — CONFIRMED.** Ground truth comes only from `GoldenSet.from_corrections` (the F-4 provenance/taint gate, re-used not re-implemented; guard.py:443-446 comment + Gap-S4 note). The proposer corpus is bound as FLUID (guard.py:480) and can never set the guard directly. Taint propagates from a fluid proposal into `GuardCertificate.tainted` (guard.py:416) so a consequential consumer can refuse a fluid-derived certificate. Distilled predicate is pure at enforcement time (no model call). Fail-closed below the bar.

### CRA-218 — Constrained / grammar-guided decoding (`grammar.py`, `run.py`, `runtime/base.py`)

- **Grammar is per-call on RunRequest, OUT of the content hash (F-5) — CONFIRMED.** `RunRequest.grammar` / `decode_seed` are request fields (base.py:92-93), never Definition fields; `content_dict` (definition/types.py:187) hashes only the Definition `model_dump`, so neither can enter `content_sha`. Test `test_grammar_and_seed_do_not_perturb_the_definition_hash` asserts `"grammar" not in d.content_dict()` and same for `decode_seed`. **content_sha carries no grammar/seed — verified.**
- **Run identity captures any decode field that affects output — CONFIRMED.** `decode_seed` is folded into the F-1 cassette `_key` (replay.py:104-106) when present; `temperature` is *derived* from the resolved Definition (base.py:113), not set on the request. The repair path becomes dead code on the constrained path (`repair_count` stays 0; `_run_constrained`, run.py:328). Graceful degradation: a non-honouring backend still gets a well-formed field from the pure `Grammar.enforce` projection.
- **Grammar is static/trusted, never fluid-derived — CONFIRMED.** `Grammar.from_output_schema` (grammar.py:140) builds from the Definition's **declared** output schema (author config); there is no constructor that reads a fluid value. Frozen model. The prompt-injection boundary is intact: the constraint is trusted config.

**SECURITY — grammar static + out-of-hash — CONFIRMED.** A fluid value cannot set the grammar; the grammar cannot version-shift the agent (out of `content_sha`).

---

## PASS-WITH-NOTE observations (non-blocking)

**N1 — Grammar is not folded into the replay cassette key (`replay.py:_key`).** Only `decode_seed` and `coordinate` are folded; `grammar` is deliberately out-of-hash (F-5). CRA-218's AC "two different decode settings do not collide on one cassette" is satisfied *for `decode_seed`*. Two **different grammars** on the same `definition/inputs/role/seed` would therefore share one raw-text cassette. This is **not a defect**: the cassette stores raw backend text, and `Grammar.enforce` (run.py:353) projects it deterministically *per grammar* after the runtime returns, so the observed constrained output still differs by grammar. The raw leaf is legitimately grammar-agnostic at record time for non-honouring backends. Worth a one-line comment in `_key` noting grammar is intentionally not a cassette axis (the enforced projection, not the raw cassette, carries the grammar's effect), so a future reader doesn't mistake it for an omission. No change required for correctness.

**N2 — Quorum clobbers a caller-pinned `decode_seed` (quorum.py:366).** `request.model_copy(update={"decode_seed": seed})` overwrites any seed the caller set on the inbound request with the per-sample derived seed. Correct for quorum's ownership of sampling (it must vary the seed across k draws to get independent leaves), and the whole quorum stays reproducible from `base_seed`. Note only: a caller who pinned a seed upstream loses it inside quorum. Acceptable; the quorum owns the decode surface for its leaves.

---

## Summary confirmations (as requested)

- **Quorum taint = union across k samples** — CONFIRMED (quorum.py:407; vote default + tally static, never fluid-derived).
- **Abstention fail-safe** — CONFIRMED (missing confidence abstains; taint propagates via `derive`; abstaining value can't be a static Sink target / idempotency key).
- **House-guard earns-enforcement / fail-closed + distilled-predicate pure** — CONFIRMED (joint Wilson-LB precision ∧ coverage gate; no corpus ⇒ WARN; predicate is closed-grammar, no `eval`/`exec`, zero model calls at enforcement).
- **Grammar out-of-hash + static** — CONFIRMED (`content_dict` excludes grammar/seed; grammar built only from declared schema / author constants; `decode_seed` in run identity, grammar deliberately not a cassette axis).

**No BLOCK defects.** Milestone M4 passes architecture and security review.
