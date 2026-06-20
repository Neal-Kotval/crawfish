# Crawfish Security Spine

Security is a **spine, not a phase** — enforced on every feature from day one.

## The invariants

1. **Fluid inputs are untrusted session data (the prompt-injection boundary).**
   `Flow.FLUID` values (a ticket body, a diff an agent produced) reach the model as
   *data*, never concatenated into instructions. `Flow.STATIC` values are set once at
   batch start. Typing distinguishes the two (`crawfish.core`); the Definition
   compiler/runtime enforces the boundary (M1).

2. **Consequential Sink targets are static-only.** A Sink's *destination* (repo,
   project, channel) comes from `Flow.STATIC` config — never from fluid, model- or
   data-derived values. A compromised item cannot redirect a write.

3. **Idempotency keys derive from static config.** `key = hash(batch_id, item_id,
   static_sink_config)`; the check-then-write is a single transaction
   (`SqliteStore.claim_idempotency`, `INSERT OR IGNORE`) — no race under concurrency.

4. **Secrets matched to nodes; never logged or in-prompt.** `.env` is gitignored;
   a node receives only the secrets it declares (least privilege — the embryonic
   capability manifest). Credentials resolve **by reference**, never in `config`.
   Transcripts are scrubbed.

5. **Host-side node code runs out-of-process; taint propagates from fluid inputs.**
   Any value derived from a fluid input stays tainted and cannot silently become a
   static Sink target or an idempotency key.

6. **Supply chain.** `crawfish.lock` carries integrity hashes; install-time
   capability consent gates what a plugin may touch.

## Implementation status (Phase 1)

Shipped: static-vs-fluid typing (`crawfish.core`) + prompt-compiler boundary
(`runtime/prompt.py`); static-only Sink targets + idempotency keyed on **stable
per-item lineage + static config only** (never the random output id or model output)
with the approval gate evaluated *before* the claim (`nodes/sink.py`); taint
**originated** on fluid-source fan-out and on Runs with fluid inputs, propagating
through `Output.derive`/lineage (`nodes/source.py`, `run.py`); credentials by
reference + `.env` loader + node↔secret least-privilege mapping (`crawfish.secrets`);
transcript/telemetry redaction before the Store write (`ScrubbingStore`); install-time
capability consent + full-digest lockfile integrity (`craw install` / `craw freeze`);
out-of-process host-side execution + an egress-allowlist primitive (`crawfish.sandbox`).

Deferred (tracked separately): egress-mediated secret *injection* (a local
CommandRuntime can still read `.env` in-sandbox — the known v1 tradeoff); transparent
egress *interception* (the broker is a cooperative `guard()` allowlist today, not a
network chokepoint) and runtime enforcement of the consented capability manifest;
full microVM/seccomp hardening beyond out-of-process isolation.

## The operate/observe layer

The always-on layer — [deploy](../guide/deploy.md), [observers](../guide/observers.md),
[visualize](../guide/visualize.md), [manage](../guide/manage.md),
[export](../guide/claude-code-export.md) — inherits the spine above and adds four
operate-specific guarantees:

1. **Scrubbed observer events & run-info.** `ObserverEvent` and `RunInfo` are written
   through `ScrubbingStore` (reused, not reinvented) before the Store write, so no secret
   value reaches an event, the dashboard, `craw manage logs`, or a log file. Every row
   carries `org_id`.

2. **No-secret detached processes.** The `craw deploy` supervisor keeps secrets **by
   reference**, exactly as a foreground run: no credential in argv, the session name
   (`crawfish/<pipeline>`), the detached environment, the deploy registry row, or the
   supervisor log.

3. **Loopback-only dashboard.** `craw visualize` binds `127.0.0.1` only — no off-host
   surface — and renders only the scrubbed run-info surface.

4. **Cost-capped LLM observers.** A Definition-backed observer judge runs under the same
   `CostBudget`/`CostMeter` and the same static-vs-fluid prompt-injection boundary as any
   Definition: run data is **data**, never instructions, and spend is capped and
   telemetered.

The [`craw export --claude-code`](../guide/claude-code-export.md) output carries **no
secrets** — it maps tool/MCP *references* only (the `tools` allowlist), never an `auth`
reference or a credential value, so the generated file is safe to commit.

## Review gate

Every feature is audited against these invariants by the security reviewer before
its Linear issue can move to `Done`. High/Critical findings **block** completion.
The final pass includes a prompt-injection red-team against the demo's fluid inputs.
