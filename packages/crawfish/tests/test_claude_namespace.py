"""ADR 0012 acceptance: the ``.claude/`` namespaces are disjoint and sha-excluded.

The plugin install (``.claude/plugins/crawfish/``) and the per-Definition export
(``.claude/agents/``) never collide, and neither perturbs the Definition content sha (the
whole ``.claude`` tree is excluded). Deterministic: tmp dirs, no network/model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crawfish.code.cli import run_code
from crawfish.scaffold import scaffold_project


def test_export_and_plugin_namespaces_are_disjoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proj = Path(scaffold_project(str(tmp_path / "proj")))
    assert run_code(["adopt", str(proj)]) == 0
    capsys.readouterr()
    agents = proj / ".claude" / "agents"
    plugins = proj / ".claude" / "plugins"
    # export's namespace exists; if a plugin shipped, it is under a disjoint path
    assert agents.is_dir()
    if plugins.exists():
        # the reserved crawfish-* prefix keeps the plugin under plugins/crawfish/
        assert (plugins / "crawfish").exists()
        # no cross-contamination of the two namespaces
        assert not any(p.name == "agents" for p in (plugins / "crawfish").rglob("*"))


def test_claude_tree_is_excluded_from_definition_sha(tmp_path: Path) -> None:
    """Writing into .claude/ never changes a Definition's content sha (identity-stable)."""
    from crawfish.definition.compiler import _content_sha

    proj = Path(scaffold_project(str(tmp_path / "proj")))
    defn = proj / "definitions" / "triage-bot"
    before = _content_sha(defn)
    # simulate an export/plugin install writing into the Definition's .claude tree
    claude = defn / ".claude" / "agents"
    claude.mkdir(parents=True)
    (claude / "triage-bot.md").write_text("---\nname: triage-bot\n---\nexported\n")
    after = _content_sha(defn)
    assert before == after  # .claude is excluded — identity unchanged


def test_agents_dir_holds_only_exported_subagents(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proj = Path(scaffold_project(str(tmp_path / "proj")))
    run_code(["adopt", str(proj)])
    capsys.readouterr()
    agents = proj / ".claude" / "agents"
    # every file in the export namespace is a per-Definition subagent markdown
    for f in agents.iterdir():
        assert f.suffix == ".md"
