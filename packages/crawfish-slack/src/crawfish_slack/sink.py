"""A Slack message sink — the worked example connector (~30 lines of real code).

``SlackSink`` posts a message to a Slack channel. It is the reference every new
connector copies:

* **Static-only target.** The ``channel`` is a ``Flow.STATIC`` target param, so a
  model-influenced value can never redirect the write (rejected at construction).
* **Credentials by reference.** ``config["credential_ref"]`` is the *name* of the
  env var holding the bot token — the secret value never enters config, the
  ``Output``, logs, or telemetry.
* **Dry-run by default.** In ``dry_run`` mode the would-be message is appended to
  :attr:`writes` instead of hitting the network, keeping tests offline and
  deterministic. Mirrors the in-tree ``LinearSink`` / ``GitHubPRSink`` pattern.

See ``docs/guide/contributing-a-connector.md`` for the full walkthrough.
"""

from __future__ import annotations

from crawfish.core.context import RunContext
from crawfish.core.types import Flow, JSONValue, Parameter
from crawfish.nodes.sink import Sink
from crawfish.output import Output

__all__ = ["SlackSink"]


class SlackSink(Sink[JSONValue]):
    """Post a message to a static Slack channel. Dry-run by default (network-free)."""

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
        # Live path (intentionally unimplemented in the reference connector).
        raise NotImplementedError("SlackSink live mode is not implemented")
