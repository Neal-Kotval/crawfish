# Drive the language from the CLI

[Milestone 5](release-notes.md#agent-language-milestone-5-the-operator-surface) makes the
whole optimization plane drivable from the shell. Where the
[train-and-tune](train-and-tune.md) and [tameness](tameness.md) guides reach for Python, this
guide does the same loop from `craw` — score, search, refine, learn, guard, and lock — plus
the two accuracy-and-honesty primitives that ship alongside the surface: the **honest cost
interval** and **single-flight caching**. Every command is deterministic by default (the mock
runtime, all randomness through `--seed`), so each example reproduces byte-for-byte.

The full per-command flag list is the [CLI reference](cli.md); this is the runnable path, in
the order you actually do it.

## 1. Score and gate — `craw eval`

The eval gate is the foundation everything else stands on: it scores the **frozen, eval-mode**
Definition against a Benchmark and refuses to pass if a metric regressed.

```bash
# First time: establish the baseline.
craw eval definitions/triage-bot --set-baseline --baseline prod --seed 1

# Thereafter (in CI): gate against it. Exits non-zero on any regression.
craw eval definitions/triage-bot --baseline prod --tolerance 0.02 --json
```

The `--json` payload carries per-metric scores, per-metric **deltas** vs the baseline, and the
honest cost band (next section). Because `craw eval` exits non-zero *iff* a metric regresses
past `--tolerance`, it drops straight into a CI step — no wrapper script.

## 2. The honest cost interval

Look at the cost block in that `--json` payload. It is **three numbers, not one**:

```json
"cost": { "lower_usd": 0.30, "expected_usd": 0.48, "worst_case_usd": 0.60 }
```

A single point estimate is a dishonest preview: counting one run per agent is blind to the
re-run multipliers that escalation, repair, retry, and `Refine` add, so the advertised number
could only ever *undershoot*. Milestone 5 makes the preview an **honest band**:

- `lower_usd` — the old point estimate: one run per agent, the **lower bound**.
- `worst_case_usd` — every operator multiplier folded in, escalation re-priced on the strong
  model. This is the **advertised band's ceiling**: a real run never exceeds it.
- `expected_usd` — between the two, derived from measured re-run rates (with a CI band). With
  no measured rates, `expected == worst_case` — the preview never undercounts.

The multipliers compose *multiplicatively* along the operator nesting: a `Quorum(5)` over an
`Escalating(2×)` over a leaf previews `5 × 2 = 10×`. The whole fold is pure static analysis —
it walks the assembled runtime's wrapper chain and reads declared bounds; no model call. The
mechanism is `CostShape` + `compose_cost`; see the
[cost reference](../reference/cost-routing-cache.md#costshape).

!!! note "Why this matters"

    The contract is one-directional and load-bearing: **the advertised band is a true upper
    bound.** A budget set to `worst_case_usd` can never be blown by the run it previewed.

## 3. Single-flight caching — one charge for N identical calls

The disk cassette only helps the *second* run. Two identical items in the *same* `Batch` both
miss the cassette and both spend. **Single-flight** (request coalescing) closes that window:
when N concurrent callers issue the *same* request, only the first (the leader) runs the real,
metered call; the rest await its result.

The guarantee is exact: **one `inner.run` per key ⇒ one `CostBudget.charge`.** The coalesced
waiters charge `$0` and tally the spend they avoided into `saved_usd`. You see it in the cache
stats:

- `coalesced` — requests that awaited an in-flight peer instead of issuing their own call.
- `hit_rate` is now `(hits + coalesced) / total` — both avoided a fresh spend.

It is a *strict* refinement: the coalescing key is the replay layer's own deterministic
cassette key, salted with `org_id`, so coalescing only changes *how many times* a leaf runs,
never *what* it returns (replay is bit-for-bit either way). And it is tenant-safe: two orgs
issuing an identical call get **two** runs — org A's computation is never served to org B. See
[`CachingRuntime`](../reference/cost-routing-cache.md#cachingruntime).

When the triage demo fans out a batch with two identical tickets in flight, single-flight
coalesces them: the ledger shows one model call, the second item charged `$0`.

## 4. Search, refine, learn — `tune` / `refine` / `learn`

With a gate and an honest budget in hand, drive the optimization itself:

```bash
# Search the knob space under the cost-regularized objective, budget-bounded.
craw tune definitions/triage-bot \
  --models claude-haiku-4-5 claude-sonnet-4-6 \
  --max-trials 12 --cost-per-trial 0.05 --budget 0.40 \
  --cost-regularized --seed 7

# Iterate the verifier-gated Refine loop until a Rubric goal (or a bound).
craw refine definitions/triage-bot --until 'score>=0.95' --max-iters 8 --seed 7

# One eval-gated self-versioning cycle…
craw learn definitions/triage-bot --name triage --max-trials 6 --seed 7
# …or instantly roll back to a prior version (a pointer move — no model call).
craw learn definitions/triage-bot --rollback <sha>
```

Each is bounded and honest: `--seed 7` makes `tune` byte-identical across runs; `--budget`
stops the search with `stopped_reason="budget"` (never wall-clock); `craw refine` exits
non-zero if the goal was *not* reached (a bound is a bound); and a `learn` promotion or
rollback emits an audit-trail event reachable by the circuit breaker.

## 5. Distil a deterministic guard — `craw guard`

Mine the corrections corpus into a guard. The predicate is parsed *as data* into a closed
grammar (never `eval`/`exec`), and the guard **earns** its blocking stage only by clearing a
joint precision/coverage gate — it cannot self-promote to `block`:

```bash
craw guard definitions/triage-bot \
  --predicate '{"kind":"comparison","field":"priority","op":"in","value":["P0","P1","P2","P3"]}' \
  --precision-floor 0.95 --min-coverage 0.30 --seed 1
```

A guard that clears the gate is synthesized at `block`; one that doesn't stays at `warn` or
`shadow` (fails closed). The conceptual frame is the
[house-guard in the tameness guide](tameness.md).

## 6. The dependency closure and lockfile — `craw lock`

A Definition *summons* units by reference at a version constraint. An unpinned transitive
closure breaks replay reproducibility — an un-versioned mutation could silently enter a frozen
run. `craw lock` resolves the closure (highest compatible version, conflict/cycle detection)
and pins every transitive ref to an exact version + `sha256:` integrity:

```bash
# Resolve + write the pinned closure. Commit this file.
craw lock --dir .
git add crawfish.closure.lock && git commit -m "lock dependency closure"

# In CI: fail closed if the closure drifted from the committed lockfile.
craw lock --dir . --check
```

The lockfile records one small `closure_sha()` — the reference a run embeds, keeping run
identity small. Reading a lockfile is **data-only** (it never executes unit code) and
re-verifies that recorded sha, failing closed on a tampered file. `--check` is a pure
`closure_sha` comparison: any drift, or a missing/invalid lockfile, exits non-zero. A mutated
summoned unit gets a new content sha, so its pin — and the whole `closure_sha` — diverges; an
un-versioned mutation cannot enter a previously-frozen closure without a re-freeze. The
resolver internals are in the [API reference](api-reference.md) (`resolve`, `Lockfile`, `Pin`,
`SemVer`, `CandidateSource`).

## The shape of the loop

```text
craw eval   → gate on the baseline (honest cost band in --json)
craw tune   → search the knobs (budget-bounded, cost-regularized)
craw refine → iterate to a Rubric goal
craw learn  → promote a version (or roll one back)
craw guard  → distil a deterministic guard that earns its authority
craw lock   → pin the reproducible closure, fail closed on drift
```

Every step is deterministic under `--seed`, fires no Sink (the optimization plane is
egress-free), and emits a versioned `--json` schema a downstream tool can parse. That is the
operator surface: the self-optimizing app drives Crawfish through the same shell you do.

## See also

- [CLI reference](cli.md) — every `craw` subcommand and flag.
- [Train, calibrate & promote](train-and-tune.md) · [Taming stochasticity](tameness.md).
- [Cost, routing & cache](../reference/cost-routing-cache.md) — the honest interval and
  single-flight internals.
