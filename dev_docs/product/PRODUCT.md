# Crawfish — Product

Positioning, the hero use case, and who Crawfish is for.

## Positioning (the wedge)

Crawfish is a framework for **building agents like software**. You define an agent — or a
whole team — as typed, versioned components in a directory, run it locally against
`claude -p` or a local model, and treat the result as something you test, diff, and
improve, not a prompt you keep poking at.

Most agent frameworks are **conversation-centric** (one chat, one task) or a thin SDK over
a hosted API. Crawfish brings real-engineering discipline to agent work instead:

- **Agents as code.** Agents, tools, data shapes, and policies are plain files you check
  into git — infrastructure-as-code for local model work.
- **Composable by design.** Small typed nodes snap together; one node's output wires to
  the next only when their shapes match.
- **Deterministic and testable.** Typed IO, structural type-checking, frozen versions, and
  record/replay make a run reproducible — snapshot it and gate changes in CI, no live model.
- **Built to improve.** Score a pipeline with rubrics and evals, then let the tuner search
  for better prompts and settings and promote the winner.
- **Local-first.** Everything runs on your machine by default; cloud and scale are a driver
  swap, not a rewrite.

## Hero use case

> Build a single sharp agent, a multi-agent team, or a scheduled automation as typed code —
> run it locally, test it like software, and improve it on purpose.

Running a job over your data **in bulk** is one thing you can build this way: a multi-item
Source fans out (`Source → Batch → Aggregator → Router → Sink`), a Definition team runs per
item via `claude -p`, an Aggregator reduces, a Router branches by classification, and a Sink
opens real PRs (dry-run → real). The same building blocks express a lone agent or a
scheduled team just as readily.

## Personas

- **The builder** — wants to ship an agent as code, not maintain a brittle prompt. Cares
  about typed IO, composition, and running the same definition locally and in CI.
- **The automator** — wants many items triaged/processed without babysitting a chat. Cares
  about fan-out, retries/dead-letter, and cost caps.
- **The quality owner** — wants to *trust* agent output before it ships. Cares about
  rubrics, benchmarks vs. golden sets, and catching regressions across Definition versions.
- **The framework author** — builds reusable Definitions (agent-team directories) and
  shares them. Cares about typed IO, versioning/freezing, and a stable API.

## Why local-first matters

`pip install crawfish` + `craw init` + `craw dev` gives a working loop in minutes with
**zero API key** — it uses the user's Claude subscription via `claude -p`. Adoption lever
#1: minutes from install to an impressive, useful result.

!!! note "Good to know"
    Local-first is the default, not a limitation. The three architectural seams
    (`AgentRuntime`, `Store`, `ArtifactStore`) mean the same definition that runs on your
    laptop scales to cloud by swapping a driver — see [Architecture](../architecture/ARCHITECTURE.md).

## See also

- [Getting started](../guide/getting-started.md) — install and run your first agent
- [Concepts](../guide/concepts.md) — the directory model, pipelines, and runtimes
- [Architecture](../architecture/ARCHITECTURE.md) — the three swappable seams
- [Roadmap](../roadmap/README.md) — what shipped and what's next
