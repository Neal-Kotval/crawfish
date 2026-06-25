# Diff, prove, and counterfactual replay

You can review an agent change like code, certify it before a run, and re-run a recorded run against a candidate change for close to zero cost. This page shows three tasks: diff two agents, merge two variants, prove no injection, and replay a run with one model swapped.

A frozen `Definition` is content-addressed: its identity is a hash of its contents. These tools build on that. Everything here is public API from the top-level `crawfish` package, and every example is deterministic under `MockRuntime`.

You will learn how to:

- Compare two Definitions with `diff`.
- Combine two variants with `merge`.
- Certify no injection path with `craw prove --no-injection`.
- Re-run a recorded run against a model swap with `craw replay --swap`.

## Diff two variants with `diff`

`diff(a, b)` returns a typed, field-level diff over the fields that fold into `Definition.content_sha`, the canonical content payload. It diffs exactly what the hash covers, so the diff is non-empty if and only if the two content hashes differ.

```python
import crawfish as cw

base = cw.eval(cw.Definition.from_package("demo/triage-bot"))   # eval() freezes the agent
variant = cw.with_skill(base, cw.SkillRef(id="label-taxonomy", version="1.0"))

d = cw.diff(base, variant)
assert not d.is_empty
for change in d.changes:
    print(change.kind, change.path, change.before, "->", change.after)
# ChangeKind.ADDED  dependencies.skill:label-taxonomy.version  None -> 1.0
```

Each differing field is a `FieldChange(path, kind, before, after)`. The `path` is a stable dotted path (for example `team.agents.reviewer.prompt` or `inputs.ticket.flow`), and `kind` is `ADDED`, `REMOVED`, or `CHANGED`. Keyed lists are matched by identity (agents by `role`, parameters by `name`, dependency pins by `id`, policies and MCP entries by `name`), so re-ordering a list without editing it is not reported as a change. Changes come back sorted by path, so the result is deterministic. `DefinitionDiff` is a frozen, hashable value with `.is_empty` and `.paths()`.

## Combine two variants with `merge`

`merge(base, a, b)` is a three-way merge over the lineage: `base` is the common ancestor, and `a` and `b` are two variants derived from it. Per field, a one-sided change wins, a same-value change on both sides is agreement, and a change to different values on both sides is a typed conflict. A conflict is never resolved silently.

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

A clean merge re-validates the merged payload into a `Definition` (it is type-checked, never hand-assembled), keeps `base`'s `id` so it stays on base's lineage, and re-seals through the same content-hash copy-on-write rule as composition. The result is a new frozen artifact with a deterministic content hash: the same three inputs always merge to the same hash. Any conflict makes the whole result a `MergeConflict` carrying the full, path-sorted conflict set.

!!! note "A conflict surfaces when both sides change the same field"

    A `Parameter`'s `flow` (the static/fluid boundary) and a `Policy` (static consequential
    config) are ordinary diffable fields. A `flow` change applies only when exactly one side
    made it. When both sides change the same field to different values, the merge reports a
    typed conflict for review instead of widening the boundary on its own.

Merging a prompt body is whole-field, not token-level. Two edits to the same prompt collide as one conflict, even if they touch different sentences. A token-level merge over prompt text is not yet available.

## Prove no injection with `craw prove --no-injection`

`craw prove --no-injection <def>` checks, before you run, that no untrusted (fluid) input can reach a consequential static-only sink target or idempotency slot. A *fluid* input is untrusted session data; a *static* target is fixed author config. If the check cannot prove the agent is clean, it fails. Use it as a pre-flight gate in CI.

```console
$ craw prove --no-injection path/to/clean-definition
guarantee: alg3-conservative-static-rejection
proven: True
$ echo $?
0
```

It exits non-zero on a suspected fluid-to-static path and zero when the check passes. The check is conservative and fail-closed: a Definition that declares a consequential output as `Flow.FLUID`, or wires a fluid value toward a static-only slot, is reported as not proven. It refuses to certify a suspected path rather than wave it through. `--json` emits the versioned `craw.prove.v1` schema (`guarantee`, `proven`, the `fluid_inputs` and `static_slots` surfaces, per-slot `obligations`, and `violations`). The same check is available in-process as `crawfish.prove_no_injection(definition) -> ProofResult`.

The guarantee that ships today is the ALG-3 conservative static-rejection check, named `alg3-conservative-static-rejection`. It is an assembly-time, fail-closed check that rejects any wiring where a fluid-tainted value can reach a static-only sink target or idempotency key. It is sound for the class it covers: it never passes a wiring that the runtime `TargetMustBeStaticError` or `StaticOnlyError` gates would reject. It is incomplete: it certifies the declared fluid-to-static-slot class, not the absence of every possible injection path. A consequential output mis-declared as `Flow.FLUID` is reported as a suspected path, never assumed safe. A full-graph non-interference proof is a research follow-on and is not yet available.

`prove` is an extra assembly-time gate, defense in depth. It does not replace the runtime `StaticOnlyError` and `TargetMustBeStaticError`, which still fire at construction and run time. The certificate catches a fluid-to-static wiring before a run.

## Replay a run with `craw replay --swap`

`craw replay --swap <from>=<to>` re-runs a recorded run against a candidate change for close to zero cost. A *leaf* is one recorded model call, keyed by its execution coordinate. A leaf is *dirtied* if its recorded `RunResult.model` equals `from`. Every other leaf is clean and replays byte-for-byte from the recording, with no model call and no spend.

```console
$ craw replay --cassettes runs/2026-06-20 \
      --swap claude-haiku-4-5=claude-opus-4-8 \
      --alt-cassettes runs/opus-candidate --json
```

In-process, the same plan is `crawfish.parse_swap("from=to")`, which returns a `SwapSpec`, then `crawfish.run_swap(cassette_dir, spec, ...)`, which returns a `SwapReport`.

- Clean leaves replay bit-for-bit. A dirtied leaf's counterfactual comes from an `--alt-cassettes` directory (a previously recorded `to` run, the deterministic test path) or, if none is given, a deterministic placeholder charged `--cost-per-leaf`.
- The dirtied fraction is reported before any spend. With `--budget` set, a dirtied live cascade whose projected spend exceeds the budget is refused (no live call) and the command exits non-zero, so the blast radius of an upstream change stays bounded and visible.
- `--org` carries `org_id` onto the report. The cassette key already folds it in, so a replay never reads another org's leaves.
- `--json` emits the versioned `craw.replay.v1` schema (original versus counterfactual per leaf, dirtied fraction, spend, over-budget).

## How these fit together

These three verbs build on one fact: a frozen `Definition` is content-addressed, and every model call is recorded.

- A content-addressed agent is diffable and mergeable. `diff` and `merge` make an agent reviewable the way code is, with the static/fluid boundary as a typed field a merge cannot widen on its own.
- `prove --no-injection` turns the static/fluid boundary into something you certify before a run, fail-closed, instead of a property you hope held.
- Counterfactual replay is close to free, because a recorded run lets you swap one model and re-execute only the dirtied leaves. The rest is determinism, not spend.

## Next steps

- [Compose, version, and summon knowledge](variables-and-knowledge.md) covers the `with_*` operators and the version log that `diff` and `merge` work over.
- [Injection rejected by construction](injection-rejected-by-construction.md) goes deeper on the static/fluid boundary that `prove` certifies.
- [Definition reference](../reference/definition.md) has the exact signatures.
