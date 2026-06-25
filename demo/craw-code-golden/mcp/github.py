"""GitHub MCP connection.

``auth`` is a SECRET REFERENCE — an env-var name, never an inline credential. It resolves
into the server env at run time and never reaches a prompt, config, or log. Adding this
connection is a new capability (egress + a secret reference), so it re-enters the consent
gate (``craw code grant``, CRA-277).
"""

from __future__ import annotations

from crawfish.definition.types import MCPConnection

github = MCPConnection(
    name="github",
    description="GitHub issues/PRs server — file a triage as an issue.",
    command=["npx", "-y", "@modelcontextprotocol/server-github"],
    auth="GITHUB_TOKEN",  # ← reference only; resolved into the server env at run time
    tools=["create_issue", "search_issues"],
)
