# Editorial spec — readability pass (for doc subagents)

Goal: make the docs **flow** and be **understandable to a working developer who is new
to Crawfish**. Cut excess prose and unnecessary technicality. You have broad latitude to
rewrite prose — but never break what is verified or factual (see HARD CONSTRAINTS).

## The bar
- **Lead with the point.** First sentence of any section says what it is and why it
  matters. No throat-clearing wind-ups.
- **Plain words first.** Prefer the everyday word over the jargon one. When a technical
  term is unavoidable, define it in plain words at first use, then use it freely.
- **Short sentences, active voice.** Break any sentence that runs past ~25 words or holds
  two ideas. Cut filler: "basically", "in order to", "it's worth noting", "simply",
  "note that", "essentially", "as such", "in essence", hedges like "generally"/"typically"
  when they add nothing.
- **One idea per paragraph.** Long dense paragraphs become 2–3 short ones or a list.
- **Concrete over abstract.** A short example or a named thing beats an abstract
  description. Tables/bulleted lists beat a wall of prose when enumerating.
- **Say it once.** Remove repetition within a page and obvious restatement across tiers.
- **Trim technicality that doesn't earn its place.** Internal mechanism detail that a user
  never acts on can be cut or moved to a single "How it works" line. Keep the invariants and
  rationale that change how someone uses the thing.

## Reference pages specifically
- Keep the three tiers: **Core** (newcomer-readable, plain English), **How it works**
  (mechanics + rationale, but flowing — not a wall of invariants), **API reference**
  (lookup tables/signatures — keep intact, just keep any intro sentence short).
- Keep every symbol covered. Do not drop a symbol from the page.

## HARD CONSTRAINTS (do not violate)
- **Never modify a ```python code block, a ```text output block, a shell command, or a
  signature.** The reference examples are verified byte-for-byte and must stay identical.
  Edit prose around them only.
- **Never change a technical claim, field name, default, enum value, or behavioural fact.**
  Those are verified against source. You are improving wording and flow, not facts. If a
  sentence is wrong, leave it and note it in your reply — do not invent a correction.
- Keep the page's required headings and structure intact.
- Edit prose in place with the Edit tool. Do not touch any file outside your assignment.

## Your reply
Per page: one line on what you changed (or "no change needed"), and flag any factual
sentence you suspect is wrong (so the orchestrator can verify it against source).
