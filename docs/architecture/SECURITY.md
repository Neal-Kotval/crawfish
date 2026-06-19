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
   data-derived values. A compromised item cannot redirect a write. (CRA-104/CRA-114)

3. **Idempotency keys derive from static config.** `key = hash(batch_id, item_id,
   static_sink_config)`; the check-then-write is a single transaction
   (`SqliteStore.claim_idempotency`, `INSERT OR IGNORE`) — no race under concurrency.

4. **Secrets matched to nodes; never logged or in-prompt.** `.env` is gitignored;
   a node receives only the secrets it declares (least privilege — the embryonic
   capability manifest). Credentials resolve **by reference**, never in `config`.
   Transcripts are scrubbed. (CRA-114)

5. **Host-side node code runs out-of-process; taint propagates from fluid inputs.**
   Any value derived from a fluid input stays tainted and cannot silently become a
   static Sink target or an idempotency key. (CRA-114)

6. **Supply chain.** `crawfish.lock` carries integrity hashes; install-time
   capability consent gates what a plugin may touch. (CRA-113/CRA-114)

## Review gate

Every feature is audited against these invariants by the security reviewer before
its Linear issue can move to `Done`. High/Critical findings **block** completion.
The final pass includes a prompt-injection red-team against the demo's fluid inputs.
