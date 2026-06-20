"""Claude Code export — a Definition as a CC subagent / skill.

A Crawfish :class:`~crawfish.definition.types.Definition` is a self-contained agent
team; Claude Code's **subagent** format is a Markdown file with YAML front-matter
(``name``/``description``/``model``/``tools``) followed by the system prompt. This
module renders a Definition into that shape so a team authored in Crawfish runs as a
Claude Code teammate, and (with ``--skill``) as an invocable slash-command.

Security spine (the load-bearing rule for this feature): the export carries **no
secrets**. A Definition references credentials by *name* (an ``MCPConnection.auth``
env-var reference, never an inline value); the export maps tool/MCP *references* only —
the allowlist names the tools, never the ``auth`` reference or any credential. The
generated file is therefore safe to commit and share.

Mapping:

* ``instructions.md`` (+ ``agents/*.md``) → the subagent body (system prompt), with
  injected prompts appended.
* the Definition's pinned model → a CC model alias (:func:`model_alias`).
* per-agent ``tools`` ∪ MCP-exposed tool names → the ``tools`` allowlist; MCP tools
  render as ``mcp__<server>__<tool>`` (:func:`map_tools`).

Example::

    definition = Definition.from_package("definitions/triage_fix")
    paths = export_claude_code(definition, Path("."), skill=True)
    # → [.claude/agents/triage-fix.md, .claude/skills/triage-fix/SKILL.md]
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path

    from crawfish.definition.types import Definition

__all__ = [
    "ClaudeCodeAgent",
    "ClaudeCodeSkill",
    "definition_to_cc_agent",
    "export_claude_code",
    "model_alias",
    "map_tools",
    "kebab_case",
]

# Map a Definition's pinned model to a Claude Code model alias. Anything we don't
# recognise (including ``mock``/``None``) resolves to ``inherit`` — never a hard error,
# so an export always produces a runnable file.
_MODEL_ALIASES = ("opus", "sonnet", "haiku")


def kebab_case(name: str) -> str:
    """Normalise an identifier to kebab-case (CC requires it for ``name``)."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "agent"


def model_alias(model: str | list[str] | None) -> str:
    """Map a Definition's pinned model to a CC alias (``opus``/``sonnet``/``haiku``).

    A list (model-universal with preferences) resolves on its first entry; ``mock``,
    an unrecognised id, or ``None`` resolves to ``inherit`` (the platform picks).
    """
    if isinstance(model, list):
        model = model[0] if model else None
    if not model:
        return "inherit"
    lowered = model.lower()
    for alias in _MODEL_ALIASES:
        if alias in lowered:
            return alias
    return "inherit"


def map_tools(definition: Definition) -> list[str]:
    """The subagent's ``tools`` allowlist: union of agent tools + MCP tool names.

    MCP-exposed tools render as ``mcp__<server>__<tool>`` (CC's MCP tool naming). The
    result is sorted and de-duplicated for a deterministic file. **No ``auth`` /secret
    reference is ever emitted** — only tool names.
    """
    mcp_tools = {t for conn in definition.assets.mcp for t in conn.tools}
    mcp_rendered = {
        f"mcp__{conn.name}__{tool}" for conn in definition.assets.mcp for tool in conn.tools
    }

    names: set[str] = set()
    for agent in definition.team.agents:
        for tool in agent.tools:
            # A bare MCP tool name on an agent allowlist becomes its qualified form.
            if tool in mcp_tools:
                continue  # added via the qualified rendering below
            names.add(tool)
    names |= mcp_rendered
    return sorted(names)


def _compose_body(definition: Definition) -> str:
    """Compose the system prompt: lead/main first, then subagents, then injections."""
    agents = list(definition.team.agents)
    lead_role = definition.team.lead
    agents.sort(key=lambda a: (a.role != lead_role and a.role != "main", a.role))

    blocks: list[str] = []
    for agent in agents:
        prompt = agent.prompt.strip()
        if not prompt:
            continue
        if len(agents) > 1:
            blocks.append(f"## {agent.role}\n\n{prompt}")
        else:
            blocks.append(prompt)

    for injected in definition.injected_prompts:
        text = injected.text.strip()
        if text:
            blocks.append(f"## injected: {injected.target}\n\n{text}")

    return "\n\n".join(blocks).strip()


class ClaudeCodeAgent(BaseModel):
    """A Claude Code subagent: YAML front-matter + a system-prompt body."""

    name: str
    description: str = ""
    model: str = "inherit"
    tools: list[str] = Field(default_factory=list)
    body: str = ""

    def to_markdown(self) -> str:
        """Render the ``.claude/agents/<name>.md`` file (front-matter + body)."""
        lines = ["---", f"name: {self.name}"]
        if self.description:
            lines.append(f"description: {self.description}")
        lines.append(f"model: {self.model}")
        if self.tools:
            lines.append(f"tools: {', '.join(self.tools)}")
        lines.append("---")
        return "\n".join(lines) + "\n\n" + self.body.strip() + "\n"


class ClaudeCodeSkill(BaseModel):
    """A Claude Code skill wrapper — a Definition as an invocable slash-command."""

    name: str
    description: str = ""
    body: str = ""

    def to_markdown(self) -> str:
        """Render the ``.claude/skills/<name>/SKILL.md`` file."""
        lines = ["---", f"name: {self.name}"]
        if self.description:
            lines.append(f"description: {self.description}")
        lines.append("---")
        return "\n".join(lines) + "\n\n" + self.body.strip() + "\n"


def _description(definition: Definition) -> str:
    """A one-line ``description`` for the front-matter (the agent's first prompt line)."""
    for agent in definition.team.agents:
        if agent.role in {definition.team.lead, "main"}:
            first = agent.prompt.strip().splitlines()
            if first:
                return first[0].strip()
    for agent in definition.team.agents:
        first = agent.prompt.strip().splitlines()
        if first and first[0].strip():
            return first[0].strip()
    return f"Crawfish definition {definition.id}"


def definition_to_cc_agent(definition: Definition) -> ClaudeCodeAgent:
    """Render a Definition into a :class:`ClaudeCodeAgent` (no secrets emitted)."""
    agents = definition.team.agents
    model: str | list[str] | None = None
    for agent in agents:
        if agent.role in {definition.team.lead, "main"} and agent.model:
            model = agent.model
            break
    if model is None:
        model = next((a.model for a in agents if a.model), None)

    return ClaudeCodeAgent(
        name=kebab_case(definition.id),
        description=_description(definition),
        model=model_alias(model),
        tools=map_tools(definition),
        body=_compose_body(definition),
    )


def definition_to_cc_skill(definition: Definition, agent: ClaudeCodeAgent) -> ClaudeCodeSkill:
    """Render a slash-command skill wrapper that invokes the exported subagent."""
    body = (
        f"Invoke the **{agent.name}** subagent (exported from the Crawfish definition "
        f"`{definition.id}`).\n\n"
        f"{agent.description}\n\n"
        f"Use the `{agent.name}` agent to handle this task end to end."
    )
    return ClaudeCodeSkill(name=agent.name, description=agent.description, body=body)


def export_claude_code(
    definition: Definition, project_dir: Path, *, skill: bool = False
) -> list[Path]:
    """Write the CC subagent (and optional skill) under ``project_dir/.claude``.

    Returns the written paths. Always writes ``.claude/agents/<name>.md``; with
    ``skill=True`` also writes ``.claude/skills/<name>/SKILL.md``. Carries no secrets.
    """
    agent = definition_to_cc_agent(definition)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    agent_path = agents_dir / f"{agent.name}.md"
    agent_path.write_text(agent.to_markdown())
    written = [agent_path]

    if skill:
        skill_obj = definition_to_cc_skill(definition, agent)
        skill_dir = project_dir / ".claude" / "skills" / skill_obj.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(skill_obj.to_markdown())
        written.append(skill_path)

    return written
