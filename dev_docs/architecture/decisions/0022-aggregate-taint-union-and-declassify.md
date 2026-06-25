# ADR 0022 — Aggregate taint is the union of its inputs; `declassify` is the sole audited fluid→static upgrade

**Status:** Accepted · **Date:** 2026-06-24 · **Milestone:** S (Security of the generator boundary)

> Issue CRA-240 / SEC-3, ratifying the taint semantics required by CL-1 (CRA-202),
> C3 (CRA-208), TS-1 (CRA-215) and ALG-6 (CRA-236). This is **0022**. Cross-linked from
> [SECURITY.md](../SECURITY.md) (invariant 9).

## Context

Spine invariant 5 says taint propagates from fluid inputs: any value derived from a fluid
input stays `tainted`, and a tainted value cannot silently become a static Sink target or
idempotency key. Phase 1 established this for a *single* derive edge (`Output.derive`).

The Agent Language adds two cases the single-edge rule did not pin down:

1. **Aggregation.** New operators *combine many inputs into one*: a Refine/Verifier verdict
   over prior output (CL-1), a bounded self-referential `Recurse` fold (C3), a `Quorum`
   self-consistency vote over k samples (TS-1), and summaries/compaction. What is the taint
   of the *aggregate*? If a fold of {one fluid sample, k−1 clean samples} were clean, an
   attacker could **launder** a fluid value by burying it in an aggregate — "the verdict is
   PASS, and the verdict is clean now."

2. **Upgrade.** Some real flows legitimately need to move a value from fluid to static (a
   human-reviewed, sanitized value entering a trusted position). Without a single, audited
   door for this, every operator would grow its own ad-hoc downgrade — an unbounded set of
   places where taint could be dropped.

## Decision

**(a) Aggregate taint = union.** Any fold / vote / summary / aggregate is `tainted` if
**any** of its inputs was tainted. Combining values can only *add* taint, never remove it.
A Verifier verdict, a `Recurse` fold, a `Quorum` vote, and a `CarrySummary` of a tainted
entry are all tainted if any contributing value was fluid-derived. This closes the
laundering-by-aggregation gap and is the conservative (sound) choice: over-tainting is safe,
under-tainting is an injection.

**(b) `declassify` is the single audited fluid→static upgrade, unreachable from a fluid
path.** The *only* way taint may be dropped is an explicit `declassify` (ALG-6) — a
deliberate, recorded upgrade with an auditable provenance. It is **not reachable from within
a fluid dataflow path**: a fluid value cannot route itself through `declassify`; the upgrade
is an out-of-band, reviewed act, not an operator a model output can invoke. Every
`declassify` is logged so the trust transition is auditable after the fact.

Together: taint only ever **accrues** as values combine, and the **one** place it is shed is
explicit, audited, and unreachable from the data it would launder.

## Alternatives rejected

- **Majority/threshold taint for aggregates** (clean if most inputs are clean). Lets a
  single fluid value into a "clean" aggregate — exactly the laundering attack. Union is the
  only sound rule.
- **Per-operator declassification points.** An unbounded set of taint-drop sites, each its
  own audit gap and review burden. A single audited door is reviewable and minimal.
- **No declassify at all (taint is forever).** Forbids legitimate, reviewed sanitization and
  pushes users to bypass the type system entirely — worse for security than one audited
  upgrade.
- **A `declassify` reachable inside the dataflow.** Would let a crafted fluid path launder
  itself; defeats the whole control. It must be out-of-band.

## Consequences

`tainted` is a *monotone* property across the operator algebra: combination adds taint, only
`declassify` (audited, out-of-band) removes it. The behavioural red-team (CRA-239) exercises
the laundering attempt directly (`verifier_aggregate_taint_launder`), and the static
conformance suite (ALG-7) asserts the union rule across every aggregation boundary. Recorded
as **SECURITY.md invariant 9**. The full `Grade` lattice that generalizes this (ALG-1/2) is
deferred behind a spike; this ADR ratifies the two-point (clean/tainted) semantics shipping
today.
