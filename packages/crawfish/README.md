# Crawfish

[![PyPI](https://img.shields.io/pypi/v/crawfish.svg)](https://pypi.org/project/crawfish/)
[![Python](https://img.shields.io/pypi/pyversions/crawfish.svg)](https://pypi.org/project/crawfish/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/crawfishai/crawfish/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://crawfishai.github.io/crawfish/)

**Agents for bulk work over your data.** Author a pipeline as a directory —
`Source → Batch (fan-out) → Aggregator (reduce) → Router (branch) → Sink` — and run it
locally via `claude -p` with **zero API key**. Typed, versioned, benchmarked.

Think *dbt / Airflow for agents*, not another chatbot SDK.

## Install

```bash
pip install crawfish
```

Prefer an isolated CLI? Use `uv tool install crawfish` or `pipx install crawfish`.

## Quickstart

```bash
craw init my-app && cd my-app
craw dev definitions/triage-bot -i project=acme -i "ticket_body=login is broken"
```

`craw init` scaffolds a working `triage-bot` example. `craw dev` runs it on a mock
runtime — no key, no cost. The Source fans the item out, a Definition team runs per item,
an Aggregator reduces, a Router branches, and a Sink writes — and the Output comes back
typed.

## Documentation

📖 **[crawfishai.github.io/crawfish](https://crawfishai.github.io/crawfish/)**

- [Getting started](https://crawfishai.github.io/crawfish/guide/getting-started/)
- [Tutorial](https://crawfishai.github.io/crawfish/guide/tutorial/) — build the triage bot end to end
- [Concepts](https://crawfishai.github.io/crawfish/guide/concepts/) — the directory model, runtimes, the security boundary
- [API reference](https://crawfishai.github.io/crawfish/guide/api-reference/)

## Links

- Source: [github.com/crawfishai/crawfish](https://github.com/crawfishai/crawfish)
- Issues: [github.com/crawfishai/crawfish/issues](https://github.com/crawfishai/crawfish/issues)
- Changelog: [CHANGELOG.md](https://github.com/crawfishai/crawfish/blob/main/CHANGELOG.md)

## License

[Apache-2.0](https://github.com/crawfishai/crawfish/blob/main/LICENSE).
