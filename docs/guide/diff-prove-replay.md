# Diff, prove, and counterfactual replay

Milestone 7 turns the content-addressed agent into something you can **review like code**,
**certify before a run**, and **time-travel against a candidate change** for near-$0. Three
moves, all real public API importable from the top-level `crawfish` package, all
deterministic under `MockRuntime`:

- **Diff & merge** — `diff` / `merge`. A frozen `Definition` is content-addressed; M7 lifts
  "two shas are equal or not" into a typed, field-level diff and a three-way merge — **git for
  agents**, the verbs.
- **Prove no injection** — `craw prove --no-injection`. A pre-flight, fail-closed certificate
  that no `Flow.FLUID` input can reach a consequential static-only Sink target or idempotency
  slot.
- **Counterfactual replay** — `craw replay --swap`. Re-run a historical recorded run against a
  candidate model/decode change; every unaffected leaf replays bit-for-bit, only the dirtied
  leaves re-execute.

On this page:

- [Diff two variants — `diff`](#diff-two-variants-diff)
- [Three-way merge — `merge`](#three-way-merge-merge)
- [Prove no injection — `craw prove --no-injection`](#prove-no-injection-craw-prove-no-injection)
- [Counterfactual replay — `craw replay --swap`](#counterfactual-replay-craw-replay-swap)
- [What this advances (the thesis)](#what-this-advances-the-thesis)

## Diff two variants — `diff`

`diff(a, b)` takes a typed, field-level structural diff over the *canonical content payload*
(the fields that fold into `Definition.content_sha`). Because it diffs exactly what the hash
sees, the diff is non-empty **iff** the two content shas differ.

```python
import crawfish as cw

base = cw.eval(cw.Definition.from_package("demo/triage-bot"))   # eval() == freeze
variant = cw.with_skill(base, cw.SkillRef(id="label-taxonomy", version="1.0"))

d = cw.diff(base, variant)
assert not d.is_empty
for change in d.changes:
    print(change.kind, change.path, change.before, "->", change.after)
# ChangeKind.ADDED  dependencies.skill:label-taxonomy.version  None -> 1.0
```

Each differing field is a `FieldChange(path, kind, before, after)` with a stable dotted `path`
(e.g. `team.agents.reviewer.prompt`, `inputs.ticket.flow`) and a `ChangeKind` of `ADDED` /
`REMOVED` / `CHANGED`. Keyed lists — agents by `role`, parameters by `name`, dependency pins by
`id`, policies/mcp by `name` — are re-keyed to identity, so a **re-order without an edit is not
a spurious change**. Changes come back path-sorted (deterministic); `DefinitionDiff` is a frozen
hashable value with `.is_empty` and `.paths()` for ergonomics.

## Three-way merge — `merge`

`merge(base, a, b)` is a three-way merge over the lineage — `base` is the common ancestor, `a`
and `b` two derived variants. Per leaf: a one-sided change wins; a same-value change on both
sides is harmless agreement; a both-sided change to **different** values is a typed conflict —
**never silently resolved**.

```python
import crawfish as cw

base = cw.eval(cw.Definition.from_package("demo/triage-bot"))
a = cw.with_skill(base, cw.SkillRef(id="label-taxonomy", version="1.0"))  # one side adds a skill
b = cw.with_skill(base, cw.SkillRef(id="triage-runbook", version="2.0"))  # the other adds a different one

result = cw.merge(base, a, b)
if isinstance(result, cw.MergeConflict):
    for c in result.conflicts:               # FieldConflict(path, base, a, b)
        print("CONFLICT", c.path, c.base, c.a, c.b)
else:
    print("clean merge:", result.content_sha())           # a new frozen Definition
    assert not cw.diff(a, result).is_empty                # carries b's change too
```

A clean merge unflattens the merged payload, **re-validates** it into a `Definition`
(type-checked, never hand-assembled), keeps `base`'s `id` (stays on base's identity lineage),
and re-seals through the same content-hash copy-on-write law as composition. The result is a
**new frozen** artifact with a **deterministic** content sha — the same three inputs always
merge to the same sha. Any conflict makes the whole merge a `MergeConflict` carrying the full
path-sorted conflict set.

!!! note "The injection boundary is a diffable leaf — and merge never silently widens it"

    A `Parameter`'s `flow` (the static/fluid prompt-injection boundary) and a `Policy` (static
    consequential config) are ordinary diffable leaves. A `flow` move applies only when
    **exactly one** side made it; whenever it collides with the other side's change to the same
    leaf it surfaces as a typed conflict for review. A merge can never **silently** widen the
    boundary.

!!! warning "Deferred — `merge` granularity is whole-field, not token-level"

    Three-way merge over a prompt **body** (token/line-level, the way a text merge tool works)
    is **deferred**. Today a prompt change is a single whole-field leaf: two edits to the same
    prompt collide as one conflict, even if they touch different sentences.

## Prove no injection — `craw prove --no-injection`

`craw prove --no-injection <def>` is a pre-flight certificate over a Definition's declared
contract: it proves that no `Flow.FLUID` input can reach a consequential static-only Sink target
or idempotency slot.

```console
$ craw prove --no-injection path/to/clean-definition
guarantee: alg3-conservative-static-rejection
proven: True
$ echo $?
0
```

It exits **non-zero** on a suspected fluid→static-slot path, **zero** when the static check
passes. Because the check is **conservative and fail-closed**, a Definition that declares a
consequential output as `Flow.FLUID` (or wires a fluid value toward a static-only slot) is
reported as *not proven* — a suspected path it refuses to certify, never silently waves through.
`--json` emits the versioned `craw.prove.v1` schema (`guarantee`, `proven`, the
`fluid_inputs` / `static_slots` surfaces, per-slot `obligations`, and `violations`). The same
check is available in-process as `crawfish.prove_no_injection(definition) -> ProofResult`.

!!! warning "What guarantee actually ships — read this"

    This is a **moonshot, spike-first** issue, and a **sound** full-graph non-interference proof
    is **not** what ships today. The timeboxed spike concluded a sound proof needs a first-class,
    inspectable dataflow graph carrying the summarization/carry operators, an agent-leaf
    declassification point, and the bounded-refine/branch fragment — none of which the Definition
    yet exposes as a serialized artifact.

    What ships is the **ALG-3 conservative static-rejection fallback**, named
    `alg3-conservative-static-rejection`: a conservative, assembly-time, **fail-closed** check
    that **rejects** any wiring where a fluid-tainted value can reach a static-only Sink target /
    idempotency key. It is **sound for the fragment it covers** (it never passes a wiring the
    runtime `TargetMustBeStaticError` / `StaticOnlyError` gates would reject) and **incomplete**
    (it certifies only the declared fluid→static-slot class, not the absence of *every* injection
    path). A consequential output mis-declared `Flow.FLUID` is reported as a suspected path, never
    assumed safe.

    **The sound proof and the formal conformance suite remain a research follow-on (deferred).**

`prove` is an *additional* assembly-time gate (defense-in-depth). It **never replaces** the
runtime `StaticOnlyError` / `TargetMustBeStaticError` — those still fire at construction/run
time. The certificate just catches a fluid→static-slot wiring *before* a run.

## Counterfactual replay — `craw replay --swap`

`craw replay --swap <from>=<to>` re-runs a historical recorded run against a candidate change
for near-$0. A leaf is one cassette — one model call, keyed by the execution coordinate. A leaf
is **dirtied** iff its recorded `RunResult.model == from`; every other leaf is **clean** and
replays byte-for-byte (same recorded result, $0, no model call).

```console
$ craw replay --cassettes runs/2026-06-20 \
      --swap claude-haiku-4-5=claude-opus-4-8 \
      --alt-cassettes runs/opus-candidate --json
```

In-process, the same plan is `crawfish.parse_swap("from=to")` → a `SwapSpec`, then
`crawfish.run_swap(cassette_dir, spec, ...)` → a `SwapReport`.

- **Determinism.** Clean leaves replay bit-for-bit. A dirtied leaf's counterfactual comes from
  an `--alt-cassettes` dir (a previously recorded `to` run — deterministic, the test path) or,
  absent that, a deterministic re-stamp placeholder charged `--cost-per-leaf`.
- **Cost-bounded cascade.** The dirtied fraction is reported *before* spending. With `--budget`
  set, a dirtied live cascade whose projected spend exceeds the budget is **refused** (no live
  call) and the command exits non-zero — so an upstream-change blast radius stays bounded and
  visible.
- **Tenancy.** `--org` carries `org_id` onto the report; the cassette key already folds it in,
  so a counterfactual never reads another org's leaves.
- `--json` emits the versioned `craw.replay.v1` schema (original vs. counterfactual per leaf,
  dirtied fraction, spend, over-budget).

## What this advances (the thesis)

Each M7 verb is the agent-language thesis made operational on the content-addressed substrate
M6 shipped:

- **Content-addressed agents are diffable and mergeable.** A frozen `Definition` was already
  *git's immutable side* (a content sha). `diff` / `merge` add the review verbs — an agent
  program is now reviewable the way code is, with the injection boundary as a typed leaf a merge
  can never silently widen.
- **Injection is rejected by construction.** `prove --no-injection` makes the static/fluid
  boundary a thing you certify *before* a run, fail-closed — not a property you hope held.
- **Counterfactual replay is near-free.** Because every leaf is content-addressed and recorded,
  swapping one model re-executes only the dirtied fraction; the rest is determinism, not spend.

See the [release notes](release-notes.md) for the shipped surface and the
[Concepts → revolutionary capabilities](concepts.md#revolutionary-capabilities-diff-prove-replay)
section for the mental model.
