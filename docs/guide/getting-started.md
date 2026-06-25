# Install and run

This page takes you from a clean machine to a running agent team in a few minutes. You install
the `craw` CLI, run a built-in example on the mock runtime, then run the same example against a
real model. The dev loop needs no hosted service and no API key.

!!! note "What you'll learn"

    - How to install the `craw` CLI and check it
    - How runs work, and why the dev loop costs nothing
    - How to scaffold and run your first agent team
    - How to switch to a real model, which is a runtime swap and not a code change
    - How to call the typed core API directly, without the CLI

## Install

Install the package and you get the `craw` CLI:

```bash
pip install crawfish
craw --version
# crawfish 0.2.0
```

To keep the CLI isolated from your project's environment, use `uv tool install crawfish` or
`pipx install crawfish`. For a machine with no Python set up, the bootstrap script installs
[`uv`](https://docs.astral.sh/uv/) if needed, then the CLI:

```bash
curl -LsSf https://raw.githubusercontent.com/Neal-Kotval/crawfish/main/install.sh | sh
```

The fastest path to a running team is `craw init`, which scaffolds a project with a working
`triage-bot` example. That is what the rest of this page uses. If you cloned the repo instead,
the same example ships at `demo/triage-bot`.

### Develop from source

Working on Crawfish itself? It is a [`uv`](https://docs.astral.sh/uv/) workspace:

```bash
git clone https://github.com/Neal-Kotval/crawfish && cd crawfish
uv sync                  # installs the workspace, including the craw CLI
uv run craw --version
```

When you develop this way, prefix the commands below with `uv run`.

## How runs work

Every run goes through one interface, `AgentRuntime`. You choose how the run actually happens by
choosing a runtime:

| Runtime | What it does | Key? | Cost |
| --- | --- | --- | --- |
| `MockRuntime` | returns deterministic canned responses, for the dev and test loop | no | $0 |
| `CommandRuntime` | drives your local `claude -p` subprocess | no | uses your Claude session |
| `RecordReplayRuntime` | records once, then replays from saved cassettes | no on replay | $0 on replay |
| `ClientRuntime` / `ManagedRuntime` | API key or hosted backends | yes | metered |

The dev loop costs nothing. `MockRuntime`'s output depends only on the request, so iterating on
a pipeline never spends money and tests stay deterministic: the same input gives the same output
every time. For real runs you swap in `CommandRuntime`, which uses your local `claude -p`. Going
from dev to prod is a runtime swap, not a code change.

## First run: the no-op pipeline

`craw run` exercises the engine from end to end. With no project authored yet, it runs a no-op
pipeline, which confirms the `Engine → RunContext → Store` path works:

```bash
craw run
# pipeline ok: 0 output(s)
```

## First real run: scaffold, then `craw dev`

`craw init` scaffolds a project with a working example. `craw dev` then compiles a *Definition*,
which is an agent team authored as a directory of files, and runs it on `MockRuntime` with no
key and no cost. The example is `triage-bot`: a lead agent that triages a support ticket by
delegating to a classifier and a summarizer.

```bash
craw init my-app && cd my-app
craw dev definitions/triage-bot -i project=acme -i ticket_body="login button broken"
```

You will see the lead's combined result, with the classifier and summarizer results threaded
back in as data. The mock echoes structured input, so the shape is visible:

```text
[lead] processed: {"classifier_result": "[classifier] processed: ...",
                   "summarizer_result": "[summarizer] processed: ...",
                   "ticket_body": "login button broken"}
```

`-i name=value` binds an input, and you can repeat it. The two inputs are different kinds.
`project` is *static*, meaning trusted config you set once. `ticket_body` is *fluid*, meaning
untrusted data that changes per item.

!!! warning "Static versus fluid is the prompt-injection boundary"

    A fluid input reaches the model only as data, inside a fenced block the model is told to
    treat as data, never as instructions. That is what stops per-item content from injecting
    commands into the agent. Mark an input static only when it is trusted config you set once.
    [Core concepts](concepts.md) covers this in full.

## Run it with a real model

Same Definition, real model. You only swap the runtime. `craw dev` is mock-only by design, so to
run against your local Claude, use the API directly:

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

`CommandRuntime` shells out to your local `claude` binary (`claude -p`) and reuses your existing
Claude session, so there is no API key to manage.

## Call the core API directly

The primitives are plain, typed Python. You can use them without the CLI:

```python
from crawfish import Flow, Parameter, parameters_compatible, SqliteStore, Version

# Typed IO atoms: static is trusted config, fluid is untrusted per-item data
repo = Parameter(name="repo", type="str", flow=Flow.STATIC)
body = Parameter(name="ticket_body", type="str")  # fluid by default

# Structural type compatibility decides what can wire to what
assert parameters_compatible(repo, body)

# Versioned, freezable artifacts
v = Version(major=0, minor=1, sha="abc")
print(str(v))  # 0.1-abc

# Persistence goes through the Store interface (SQLite locally, Postgres later)
store = SqliteStore()
store.put_record("definition", "d1", {"name": "clarity"})
```

## What the CLI ships today

The CLI ships `craw init`, `run`, `dev`, `list`, `doctor`, `install`, `freeze`, `test`, and
`build`, plus the operations commands `deploy`, `manage`, `visualize`, and `export`. `publish` is
a stub for now, since the registry is not live yet. Run `craw --help` for the full list.

## Next steps

- [Tutorial: build the triage bot](tutorial.md) walks the whole example end to end.
- [Core concepts](concepts.md) explains the directory model, pipelines, runtimes, and the
  injection boundary.
- [Cookbook](cookbook.md) has short, copy-paste recipes.
- [API reference](api-reference.md) lists every public symbol.
