# Lay out a project and check it with craw doctor

A Crawfish project is a directory of components you author plus state Crawfish generates. By
default, Crawfish discovers components from the standard layout. When a different shape fits
your repo, move folders in `crawfish.toml`. `craw doctor` checks the structure and flags
problems.

## The canonical layout

```text
my-app/
├── crawfish.toml          # project config + profiles
├── sources/               # Source nodes (pipeline ingress)
├── sinks/                 # Sink nodes (the egress side effect)
├── definitions/           # Definition directories (the agent teams)
├── pipelines/             # Workflows wiring source to batch to sink
├── observers/             # Observer definitions
├── tools/                 # tool callables
├── policies/              # Policy instances
└── .crawfish/             # GENERATED — locks, ledger, cassettes, registry (gitignore)
```

You write and commit the first seven folders. `.crawfish/` is generated: locks, the
execution ledger, cassettes, and the deploy registry. Crawfish keeps the two separate so
your intent and the machine's state never mix.

!!! warning "Do not hand-edit `.crawfish/`"
    Everything under `.crawfish/` is machine state: the ledger, registry, and cassettes.
    Gitignore it and leave it alone. `craw doctor` flags a hand-edited generated artifact,
    because a tampered artifact must never pass for trusted authored config.

## Relocate folders with [project.paths]

Override any folder location in `crawfish.toml`. The CLI, the compiler, and `craw doctor`
all read the configured path, so discovery follows the override everywhere:

```toml
[project.paths]
definitions = "agents/"      # author Definitions under agents/ instead
observers   = "watch/"
# unset keys keep their canonical default (sources/, sinks/, …)
```

After this, `craw deploy agents/triage-bot` and `Definition.from_package("agents/...")`
resolve against the relocated tree. Nothing else changes.

## Check the project with craw doctor

Run `craw doctor` to confirm your project matches the layout Crawfish expects.

```bash
craw doctor
```

`craw doctor` checks three things. First, it confirms each configured folder exists. Second,
it flags misplaced files, such as a Definition sitting in `tools/`, or a stray Python file
outside any known folder. Third, it verifies that authored and generated state stay
separate: nothing under `.crawfish/` is hand-edited, and no generated artifact has leaked
into the authored tree.

`craw doctor` reads the filesystem and `crawfish.toml` only. It never resolves a secret or
runs a model, so it is safe to run anytime: in CI, in a hook, or on a fresh clone.

Run it against the demo project:

```bash
craw doctor
# project: my-app   (crawfish.toml ok)
# ✔ sources/        2 files
# ✔ definitions/    1 (triage-bot)
# ✔ pipelines/      1
# ✔ observers/      1 (quality)
# ✔ .crawfish/      generated — clean (ledger, registry, cassettes)
# ⚠ tools/format.py  looks like a Definition (has instructions.md) — move to definitions/?
# doctor: 1 warning
```

To fix the warning, move the misplaced directory. Or, if you meant to use a custom layout,
declare it in `[project.paths]` and re-run. The warning clears once discovery and the
filesystem agree.

## Why the authored-vs-generated split matters

The authored-vs-generated check is itself a guardrail. Keeping `.crawfish/` (the ledger,
registry, and cassettes) separate from authored components means a generated artifact
cannot be mistaken for trusted authored config. That is the same boundary that keeps
[deploy](deploy.md) and [observers](observers.md) honest.

## Next steps

- [Deploy a pipeline](deploy.md) schedules a pipeline from the layout above.
- [Observe a running pipeline](observers.md) authors the watchers in `observers/`.
- [SECURITY.md](../architecture/SECURITY.md) covers the authored-vs-generated boundary in
  full.
