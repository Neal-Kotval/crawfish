# ADR 0020 — A consequential Sink fires only in eval mode (against a frozen Definition)

**Status:** Accepted · **Date:** 2026-06-24 · **Milestone:** S (Security of the generator boundary)

> Issue CRA-240 / SEC-3, ratifying the AL-T1 (CRA-209) invariant. Numbering: 0019 was the
> last accepted ADR → this is **0020**. Cross-linked from
> [SECURITY.md](../SECURITY.md) (invariant 7) and the AL-T1 / CL-1 / consequential-Sink
> tickets.

## Context

The Agent Language splits a `Definition`'s lifecycle into two modes (AL-T1, CRA-209):

- **train / `mutable`** — the artifact's content (prompts, decode knobs, learned guards,
  Wiki pages) may change. This is the PyTorch-for-LLMs half: optimize, tune, mutate.
- **eval** — the artifact is **frozen**, content-hashed (ADR 0006/0012/0019), and
  reproducible.

A **consequential Sink** is the one node that takes an irreversible, outward-facing action
(open a PR, write to Linear, post to a channel). The spine already keeps its *target*
static (invariant 2). But mode introduces a new question the original six invariants did
not answer: **may a Sink fire while the Definition is still mutable?**

If it could, the artifact that produced the side effect would be **unreproducible** — its
prompts/knobs could have been mid-mutation, so there is no stable content hash to attribute
the action to, and the train-mode borrow (ADR 0018) could be rewriting the very logic that
chose to fire. A side effect with no reproducible cause is both a correctness hazard and an
audit gap: you cannot replay, diff, or attribute it.

## Decision

**A consequential Sink fires only in eval mode — against a frozen, content-hashed
Definition. A Sink reached while the Definition is unfrozen (train / `mutable`) raises.
Eval mode == frozen; only a frozen artifact may take an irreversible action.**

This makes "fires a side effect" a property of a *specific content hash*, never of a
moving target. Concretely:

- `eval()` returns the frozen view; `mutable()` / `train()` returns an unfrozen edit
  handle. A frozen artifact rejects mutation (`FrozenError`, `Freezable`).
- The same rule extends to knowledge artifacts a consequential run summons: an eval-mode
  `Wiki` is frozen and refuses a `mutable()` handle (`wiki.py`), so retrieval feeding a
  consequential action cannot be rewritten under it.
- The borrow (ADR 0018) and this gate compose: train-mode mutation is exclusive and
  cannot span a consequential run, and a consequential run requires the frozen view.

## Alternatives rejected

- **Allow a Sink in train mode, snapshot the content at fire time.** A snapshot taken
  mid-mutation is not the artifact anyone reviewed or promoted; it launders an unfrozen
  state into a pseudo-reproducible one. The promotion/eval gates operate on frozen hashes —
  a train-mode side effect would bypass them.
- **Warn but allow.** A warning is not a gate; the review DoD requires that a consequential
  action be attributable to a frozen hash, not best-effort.
- **Make freezing implicit at Sink construction.** Hides the mode transition the user must
  reason about (and that the borrow enforces); explicit eval/train is the contract AL-T1
  already exposes.

## Consequences

A consequential action is always attributable to one reproducible content hash — replayable,
diffable (`agentdiff`), and auditable. This is a **new consequential-action gate** alongside
invariants 2–3: target-is-static answers *where*, this answers *under what artifact state*.
The runtime enforcement seam is the freeze check at the Sink boundary; M-S issue CRA-241
wires `guard_consequential` into Sink egress so the gate is enforced, not merely documented.
Recorded as **SECURITY.md invariant 7**.
