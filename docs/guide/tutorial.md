# Tutorial — build the triage bot

This walkthrough builds the hero example end to end: an agent team that triages support
tickets, then a fan-out pipeline that runs it over many tickets, writes results to a
sink, and measures quality with a rubric. Everything runs on `MockRuntime` (zero key,
zero budget), so you can follow along without spending anything.

The finished Definition ships at `demo/triage-bot/` — open it alongside this page.

## 1. The directory model

A Definition is **authored as a directory** and compiled into a typed object. The
compiler reads a fixed layout:

```
triage-bot/
├── instructions.md      # the lead agent (its markdown body becomes the prompt)
├── agents/
│   ├── classifier.md     # one subagent per file (role = filename stem)
│   └── summarizer.md
├── definition.py         # typed inputs/outputs, coordination, the lead role
├── pyproject.toml        # name (identity) + version
└── tools/*.py            # optional: host tools (tool name = filename stem)
```

Compile contract:

- `instructions.md` (+ `agents/*.md`) → the team's agents.
- `tools/*.py` → a tool named after the file's stem (the file must define a callable of
  the same name). No registration step.
- `skills/*.md`, `mcp/*.py`, `policies/*.py` → `DefinitionAssets`.
- `definition.py` → typed `inputs`/`outputs`, `dependencies`, coordination, `lead`.

Broken bindings fail at **load time** — an agent referencing an unknown tool or policy
never compiles.

## 2. The lead agent

`instructions.md` carries the lead's prompt in its body and the team topology in YAML
front-matter:

```markdown
---
role: lead
delegates_to: [classifier, summarizer]
---
You triage an incoming support ticket. Delegate classification and summarization to
your subagents, then combine their typed results into a single triage decision:
the category plus a one-line summary.
```

`delegates_to` declares the subagent roles this lead dispatches.

## 3. The subagents

Each file in `agents/` is one subagent; its role is the filename stem.

`agents/classifier.md`:

```markdown
You classify a support ticket into exactly one of: bug, question, feature_request.
Respond with just the category.
```

`agents/summarizer.md`:

```markdown
You write a single-sentence summary of a support ticket for a triage queue.
```

## 4. The typed IO boundary

`definition.py` declares the typed inputs/outputs and the coordination. This is also
where the **static-vs-fluid** distinction is set:

```python
from __future__ import annotations

from crawfish.core import Flow, Parameter

inputs = [
    Parameter(name="project", type="str", flow=Flow.STATIC),  # trusted config
    Parameter(name="ticket_body", type="str"),                # fluid (per-item)
]
outputs = [Parameter(name="triage", type="str")]

lead = "lead"
```

- `project` is `Flow.STATIC` — trusted, set once, may be interpolated into instructions.
- `ticket_body` is fluid by default — **untrusted per-item data**, placed only in a
  fenced data block the model is told to treat as data, never instructions. This is the
  prompt-injection boundary (see [concepts](concepts.md)).
- Setting `lead = "lead"` (a module-level string) tells the compiler the coordinator
  role; with more than one agent the compiler picks the `LEAD` coordination topology.

`pyproject.toml` supplies identity and version:

```toml
[project]
name = "triage-bot"
version = "0.1.0"
```

## 5. Compile it

`Definition.from_package` runs the canonical loader (and writes a `definition.lock` for
reproducibility):

```python
from crawfish import Definition

definition = Definition.from_package("demo/triage-bot")
print(definition.id)                       # "triage-bot"
print(str(definition.version))             # "0.1-<sha>"  (content-derived sha)
print([a.role for a in definition.team.agents])  # ['lead', 'classifier', 'summarizer']
```

Or from the CLI — `craw dev` compiles and runs in one step on the mock runtime:

```bash
uv run craw dev demo/triage-bot -i project=acme -i ticket_body="login button broken"
```

## 6. Run the team

A `Run` is one durable execution of a Definition against one input set. It drives the
team through the `AgentRuntime` seam, validates inputs before any model call, and emits
telemetry into the `Store`:

```python
import asyncio

from crawfish import Definition, MockRuntime, Run, RunContext, SqliteStore

definition = Definition.from_package("demo/triage-bot")

async def main() -> None:
    ctx = RunContext(store=SqliteStore())
    run = Run(definition, {"project": "acme", "ticket_body": "login button broken"})
    out = await run.execute(ctx, MockRuntime())  # zero key, zero budget
    print(out.value)

asyncio.run(main())
```

Under `LEAD` coordination, `run_team` dispatches each delegate, threads each typed result
back to the lead as fluid data (`classifier_result`, `summarizer_result`), then runs the
lead to combine them. To run against the real model, swap `MockRuntime()` for
`CommandRuntime()` (drives `claude -p`, still no API key).

## 7. Wire a Source → Batch → Sink pipeline

The triage bot becomes a *bulk* tool when you fan it out over many tickets. A multi
`Source` emits a list; a `Batch` fans out to one `Run` per item; a `Sink` writes results.

```python
import asyncio

from crawfish import (
    Batch, Definition, Flow, MockRuntime, Parameter, PullRequestSource,
    RunContext, SqliteStore, LinearSink,
)

definition = Definition.from_package("demo/triage-bot")

# A multi source: each item is a dict matching the source's declared shape.
tickets = PullRequestSource(
    "tickets",
    config={"repo": "acme/app", "items": [
        {"number": 1, "title": "login button broken"},
        {"number": 2, "title": "add dark mode"},
    ]},
)

# A dry-run sink (network-free by default) — its target is static-only.
sink = LinearSink(
    "triage-out",
    config={"team": "SUP", "project": "triage"},
    target_params=[Parameter(name="project", type="str", flow=Flow.STATIC)],
)

async def main() -> None:
    ctx = RunContext(store=SqliteStore())
    batch = Batch(definition, "triage", runtime=MockRuntime()).add_input(tickets)
    batch.check_wiring()                 # type-checked at assembly, before any model call
    outputs = await batch.run(ctx)       # one Run per ticket (fan-out)
    for out in outputs:
        await sink.write(out, ctx)       # dry-run: recorded into sink.writes
    print(f"{len(outputs)} tickets triaged; {len(sink.writes)} writes")

asyncio.run(main())
```

Wiring is **type-checked at assembly** (`check_wiring`): a mistyped or missing wire is
rejected before any model call, not at run time. The sink is dry-run by default, so this
is fully offline. For a top-level, durable, checkpointed pipeline, compose the same steps
into a `Workflow` (see [concepts](concepts.md)).

## 8. Measure quality with a Rubric

The point of bulk runs is to *measure and improve*. A `Metric` scores one `Output`; a
`Rubric` bundles metrics into a score vector; a `Benchmark` runs a rubric over a fixed
task set and aggregates — all deterministic under `MockRuntime`, so iterating on metrics
never costs anything.

```python
import asyncio

from crawfish import (
    Benchmark, Definition, MockRuntime, Rubric, RunContext, SqliteStore,
    Task, is_nonempty,
)

definition = Definition.from_package("demo/triage-bot")

rubric = Rubric([is_nonempty()], name="triage-quality")
tasks = [
    Task(description="login button broken"),
    Task(description="please add dark mode"),
]
benchmark = Benchmark(rubric, tasks, name="triage-bench")

async def main() -> None:
    ctx = RunContext(store=SqliteStore())
    scores = await benchmark.run(definition, ctx, MockRuntime())
    print(scores)  # {"is_nonempty": 1.0}  (mean over tasks)

asyncio.run(main())
```

From here, compare two Definition versions over the same tasks with `compare` and flag a
worse candidate with `is_regression` — the improvement loop. See the
[cookbook](cookbook.md) for eval-as-test and snapshot/replay recipes.

## Where to go next

- **[Concepts](concepts.md)** — the model behind everything you just used.
- **[Cookbook](cookbook.md)** — recipes for fan-in, routing, dedup, retries, cost.
- **[API reference](api-reference.md)** — every symbol, generated from the typed core.
