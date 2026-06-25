# Compose, version, and summon knowledge

You can build an agent from parts, give it a name, and move that name through a version log, the way you use git for code. You can also attach knowledge to an agent and read it at run time as data. This page shows three tasks: compose a variant, name and version it, and summon a knowledge unit.

Crawfish is a programming language for agents, and an agent is a value in that language. A *Definition* is a compiled agent: a typed, frozen, content-addressed object. Content-addressed means its identity is a hash of its contents, so two agents with the same contents have the same hash, and any change produces a new hash.

Everything here is public API from the top-level `crawfish` package, and every example is deterministic under `MockRuntime`.

You will learn how to:

- Build a variant with the `with_*` operators.
- Name and version a Definition with `DefinitionStore`.
- Move a name pointer with `modify` and `reset`.
- Attach and read knowledge with a `Wiki`.

## Build a variant with `with_*`

The `with_*` operators take a Definition, apply one edit, and return a new frozen Definition with a fresh content hash. The original is never changed. This is copy-on-write: each operator makes a copy, edits the copy, and seals it.

```python
import crawfish as cw

base = cw.eval(cw.Definition.from_package("demo/triage-bot"))   # eval() freezes the agent

# Add a skill, pinned to a version.
variant = cw.with_skill(base, cw.SkillRef(id="label-taxonomy", version="1.0"))

# Add a team agent (replace=True swaps a same-role agent instead of adding one).
variant = cw.with_agent(variant, reviewer_agent)

assert variant.frozen                                  # the result is sealed
assert variant.content_sha() != base.content_sha()     # one change, a new hash
assert base.content_sha() == base.content_sha()        # the base is unchanged
```

Two variants built from the same edits share one hash, so building the same agent twice is the same agent. Any difference produces a different hash. Every operator runs through the same content-hash path, so you cannot edit a Definition without producing a new version. Calling `with_*` on a frozen Definition copies first, so it never raises `FrozenError`, but editing the returned frozen object in place does.

The operators:

| Operator | Adds |
| --- | --- |
| `with_skill(base, SkillRef)` | a skill, pinned to a version |
| `with_agent(base, agent, *, replace=False)` | a team agent, or swaps a same-role one |
| `with_context(base, summonable, *, mode=SummonMode.READONLY)` | a knowledge unit, pinned to a version |
| `with_inputs(base, *params)` | new typed inputs (never widens fluidity) |
| `with_policy(base, policy)` | a static consequential policy |

`with_context` accepts anything that is `Summonable`. A `Wiki` is the built-in option, covered [below](#summon-knowledge-with-a-wiki). For the boundary that decides what counts as trusted, see [Static versus fluid](concepts.md#static-versus-fluid).

## Name and version it with `DefinitionStore`

Composition gives you content hashes but no names. `DefinitionStore` maps a name to a hash. It is backed by a `Store`, append-only, and scoped to an org.

```python
from crawfish.store import SqliteStore

ds = cw.DefinitionStore(SqliteStore("agents.db"), org_id="local")

sha = ds.save("triage", base)                       # requires a frozen Definition
assert ds.recall("triage").content_sha() == sha     # recall the latest

ds.save("triage", variant, parent=sha)              # move the name to the variant
assert len(ds.log("triage")) == 2                   # the version log, oldest to newest
assert ds.head("triage") == variant.content_sha()
```

`save` moves the name pointer and records one version event carrying the `parent` edge. The body is stored by content hash, so two byte-identical saves store one object but record two events. `recall` reads a stored object and re-seals it frozen. It never produces a new hash. A historical version stays reachable by its hash:

```python
old = ds.recall("triage", sha=sha)          # or recall("triage@<sha>"), or a bare sha
assert old.content_sha() == sha             # still reachable after the name moved on
```

Saving an unfrozen (train-mode) Definition raises `UnfrozenDefinitionError`, because a training artifact has no stable identity to key the registry. An unknown name, or a name in another org, raises `UnknownNameError`. Tenancy is enforced: a name in one org is never visible to another.

## Move the name pointer with `modify` and `reset`

`modify` and `reset` are the commit and checkout verbs over the version log.

```python
# modify: recall, apply a function, save with parent set to the old hash.
# The function composes with the with_* operators, so each step returns a new
# frozen Definition and modify records the lineage edge.
new_sha = cw.modify(ds, "triage",
                    lambda d: cw.with_skill(d, cw.SkillRef(id="severity", version="0.1")))
assert len(ds.log("triage")) == 3           # the pointer advanced, parent edge recorded

# reset: move the name back to an earlier hash. Creates no object, no event.
cw.reset(ds, "triage", sha)                 # rewind to the original
assert ds.recall("triage").content_sha() == sha
```

`modify` runs through the same content-hash rule as `with_*`: no in-place edit, no model call. A function that edits a recalled frozen Definition in place raises `FrozenError`. One that returns an unfrozen draft raises `UnfrozenDefinitionError`.

`reset` moves a name to an earlier hash. It creates nothing, is reversible, and refuses a target that is not in `log(name)` (`UnreachableShaError`). It never prunes old versions, so an earlier hash stays recallable and `craw share` stays reproducible. Three-way `merge` is covered in [Diff, prove, and replay](diff-prove-replay.md).

Together these give you the git model for agents: a name pointer you move with `save` and `reset`, over an append-only store of immutable, content-addressed Definitions.

## Summon knowledge with a `Wiki`

A *Wiki* is a versioned, content-hashed knowledge unit you can attach to an agent. Its content hash is a Merkle hash over its pages, so re-hashing only re-derives the page you changed, and two identical Wikis share one hash.

```python
arch = (
    cw.Wiki(org_id="local")
    .with_page("escalation", {"rule": "P0 → page on-call immediately"},
               trust=cw.TrustTier.TRUSTED)
    .with_page("taxonomy", {"labels": ["bug", "billing", "feature"]},
               trust=cw.TrustTier.TRUSTED)
)
```

`with_page` is copy-on-write: it returns a new frozen Wiki with a distinct hash, the receiver is unchanged, and reusing a title overwrites only that page. Pages are *tainted* by default, meaning they are treated as untrusted data, and they stay tainted across an edit. Each page carries a `TrustTier` (`TRUSTED`, `COMMUNITY`, or `UNTRUSTED`, default untrusted). The tier can only raise suspicion. It never lowers taint, so a low-trust corpus is never silently trusted like your own source.

Attach a Wiki to a Definition by pinned snapshot:

```python
agent = cw.with_context(base, arch, mode=cw.SummonMode.READONLY)
```

`readonly()` returns a `SummonRef` that carries the unit id and the pinned content hash, never the body. So `export()["checksum"]` tracks the pin, and the page values never appear in the export. `mutable()` is the train-mode edit handle and is rejected on a frozen Wiki, mirroring `train()` and `eval()`: knowledge edits are copy-on-write only.

When a step needs the knowledge, `consult()` turns the Wiki into a `Context` whose entries are tainted (fluid). Summoned knowledge reaches the model as data, never as instructions, so it can never reach an instruction slot or a static-only sink target. `consult()` is pure: it takes a Wiki and returns a `Context`, with no model call.

```python
ctx = arch.consult()
assert all(entry.tainted for entry in ctx.entries)   # data, never instructions
```

Persistence uses the `Store` seam (`persist()` and `load()`), scoped by `org_id`. A `ScrubbingStore` redacts secrets on write, so no secret body is stored unredacted, and a Wiki saved in one org never loads under another.

!!! note "Retrieval (`Rag`) ships as a seam only"

    `Rag`, retrieval over a content-hashed corpus snapshot, ships as a seam: the `RagSeam`
    protocol plus a `RagDeferred` marker. The seam fixes two properties so a later
    implementation cannot regress them: embeddings route through the secret-scrubbing seam,
    and retrieved hits are tainted by default and carry the source page's trust tier. Calling
    it today raises `RagDeferred`.

## What stays static

Composing, versioning, and summoning never widen the security boundary described in [Security](../architecture/SECURITY.md):

- Consequential settings stay static. The model, policies, and sink targets are author config. `with_*` never derives them from a fluid value.
- Summoned knowledge is data. A summon enters an agent's identity through its pinned hash, the body is never carried in the reference or the checksum, and `consult()` entries are tainted, so they can never reach an instruction slot or a static-only sink.
- Acting requires eval mode. `save` requires a frozen Definition, and `mutable()` is rejected on a frozen Wiki. Only sealed, content-addressed, eval-mode values touch the outside world.

## Next steps

- [Diff, prove, and replay](diff-prove-replay.md) covers `diff`, `merge`, and counterfactual replay.
- [Definition reference](../reference/definition.md) has the exact signatures for the `with_*` operators.
- [Persistence reference](../reference/persistence.md) covers `DefinitionStore`, `Wiki`, and the `Store` seam.
- [Static versus fluid](concepts.md#static-versus-fluid) explains the trust boundary in full.
