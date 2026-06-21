# Contributing a connector

A connector teaches the framework to read from or write to one more place — Slack,
Notion, Gmail, Jira, Postgres, a webhook. Connectors are the easiest and most useful
way to contribute to Crawfish. This page builds one end to end: a Slack sink, about 30
lines, that posts a message to a channel, holds its token securely, and ships with a
real test.

The complete, working code lives in
[`packages/crawfish-slack/`](https://github.com/Neal-Kotval/crawfish/tree/main/packages/crawfish-slack).
Every snippet below is copied from it, so you can run it as you read.

## What you're building

A **sink** is the only place a pipeline performs an external side effect — posting a
message, opening a PR. Crawfish wraps every sink in three guarantees so you don't have
to build them yourself:

- **Static-only targets.** The destination, a Slack channel here, is chosen once and
  never derived from model output, so a prompt-injection can't redirect your write.
- **Idempotency.** Re-running the same batch is a no-op, not a duplicate post.
- **Credentials by reference.** Your sink holds the *name* of an env var, never
  the secret value.

You write one method, `_write`. The base class handles the rest.

!!! tip "Sources vs. sinks"
    This guide builds a **sink** (egress). A **source** (ingress) subclasses
    `Source` instead and implements `async def fetch(self, ctx)`. The mechanics are
    identical: typed I/O, entry-point registration, fixture tests. See the
    [connector ideas](#connector-starter-issues) below for source-shaped starters.

## 1. Subclass `Sink`

Subclass `Sink[T]`, where `T` is the type of value you write. Create
`src/crawfish_slack/sink.py` and import the framework's public types — never a concrete
backend:

```python
from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.nodes.sink import Sink
from crawfish.output import Output


class SlackSink(Sink[JSONValue]):
    """Post a message to a static Slack channel. Dry-run by default (network-free)."""
```

## 2. Declare a static target and hold creds by reference

Declare the destination as a **static** `Parameter` in `__init__`. Passing a
`Flow.FLUID` target raises `TargetMustBeStaticError` at construction, so the guarantee
is enforced at wire time, not runtime. Adopt the `dry_run` pattern the in-tree
`LinearSink` and `GitHubPRSink` use: default it `True` so tests stay offline.

```python
    def __init__(
        self,
        name: str = "slack",
        config: dict[str, JSONValue] | None = None,
        *,
        always_ask: bool = False,
        dry_run: bool = True,
    ) -> None:
        # The destination channel is a static target: chosen once, never fluid.
        target = Parameter(name="channel", type="str", flow=Flow.STATIC)
        super().__init__(name, config, always_ask=always_ask, target_params=[target])
        self.dry_run = dry_run
        self.writes: list[dict[str, JSONValue]] = []
```

Pass `credential_ref` in `config` — the *name* of the env var that holds the token.
The secret resolves only at egress, and never reaches stored config, the `Output`,
logs, or telemetry.

!!! warning "Never put a secret value in `config`"
    `config` carries the env-var *name*, not the token itself. A token in `config`
    lands in stored config, the `Output`, and logs. Hold the reference; resolve the
    value only at egress.

## 3. Implement `_write`

`_write` is the only method you must write. In dry-run mode, append the would-be write
to `self.writes` instead of hitting the network. That keeps your test deterministic
and offline:

```python
    async def _write(self, output: Output[JSONValue], ctx: RunContext) -> None:
        # Resolve the credential by reference only at egress; never store the value.
        ref = self.config.get("credential_ref")
        record: dict[str, JSONValue] = {
            "kind": "slack_message",
            "channel": self.config.get("channel"),
            "text": output.value,
            "output_id": output.id,
            "credential_ref": ref,  # the env-var NAME, not the secret value
        }
        if self.dry_run:
            self.writes.append(record)
            return
        # Live path: read os.environ[ref], call the Slack API. Left to the reader.
        raise NotImplementedError("SlackSink live mode is not implemented")
```

That's the whole sink, about 30 lines. You never touch idempotency or the approval
gate. The base class's public `write()` claims the idempotency key, runs the
approval callback for `always_ask` sinks, calls your `_write`, then records a
secret-free telemetry event.

!!! note "Good to know"
    You implement `_write`; users call `write()`. The public `write()` wraps your
    method with the idempotency claim, the approval gate, and telemetry — so a second
    identical write is a no-op, not a duplicate post.

## 4. Register the entry point

Add one entry-point stanza so the connector ships as its own pip-installable package.
Users get it with `pip install crawfish-slack` and no wiring. Module discovery
([`crawfish.discovery`](https://github.com/Neal-Kotval/crawfish/blob/main/packages/crawfish/src/crawfish/discovery.py))
reads the `crawfish.sinks` entry-point group and registers your sink as
`("sink", "slack")`:

```toml
[project]
name = "crawfish-slack"
version = "0.1.0"
dependencies = ["crawfish", "pydantic>=2.7"]

# Installing this package makes Registry.discover() find the sink — no host wiring.
[project.entry-points."crawfish.sinks"]
slack = "crawfish_slack.sink:SlackSink"
```

The four discovery groups are `crawfish.sources`, `crawfish.sinks`,
`crawfish.definitions`, and `crawfish.types`. Name collisions resolve **first-wins
with a warning**.

## 5. Add a fixture-based test

Test against the dry-run path and an in-memory store — Crawfish tests never call a
live model or network. Mirror the in-tree sink fixtures: a `RunContext` over an
in-memory `SqliteStore` with a fixed `batch_id`, and a plain `Output`:

```python
from __future__ import annotations

import json

from crawfish.core.context import RunContext
from crawfish.output import Output
from crawfish.store import SqliteStore
from crawfish_slack import SlackSink


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore(), batch_id="b1")


async def test_write_is_recorded_in_dry_run() -> None:
    ctx = _ctx()
    sink = SlackSink(config={"channel": "#alerts", "credential_ref": "SLACK_BOT_TOKEN"})

    wrote = await sink.write(Output(value="deploy finished", produced_by="node-x"), ctx)

    assert wrote is True
    assert sink.writes[0]["channel"] == "#alerts"
```

Two more tests are worth copying from the example: an **idempotency** check (a second
identical write returns `False` and records nothing new), and a **no-leak** check (the
recorded write and telemetry contain the env-var name but never the secret value).

You can also assert your entry point really resolves once installed:

```python
from crawfish.discovery import Registry


def test_entry_point_is_discoverable() -> None:
    reg = Registry()
    reg.discover_entry_points()
    ref = reg.get("sink", "slack")
    assert ref is not None
    assert ref.target == "crawfish_slack.sink:SlackSink"
```

## 6. Run and discover it

Install your package editable, then run the suite and confirm the framework sees it.

```bash
uv sync
uv run pytest packages/crawfish-slack/tests -q
craw                       # discovered units, including your slack sink, are listed
craw dev <project>         # exercise it inside a pipeline (dry-run, no network)
```

## Security invariants to uphold

Your connector sits on Crawfish's [security spine](../architecture/SECURITY.md). Two
invariants matter for any sink. Keep both and your connector is safe by construction;
the base class enforces the rest.

!!! warning "Sink targets are static-only"
    Declare destinations as `Flow.STATIC` target params (invariant #2). Never read a
    channel, repo, or recipient from fluid / model-derived data — a prompt-injection
    could otherwise redirect your write. See the
    [security spine](../architecture/SECURITY.md).

!!! warning "Secrets resolve by reference, never in a log or prompt"
    Hold `credential_ref` (an env-var name) and resolve the value only at egress
    (invariant #4). Never put a token in `config`, the `Output`, or a log line. See the
    [security spine](../architecture/SECURITY.md).

## Connector starter issues

Want a connector to build but aren't sure which? These make good first contributions.
Each names the base class and sketches its typed I/O.

- **Slack sink** *(the worked example above — start here)* — post a message to a
  static channel. `Sink[JSONValue]`; target `channel: str (static)`;
  `credential_ref` → bot token env var.
- **Notion sink** — append a block / create a page in a static database.
  `Sink[JSONValue]`; target `database_id: str (static)`; value = page properties;
  `credential_ref` → integration token.
- **Gmail source** — fetch messages matching a static query. `Source[JSONValue]`,
  `multi=True`; output `messages: list[Email]`; `credential_ref` → OAuth token ref.
- **Jira sink** — create or comment on an issue in a static project.
  `Sink[JSONValue]`; target `project_key: str (static)`; value = issue fields;
  `credential_ref` → API token.
- **Postgres source** — stream rows from a static, parameterised query.
  `Source[JSONValue]`, `multi=True`; output `rows: list[Row]`; `credential_ref` →
  DSN env var. Query is static; only bound params may vary.
- **RSS source** — pull entries from a static feed URL. `Source[JSONValue]`,
  `multi=True`; output `entries: list[FeedEntry]`; no credential needed.
- **Webhook sink** — POST the output to a static URL. `Sink[JSONValue]`; target
  `url: str (static)`; value = JSON body; optional `credential_ref` → signing-secret
  env var.

Pick one, copy the Slack example, swap the `_write` body, and open a PR. See
[`docs/guide/connector-ideas.md`](connector-ideas.md) for the full scope of each.

## See also

- [Connector ideas](connector-ideas.md) — the full scope of each starter, ready to file.
- [Security spine](../architecture/SECURITY.md) — the invariants every connector upholds.
- [Operations overview](operations.md) — the rest of the operate/integrate layer.
