# CLI reference — `craw`

`craw` is the single entry point to a Crawfish project. Authoring, running, operating, and —
as of [Milestone 5](release-notes.md#agent-language-milestone-5-the-operator-surface) — the
**whole optimization plane** are reachable from the shell. Run `craw --help` for the live
list, or `craw <cmd> --help` for a command's exact flags; this page is the narrative map.

```text
craw {run,dev,demo,init,list,doctor,install,freeze,publish,test,build,
      deploy,manage,visualize,dashboard,export,eval,tune,refine,learn,guard,lock,
      inspect,logs}
```

## Project lifecycle

| Command | What it does |
| --- | --- |
| `craw init <dir>` | Scaffold a new project with a working example. |
| `craw dev <defn> -i k=v …` | Compile + run a Definition on the **mock** runtime (deterministic, never live). |
| `craw run` | Run the project's pipeline (the engine behind [run & engine](../reference/run-and-engine.md)). |
| `craw list` / `craw doctor` | List discovered units · report project-structure health. |
| `craw install <unit>` | Install a unit, surfacing its capabilities for consent. |
| `craw test <defn>` | Run fixtures against a Definition (eval-as-test). |
| `craw freeze` | Write `crawfish.lock` with integrity hashes (see also `craw lock`, below). |
| `craw inspect <run>` / `craw logs <run>` | Inspect a recorded run · tail its events. |

Operating a finished pipeline — `craw deploy`, `craw manage`, `craw build`, `craw visualize`,
`craw dashboard`, `craw export` — is covered in [Operate, manage & triggers](../reference/operate.md)
and [Export to Claude Code](claude-code-export.md).

## The optimization plane

The five optimization subcommands bind the already-shipped primitives — nothing here
re-implements a cost model, a search, or a gate; they make the
[PyTorch-for-LLMs library](train-and-tune.md) and the [tameness layer](tameness.md) drivable
from the shell. Every one is **deterministic by default**: all randomness flows through the
recorded `--seed`, and the default backend is the deterministic `MockRuntime`, so **there is
no live model call** unless you pass `--live`.

### Shared flags

Every optimization subcommand accepts the same five:

| Flag | Meaning |
| --- | --- |
| `--budget USD` | Cost ceiling (→ `CostBudget`); omit for unbounded. |
| `--seed N` | Deterministic seed — carries *all* randomness. Same seed ⇒ byte-identical result. |
| `--org ID` | Tenancy `org_id`, threaded to every Store read/write. |
| `--model ID` | The model id the primary agent is tuned/run on. |
| `--live` | Run against the real `claude -p` backend (default: the deterministic mock). |
| `--json` | Emit the versioned, machine-readable schema (`craw.<cmd>.v<N>`). |

The `--json` payload is the integration surface — it carries a versioned `schema` key and is
snapshot-tested, so a downstream tool can parse it stably. None of these commands fire a Sink
(Sinks are **eval-only**); they drive benchmarks and searches, not consequential egress.

### `craw eval` — score and gate on a baseline

Runs a Benchmark against the **eval-mode, frozen** Definition (it asserts the freeze via
`guard_consequential` before a recorded run) and gates the scores against a named stored
baseline. **Exits non-zero iff a metric regresses** past tolerance — wire it straight into CI.

| Flag | Meaning |
| --- | --- |
| `--baseline NAME` | The stored baseline to gate against. |
| `--set-baseline` | Save these scores *as* the baseline. |
| `--tolerance T` | Per-metric regression tolerance. |

`--json` emits per-metric scores, per-metric deltas vs the baseline, and the honest
[OPT-2 cost band](optimize-from-the-cli.md#2-the-honest-cost-interval)
(`lower_usd` / `expected_usd` / `worst_case_usd`).

```bash
craw eval definitions/triage-bot --baseline prod --tolerance 0.02 --json
```

### `craw tune` — search the knob space

Searches the Definition's tunable knobs under the cost-regularized `Objective` and the
variance-aware promotion gate. Runs in **train** mode. Same `--seed` ⇒ a byte-identical
`winner` sha and trial log.

| Flag | Meaning |
| --- | --- |
| `--models A B …` | The model knob grid to search. |
| `--max-trials N` | Autonomy ceiling on the trial count. |
| `--cost-per-trial USD` | USD charged per trial against `--budget`. |
| `--cost-regularized` | Re-rank survivors by the cost-regularized `Objective`. |

`--budget` with a per-trial cost stops with `stopped_reason="budget"` — the search is
budget-bounded, never wall-clock.

```bash
craw tune definitions/triage-bot --models claude-haiku-4-5 claude-sonnet-4-6 \
  --max-trials 12 --cost-per-trial 0.05 --budget 0.40 --cost-regularized --seed 7
```

### `craw refine` — iterate to a goal or bound

Runs the verifier-gated `Refine` loop until a goal is met or a bound is hit. **Exits non-zero
if the goal was not reached** (a bound was a bound, not a success).

| Flag | Meaning |
| --- | --- |
| `--until EXPR` | Stop expression over a Rubric metric: `<metric><op><threshold>`, op ∈ `>=`,`>` (e.g. `score>=0.95`). |
| `--max-iters N` | Max body executions — the loop bound. |

The `--until` expression DSL is shared with `--set`-style operators across the language, so the
same `score>=0.95` reads the same everywhere.

### `craw learn` — one self-versioning cycle (or roll back)

Runs one eval-gated `LearningLoop.improve` cycle that self-versions the agent, or — with
`--rollback <sha>` — re-activates a prior `VersionRecord`. **A rollback is a pointer move: no
model call.** Either a promotion or a rollback emits an audit-trail event reachable by the
AnomalyEngine circuit breaker.

| Flag | Meaning |
| --- | --- |
| `--name NAME` | The agent lineage name in the Store. |
| `--models A B …` / `--max-trials N` | The search the improve cycle runs (as `craw tune`). |
| `--rollback SHA` | Re-activate a prior version — no model call. |

### `craw guard` — distil a learned rule into a deterministic guard

Mines the `--org` corrections corpus into a `GoldenSet`, distils the supplied
**closed-grammar** predicate (parsed *as data* — never `eval`/`exec`), and synthesizes a
[`HouseGuard`](tameness.md) at its **earned** stage (`shadow` | `warn` | `block`). A guard
**cannot self-promote to `block`**; it earns blocking authority only by clearing the joint
precision/coverage gate. A blocking synthesis emits an audit event; a malformed predicate
fails closed.

| Flag | Meaning |
| --- | --- |
| `--predicate JSON` | The closed-grammar predicate, e.g. `'{"kind":"comparison",…}'`. |
| `--precision-floor P` | Precision the guard must earn before it may block. |
| `--min-coverage C` | Coverage the guard must earn before it may block. |

### `craw lock` — the reproducible dependency closure

A Definition *summons* units by reference at a version constraint; an unpinned transitive
closure breaks replay reproducibility. `craw lock` discovers the project's Definition units,
resolves the [transitive closure](optimize-from-the-cli.md#6-the-dependency-closure-and-lockfile-craw-lock),
and writes a pinned,
committable lockfile (`crawfish.closure.lock`) — every transitive ref pinned to an exact
version + `sha256:` integrity.

| Flag | Meaning |
| --- | --- |
| `--dir PATH` | Project directory holding the root Definition. |
| `--org ID` | Tenancy `org_id` recorded on the closure. |
| `--check` | **CI drift gate**: re-resolve and compare against the on-disk lockfile; exit non-zero on any drift or a missing/invalid lockfile. |

```bash
craw lock --dir .                 # write crawfish.closure.lock (commit it)
craw lock --dir . --check         # CI: fail closed if the closure drifted
```

## See also

- [Drive the language from the CLI](optimize-from-the-cli.md) — the end-to-end how-to that
  mirrors the demo.
- [The honest cost interval](optimize-from-the-cli.md#2-the-honest-cost-interval) and the
  [cost reference](../reference/cost-routing-cache.md).
- [Train, calibrate & promote](train-and-tune.md) · [Taming stochasticity](tameness.md) — the
  libraries these commands drive.
