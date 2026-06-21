# Crawfish

Crawfish is a framework for building agents like software. You define an agent — or a
whole team of them — as typed, versioned components in a directory, run it locally against
`claude -p` or a local model, and treat the result as something you can test, diff, and
improve, not a prompt you keep poking at.

It brings the things you expect from real engineering to agent work:

- **Agents as code.** The agents, their tools, the data shapes they pass, and the policies
  that govern them are plain files you check into git — infrastructure-as-code for local
  model work, not settings buried in a notebook.
- **Composable by design.** Small typed nodes snap together into larger pipelines. One
  node's output wires to the next only when their shapes match, so a team is assembled from
  parts the way a program is.
- **Deterministic and testable.** Typed inputs and outputs, structural type-checking, frozen
  versions, and record/replay make a run reproducible. Snapshot it, assert on it, and gate
  changes in CI — no live model required.
- **Built to improve.** Score a pipeline with rubrics and evals, then let the tuner search
  for better prompts and settings and promote the winner. Pipelines get better on purpose.
- **Local-first.** Everything runs on your machine by default. Cloud and scale are a driver
  swap, not a rewrite.

Running a job over your data in bulk is one thing you can build this way — fan it out
across thousands of items, reduce, branch, and write the results somewhere
(`Source → Batch → Aggregator → Router → Sink`). The same building blocks just as easily
express a single sharp agent, a multi-agent team, or a scheduled automation.

## Install the CLI

Installing the package gives you the `craw` command:

```bash
pip install crawfish
craw --version
```

Pick the install that fits what you're doing:

| You want to… | Install with |
| --- | --- |
| Build *with* the framework (`import crawfish`) | `pip install crawfish` · `uv add crawfish` |
| Just run the `craw` CLI, isolated | `uv tool install crawfish` · `pipx install crawfish` |
| Try it with zero Python setup | `curl -LsSf https://raw.githubusercontent.com/Neal-Kotval/crawfish/main/install.sh \| sh` |

The `curl` line is a thin wrapper: it installs [`uv`](https://docs.astral.sh/uv/) if you
don't have it, then the CLI. The package always comes from PyPI. Working on Crawfish itself?
See [Getting started → Develop from source](guide/getting-started.md#develop-from-source).

## Start here

- **[Getting started](guide/getting-started.md)** — install and run your first agent in a few minutes
- **[Tutorial](guide/tutorial.md)** — build the triage bot end to end
- **[Concepts](guide/concepts.md)** — the directory model, pipelines, runtimes, and the security boundary
- **[Cookbook](guide/cookbook.md)** — copy-paste recipes
- **[API reference](guide/api-reference.md)** — the public surface

## Operate and observe

Run a pipeline once, or keep it running. These pages cover deploying, watching, and
controlling pipelines locally.

- **[Operations overview](guide/operations.md)** — the deploy → observe → visualize → manage loop
- **[Deploy](guide/deploy.md)** — `craw deploy`: a detached, scheduled, self-restarting supervisor
- **[Manage](guide/manage.md)** — `craw manage`: list, stop, restart, and tail logs for deployed pipelines
- **[Observers](guide/observers.md)** — `crawfish.observe`: rule- and LLM-based watchers over a run
- **[Visualize](guide/visualize.md)** — `craw visualize`: a localhost-only dashboard
- **[Project structure](guide/project-structure.md)** — the standard layout, `[project.paths]`, and `craw doctor`
- **[Export to Claude Code](guide/claude-code-export.md)** — `craw export --claude-code`: run a Definition as a subagent

## Under the hood

- **[Architecture](architecture/ARCHITECTURE.md)** — the three swappable seams · [ADRs](architecture/decisions)
- **[Security](architecture/SECURITY.md)** — the prompt-injection boundary, secrets, and taint
- **[API stability](architecture/API-STABILITY.md)** — semver and deprecation policy
- **[Product](product/PRODUCT.md)** — positioning, hero use case, personas
- **[Roadmap](roadmap/README.md)** — the Phase-1 plan

## The 30-second version

```bash
pip install crawfish
craw init my-app && cd my-app
craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"
```
