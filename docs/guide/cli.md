# CLI reference: `craw`

`craw` is the entry point to a Crawfish project. You author, run, operate, and optimize a project from the shell. Run `craw --help` for the live list, or `craw <cmd> --help` for a command's exact flags. This page is the narrative map.

```text
craw {run,dev,demo,init,list,doctor,install,freeze,publish,test,build,
      deploy,manage,visualize,dashboard,export,eval,tune,refine,learn,guard,lock,
      inspect,logs}
```

## Project lifecycle

| Command | What it does |
| --- | --- |
| `craw init <dir>` | Scaffold a new project with a working example. |
| `craw dev <defn> -i k=v …` | Compile and run a Definition on the mock runtime (deterministic, never live). |
| `craw run` | Run the project's pipeline (the engine behind [run and engine](../reference/run-and-engine.md)). |
| `craw list` / `craw doctor` | List discovered units. Report project-structure health. |
| `craw install <unit>` | Install a unit, surfacing its capabilities for consent. |
| `craw test <defn>` | Run fixtures against a Definition (eval-as-test). |
| `craw freeze` | Write `crawfish.lock` with integrity hashes (see also `craw lock`, below). |
| `craw inspect <run>` / `craw logs <run>` | Inspect a recorded run. Tail its events. |

Operating a finished pipeline (`craw deploy`, `craw manage`, `craw build`, `craw visualize`, `craw dashboard`, `craw export`) is covered in [Operate, manage and triggers](../reference/operate.md) and [Export to Claude Code](claude-code-export.md).

## The optimization plane

Five subcommands drive the optimization library and the tameness layer from the shell. None of them re-implement a cost model, a search, or a gate. They make the [tunable-ML library](train-and-tune.md) and the [tameness layer](tameness.md) drivable from the shell.

Every one is deterministic by default. All randomness flows through the recorded `--seed`, and the default backend is the deterministic `MockRuntime`, so there is no live model call unless you pass `--live`.

### Shared flags

Every optimization subcommand accepts the same flags:

| Flag | Meaning |
| --- | --- |
| `--budget USD` | Cost ceiling (becomes a `CostBudget`). Omit for unbounded. |
| `--seed N` | Deterministic seed, carrying all randomness. The same seed gives a byte-identical result. |
| `--org ID` | Tenancy `org_id`, threaded to every Store read and write. |
| `--model ID` | The model id the primary agent is tuned or run on. |
| `--live` | Run against the real `claude -p` backend (default: the deterministic mock). |
| `--json` | Emit the versioned, machine-readable schema (`craw.<cmd>.v<N>`). |

The `--json` payload is the integration surface. It carries a versioned `schema` key and is snapshot-tested, so a downstream tool can parse it stably. None of these commands fire a sink (sinks are eval-only). They drive benchmarks and searches, not consequential egress.

### `craw eval`: score and gate on a baseline

Runs a Benchmark against the eval-mode, frozen Definition (it asserts the freeze via `guard_consequential` before a recorded run) and gates the scores against a named stored baseline. Exits non-zero when a metric regresses past tolerance, so you can wire it straight into CI.

| Flag | Meaning |
| --- | --- |
| `--baseline NAME` | The stored baseline to gate against. |
| `--set-baseline` | Save these scores as the baseline. |
| `--tolerance T` | Per-metric regression tolerance. |

`--json` emits per-metric scores, per-metric deltas against the baseline, and the cost band (`lower_usd` / `expected_usd` / `worst_case_usd`).

```bash
craw eval definitions/triage-bot --baseline prod --tolerance 0.02 --json
```

### `craw tune`: search the knob space

Searches the Definition's tunable knobs under the cost-regularized `Objective` and the variance-aware promotion gate. Runs in train mode. The same `--seed` gives a byte-identical `winner` sha and trial log.

| Flag | Meaning |
| --- | --- |
| `--models A B …` | The model knob grid to search. |
| `--max-trials N` | Autonomy ceiling on the trial count. |
| `--cost-per-trial USD` | USD charged per trial against `--budget`. |
| `--cost-regularized` | Re-rank survivors by the cost-regularized `Objective`. |

`--budget` with a per-trial cost stops with `stopped_reason="budget"`. The search is budget-bounded, never wall-clock.

```bash
craw tune definitions/triage-bot --models claude-haiku-4-5 claude-sonnet-4-6 \
  --max-trials 12 --cost-per-trial 0.05 --budget 0.40 --cost-regularized --seed 7
```

### `craw refine`: iterate to a goal or bound

Runs the verifier-gated `Refine` loop until a goal is met or a bound is hit. Exits non-zero if the goal was not reached (a bound is a bound, not a success).

| Flag | Meaning |
| --- | --- |
| `--until EXPR` | Stop expression over a Rubric metric: `<metric><op><threshold>`, op in `>=`, `>` (for example, `score>=0.95`). |
| `--max-iters N` | Maximum body executions, the loop bound. |

The `--until` expression syntax is shared with the `--set`-style operators across the language, so the same `score>=0.95` reads the same everywhere.

### `craw learn`: one self-versioning cycle, or roll back

Runs one eval-gated `LearningLoop.improve` cycle that self-versions the agent. With `--rollback <sha>`, it re-activates a prior `VersionRecord`. A rollback is a pointer move: no model call. Either a promotion or a rollback emits an audit-trail event reachable by the AnomalyEngine circuit breaker.

| Flag | Meaning |
| --- | --- |
| `--name NAME` | The agent lineage name in the Store. |
| `--models A B …` / `--max-trials N` | The search the improve cycle runs (as in `craw tune`). |
| `--rollback SHA` | Re-activate a prior version. No model call. |

### `craw guard`: distil a learned rule into a deterministic guard

Mines the `--org` corrections corpus into a `GoldenSet`, distils the supplied closed-grammar predicate (parsed as data, never `eval` or `exec`), and synthesizes a [`HouseGuard`](tameness.md) at its earned stage (`shadow`, `warn`, or `block`). A guard cannot self-promote to `block`. It earns blocking authority only by clearing the joint precision and coverage gate. A blocking synthesis emits an audit event. A malformed predicate fails closed.

| Flag | Meaning |
| --- | --- |
| `--predicate JSON` | The closed-grammar predicate, for example `'{"kind":"comparison",…}'`. |
| `--precision-floor P` | Precision the guard must earn before it may block. |
| `--min-coverage C` | Coverage the guard must earn before it may block. |

### `craw lock`: the reproducible dependency closure

A Definition summons units by reference at a version constraint. An unpinned transitive closure breaks replay reproducibility. `craw lock` discovers the project's Definition units, resolves the transitive closure, and writes a pinned, committable lockfile (`crawfish.closure.lock`). Every transitive ref is pinned to an exact version plus a `sha256:` integrity hash.

| Flag | Meaning |
| --- | --- |
| `--dir PATH` | Project directory holding the root Definition. |
| `--org ID` | Tenancy `org_id` recorded on the closure. |
| `--check` | CI drift gate: re-resolve and compare against the on-disk lockfile. Exits non-zero on any drift or a missing or invalid lockfile. |

```bash
craw lock --dir .                 # write crawfish.closure.lock (commit it)
craw lock --dir . --check         # CI: fail closed if the closure drifted
```

## Next steps

- [Drive the language from the CLI](optimize-from-the-cli.md): the end-to-end how-to that mirrors the demo.
- [Cost reference](../reference/cost-routing-cache.md): how cost estimates and routing work.
- [Train, calibrate and promote](train-and-tune.md) and [Taming stochasticity](tameness.md): the libraries these commands drive.
