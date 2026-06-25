# How to write the Crawfish docs

This is the playbook for writing and editing the public docs. It covers the one vision the
docs sell, how pages are structured, what goes public versus internal, and the checklist a page
must pass before it ships. Pair it with [WRITING_STYLE.md](./WRITING_STYLE.md), which covers
voice and sentence-level rules.

## The one vision

Everything in the public docs serves a single idea:

> **Crawfish is a programming language for agents.**

You write agents as typed components in a directory. Like any language, Crawfish gives you
primitives (typed inputs and outputs, nodes, runtimes), a way to compose them (pipelines that
fan out, reduce, branch, and write results), versioning (every agent is content-addressed, like
git), and tooling to run, test, and improve what you build.

The other themes are features of that language, not competing visions. Frame them this way:

- **Testing and iteration** is the language's tooling: deterministic runs, evals, the tuner.
  ("Like a compiler and a test runner for agents.")
- **Visibility** is being able to read any run: the event ledger, the inspector, the dashboard.
- **Composability** is the type system: nodes wire together only when their shapes match.
- **Local-first** is where the language runs by default: your machine, no API key.

Do not introduce a second framing on a page. Do not write "Crawfish is two halves" or "the
PyTorch half." A reader should be able to repeat the one-line vision after reading any page.

## What is public, what is internal

Public docs (`docs/`, the published site) teach a developer how to use Crawfish. They contain
getting started, the tutorial, concept and how-to guides, the CLI and API reference, and a
short architecture and security overview.

Internal docs (`dev_docs/`, not published) are for the people building Crawfish. They contain
the roadmap, the language vision, the ADRs (decision records), the product positioning, the
build log, and the changelog working notes.

The test: if a page argues for a decision, lists what is not built yet, or tracks the team's
plan, it is internal. If a page helps a reader build and run something, it is public. When a
public page wants to explain why a design is the way it is, give it one sentence and link to the
ADR in `dev_docs/`.

There is no "Product" page and no "Roadmap" page in the public nav. Positioning lives on the
home page as a working example, not as a pitch. The roadmap lives in `dev_docs/`.

## Page types

Match the page to the reader's job. We use four types, following the Stripe and Next.js split.

**Home (`index.md`).** One screen: what Crawfish is (the one vision), the 30-second install and
run, and links into the three sections. No feature tour.

**Getting started and tutorial.** A path from zero to a running, useful result. Numbered steps.
Every command and code block runs as written. Open with a "What you'll build" list. This is the
Stripe quickstart shape.

**Guides (the Learn section).** One page per task or concept the reader needs to understand:
pipelines, the type and injection boundary, runtimes, refine and verify, compose, train and
tune, and so on. A guide teaches one idea with a runnable example, then links to the reference
for the exact signatures. Open with one or two sentences on what you will do and why it matters.

**Reference.** Look-up pages for exact API: every public symbol, each node's signature, the CLI.
Terse, complete, accurate. The reader is here to confirm a type or an argument, not to learn the
concept. Link back to the guide that teaches it.

## The shape of a guide page

1. Title names the task or the thing, in sentence case.
2. One or two sentences: what you will do, and the one reason it matters.
3. Optional "What you'll build" or "You will learn" list, only if the page has several sections.
4. The first code block or command appears early, within the first screen.
5. Each section: show the code, then explain in a sentence or two. Point at the key detail.
6. At most one callout per concept, for a real footgun.
7. "Next steps": two to four links to the logical next pages.

## Process: small to large

Write and review in order, so the voice is set before it spreads.

1. Set the foundation: this playbook and the style guide. Done first because everything
   references them.
2. Rewrite the core pages: home, getting started, concepts, tutorial. These set the tone.
3. Fan out to the rest: the remaining guides, then the reference pages.
4. Verify: build the site, check links, grep for em dashes and banned words, read for flow.

When you rewrite a page, change the voice and the structure, but keep the technical facts. Do
not invent API. If the existing page says `check_wiring()` type-checks at assembly, the rewrite
says the same thing in plainer words. When unsure whether a fact is current, check the reference
page or the source in `packages/crawfish/`, do not guess.

## Internalize the reference style first

Before writing, actually read the reference doc sites, following their subroutes a few pages
deep. The specific pages to study are listed in [WRITING_STYLE.md](./WRITING_STYLE.md) under
"Read these before you write." The point is to match the rhythm of a real page (where the first
code block lands, how short the paragraphs are, how a page hands off to the next), which a rules
list alone will not give you. If a page returns only a shell when fetched, render it with the
browser tools rather than working from memory.

## Checklist before a page ships

A page is done when:

- The first sentence states the task or the fact, not the philosophy.
- A code block or command appears within the first screen.
- There are no em dashes. (Search the file.)
- There are no banned words from the style guide ("revolutionary," "the X half," "load-bearing,"
  "leverage," "simply," "just").
- Headings are sentence case and name a task or a thing.
- Every code block declares a language and runs as written.
- Bold and callouts are rare. At most one callout per concept.
- Every term is defined the first time it appears.
- The page ends with two to four "Next steps" links.
- It reads in one pass. A new developer would not need to re-read a sentence.
