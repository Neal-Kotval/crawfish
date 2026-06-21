# ADR 0010 — Ruflo: inspiration, not adoption

**Status:** Accepted · **Date:** 2026-06-20 · **Milestone:** Phase 2

## Context

[Ruflo](https://github.com/ruvnet/ruflo) (formerly claude-flow, MIT) is a mature
multi-agent orchestration layer for Claude Code with capabilities that overlap our
Phase 2 backlog: self-learning agents (SONA neural patterns, ReasoningBank, trajectory
learning), HNSW vector memory (AgentDB), multi-provider smart routing with failover,
local-model inference (ruvLLM + MicroLoRA), a WASM agent sandbox (rvagent), and
federation with PII/secret stripping. The MIT license permits us to read, adapt, and
even copy its code with attribution. The temptation is to recreate its feature set.

Two facts make wholesale adoption the wrong move. First, **philosophy mismatch**: Ruflo
is broad and fuzzy by design (33 plugins, 100+ agents, vector recall, "a nervous system
for Claude Code"); Crawfish's wedge is the opposite — a small, typed, versioned,
deterministic, auditable core (the security spine, content-hashed Definitions, the
static/fluid boundary). Importing Ruflo's surface area would dilute exactly what
differentiates us, and we cannot out-surface-area a project with that much momentum.
Second, **stack mismatch**: Ruflo is TypeScript + a Rust engine + WASM; Crawfish is
Python. Most of it cannot be lifted, so anything we adopt is reimplemented regardless.

## Decision

Treat Ruflo as **inspiration, not a dependency to clone**. Ideas and algorithms are fair
to borrow; code and architecture are not adopted directly. Anything we adopt is
reimplemented natively in Python **through an existing seam** (`AgentRuntime`, `Store`,
`ArtifactStore`, `Output`/taint, `Definition`/`Version`) so it inherits our typing, taint
propagation, and determinism. Heavy infrastructure far from our core value is integrated
as an optional dependency, never recreated.

Per-capability stance:

| Ruflo capability | Stance | Why |
| --- | --- | --- |
| Smart multi-provider routing / failover | **Borrow idea, reimplement** | Maps cleanly onto `AgentRuntime`; keep small and typed (ADR 0005 universal model type holds). |
| Trajectory learning (SONA / ReasoningBank) | **Borrow idea, reimplement** | Use trajectory capture as the *signal* for learning agents; keep eval-gated, versioned promotion as the safety layer. |
| Local-model inference (ruvLLM, MicroLoRA) | **Depend on, don't rebuild** | Hard infra (Rust engine), far from core value; wire behind `AgentRuntime` as a backend after an evaluation spike. |
| Agent sandbox (rvagent WASM) | **Depend on / reference** | Reference for the out-of-process sandbox; evaluate WASM vs subprocess-jail rather than hand-roll. |
| Vector memory (AgentDB / HNSW) | **Use a library if ever needed** | Do not hand-roll a vector DB (use sqlite-vec / lancedb / `ruvector`); our typed KV + dedup memory is the better fit for the thesis. |
| Federation, plugin marketplace, GOAP planner | **Skip (off-thesis for now)** | Interesting, not the Phase 2 wedge. |

If any actual Ruflo source is copied (not merely reimplemented), retain the MIT notice
and cite it here.

## Alternatives rejected

- **Recreate Ruflo's feature set in Crawfish.** A treadmill against a faster-moving,
  better-resourced project; imports its fuzzy paradigm and erodes our typed/deterministic
  edge.
- **Adopt Ruflo wholesale as a dependency.** Cross-stack (TS/Rust/WASM), and its plugin
  sprawl + ambient agent model conflict with the security spine and content-hashed identity.
- **Ignore it entirely.** Wastes real, validated ideas (eval signals from trajectories,
  local-model routing for cost) that serve our backlog when reimplemented our way.

## Consequences

Phase 2 work cites this ADR where it touches Ruflo's territory: learning agents
(trajectory signal, our eval-gated versioning), sandboxing (rvagent reference), and
cost/CPU optimization (build-vs-buy on ruvLLM). Adopting a heavy dependency (e.g. ruvLLM
behind `AgentRuntime`) requires its own evaluation spike and a follow-up ADR. The cost of
this discipline is occasionally rebuilding something Ruflo already ships; the benefit is a
core that stays typed, deterministic, and auditable.
