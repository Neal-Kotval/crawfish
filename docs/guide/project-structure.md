# Project structure & `craw doctor`

A Crawfish project is a directory of authored components plus generated state. The layout
is **canonical but relocatable**: discovery follows convention by default, and you can
move folders via `crawfish.toml` when a different shape fits your repo. `craw doctor`
audits the structure and flags problems.

## The canonical layout

```text
my-app/
├── crawfish.toml          # project config + profiles
├── sources/               # Source nodes (pipeline ingress)
├── sinks/                 # Sink nodes (the egress side effect)
├── definitions/           # Definition directories (the agent teams)
├── pipelines/             # Workflows wiring source → batch → … → sink
├── observers/             # Observer definitions
├── tools/                 # tool callables
├── policies/              # Policy instances
└── .crawfish/             # GENERATED — locks, ledger, cassettes, registry (gitignore)
```

The first seven folders are **authored** (you write them, they're committed).
`.crawfish/` is **generated** — locks, the execution ledger, cassettes, and the deploy
registry. The two are kept strictly separate so authored intent and machine state never
bleed together.

## Relocating folders — `[project.paths]`

Override any folder location in `crawfish.toml`. Discovery follows the override
everywhere — the CLI, the compiler, and `craw doctor` all read the configured path:

```toml
[project.paths]
definitions = "agents/"      # author Definitions under agents/ instead
observers   = "watch/"
# unset keys keep their canonical default (sources/, sinks/, …)
```

After this, `craw deploy agents/triage-bot` and `Definition.from_package("agents/...")`
resolve against the relocated tree; nothing else changes.

## `craw doctor`

```bash
craw doctor
```

`craw doctor` reports structure health: it confirms each configured folder exists, flags
**misplaced files** (a Definition sitting in `tools/`, a stray Python file outside any
known folder), and verifies the **authored-vs-generated separation** — that nothing under
`.crawfish/` is hand-edited and that no generated artifact has leaked into the authored
tree.

## Worked example

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

Fix the warning by moving the misplaced directory, or — if you intended a custom layout —
declare it in `[project.paths]` and re-run; the warning clears once discovery and the
filesystem agree.

## Security

`craw doctor` reads the filesystem and `crawfish.toml` only; it never resolves a secret
or runs a model. The authored-vs-generated check is itself a guardrail: keeping
`.crawfish/` (the ledger, registry, cassettes) separate from authored components means a
generated artifact can't be mistaken for trusted authored config — the same boundary that
keeps [deploy](deploy.md) and [observers](observers.md) honest. See
[SECURITY.md](../architecture/SECURITY.md).
