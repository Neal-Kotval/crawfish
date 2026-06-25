# Crawfish writing style

This is the house style for the public Crawfish docs. It is compiled from three docs sites
we want to read like: [Stripe](https://docs.stripe.com/), [Next.js](https://nextjs.org/docs),
and [React](https://react.dev/learn). Read this before you write or edit a public page. The
companion playbook, [HOW_TO_WRITE_DOCS.md](./HOW_TO_WRITE_DOCS.md), covers page structure and
process.

The short version: write to one developer, lead with the task, show the code, explain in one
line, and cut every word that does not change the meaning.

## Read these before you write

Do not work from this summary alone. Open the reference sites and read several pages deep,
following the subroutes, so you absorb how a real page is paced (where the first code block
lands, how long a paragraph runs, when a heading turns over). Read at least three subpages from
each site:

- React, for teaching voice and "show then explain":
  [Quick Start](https://react.dev/learn), [Describing the UI](https://react.dev/learn/describing-the-ui),
  [Adding Interactivity](https://react.dev/learn/adding-interactivity),
  [Tutorial: Tic-Tac-Toe](https://react.dev/learn/tutorial-tic-tac-toe).
- Stripe, for task-first pages and numbered steps:
  [Accept a payment](https://docs.stripe.com/payments/accept-a-payment),
  [Quickstart](https://docs.stripe.com/payments/quickstart),
  [Checkout](https://docs.stripe.com/payments/checkout).
- Next.js, for IA and "tell the reader where they are":
  [Docs home](https://nextjs.org/docs), [Getting Started](https://nextjs.org/docs/app/getting-started),
  [Installation](https://nextjs.org/docs/app/getting-started/installation),
  [Project Structure](https://nextjs.org/docs/app/getting-started/project-structure).

If a fetch returns only a page shell, render it with the browser tools instead of guessing.
Spend the time here. The goal is to match the rhythm, not just the rules.

## What we borrow from each site

**React (react.dev/learn): teach, don't lecture.** Warm and direct. Talks to "you." One
concept at a time, each with a small example you can run. After the example, one sentence on
why it works. Points at the important detail ("Notice how the target is static"). Introduces a
term in italics the first time, then just uses it.

**Next.js: tell the reader where they are.** Every section says what it is for. The docs are
split into Getting Started (learn the basics), Guides (solve one use case), and Reference (look
up the details), and the intro says so. State prerequisites up front. No throat-clearing.

**Stripe: lead with the task.** Pages are named for what you are doing ("Accept a payment"),
not for the concept. Numbered steps. Code you can copy and run. Almost no vision talk in a
how-to page. The reader wants to ship something, so the page helps them ship it.

## Voice

Write in second person, present tense, active voice. The reader is "you." Crawfish is "it" or
"Crawfish," never "we."

Lead with the task or the fact, not the philosophy. The first sentence of a page or section
says what you will do or what the thing is. Save the motivation for one line after, if at all.

Show, then explain. Put the code or the command first, or right next to the claim. Follow it
with one sentence on why it matters. Do not explain for three paragraphs before the reader sees
anything concrete.

Be plain. A smart developer who is new to Crawfish should understand every sentence on the
first read. If a sentence needs a second read, split it or cut it.

Teach how to use the thing. Public docs explain what something does and how to use it. They do
not argue for the design or walk through alternatives we rejected. That belongs in `dev_docs/`
(the ADRs and the language vision). If you find yourself defending a decision, move it.

## Sentences

Keep sentences short. One idea each. If a sentence has three clauses joined by dashes, it is
three sentences.

Cut filler. Remove "in order to" (use "to"), "is able to" (use "can"), "it is important to
note that," "simply," "just," "basically," "of course." A good test: delete a word. If the
meaning survives, leave it deleted.

Prefer concrete nouns over abstract ones. Write "the ticket body" not "the per-item payload."
Write "the sink writes to Linear" not "the egress boundary performs a side effect."

Define a term the first time you use it, in plain words, then use the term. Example: "A *sink*
is the one place a pipeline writes to the outside world. Every sink target is static."

## Punctuation

No em dashes. They hide run-on sentences. Replace them with a period, a comma, a colon, or
parentheses. If you reach for a dash to join two thoughts, that is usually two sentences.

- Before: "Going from dev to prod is a runtime swap — not a code change — and it costs nothing."
- After: "Going from dev to prod is a runtime swap, not a code change. It costs nothing."

Use parentheses sparingly, and never stack them. One aside per sentence at most. If a sentence
has two parentheticals, rewrite it.

Use a colon to introduce a list or a definition. Use a period to end a thought. That is most of
the punctuation you need.

## Formatting

Headings are sentence case ("Run it with a real model," not "Run It With A Real Model"). They
describe a task or a thing, like a Stripe page title. Avoid clever headings like "The PyTorch
half." Name what the section teaches.

Use **bold** rarely. Bold a term the first time it carries weight, or the word "static" /
"fluid" when the safety rule depends on it. Do not bold whole sentences. If half a paragraph is
bold, none of it stands out.

Use *italics* for a term on first definition only.

Always put a blank line before a list, and a blank line between a heading and the content under
it. This is required for correct rendering.

Bullets are for genuinely parallel items (a set of runtimes, a set of options). Prose is for
explanation. Do not turn an explanation into a bullet list to look shorter. Each bullet is a
full sentence or a clean `name` + short gloss.

Code fences always declare a language (` ```python `, ` ```bash `, ` ```text `). Keep examples
runnable and minimal. Show the smallest thing that makes the point, then build on it.

Use a table when you are comparing options across the same columns (runtimes by cost, install
methods by use case). Do not use a table for prose.

Callouts (`!!! note`, `!!! warning`) are rare. At most one per concept. A warning marks a real
footgun (the static-vs-fluid boundary, static-only sink targets). A note adds a useful aside.
If every section has a callout, they stop meaning anything.

## Words to avoid

Cut hype and insider shorthand:

- "revolutionary," "powerful," "seamless," "magic," "simply," "just"
- "the X half," "one level up," "the unifier," "the thesis"
- "load-bearing," "by construction" (unless you immediately say how), "first-class"
- "leverage" (use "use"), "utilize" (use "use"), "performant" (use "fast")

Prefer the plain word: use over leverage, run over execute (when talking to the reader), set up
over configure (when casual), fast over performant.

## Linking and structure

Link forward to the next thing the reader should read, and link to the reference page for exact
signatures. Do not re-explain a concept that has its own page; link to it in one clause.

End a page with a short "Next steps" list of two to four links. Start a learning page with a
one-line "You will learn" or "What you'll build" list if it has more than a couple of sections.

## Before and after

These are real edits from the current docs. Use them as a calibration.

**Lead with the task, drop the manifesto.**

- Before: "Everything above is the deterministic, typed, versioned half of Crawfish: an agent
  is a frozen artifact with a content hash. This section is the other half, the part that
  learns. The thesis is one sentence: an agent is a model with tunable weights."
- After: "You can score a pipeline and let Crawfish search for better prompts and settings, then
  promote the version that wins. This page shows the loop: measure, tune, promote."

**Kill the dashes and the stacked clauses.**

- Before: "`Refine` is that loop; `Verifier` is the critic that can stop it — and a critic must
  *earn* the authority to stop you (fail-closed, gated, benchmarked)."
- After: "`Refine` runs a step in a loop until the result is good enough. A `Verifier` decides
  when to stop. A verifier cannot stop a loop until it has been benchmarked and gated, so an
  untested critic fails closed instead of ending the loop early."

**Say what it does before why it is safe.**

- Before: "Injection is rejected by construction. `craw prove --no-injection` is a pre-flight,
  fail-closed certificate that no `Flow.FLUID` input can reach a consequential static-only Sink
  target or idempotency slot."
- After: "`craw prove --no-injection` checks, before you run, that no untrusted (fluid) input
  can reach a sink target. If it cannot prove that, it fails. Use it as a pre-flight gate in
  CI."

**Plain words.**

- Before: "A multi source fans out to one `Run` per item, and `check_wiring()` type-checks at
  assembly."
- After: "A multi source produces one run per item. `check_wiring()` checks the types when you
  assemble the pipeline, before any model call."
