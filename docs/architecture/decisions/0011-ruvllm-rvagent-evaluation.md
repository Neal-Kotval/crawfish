# ADR 0011 — ruvLLM / rvagent evaluation (the ADR 0010 "depend on after a spike" clause, made concrete)

**Status:** Accepted · **Date:** 2026-06-21 · **Milestone:** Phase 2 · **Spike:** CRA-183

## Context

[ADR 0010](0010-ruflo-inspiration-not-adoption.md) settles the build-vs-adopt
philosophy for Ruflo: borrow ideas, reimplement natively through our seams, and
**depend on heavy infrastructure only "after an evaluation spike and a follow-up
ADR."** Two rows in ADR 0010's table were explicitly deferred to that gate:

- **Local-model inference (ruvLLM / MicroLoRA)** — "Depend on, don't rebuild … wire
  behind `AgentRuntime` as a backend after an evaluation spike." This is the cost
  track: **CRA-182** ([P2-12] Cost & CPU optimization) wants cheap local models for
  cheap/low-stakes steps, gated by an eval (CRA-175) to prove no quality regression.
- **Agent sandbox (rvagent WASM)** — "Reference for the out-of-process sandbox;
  evaluate WASM vs subprocess-jail." This is the isolation mechanism for **CRA-179**
  ([P2-09] Sandboxed pipelines).

This ADR records the evidence ADR 0010's clause requires. It does **not** relitigate
the philosophy. It evaluates each of the two candidate dependencies against the frozen
seams (the `Provider` / `AgentRuntime` model-call seam from ADR 0001/0005, and the
`Jail` isolation seam CRA-179 relies on) and reaches a per-capability verdict.

The OS-native side of the sandbox question (seccomp / namespaces / `sandbox-exec`
portability) is owned by the sibling spike **CRA-188** and is deliberately **not**
decided here; this ADR scopes only whether the **rvagent / WASM** option is mature and
adoptable as our isolation mechanism, and feeds its verdict into CRA-188's comparison.

Per the CRA-183 review addendum, the evaluation includes a **license + supply-chain +
threat-model** review per capability — running third-party Rust/WASM for inference or
isolation is a trust decision, not just a perf number.

## What was evaluated

1. **ruvLLM** (and the realistic local-inference path behind our `Provider` protocol)
   on these axes: maturity / licensing, fit *behind* the frozen `Provider` /
   `AgentRuntime` seam (`name` / `models` / `supports` / async `run`) without bypassing
   it, determinism / testability (can it be mocked or record-replayed so tests stay
   live-call-free per our Definition of Done?), footprint, and dependency-vs-thin-adapter.
2. **rvagent / WASM sandboxing** as the CRA-179 isolation mechanism: maturity /
   adoptability, taint / escape guarantees (FS + egress isolation, the property CRA-179
   relies on), and footprint — deferring the deep OS comparison to CRA-188.

## Evidence

### ruvLLM (local inference)

- **It is not a mature, general-purpose, Python-callable inference server.** ruvLLM
  lives inside `ruvnet/RuVector` as an **edge / embedded** engine: Rust-first, SIMD +
  WASM + ESP32 microcontroller focus, Q4_K_M quantization, sparse attention for
  bare-metal class hardware. The published crates are `ruvllm-esp32` (v0.3.2) and
  `ruvllm_sparse_attention` (v0.1.1) — microcontroller-grade version numbers, not a
  serving runtime.
- **It deliberately refuses a Python runtime.** The `ruvllm_sparse_attention` crate
  states plainly: *"There are no plans to add Python bindings, as this crate is
  intentionally Rust-only — the value is in not depending on a Python runtime."*
  Crawfish is the Python framework. Adopting ruvLLM means embedding a Rust/WASM engine
  with no first-class Python surface — the exact cross-stack lift ADR 0010 rejects.
- **It is entangled with SONA / MicroLoRA self-learning.** Its differentiator is
  per-request fine-tuning and continuous self-optimization — *non-deterministic by
  design*. That collides head-on with our Definition of Done: deterministic,
  live-call-free tests (fixtures / record-replay). A model that mutates itself per
  request is not record-replayable behind our seam without disabling its reason to exist.
- **The realistic local-inference path is already a thin adapter.** `llama.cpp` /
  `llama-server` and Ollama expose an **OpenAI-compatible HTTP API**
  (`localhost:8080` / `localhost:11434/v1`), accept a `--seed` for reproducible
  decoding, and are reachable from any HTTP client with zero engine code. This fits
  *behind* our frozen `Provider` protocol as a `LocalHTTPProvider` (`name` =
  `"local"`, `models` from the served set, async `run` = one HTTP call) with **no new
  heavy dependency** and full record-replay (the existing `RecordReplayRuntime` `_key`
  cassette hash covers it unchanged). Determinism is "good enough to compare" via seed
  pinning; tests record the cassette and never call the model live.

### rvagent (WASM sandbox)

- **It is real and the isolation model is sound — but it is npm/JS-native.** rvagent is
  `@ruvector/rvagent-wasm`, surfaced through Ruflo's `ruflo-agent` plugin as a local,
  WASM-sandboxed agent harness on Wasmtime. The capability story is exactly what
  CRA-179 needs: WASI is **deny-by-default** for filesystem, network, and OS — no host
  FS access unless a directory is explicitly *preopened*, **no network capability
  unless granted**, plus memory isolation and fuel-metered CPU. *"A WASM agent can't
  touch your filesystem"* is the documented contract.
- **The escape guarantee comes from Wasmtime, not from rvagent.** The strong isolation
  is Wasmtime's WASI capability model (preopen dirs, deny-all egress, CFI in progress).
  rvagent is a JS wrapper around it. We can get the *same* guarantee from
  **`wasmtime-py`** (the official Python bindings: WASI preopen, fuel, memory caps)
  without adopting the npm package or standing up a Node host inside our Python engine.
- **rvagent runs agent *prompts*, not arbitrary host-side Python.** rvagent's tools
  (`wasm_agent_create` / `wasm_agent_prompt` / …) sandbox an *agent loop*. CRA-179's
  `Jail` must sandbox **host-side user node code** (sources / sinks / filters) and
  serialize `Output.tainted` across the boundary. rvagent has no concept of our taint
  contract; bolting it on is reimplementation regardless. The reusable asset is the
  Wasmtime/WASI *pattern*, which `wasmtime-py` gives us directly in-process.

## Decision

**ruvLLM — do-not-adopt (defer / reimplement as a thin adapter).** Do not take ruvLLM
(or any RuVector crate) as a dependency. The cheap-local-model leg of CRA-182 is served
by a `LocalHTTPProvider` thin adapter behind the frozen `Provider` protocol, targeting
an OpenAI-compatible local server (llama.cpp / Ollama), seed-pinned for determinism and
record-replayed in tests. No new heavy dependency lands; no engine code is vendored.

**rvagent — do-not-adopt (use the WASM *mechanism* via `wasmtime-py`, not the npm
package).** Do not take `@ruvector/rvagent-wasm` as a dependency. If CRA-188 selects
WASM as the CRA-179 isolation mechanism, implement the `Jail` against **`wasmtime-py`**
(WASI preopen for folder-scoped FS, deny-all egress, fuel/memory caps), with our taint
serialized across the boundary natively. rvagent remains a *reference* for the WASI
capability shape, consistent with ADR 0010's "reference, don't rebuild a sandbox."

Both verdicts honor ADR 0010: the *ideas* (local-model routing for cost; WASI
capability isolation) are adopted; the *cross-stack code* is not. The "depend on heavy
infra" clause is satisfied by depending on a mature, Python-reachable runtime
(llama.cpp/Ollama via HTTP; Wasmtime via `wasmtime-py`) rather than the ruv-ecosystem
packages, which the evidence shows are immature for our use and stack-mismatched.

## Impact on dependent issues (orchestrator: read this)

**CRA-182 premise — NOT invalidated, but re-pointed.** The cheap-local-model cost path
*survives*: it just routes to a `LocalHTTPProvider` (llama.cpp/Ollama), not ruvLLM.
CRA-182's acceptance criteria are unchanged. Concretely: implement `Provider`
resolution so a `RoutingPolicy` rule can target `model="local"`; the local leg is a
seed-pinned HTTP call recorded as a cassette; the eval gate (CRA-175) still proves no
quality regression. The only edit is the *backend identity*, not the design.

**CRA-179 premise — NOT invalidated.** The out-of-process, folder-scoped jail *survives*.
The mechanism choice stays gated on **CRA-188**; this ADR narrows CRA-188's WASM option
to **`wasmtime-py` (in-process WASI)**, not rvagent/npm. If CRA-188 picks WASM, build
`Jail` on `wasmtime-py`; if it picks a subprocess jail, rvagent was never on the table.
Either way CRA-179's acceptance criteria (no out-of-folder read, no undeclared egress,
taint survives the boundary) are met natively.

**Escalation flag: NO.** No dependent issue's premise is invalidated. Both negative
verdicts (don't adopt ruvLLM; don't adopt rvagent) leave the dependent issues fully
buildable via mature Python-reachable substitutes; no re-scoping is required. The spike
returns a clean "depend on the mature substrate, not the ruv package" result.

## Alternatives rejected

- **Adopt ruvLLM behind `AgentRuntime`.** Rust/WASM/ESP32-grade, no Python bindings *by
  design*, and self-mutating (SONA/MicroLoRA) — un-record-replayable, breaking our
  deterministic-test rule. Cross-stack lift ADR 0010 already warns against.
- **Adopt `@ruvector/rvagent-wasm` for CRA-179.** npm/JS-native; would require a Node
  host inside the Python engine, sandboxes agent prompts not host-side Python nodes, and
  has no notion of our taint contract. The reusable part (Wasmtime/WASI) is available
  directly via `wasmtime-py`.
- **Hand-roll a local inference engine or a sandbox.** Off-thesis and exactly what ADR
  0010 forbids ("do not hand-roll"); the mature substrates (llama.cpp/Ollama, Wasmtime)
  already exist and sit cleanly behind our seams.
- **Defer the cost path entirely until a ruv package matures.** Unnecessary — the thin
  adapter unblocks CRA-182 now with no heavy dependency and no quality risk (eval-gated).

## Consequences

- CRA-182 gains a local-inference cost leg with **zero new heavy dependency** — a thin
  `LocalHTTPProvider` adapter behind the frozen `Provider` protocol, seed-pinned and
  record-replayed.
- CRA-179 / CRA-188 carry forward a **single concrete WASM option** (`wasmtime-py`),
  removing rvagent/npm from the comparison and keeping the taint contract native.
- ADR 0010's per-capability table is now backed by evidence for its two deferred rows;
  no production dependency on the ruv ecosystem is added, as that ADR required.
- The cost of this discipline is writing two thin adapters instead of importing a
  pre-built one; the benefit is a core that stays Python-native, deterministic, and
  auditable, with no Rust/WASM/npm runtime smuggled across our seams.
