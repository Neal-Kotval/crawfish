# Security

Crawfish holds an agent's untrusted data away from its consequential actions. This page
explains the boundaries that make that hold and the guarantees you can rely on. Security
is enforced on every feature, not added as a phase.

The central idea is the prompt-injection boundary. A *fluid* value is untrusted session
data, such as a ticket body or a diff the agent produced. A fluid value reaches the model
as data, never as instructions. A *static* value is set once at batch start. The type
system distinguishes the two, and the compiler and runtime enforce the boundary.

!!! warning "The prompt-injection boundary"
    `Flow.FLUID` values are untrusted session data. They reach the model as data, never
    as instructions. Consequential sink targets and idempotency keys are static-only, so
    a compromised item can never redirect a write or forge an idempotency key.

## The core rules

These six rules hold across every feature.

1. Fluid inputs are untrusted session data. A `Flow.FLUID` value reaches the model as
   data, never concatenated into instructions. A `Flow.STATIC` value is set once at batch
   start. Typing distinguishes the two in `crawfish.core`, and the Definition compiler and
   runtime enforce the boundary.

2. Consequential sink targets are static-only. A sink's destination (a repo, a project, a
   channel) comes from static config, never from fluid or model-derived values, so a
   compromised item cannot redirect a write.

3. Idempotency keys derive from static config. The key hashes the batch id, item id, and
   static sink config. The check-then-write is a single transaction
   (`SqliteStore.claim_idempotency` with `INSERT OR IGNORE`), so there is no race under
   concurrency.

4. Secrets are matched to nodes and never logged or placed in a prompt. `.env` is
   gitignored, and a node receives only the secrets it declares. Credentials resolve by
   reference, never in `config`, and transcripts are scrubbed.

5. Host-side node code runs out of process, and taint propagates from fluid inputs. Any
   value derived from a fluid input stays tainted, so it cannot silently become a static
   sink target or an idempotency key.

6. The supply chain is pinned. `crawfish.lock` carries integrity hashes, and install-time
   capability consent gates what a plugin may touch.

!!! warning "Secrets resolve by reference"
    A node receives only the secrets it declares, resolved by reference, never in
    `config`, never logged, never in a prompt. Transcripts and telemetry are scrubbed
    before the Store write.

## What ships today

Crawfish enforces static-vs-fluid typing (`crawfish.core`) plus the prompt-compiler
boundary (`runtime/prompt.py`). Sink targets are static-only, and idempotency keys derive
from stable per-item lineage and static config only, never the random output id or model
output. The approval gate runs before the idempotency claim (`nodes/sink.py`).

Taint originates on fluid-source fan-out and on runs with fluid inputs, and propagates
through `Output.derive` and lineage (`nodes/source.py`, `run.py`). Credentials resolve by
reference through an `.env` loader with a node-to-secret least-privilege mapping
(`crawfish.secrets`). Transcripts and telemetry are redacted before the Store write
(`ScrubbingStore`). Install-time capability consent and full-digest lockfile integrity
ship in `craw install` and `craw freeze`. Host-side code runs out of process, with an
egress-allowlist primitive (`crawfish.sandbox`).

Some hardening is deferred and tracked separately. A local `CommandRuntime` can still read
`.env` inside its sandbox, which is a known v1 tradeoff. Egress is a cooperative `guard()`
allowlist rather than a network chokepoint, and the consented capability manifest is not
yet enforced at runtime. Full microVM and seccomp hardening beyond out-of-process
isolation is also pending.

## The operate and observe layer

The always-on layer inherits the rules above and adds four guarantees. It covers
[deploy](../guide/deploy.md), [observers](../guide/observers.md),
[visualize](../guide/visualize.md), [manage](../guide/manage.md), and
[export](../guide/claude-code-export.md).

1. Observer events and run info are scrubbed. `ObserverEvent` and `RunInfo` are written
   through `ScrubbingStore` before the Store write, so no secret value reaches an event,
   the dashboard, `craw manage logs`, or a log file. Every row carries an `org_id`.

2. Detached processes carry no secrets. The `craw deploy` supervisor keeps secrets by
   reference, exactly as a foreground run. No credential lands in argv, the session name,
   the detached environment, the deploy registry row, or the supervisor log.

3. The dashboard is loopback only. `craw visualize` binds `127.0.0.1` only, with no
   off-host surface, and renders only the scrubbed run-info surface.

4. LLM observers are cost-capped. A Definition-backed observer judge runs under the same
   cost budget and the same prompt-injection boundary as any other Definition. Run data is
   data, never instructions, and spend is capped and telemetered.

The `craw export --claude-code` output carries no secrets. It maps tool and MCP references
only, never an auth reference or a credential value, so the generated file is safe to
commit.

## Tenancy and run identity

Tenancy enters run identity. The `org_id` folds into the replay cassette key (when it is
not `"local"`) and is carried on every loop-ledger row. Two tenants cannot collide on a
cassette, and a resume in one org sees none of another org's completed loop iterations, so
cross-tenant resume cannot replay another org's work.

No decode field escapes run identity. The tunable knobs (`temperature`, `top_p`,
`sample_k`) enter the Definition's version hash, and the per-call `decode_seed` enters the
cassette key. Two distinct decode settings can no longer replay identically.

Mutable borrows are tenancy-scoped and Store-enforced. The train-mode exclusive borrow
keys both its idempotency claim and its lock record on `org_id`, so a borrow held by one
org never blocks or is visible to another. Enforcement lives in the Store, so exclusivity
holds across processes and survives the SQLite-to-Postgres swap.

## Language-era surfaces

The agent language adds new fluid surfaces and new consequential gates. These extend the
six core rules, never relax them. Each new surface is `Flow.FLUID`: it reaches the model
as data, and any value derived from it stays tainted.

| Surface | What it is | How it is bounded |
| --- | --- | --- |
| Refine feedback | prior model output fed into the next iteration | stays fluid and tainted, and cannot reach a static sink target |
| router and classifier labels | a model-derived branch label | may gate whether a consequential action fires, never choose among distinct consequential sinks |
| verifier verdicts and quorum samples | a fold or vote over prior output | tainted if any input was |
| retrieved knowledge | summoned wiki or retrieved documents | retrieved content is tainted, and a summoned wiki is frozen and cannot be mutated under a run |
| generated artifacts | a Definition or guard the `craw code` loop produced | must pass the assembly gate to ship, and an un-benchmarked guard cannot gate |
| correction corpus | ground truth for learned guards and verifiers | admitted only if its provenance is trusted and it is not tainted, otherwise quarantined |

Three more rules cover these surfaces.

7. A consequential sink fires only in eval mode. A sink reached against an unfrozen
   (train or `mutable`) Definition raises. Only a frozen, content-hashed artifact may take
   an irreversible action, so every side effect is attributable to one reproducible hash.
   A summoned wiki is likewise frozen in eval mode.

8. Fluid-to-static-sink injection is rejected at assembly time. A wiring where a fluid
   value could reach a consequential static-only slot is rejected before any model call,
   and a generated artifact must clear it to ship. The check is conservative: sound for
   the fragment it covers, incomplete, and fails closed. It is defense in depth atop the
   runtime `StaticOnlyError` and `TargetMustBeStaticError`.

9. Aggregate taint is the union, and `declassify` is the only audited way to drop it. Any
   fold, vote, or summary is tainted if any input was, so taint cannot be laundered by
   aggregation. The only way to drop taint is an explicit, audited `declassify`, which is
   unreachable from a fluid dataflow path. Taint accrues monotonically.

The correction corpus is ground truth for learned guards and verifiers, so a poisoned
corpus is an attack surface. Every correction declares its provenance (trusted or
untrusted) and carries the taint propagated from any fluid-derived value. A correction
becomes trusted ground truth only if its provenance is trusted and it is not tainted.
Anything untrusted or tainted is quarantined: it stays on the ledger for audit but never
gates anything. A fluid-derived value cannot become ground truth even if mislabelled
trusted, because taint wins.

The precision gate fails closed. It is an absolute decision-quality gate for consequential
verifiers, guards, and sinks. An un-benchmarked verifier, no positive predictions, or
measured precision below the minimum all raise. The rule is reject unless measured good,
not admit unless proven bad. A consequential verifier or guard must pass the precision gate
against a real baseline before it may gate anything.

## Review gate

Every feature is audited against these rules before it ships. The security reviewer signs
off before an issue can move to done, and high or critical findings block completion.

The sign-off pairs two suites. The static suite is the taint and non-interference
conformance suite, which asserts that `tainted` survives every boundary, including the
aggregate-union rule. The behavioural gate is the operator-level prompt-injection red team
(`packages/crawfish/tests/test_redteam_security.py`,
`crawfish.testing.redteam_attacks`), which asserts that a concrete injection against each
new fluid surface is blocked offline. A change that adds a new fluid surface must add at
least one injection payload for it.

## Next steps

- [Architecture](ARCHITECTURE.md) covers the three seams the security model rides on.
- [Concepts](../guide/concepts.md) covers the boundary in the directory model.
- [API stability](API-STABILITY.md) covers semver and the deprecation policy.
