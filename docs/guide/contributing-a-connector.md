# Contributing a connector

A connector teaches Crawfish to read from or write to one more place: Slack, Notion,
Gmail, Jira, Postgres, a webhook. Connectors are the easiest and most useful way to
contribute. This page builds one end to end. It is a Slack sink, about 30 lines, that
posts a message to a channel, holds its token securely, and ships with a real test.

The complete working code lives in
[`packages/crawfish-slack/`](https://github.com/crawfishai/crawfish/tree/main/packages/crawfish-slack).
Every snippet below comes from it, so you can run it as you read.

## What you'll build

A *sink* is the one place a pipeline writes to the outside world, like posting a message
or opening a PR. Crawfish wraps every sink in three guarantees so you do not build them
yourself:

- Static-only targets. The destination, a Slack channel here, is chosen once and never
  derived from model output, so a prompt injection cannot redirect your write.
- Idempotency. Re-running the same batch writes nothing new, instead of posting a
  duplicate.
- Credentials by reference. Your sink holds the name of an env var, never the secret
  value.

You write one method, `_write`. The base class handles the rest.

!!! tip "Sources and sinks"
    This guide builds a sink, which writes out. A *source*, which reads in, subclasses
    `Source` instead and implements `async def fetch(self, ctx)`. The mechanics are the
    same: typed inputs and outputs, entry-point registration, fixture tests. See the
    [connector ideas](#connector-starter-issues) below for source-shaped starters.

## 1. Subclass `Sink`

Subclass `Sink[T]`, where `T` is the type of value you write. Create
`src/crawfish_slack/sink.py` and import Crawfish's public types, never a concrete
backend.

```python
from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.nodes.sink import Sink
from crawfish.output import Output


class SlackSink(Sink[JSONValue]):
    """Post a message to a static Slack channel. Dry-run by default (network-free)."""
```

## 2. Declare a static target and hold credentials by reference

Declare the destination as a *static* `Parameter` in `__init__`. A static value is set
once at batch start and never derived from model output. Passing a `Flow.FLUID` target
raises `TargetMustBeStaticError` at construction, so Crawfish enforces the rule when you
wire the pipeline, not at runtime. Follow the `dry_run` pattern the in-tree `LinearSink`
and `GitHubPRSink` use: default it `True` so tests stay offline.

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

Pass `credential_ref` in `config`. It is the name of the env var that holds the token.
The secret resolves only when the sink writes, and never reaches stored config, the
`Output`, logs, or telemetry.

!!! warning "Never put a secret value in `config`"
    `config` carries the env-var name, not the token itself. A token in `config` lands
    in stored config, the `Output`, and logs. Hold the reference and resolve the value
    only when you write.

## 3. Implement `_write`

`_write` is the only method you write. In dry-run mode, append the would-be write to
`self.writes` instead of hitting the network. That keeps your test deterministic and
offline.

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

That is the whole sink, about 30 lines. You never touch idempotency or the approval
gate. The base class's public `write()` claims the idempotency key, runs the approval
callback for `always_ask` sinks, calls your `_write`, then records a secret-free
telemetry event.

!!! note "Who calls what"
    You implement `_write`. Users call `write()`. The public `write()` wraps your method
    with the idempotency claim, the approval gate, and telemetry, so a second identical
    write does nothing instead of posting a duplicate.

## 4. Register the entry point

Add one entry-point stanza so the connector ships as its own pip-installable package.
Users get it with `pip install crawfish-slack` and no wiring. Module discovery
([`crawfish.discovery`](https://github.com/crawfishai/crawfish/blob/main/packages/crawfish/src/crawfish/discovery.py))
reads the `crawfish.sinks` entry-point group and registers your sink as
`("sink", "slack")`.

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
`crawfish.definitions`, and `crawfish.types`. When two names collide, the first one
wins and Crawfish logs a warning.

## 5. Add a fixture-based test

Test against the dry-run path and an in-memory store. Crawfish tests never call a live
model or network. Mirror the in-tree sink fixtures: a `RunContext` over an in-memory
`SqliteStore` with a fixed `batch_id`, and a plain `Output`.

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

Two more tests are worth copying from the example. An idempotency check confirms that a
second identical write returns `False` and records nothing new. A no-leak check confirms
that the recorded write and telemetry contain the env-var name but never the secret
value.

You can also assert that your entry point resolves once installed.

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

Install your package editable, then run the suite and confirm Crawfish sees it.

```bash
uv sync
uv run pytest packages/crawfish-slack/tests -q
craw                       # discovered units, including your slack sink, are listed
craw dev <project>         # exercise it inside a pipeline (dry-run, no network)
```

## Security rules to uphold

Your connector sits on Crawfish's [security model](../architecture/SECURITY.md). Two
rules matter for any sink. Keep both and your connector is safe. The base class enforces
the rest.

!!! warning "Sink targets are static-only"
    Declare destinations as `Flow.STATIC` target params. Never read a channel, repo, or
    recipient from fluid or model-derived data. A prompt injection could otherwise
    redirect your write. See the [security model](../architecture/SECURITY.md).

!!! warning "Secrets resolve by reference, never in a log or prompt"
    Hold `credential_ref`, an env-var name, and resolve the value only when you write.
    Never put a token in `config`, the `Output`, or a log line. See the
    [security model](../architecture/SECURITY.md).

## Connector starter issues

Want a connector to build but are not sure which? These make good first contributions.
Each names the base class and sketches its typed inputs and outputs.

- Slack sink, the worked example above. Start here. Post a message to a static channel.
  `Sink[JSONValue]`, target `channel: str (static)`, `credential_ref` to a bot-token
  env var.
- Notion sink. Append a block or create a page in a static database.
  `Sink[JSONValue]`, target `database_id: str (static)`, value is page properties,
  `credential_ref` to an integration token.
- Gmail source. Fetch messages matching a static query. `Source[JSONValue]`,
  `multi=True`, output `messages: list[Email]`, `credential_ref` to an OAuth token
  reference.
- Jira sink. Create or comment on an issue in a static project. `Sink[JSONValue]`,
  target `project_key: str (static)`, value is issue fields, `credential_ref` to an API
  token.
- Postgres source. Stream rows from a static, parameterised query. `Source[JSONValue]`,
  `multi=True`, output `rows: list[Row]`, `credential_ref` to a DSN env var. The query
  is static, and only bound params vary.
- RSS source. Pull entries from a static feed URL. `Source[JSONValue]`, `multi=True`,
  output `entries: list[FeedEntry]`, no credential needed.
- Webhook sink. POST the output to a static URL. `Sink[JSONValue]`, target
  `url: str (static)`, value is the JSON body, optional `credential_ref` to a
  signing-secret env var.

Pick one, copy the Slack example, swap the `_write` body, and open a PR. See
[connector ideas](connector-ideas.md) for the full scope of each.

## Next steps

- [Connector ideas](connector-ideas.md) covers the full scope of each starter, ready to
  file.
- [Security model](../architecture/SECURITY.md) covers the rules every connector
  upholds.
- [Operations overview](operations.md) covers the rest of the operate and integrate
  layer.
