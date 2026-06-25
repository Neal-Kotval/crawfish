# Optimize an agent from the CLI

You can run the whole optimization loop from the shell: score, search, refine, learn, guard, and lock. Where the [train and tune](train-and-tune.md) and [tameness](tameness.md) guides reach for Python, this guide does the same loop with `craw`. It also covers two tools that ship with the CLI surface: an honest cost interval and single-flight caching.

Every command is deterministic by default. The mock runtime backs each example and all randomness runs through `--seed`, so each example reproduces byte-for-byte.

For the full flag list, see the [CLI reference](cli.md). This guide is the runnable path, in the order you do it.

## 1. Score and gate with `craw eval`

`craw eval` scores a frozen, eval-mode Definition against a Benchmark and refuses to pass if a metric regressed. Everything else builds on this gate.

```bash
# First time: establish the baseline.
craw eval definitions/triage-bot --set-baseline --baseline prod --seed 1

# Thereafter, in CI: gate against it. Exits non-zero on any regression.
craw eval definitions/triage-bot --baseline prod --tolerance 0.02 --json
```

The `--json` payload carries per-metric scores, per-metric deltas against the baseline, and the honest cost band (next section). `craw eval` exits non-zero when a metric regresses past `--tolerance`, so it drops into a CI step with no wrapper script.

## 2. Read the honest cost interval

Look at the cost block in that `--json` payload. It is three numbers, not one:

```json
"cost": { "lower_usd": 0.30, "expected_usd": 0.48, "worst_case_usd": 0.60 }
```

A single number is a misleading preview. Counting one run per agent ignores the re-run multipliers that escalation, repair, retry, and `Refine` add, so a single number can only undershoot. The cost band gives you three:

- `lower_usd`: one run per agent, the lower bound.
- `worst_case_usd`: every operator multiplier folded in, with escalation re-priced on the strong model. This is the ceiling of the band, and a real run never exceeds it.
- `expected_usd`: between the two, derived from measured re-run rates with a confidence band. With no measured rates, `expected` equals `worst_case`, so the preview never undercounts.

The multipliers compose multiplicatively along the operator nesting. A `Quorum(5)` over an `Escalating(2x)` over a leaf previews `5 x 2 = 10x`. The whole fold is static analysis: it walks the assembled runtime's wrapper chain and reads declared bounds, with no model call. The mechanism is `CostShape` plus `compose_cost`. See the [cost reference](../reference/cost-routing-cache.md#costshape).

!!! note "The band's ceiling is a true upper bound"

    A budget set to `worst_case_usd` can never be blown by the run it previewed.

## 3. Coalesce identical calls with single-flight caching

The disk cassette only helps the second run. Two identical items in the same `Batch` both miss the cassette and both spend. *Single-flight* caching closes that window: when N callers issue the same request at the same time, only the first (the leader) runs the real, metered call, and the rest wait for its result.

The guarantee is exact: one `inner.run` per key gives one `CostBudget.charge`. The waiters charge `$0` and tally the spend they avoided into `saved_usd`. You see it in the cache stats:

- `coalesced`: requests that waited on an in-flight peer instead of issuing their own call.
- `hit_rate` is now `(hits + coalesced) / total`, since both avoided a fresh spend.

The coalescing key is the replay layer's own deterministic cassette key, salted with `org_id`. So coalescing changes only how many times a leaf runs, never what it returns: replay is bit-for-bit either way. It is tenant-safe: two orgs issuing an identical call get two runs, and org A's result is never served to org B. See [`CachingRuntime`](../reference/cost-routing-cache.md#cachingruntime).

When the triage demo fans out a batch with two identical tickets in flight, single-flight coalesces them. The ledger shows one model call, and the second item is charged `$0`.

## 4. Search, refine, and learn with `tune`, `refine`, and `learn`

With a gate and an honest budget in hand, run the optimization itself:

```bash
# Search the knob space under the cost-regularized objective, budget-bounded.
craw tune definitions/triage-bot \
  --models claude-haiku-4-5 claude-sonnet-4-6 \
  --max-trials 12 --cost-per-trial 0.05 --budget 0.40 \
  --cost-regularized --seed 7

# Iterate the verifier-gated Refine loop until a Rubric goal, or a bound.
craw refine definitions/triage-bot --until 'score>=0.95' --max-iters 8 --seed 7

# One eval-gated self-versioning cycle.
craw learn definitions/triage-bot --name triage --max-trials 6 --seed 7
# Or roll back to a prior version (a pointer move, no model call).
craw learn definitions/triage-bot --rollback <sha>
```

Each command is bounded and deterministic. `--seed 7` makes `tune` byte-identical across runs. `--budget` stops the search with `stopped_reason="budget"`, never on wall-clock time. `craw refine` exits non-zero if the goal was not reached, since a bound is a bound. A `learn` promotion or rollback emits an audit-trail event that the circuit breaker can read.

## 5. Distil a deterministic guard with `craw guard`

`craw guard` mines the corrections corpus into a guard. The predicate is parsed as data into a closed grammar, never `eval` or `exec`. A guard earns its blocking stage only by clearing a joint precision and coverage gate. It cannot promote itself to `block`.

```bash
craw guard definitions/triage-bot \
  --predicate '{"kind":"comparison","field":"priority","op":"in","value":["P0","P1","P2","P3"]}' \
  --precision-floor 0.95 --min-coverage 0.30 --seed 1
```

A guard that clears the gate is synthesized at `block`. One that does not stays at `warn` or `shadow`, so it fails closed. For the concept, see the house-guard in the [tameness guide](tameness.md).

## 6. Pin the dependency closure with `craw lock`

A Definition summons units by reference at a version constraint. An unpinned transitive closure breaks replay reproducibility, because an un-versioned change could enter a frozen run unnoticed. `craw lock` resolves the closure (highest compatible version, with conflict and cycle detection) and pins every transitive reference to an exact version plus a `sha256:` integrity hash.

```bash
# Resolve and write the pinned closure. Commit this file.
craw lock --dir .
git add crawfish.closure.lock && git commit -m "lock dependency closure"

# In CI: fail closed if the closure drifted from the committed lockfile.
craw lock --dir . --check
```

The lockfile records one small `closure_sha()`, the reference a run embeds, which keeps run identity small. Reading a lockfile is data-only (it never executes unit code) and re-verifies that recorded hash, failing closed on a tampered file. `--check` compares `closure_sha`: any drift, or a missing or invalid lockfile, exits non-zero. A changed summoned unit gets a new content hash, so its pin and the whole `closure_sha` diverge. An un-versioned change cannot enter a frozen closure without a re-freeze. The resolver internals are in the [API reference](api-reference.md) (`resolve`, `Lockfile`, `Pin`, `SemVer`, `CandidateSource`).

## The shape of the loop

```text
craw eval   → gate on the baseline (honest cost band in --json)
craw tune   → search the knobs (budget-bounded, cost-regularized)
craw refine → iterate to a Rubric goal
craw learn  → promote a version (or roll one back)
craw guard  → distil a deterministic guard that earns its authority
craw lock   → pin the reproducible closure, fail closed on drift
```

Every step is deterministic under `--seed`, fires no sink (the optimization plane writes nothing to the outside world), and emits a versioned `--json` schema a downstream tool can parse. A self-optimizing app drives Crawfish through the same shell you do.

## Next steps

- [CLI reference](cli.md) lists every `craw` subcommand and flag.
- [Train, calibrate, and promote](train-and-tune.md) covers the same loop in Python.
- [Taming stochasticity](tameness.md) covers verifiers, guards, and the circuit breaker.
- [Cost, routing, and cache](../reference/cost-routing-cache.md) has the honest interval and single-flight internals.
