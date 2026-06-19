# Getting started

> Status: M0. The framework foundation is in place; the authoring surface
> (`craw init` / `craw dev`, Definitions, Sources, Sinks) lands across M1–M5.
> This page grows into the full ≤5-minute first-run experience (CRA-117, CRA-118).

## Install (from source, during development)

```bash
git clone <repo> && cd crawfish-framework
uv sync
uv run craw --version
```

`uv sync` installs the workspace, including the `crawfish` package in editable mode.

## Run the no-op pipeline

The engine bootstrap runs a pipeline end to end. With no project authored yet, that's
a no-op — but it exercises the whole `Engine → RunContext → Store` path:

```bash
uv run craw run
# pipeline ok: 0 output(s)
```

## Use the core API

```python
from crawfish import Parameter, Flow, parameters_compatible, SqliteStore, Version

# Typed IO atoms (static vs. fluid is the prompt-injection boundary)
repo = Parameter(name="repo", type="str", flow=Flow.STATIC)
body = Parameter(name="ticket_body", type="str")  # fluid by default

# Structural type compatibility decides what can wire to what
assert parameters_compatible(repo, body)

# Versioned, freezable artifacts
v = Version(major=0, minor=1, sha="abc")
print(str(v))  # 0.1-abc

# Persistence through the Store seam
store = SqliteStore()
store.put_record("definition", "d1", {"name": "clarity"})
```

## What's next

- **M1** — author an agent team as a directory and run it via `claude -p`.
- See the [roadmap](../roadmap/README.md) for the full plan and the
  [architecture](../architecture/ARCHITECTURE.md) for the seams.
