"""Acceptance tests for the SlackSink example connector.

Mirrors the in-tree sink tests: in-memory store, fixed batch_id, dry-run writes,
and the security invariants (static target, credential-by-reference, idempotency).
"""

from __future__ import annotations

import json

import pytest
from crawfish_slack import SlackSink

from crawfish.core.context import RunContext
from crawfish.core.types import Flow
from crawfish.discovery import Registry
from crawfish.nodes.sink import ApprovalRequired
from crawfish.output import Output
from crawfish.store import SqliteStore

SECRET_ENV_NAME = "SLACK_BOT_TOKEN"
SECRET_VALUE = "xoxb-super-secret-token-should-never-leak"


def _ctx() -> RunContext:
    return RunContext(store=SqliteStore(), batch_id="b1")


def _output() -> Output[str]:
    return Output(value="deploy finished", produced_by="node-x")


async def test_write_is_recorded_in_dry_run() -> None:
    ctx = _ctx()
    sink = SlackSink(config={"channel": "#alerts", "credential_ref": SECRET_ENV_NAME})

    wrote = await sink.write(_output(), ctx)

    assert wrote is True
    assert len(sink.writes) == 1
    assert sink.writes[0]["channel"] == "#alerts"
    assert sink.writes[0]["text"] == "deploy finished"


async def test_second_identical_write_is_noop() -> None:
    ctx = _ctx()
    sink = SlackSink(config={"channel": "#alerts", "credential_ref": SECRET_ENV_NAME})
    out = _output()

    assert await sink.write(out, ctx) is True
    assert await sink.write(out, ctx) is False  # idempotent re-run
    assert len(sink.writes) == 1


def test_channel_target_is_static() -> None:
    sink = SlackSink(config={"channel": "#alerts"})
    assert sink.target_params[0].name == "channel"
    assert sink.target_params[0].flow is Flow.STATIC


async def test_gated_sink_requires_approval() -> None:
    ctx = _ctx()
    sink = SlackSink(config={"channel": "#alerts"}, always_ask=True)
    with pytest.raises(ApprovalRequired):
        await sink.write(_output(), ctx)


async def test_no_credential_value_leak() -> None:
    ctx = _ctx()
    sink = SlackSink(config={"channel": "#alerts", "credential_ref": SECRET_ENV_NAME})
    await sink.write(_output(), ctx)

    # Recorded write holds only the env-var NAME, never the secret value.
    record_blob = json.dumps(sink.writes, default=str)
    assert SECRET_VALUE not in record_blob
    assert SECRET_ENV_NAME in record_blob

    # Telemetry events never contain the secret value.
    events_blob = json.dumps(ctx.store.events(ctx.run_id), default=str)
    assert SECRET_VALUE not in events_blob


def test_entry_point_is_discoverable() -> None:
    """The installed entry point resolves via Registry.discover() — no local scan."""
    reg = Registry()
    reg.discover_entry_points()
    ref = reg.get("sink", "slack")
    assert ref is not None
    assert ref.target == "crawfish_slack.sink:SlackSink"
    assert ref.origin == "entrypoint:crawfish.sinks"
