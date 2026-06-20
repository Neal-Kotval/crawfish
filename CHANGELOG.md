# Changelog

All notable changes to Crawfish are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [`RELEASING.md`](.github/RELEASING.md) for the full semver + stability-tier policy and the
release process.

## [Unreleased]

_Nothing yet._

## [0.1.1]

Documentation and packaging polish (no code changes):

- Published the docs site at <https://neal-kotval.github.io/crawfish/> and pointed the
  PyPI `Homepage`/`Documentation` URLs at it.
- Rewrote the PyPI landing page (package README) with install, quickstart, and absolute
  documentation links.

## [0.1.0]

First public release: the **local trust loop** for agents that do bulk work over your
data. A multi-item Source fans out, a Definition team runs per item via `claude -p`, an
Aggregator reduces, a Router branches, and a Sink writes — typed, versioned, and
benchmarked, with retries, dead-letter, and crash-resume. Runs end to end locally with
**no API key** (a mock runtime drives the demo).

### Added

- **Authoring model** — pipelines authored as directories: `Source → Batch (fan-out) →
  Aggregator (reduce) → Router (branch) → Sink`. A directory compiles to a typed
  Definition; single- and multi-agent teams run via `claude -p`.
- **Typed, structural IO** — `Flow`, `Parameter`, `Node`, `Policy`, and a structural
  `TypeRegistry`: parameter compatibility resolves by structure, never string equality.
- **Versioning** — `Version` and `Freezable` artifacts (frozen artifacts reject
  mutation) with lockfile support.
- **Three swappable seams** — `AgentRuntime` (loop/backend), `Store` (persistence,
  with a WAL-mode SQLite implementation: tenancy key, transactional idempotency, event
  ledger), and `ArtifactStore` (blobs). The product model imports protocols, never a
  concrete backend.
- **Nodes** — Source (single/multi-item fan-out), Sink (idempotency, approval gate,
  static targets), Filter/Router/Classifier (branch), Aggregator (fan-in/reduce),
  Memory/state primitive, and a durable `Run` with telemetry.
- **Pipelines** — hand-wired Batch with fan-out/fan-in, a rule-based batch executor and
  scheduler, an execution-state ledger, retries with dead-letter and replay, and
  crash-resume.
- **Measurement** — metrics, rubrics, and benchmarks against golden sets; an eval data
  lifecycle; cost preview and budgets; a run inspector with streaming.
- **CLI (`craw`)** — `init` (scaffold a project), `dev` (run a Definition locally),
  `run`, `build` (container), `test`, and `doctor`. Module discovery loads Sources,
  Sinks, Definitions, and types registered via plugin entry points.
- **Operate, observe & integrate** — `craw deploy` (always-on detached supervisor with
  auto-restart and ledger resume), an observer primitive (rule-based plus
  Definition-backed LLM judge) with `ctx.emit`, `craw manage` (list/stop/restart/logs
  over the registry + ledger + cost), `craw visualize` (loopback-only dashboard), and
  `craw export --claude-code` for Claude Code integration. Configurable project
  structure via `[project.paths]`.
- **Security spine** — `Flow.FLUID` inputs are untrusted session data and reach the
  model as data, never instructions; consequential Sink targets and idempotency keys are
  static-only; secrets are matched to nodes, resolved by reference, and never logged or
  in-prompt; host-side node code runs out-of-process with taint propagation from fluid
  inputs.
- **API-stability contract** — `crawfish.stability` with `@stable` / `@experimental` /
  `@deprecated` decorators and `stability_of`; semver helpers (`is_breaking`,
  `migration_note`). Untagged public names default to **experimental**.
- **Docs** — a MkDocs documentation site (product, architecture + ADRs, security,
  guides, cookbook, API reference).

<!-- TODO(maintainer): set the published dist name (assumed `crawfish`; confirm
     availability on PyPI) and the org/repo slug in the comparison links below. -->

[Unreleased]: https://github.com/Neal-Kotval/crawfish/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Neal-Kotval/crawfish/releases/tag/v0.1.0
