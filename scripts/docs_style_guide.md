# Crawfish docs style guide

Synthesized from how the best dev-docs are actually built (Next.js, React, Stripe,
Tailwind, Prisma, Supabase). This is the bar for every reference page.

## The shape of a reference page (flexible, not a rigid template)

There are no more `## Core` / `## How it works` tiers. Instead, each page **eases the
reader in, then deepens only as far as the topic needs**, and ends with a lookup section.
Small topics stay short; complex ones grow more sections. The progression is the point —
don't bombard the reader up front.

A typical page, top to bottom:

1. **One-line definition.** The first sentence says what the thing is, in plain words, no
   preamble. "A `Sink` is a node that writes a pipeline's results to the outside world —
   a Linear issue, a GitHub PR." Then one or two sentences on why it exists / when you reach
   for it. No wind-up, no "In this section we will…".
2. **(Optional) "On this page" bullet map** for longer pages — a short bulleted list of
   anchor links so the reader sees the scope in three seconds. Skip it on short pages.
3. **Ease-in explanation.** The plain-English mental model, in short paragraphs. Define any
   term before using it. This is where a newcomer should be able to stop and still get it.
4. **Deeper sections, only as needed**, under their own natural `##`/`###` headings named
   for what they cover ("Structural compatibility", "Width subtyping", "The lease
   lifecycle") — NOT generic tier labels. A simple page may have none of these.
5. **Example** — at least one deterministic runnable example with the collapsible
   `??? success "▶ Output"` block. Keep these exactly as they are (they're verified).
6. **API reference** — the exact signatures, fields, members for each symbol. Tables for
   model fields and enum values; fenced signatures for functions.
7. **See also / Next** — a short list of links to the natural next pages. Never dead-end.

## Voice & prose

- **Second person, present tense, imperative.** "Use `Aggregator` to reduce a batch into
  one result," not "The Aggregator is a node which can be used to…".
- **Short sentences.** Break anything over ~25 words or holding two ideas.
- **Prose is connective tissue between code, not the payload.** A sentence or two, then show
  it. Cut filler ("basically", "in order to", "it's worth noting", "simply", "note that").
- **Lead with the point** in every section's first sentence.

## Callouts (use MkDocs admonitions)

- `!!! note "Good to know"` — caveats, defaults, and gotchas, placed right after the
  happy-path explanation. (Next.js's highest-leverage device.)
- `!!! warning` — security-spine footguns and anything that can cause a consequential
  mistake. **Security-critical rules get a real warning callout, never a buried sentence.**
  Examples: `Flow.FLUID` is untrusted data; sink targets are static-only; secrets resolve
  by reference and never enter a prompt.
- `!!! tip` — optional shortcuts and good practice.

## Inline parameter tags

When a field/param carries a meaning the reader must not miss, tag it inline in its
description: **static-only**, **FLUID (untrusted)**, **secret-ref**, **required**,
default value. Make the security model legible in the param list itself.

## Examples

- Prefer a short **ladder** of named examples (simple → richer) when a page warrants it,
  each under a descriptive heading. A single solid example is fine for small pages.
- Where it fits, show the **failure path** too (a budget trip, a rejected fluid target) —
  not just the happy path.
- Examples stay deterministic (pure functions / `MockRuntime` / fixtures), and their code
  and `▶ Output` blocks are **verified byte-for-byte — never edit them**.

## HARD CONSTRAINTS

- Never modify a ```python code block, a ```text output block, a shell command, or a
  signature line. Reorganize prose and headings around them.
- Never change a technical fact, field name, default, enum value, or behavioural claim.
- Keep every assigned symbol covered on the page. Don't drop coverage.
- The page must still contain its runnable example + `▶ Output`, and an API reference of
  every symbol.
