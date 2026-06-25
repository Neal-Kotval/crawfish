# ADR 0012 — Definitions are versioned (and versioning stays invisible)

**Status:** Accepted · **Date:** 2026-06-21 · **Milestone:** Phase 2

*(ADR 0011 is reserved for the ruvLLM/rvagent adopt-vs-build decision from the
evaluation spike.)*

## Context

A fair question recurs: does a *local* agent framework need versioning at all, or
could authors "just create new files"? `versioning/` ships `Version` + `Freezable`,
the canonical loader derives a content-hash identity (ADR 0006), and the compiler
writes a `definition.lock`. That looks like ceremony a lightweight framework could
skip.

Two observations resolve it. First, **versioning is already invisible to the author**:
nobody hand-bumps a version. Identity is a SHA derived automatically from the
directory's contents; the `major.minor` comes from `pyproject.toml`. There is no
workflow imposed on the person writing markdown. Second, **versioning is load-bearing
for the things that make Crawfish more than a one-shot runner** — exactly the Phase 2
moat.

## Decision

Keep content-derived versioning, and keep it **invisible** (auto-derived, never
hand-maintained). It is justified by four concrete dependents, not by principle:

- **Eval gating** — `gate_against_baseline` compares a candidate against a stored
  baseline; "did this change regress?" requires two identifiable versions.
- **The Tuner** (Phase 2) — proposes a new `Definition` programmatically and promotes
  it only if it beats the baseline; the proposal *is* a new frozen `Version`.
- **Learning agents** (Phase 2) — self-edit instructions, promote on a benchmark win,
  and **roll back by pinning an older `Version`**; "just new files" has no lineage and
  no rollback.
- **Crash-safe resume** — the execution ledger pins an in-flight pipeline to the
  version it started on, so a redeploy applies to *new* pipelines only and a running
  one never changes behaviour mid-flight.

Constraint that comes with this decision: versioning must **stay auto-derived**. If a
change would force authors to maintain versions by hand, that change is wrong — fix the
ergonomics, don't add ceremony.

## Alternatives rejected

- **No versioning; files only.** Simplest, and correct *if* the product were only
  "run an agent once." It makes eval gating, the Tuner, learning-agent rollback, and
  version-pinned resume impossible — it would gut the Phase 2 thesis.
- **Manual semver authored by the user.** Ceremony with no payoff; the content hash
  already gives reproducible identity for free, and humans bump versions
  inconsistently.

## Consequences

Versioning earns its place specifically through *improvable, reproducible, auditable*
orchestration; it is an enabler of the moat, not decoration. The cost is the internal
machinery (`Version`/`Freezable`, the lock file), which must remain invisible to
authors. If Crawfish ever narrows to a fire-and-forget run-once tool, revisit this ADR
— the justification is the improvement loop, and it stands or falls with it.
