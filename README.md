# Crawfish

[![CI](https://github.com/Neal-Kotval/crawfish/actions/workflows/ci.yml/badge.svg)](https://github.com/Neal-Kotval/crawfish/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/crawfish.svg)](https://pypi.org/project/crawfish/)
[![Python](https://img.shields.io/pypi/pyversions/crawfish.svg)](https://pypi.org/project/crawfish/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](docs/index.md)

**Agents for bulk work over your data.** Author a pipeline as a directory —
`Source → Batch (fan-out) → Aggregator (reduce) → Router (branch) → Sink` — and run it
locally via `claude -p` with **zero API key**. Typed, versioned, benchmarked.

Think *dbt / Airflow for agents*, not another chatbot SDK.

## Install

Pick the line that matches what you're doing:

| You want to… | Install with | Why |
| --- | --- | --- |
| **Build *with* the framework** (`import crawfish`) | `pip install crawfish` &nbsp;·&nbsp; `uv add crawfish` | Lands in your project env so it resolves against your deps |
| **Just run the `craw` CLI** | `uv tool install crawfish` &nbsp;·&nbsp; `pipx install crawfish` | Isolated CLI, no env to pollute |
| **Try it with zero Python setup** | `curl -LsSf https://raw.githubusercontent.com/Neal-Kotval/crawfish/main/install.sh \| sh` | Bootstraps `uv` if needed, then installs the CLI |

The `curl` line is a thin wrapper over the same PyPI package — see [`install.sh`](install.sh).
(Once a `crawfish.dev` domain is set up, that URL shortens to `https://crawfish.dev/install.sh`.)

Then run the zero-key demo:

```bash
craw init my-app
craw dev my-app/definitions/triage-bot -i project=acme -i "ticket_body=login is broken"
```

The Source fans the item out, a Definition team runs per item on a mock runtime (no key
needed), an Aggregator reduces, a Router branches, and a Sink writes — and the Output
comes back typed.

## Develop from source

This repo is a [`uv`](https://docs.astral.sh/uv/) workspace and uses
[`just`](https://github.com/casey/just) as its task runner — run `just` to see every
recipe.

```bash
just deps              # install the workspace + dev deps (uv sync)
just demo              # run the demo end to end (zero key, mock runtime)
just check             # lint + typecheck + the full test suite
```

Or drive the CLI directly with `uv run craw …`. See
[`CONTRIBUTING.md`](.github/CONTRIBUTING.md) to go from a clone to a merged PR — the most welcome
first contribution is a connector.

## Docs

- [Product](docs/product/PRODUCT.md) — positioning, hero use case, personas
- [Architecture](docs/architecture/ARCHITECTURE.md) — the three seams · [ADRs](docs/architecture/decisions)
- [Security spine](docs/architecture/SECURITY.md)
- [Getting started](docs/guide/getting-started.md)
- [Roadmap](ROADMAP.md) — what shipped and what's next
- [Releasing](.github/RELEASING.md) — the release process + semver/stability policy · [Changelog](CHANGELOG.md)

Browse the docs locally with `just docs` (serves at http://127.0.0.1:8000).

## Status

**Phase 1 is complete** — the local trust loop runs with no hosted dependency: a
multi-item Source fans out, a Definition team runs per item via `claude -p`, an
Aggregator reduces, a Router branches, and a Sink writes — typed, versioned, and
benchmarked, with retries, dead-letter, and crash-resume. `ruff` + `mypy --strict`
clean, the test suite green and deterministic (no live model calls), and the docs build
as a MkDocs site. See the [Roadmap](ROADMAP.md) for what's next and
[CLAUDE.md](CLAUDE.md) for development guidance.

## License

[Apache-2.0](LICENSE).
