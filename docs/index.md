# Crawfish

<a class="craw-discord" href="https://discord.gg/Bc2nEAyznQ" target="_blank" rel="noopener">
  <svg class="craw-discord__logo" viewBox="0 0 127.14 96.36" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0a105.89 105.89 0 0 0-26.25 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15ZM42.45 65.69C36.18 65.69 31 60 31 53s5-12.74 11.43-12.74S54 46 53.89 53s-5.05 12.69-11.44 12.69Zm42.24 0C78.41 65.69 73.25 60 73.25 53s5-12.74 11.44-12.74S96.23 46 96.12 53s-5.04 12.69-11.43 12.69Z"/></svg>
  <span class="craw-discord__text"><strong>We're always looking for more people to join the crawfish community!</strong><span class="craw-discord__cta">Join the Discord →</span></span>
</a>

Crawfish is a programming language for agents. You write an agent, or a team of them, as
typed components in a directory. You run it locally against `claude -p` or a local model. You
test it, version it, and improve it the same way you would any other software.

Like any language, Crawfish gives you a few things:

- **Primitives.** Typed inputs and outputs, nodes, and runtimes. An agent is a value with a
  type, not a prompt you keep editing.
- **Composition.** Small nodes wire into larger pipelines. One node's output connects to the
  next only when their types match, so a pipeline is checked before it runs.
- **Versioning.** Every agent is content-addressed, like a git commit. The same inputs produce
  the same outputs, so you can diff two versions and replay an old run.
- **Tooling.** Score a pipeline with evals, let the tuner search for better settings, and watch
  any run through the inspector. The same loop you expect from a compiler and a test runner,
  for agents.

Everything runs on your machine by default. Moving to the cloud later is a driver swap, not a
rewrite.

A common thing to build this way is bulk work over your data: fan a job out across thousands of
items, reduce the results, branch on them, and write them somewhere
(`Source → Batch → Aggregator → Router → Sink`). The same pieces also express a single agent, a
multi-agent team, or a scheduled automation.

## Install

Installing the package gives you the `craw` command:

```bash
pip install crawfish
craw --version
```

Pick the install that fits what you are doing:

| You want to | Install with |
| --- | --- |
| Build with the framework (`import crawfish`) | `pip install crawfish` or `uv add crawfish` |
| Run the `craw` CLI, isolated | `uv tool install crawfish` or `pipx install crawfish` |
| Try it with no Python setup | `curl -LsSf https://raw.githubusercontent.com/Neal-Kotval/crawfish/main/install.sh \| sh` |

The `curl` line installs [`uv`](https://docs.astral.sh/uv/) if you do not have it, then the CLI.
The package always comes from PyPI. Working on Crawfish itself? See
[Install and run](guide/getting-started.md#develop-from-source).

## Run something in 30 seconds

```bash
pip install crawfish
craw init my-app && cd my-app
craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"
```

This scaffolds a project with a working triage-bot example and runs it on the mock runtime, so
it needs no API key and costs nothing.

## Where to go next

The docs are in three parts, like most framework docs:

- **Get started** teaches the basics. Begin with [Install and run](guide/getting-started.md),
  then build the [triage bot tutorial](guide/tutorial.md) end to end.
- **Learn** explains one idea at a time. Start with [Core concepts](guide/concepts.md), the
  mental model behind everything, then read the guide for whatever you are doing.
- **Reference** is for looking up exact details: the [CLI](guide/cli.md), the
  [API](guide/api-reference.md), and a page per topic.

If you want to understand how Crawfish is built, the [Architecture](architecture/ARCHITECTURE.md)
and [Security](architecture/SECURITY.md) pages cover the internals.
