# Getting started

Crawfish is **agents for bulk work over your data** —
`Source → Batch (fan-out) → Aggregator (reduce) → Router (branch) → Sink` — authored
as directories and run **locally** via `claude -p`. No hosted dependency, no API key
required for the dev loop. Think dbt/Airflow for agents, not another chatbot SDK.

This page gets you from a clean checkout to a running agent team in a few minutes.

## Install

Crawfish is a `uv` workspace. From a checkout:

```bash
git clone <repo> && cd crawfish-framework
uv sync
uv run craw --version
# crawfish 0.1.0
```

`uv sync` installs the workspace, including the `crawfish` package in editable mode and
the `craw` CLI. (Don't run `uv sync` if your environment already has the dev tools
installed — `uv run craw --version` is enough to confirm the install.)

## The zero-key story

The agent loop lives behind one seam, `AgentRuntime`, so you choose *how* runs execute:

| Runtime | What it does | Key? | Cost |
| --- | --- | --- | --- |
| `MockRuntime` | deterministic canned responses — the dev/test loop | no | $0 |
| `CommandRuntime` | drives your local `claude -p` subprocess | no | uses your Claude session |
| `RecordReplayRuntime` | records once, replays from cassettes forever after | no (on replay) | $0 |
| `ClientRuntime` / `ManagedRuntime` | API key / hosted backends | yes | metered |

The dev loop is **zero key, zero budget**: `MockRuntime` is a pure function of the
request, so iterating on a Definition never burns money and tests stay deterministic.
Real runs swap in `CommandRuntime` (your local `claude -p`) — switching dev→prod is a
runtime swap, not a code change.

## First run — the no-op pipeline

`craw run` exercises the engine bootstrap end to end. With no project authored yet it
runs a no-op pipeline, which proves the `Engine → RunContext → Store` path works:

```bash
uv run craw run
# pipeline ok: 0 output(s)
```

## First real run — `craw dev`

`craw dev` compiles a **Definition directory** and runs its agent team on the
`MockRuntime` — zero key, zero budget. The repo ships a hero example, `demo/triage-bot`,
a real compilable Definition that triages a support ticket with a lead agent delegating
to a classifier and a summarizer:

```bash
uv run craw dev demo/triage-bot -i project=acme -i ticket_body="login button broken"
```

You'll see the lead's combined result, with the classifier and summarizer results threaded
back in as data (the mock just echoes structured input, so the shape is visible):

```text
[lead] processed: {"classifier_result": "[classifier] processed: ...",
                   "summarizer_result": "[summarizer] processed: ...",
                   "ticket_body": "login button broken"}
```

`-i name=value` binds inputs (repeatable). Note `project` is a **static** input (trusted
config) and `ticket_body` is **fluid** (untrusted per-item data) — that distinction is
the prompt-injection boundary, explained in [concepts](concepts.md).

## Run it for real with `claude -p`

Same Definition, real model — just swap the runtime. `craw dev` is mock-only by design;
to run against your local Claude, use the API directly:

```python
import asyncio

from crawfish import CommandRuntime, Definition, RunContext, Run, SqliteStore

definition = Definition.from_package("demo/triage-bot")

async def main() -> None:
    ctx = RunContext(store=SqliteStore())
    run = Run(definition, {"project": "acme", "ticket_body": "login button broken"})
    out = await run.execute(ctx, CommandRuntime())  # drives `claude -p`, no API key
    print(out.value)

asyncio.run(main())
```

`CommandRuntime` shells out to your local `claude` binary (`claude -p`) — it uses your
existing Claude session, so there is no API key to manage.

## Use the core API directly

The primitives are plain, typed Python you can drive without the CLI:

```python
from crawfish import Flow, Parameter, parameters_compatible, SqliteStore, Version

# Typed IO atoms — static (trusted config) vs. fluid (untrusted per-item data)
repo = Parameter(name="repo", type="str", flow=Flow.STATIC)
body = Parameter(name="ticket_body", type="str")  # fluid by default

# Structural type compatibility decides what can wire to what
assert parameters_compatible(repo, body)

# Versioned, freezable artifacts
v = Version(major=0, minor=1, sha="abc")
print(str(v))  # 0.1-abc

# Persistence through the Store seam (SQLite locally, Postgres later — a driver swap)
store = SqliteStore()
store.put_record("definition", "d1", {"name": "clarity"})
```

## What's next

- **[Tutorial](tutorial.md)** — build the triage bot end to end: the directory model,
  compiling, running a team, wiring a `Source → Batch → Sink` pipeline, measuring with a
  Rubric.
- **[Concepts](concepts.md)** — the directory model, the pipeline, runtimes, the
  prompt-injection boundary, secrets-by-reference, team coordination, the Store seams.
- **[Cookbook](cookbook.md)** — short recipes (fan-out, fan-in, routing, dedup, retries,
  cost preview, eval-as-test, snapshot/replay).
- **[API reference](api-reference.md)** — the full public surface, auto-generated from
  `crawfish.__all__`.

### The CLI today

The M0 CLI ships `craw --version`, `craw run`, and `craw dev <path> -i name=value`. The
fuller command surface (`init / install / list / freeze / publish / build / test / logs
/ inspect`) is planned — those are noted as *coming* where relevant
and are not yet runnable.
