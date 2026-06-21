# Getting started

Go from a clean checkout to a running agent team in a few minutes. In Crawfish you build
agents as code: you author a pipeline as a folder of typed files —
`Source → Batch → Aggregator → Router → Sink` — and run it locally with `claude -p`.
The dev loop needs no hosted service and no API key.

!!! note "What you'll learn"

    - How to install the `craw` CLI and verify it
    - How runs execute, and why the dev loop costs nothing
    - How to scaffold and run your first agent team on `MockRuntime`
    - How to switch to a real model with `claude -p` — a runtime swap, not a code change
    - How to drive the typed core API directly, without the CLI

## Install

Install the package and you get the `craw` CLI:

```bash
pip install crawfish
craw --version
# crawfish 0.2.0
```

Want the CLI isolated, so it doesn't touch your project's environment? Use `uv tool install
crawfish` or `pipx install crawfish`. For zero Python setup, the bootstrap script
installs `uv` if needed, then the CLI:

```bash
curl -LsSf https://raw.githubusercontent.com/Neal-Kotval/crawfish/main/install.sh | sh
```

The fastest path to a running team is `craw init`, which scaffolds a project with a
working `triage-bot` example — that's what the examples below use. (Developing from a
clone? The same example also ships in the repo at `demo/triage-bot`.)

### Develop from source

Working on Crawfish itself? It's a [`uv`](https://docs.astral.sh/uv/) workspace:

```bash
git clone https://github.com/Neal-Kotval/crawfish && cd crawfish
uv sync                  # installs the workspace editable, incl. the craw CLI
uv run craw --version
```

When developing this way, prefix the commands below with `uv run`.

## How runs execute

The agent loop sits behind one seam, `AgentRuntime`. You pick how runs actually happen:

| Runtime | What it does | Key? | Cost |
| --- | --- | --- | --- |
| `MockRuntime` | deterministic canned responses — the dev/test loop | no | $0 |
| `CommandRuntime` | drives your local `claude -p` subprocess | no | uses your Claude session |
| `RecordReplayRuntime` | records once, replays from cassettes after | no (on replay) | $0 |
| `ClientRuntime` / `ManagedRuntime` | API key / hosted backends | yes | metered |

The dev loop costs nothing. `MockRuntime`'s output depends only on the request, so
iterating on a pipeline never spends money and tests stay deterministic (same input,
same output, every time). For real runs you swap in `CommandRuntime`, which uses your
local `claude -p`. Going from dev to prod is a runtime swap, not a code change.

## First run — the no-op pipeline

`craw run` exercises the engine end to end. With no project authored yet it runs a no-op
pipeline, which confirms the `Engine → RunContext → Store` path works:

```bash
craw run
# pipeline ok: 0 output(s)
```

## First real run — scaffold, then `craw dev`

`craw init` scaffolds a project with a working example. `craw dev` then compiles a
**Definition** — an agent team authored as a directory of files — and runs it on
`MockRuntime`, with no key and no cost. The example is `triage-bot`: a lead agent that
triages a support ticket by delegating to a classifier and a summarizer.

```bash
craw init my-app && cd my-app
craw dev definitions/triage-bot -i project=acme -i ticket_body="login button broken"
```

You'll see the lead's combined result, with the classifier and summarizer results
threaded back in as data (the mock echoes structured input, so the shape is visible):

```text
[lead] processed: {"classifier_result": "[classifier] processed: ...",
                   "summarizer_result": "[summarizer] processed: ...",
                   "ticket_body": "login button broken"}
```

`-i name=value` binds an input, and you can repeat it. The two inputs differ in kind:
`project` is **static** (trusted config you set once) and `ticket_body` is **fluid**
(untrusted data that changes per item).

!!! warning "Static vs. fluid is the prompt-injection boundary"

    `ticket_body` is **fluid (untrusted)** per-item data. It reaches the model as data
    inside a fenced block, never as instructions. Static inputs like `project` are trusted
    config you set once. That line is what stops per-item data from sneaking instructions
    into the agent. See [concepts](concepts.md).

## Run it for real with `claude -p`

Same Definition, real model — you just swap the runtime. `craw dev` is mock-only by
design, so to run against your local Claude, use the API directly:

```python
import asyncio

from crawfish import CommandRuntime, Definition, RunContext, Run, SqliteStore

definition = Definition.from_package("definitions/triage-bot")

async def main() -> None:
    ctx = RunContext(store=SqliteStore())
    run = Run(definition, {"project": "acme", "ticket_body": "login button broken"})
    out = await run.execute(ctx, CommandRuntime())  # drives `claude -p`, no API key
    print(out.value)

asyncio.run(main())
```

`CommandRuntime` shells out to your local `claude` binary (`claude -p`), reusing your
existing Claude session. There's no API key to manage.

!!! note "Good to know"

    `craw dev` is mock-only by design — it always runs on `MockRuntime`. To run a real
    model from the CLI you swap the runtime in code, as shown above. Going from dev to prod
    is a runtime swap, never a code change.

## Use the core API directly

The primitives are plain, typed Python. You can drive them without the CLI:

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
  compiling, running a team, wiring a `Source → Batch → Sink` pipeline, and measuring
  with a Rubric.
- **[Concepts](concepts.md)** — the directory model, the pipeline, runtimes, the
  prompt-injection boundary, secrets-by-reference, team coordination, and the Store seams.
- **[Cookbook](cookbook.md)** — short recipes (fan-out, fan-in, routing, dedup, retries,
  cost preview, eval-as-test, snapshot/replay).
- **[API reference](api-reference.md)** — the full public surface, auto-generated from
  `crawfish.__all__`.

### The CLI today

The CLI ships `craw init`, `run`, `dev`, `list`, `doctor`, `install`, `freeze`, `test`,
and `build`, plus the operations commands (`deploy`, `manage`, `visualize`, `export`).
`publish` is a Phase-2 stub — the registry isn't live yet. Run `craw --help` for the
full surface.
