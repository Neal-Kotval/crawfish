"""crawfish-slack — a worked example connector: a Slack message sink.

This package is the canonical "first contribution" reference. It ships a single
:class:`~crawfish_slack.sink.SlackSink` registered through a real entry point
(``[project.entry-points."crawfish.sinks"]``), so ``Registry.discover()`` finds
it the moment the package is installed — no wiring in the host project.
"""

from __future__ import annotations

from crawfish_slack.sink import SlackSink

__all__ = ["SlackSink"]
