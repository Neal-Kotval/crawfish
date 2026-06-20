# ADR 0007 — Team coordination via hierarchical delegation, not a message bus

**Status:** Accepted · **Date:** 2026-06-19 · **Milestone:** M1

## Context

A Definition's `TeamSpec` listed agents with no rule for how they work together, so
multi-agent behaviour was undefined. We need coordination semantics that preserve the
type system and the prompt-injection boundary.

## Decision

Lean on **Claude's hierarchical subagent model**, not a bespoke peer-to-peer message
bus or shared-ownership system. `TeamSpec` carries `coordination` (`single` | `lead` |
`sequential`), `lead`, and `workspace`; `AgentSpec.delegates_to` lists the subagent
roles an agent may dispatch.

Communication is **delegation-in / typed-result-out**: a lead dispatches a subagent
with typed inputs and receives a typed result, which re-enters the lead as **fluid
data** (never as instructions). There is no free-form channel.

`run_team` is a **runtime-agnostic coordinator** mapping topology to `AgentRuntime`
calls — so it works with the mock runtime and tests are deterministic. For backends
with native hierarchical subagents (CommandRuntime / CMA) the same topology can later
collapse into one native multiagent call; the explicit coordinator is the portable
default.

## Alternatives rejected

- **Peer-to-peer message bus** — free-form channels break typing and reopen the
  injection boundary (a peer could inject instructions into another).
- **Runtime-native delegation only** — not portable or testable without a live model.

## Consequences

Subagent results are always typed text re-entering as fluid data, keeping the security
boundary intact. A future optimization can delegate natively inside one runtime call
without changing the topology authors write.
