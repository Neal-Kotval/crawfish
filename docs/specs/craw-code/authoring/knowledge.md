# Knowledge — `Wiki` / `with_context`

> Feeds `crawfish-authoring-knowledge` (CRA-263). Golden:
> [`demo/craw-code-golden/knowledge.py`](../../../../demo/craw-code-golden/knowledge.py).

Knowledge is attached by **composition**, not as a directory file: you build a `Wiki`, freeze
it, and summon it into a Definition with `with_context`. The result is a new frozen Definition
that carries a pinned reference to the knowledge — the body is not copied inline.

```python
from crawfish.wiki import Wiki, TrustTier
from crawfish.derive import with_context, SummonMode

wiki = Wiki().with_page(
    "triage-rubric",
    "P0 = outage; P1 = broken core flow; P2 = degraded; P3 = cosmetic.",
    trust=TrustTier.TRUSTED,        # first-party curated; STILL summoned tainted
)
specialized = with_context(base_definition, wiki, mode=SummonMode.READONLY)
```

## Summoned knowledge is tainted data, never instructions

`wiki.consult()` materialises each page as a **tainted** context entry: knowledge arrives as
**data the agent reads, never as an instruction surface**, and a tainted entry can never reach
an instruction slot or a static-only sink. Even `TrustTier.TRUSTED` content is summoned
tainted — the trust tier only ever *raises* suspicion, it never lowers taint. Taint can be
dropped only through an audited `declassify`, which is unreachable from a fluid path. Treat a
summoned rubric as a hint to weigh, never as a command to obey.

## Pinned by content hash; the body never enters the checksum

`with_context` stores a `SummonRef` — `{id, version, mode}` — where `version` is the Wiki's
content sha **snapshotted at compose time**. The Definition is therefore **pinned by content
hash**: `export().checksum` moves iff the pinned summon version moves, and **the summoned
body never enters the export checksum**. A frozen (eval-mode) Wiki is required for a stable
summon; `readonly()` seals an unfrozen Wiki first. In eval mode the summoned Wiki is frozen,
so two runs that summon the same pin replay identically.
