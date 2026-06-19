"""Acceptance tests for Claude Code export (CRA-156)."""

from __future__ import annotations

from pathlib import Path

from crawfish.ccexport import (
    ClaudeCodeAgent,
    definition_to_cc_agent,
    export_claude_code,
    kebab_case,
    map_tools,
    model_alias,
)
from crawfish.definition.types import (
    AgentSpec,
    Coordination,
    Definition,
    DefinitionAssets,
    MCPConnection,
    Prompt,
    TeamSpec,
)

DEMO = Path(__file__).resolve().parents[3] / "demo" / "triage-bot"


def _definition(**kw: object) -> Definition:
    base: dict[str, object] = {"id": "triage_fix"}
    base.update(kw)
    return Definition(**base)  # type: ignore[arg-type]


# -- model alias mapping ----------------------------------------------------
def test_model_alias_maps_pinned_models() -> None:
    assert model_alias("claude-sonnet-4-6") == "sonnet"
    assert model_alias("claude-opus-4-8") == "opus"
    assert model_alias("claude-haiku-4-5") == "haiku"
    assert model_alias("mock") == "inherit"
    assert model_alias(None) == "inherit"
    assert model_alias([]) == "inherit"
    assert model_alias(["claude-opus-4-8", "claude-sonnet-4-6"]) == "opus"


def test_kebab_case() -> None:
    assert kebab_case("triage_fix") == "triage-fix"
    assert kebab_case("Triage Bot 2") == "triage-bot-2"
    assert kebab_case("__weird__") == "weird"


# -- body: instructions + agent prompts -------------------------------------
def test_body_carries_instructions_and_agent_prompts() -> None:
    team = TeamSpec(
        agents=[
            AgentSpec(role="lead", prompt="You triage a ticket.", model="claude-opus-4-8"),
            AgentSpec(role="classifier", prompt="You classify the ticket."),
            AgentSpec(role="summarizer", prompt="You summarize the ticket."),
        ],
        coordination=Coordination.LEAD,
        lead="lead",
    )
    agent = definition_to_cc_agent(_definition(team=team))
    assert "You triage a ticket." in agent.body
    assert "You classify the ticket." in agent.body
    assert "You summarize the ticket." in agent.body
    assert agent.model == "opus"
    # lead block comes first
    assert agent.body.index("triage") < agent.body.index("classify")


def test_injected_prompts_land_in_body() -> None:
    team = TeamSpec(agents=[AgentSpec(role="main", prompt="Do the thing.")])
    definition = _definition(
        team=team, injected_prompts=[Prompt(target="guardrails", text="Be careful.")]
    )
    agent = definition_to_cc_agent(definition)
    assert "Be careful." in agent.body


# -- tools / MCP allowlist --------------------------------------------------
def test_map_tools_union_and_mcp_rendering() -> None:
    mcp = MCPConnection(name="github", tools=["create_issue", "search"], auth="GITHUB_TOKEN")
    team = TeamSpec(
        agents=[
            AgentSpec(role="main", tools=["Read", "Grep", "create_issue"]),
        ]
    )
    definition = _definition(team=team, assets=DefinitionAssets(mcp=[mcp]))
    tools = map_tools(definition)
    assert "Read" in tools
    assert "Grep" in tools
    # MCP tool rendered qualified, bare name de-duplicated out
    assert "mcp__github__create_issue" in tools
    assert "mcp__github__search" in tools
    assert "create_issue" not in tools
    # sorted + deterministic
    assert tools == sorted(tools)


# -- security spine: NO secrets in output -----------------------------------
def test_no_secret_or_auth_ref_in_output() -> None:
    mcp = MCPConnection(
        name="github",
        tools=["create_issue"],
        auth="GITHUB_TOKEN",
        command=["gh-mcp"],
        url="https://example.com/mcp",
    )
    team = TeamSpec(agents=[AgentSpec(role="main", prompt="Triage.", tools=["Read"])])
    definition = _definition(team=team, assets=DefinitionAssets(mcp=[mcp]))
    agent = definition_to_cc_agent(definition)
    rendered = agent.to_markdown()
    assert "GITHUB_TOKEN" not in rendered
    assert "auth" not in rendered
    # the tool reference IS mapped (by name), the credential reference is NOT
    assert "mcp__github__create_issue" in rendered


# -- markdown shape ---------------------------------------------------------
def test_to_markdown_frontmatter_shape() -> None:
    agent = ClaudeCodeAgent(
        name="triage-fix",
        description="Triage tickets",
        model="sonnet",
        tools=["Read", "Grep"],
        body="System prompt here.",
    )
    md = agent.to_markdown()
    assert md.startswith("---\n")
    assert "name: triage-fix" in md
    assert "description: Triage tickets" in md
    assert "model: sonnet" in md
    assert "tools: Read, Grep" in md
    assert md.rstrip().endswith("System prompt here.")


# -- export to disk: agent always, skill only when requested ----------------
def test_export_writes_agent_only_by_default(tmp_path: Path) -> None:
    team = TeamSpec(agents=[AgentSpec(role="main", prompt="Hi.")])
    paths = export_claude_code(_definition(team=team), tmp_path)
    assert paths == [tmp_path / ".claude" / "agents" / "triage-fix.md"]
    assert paths[0].exists()
    assert not (tmp_path / ".claude" / "skills").exists()


def test_export_emits_skill_when_requested(tmp_path: Path) -> None:
    team = TeamSpec(agents=[AgentSpec(role="main", prompt="Hi there.")])
    paths = export_claude_code(_definition(team=team), tmp_path, skill=True)
    assert len(paths) == 2
    skill_path = tmp_path / ".claude" / "skills" / "triage-fix" / "SKILL.md"
    assert skill_path in paths
    skill_md = skill_path.read_text()
    assert "name: triage-fix" in skill_md
    assert "triage-fix" in skill_md


# -- the real demo definition exports to a valid file -----------------------
def test_demo_definition_exports(tmp_path: Path) -> None:
    definition = Definition.from_package(str(DEMO))
    paths = export_claude_code(definition, tmp_path, skill=True)
    agent_path = tmp_path / ".claude" / "agents" / "triage-bot.md"
    assert agent_path in paths
    md = agent_path.read_text()
    assert md.startswith("---\n")
    assert "name: triage-bot" in md
    # all three agent prompts compose into the body
    assert "triage an incoming support ticket" in md
    assert "classify a support ticket" in md
    assert "single-sentence summary" in md
    # no secrets anywhere
    assert "auth" not in md
