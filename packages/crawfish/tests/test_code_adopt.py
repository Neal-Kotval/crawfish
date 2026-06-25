"""UNFILED-ADOPT acceptance: ``craw code adopt`` brings an existing project into the loop.

Deterministic: tmp dirs, ``run_code``, no network/model. Asserts plugin+ledger reconcile
(no clobber), per-Definition export under .claude/agents/, map+sync validation reported,
exported files carry no secrets, and not_a_project → exit 9.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code
from crawfish.scaffold import scaffold_project


def _adopt_json(capsys: pytest.CaptureFixture[str], app: Path) -> tuple[int, dict[str, object]]:
    rc = run_code(["adopt", str(app), "--json"])
    cap = capsys.readouterr()
    text = cap.out.strip() or cap.err.strip()
    payload: dict[str, object] = json.loads(text.splitlines()[-1]) if text else {}
    return rc, payload


@pytest.fixture
def existing_project(tmp_path: Path) -> Path:
    """A pre-`craw code` project: scaffolded, but no .crawfish ledger / plugin yet."""
    return Path(scaffold_project(str(tmp_path / "proj")))


def test_adopt_installs_ledger_and_exports(
    existing_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, payload = _adopt_json(capsys, existing_project)
    assert rc == 0
    # ledger started under .crawfish/
    assert (existing_project / ".crawfish").is_dir()
    # per-Definition subagent exported under .claude/agents/ (export namespace)
    exported = payload["exported"]
    assert isinstance(exported, list) and exported
    assert any(e["file"].startswith(".claude/agents/") for e in exported)
    assert (existing_project / ".claude" / "agents" / "triage-bot.md").exists()
    # validation reported via sync
    validation = payload["validation"]
    assert isinstance(validation, dict)
    assert validation["sync"] == "clean"


def test_adopt_reconciles_without_clobbering_authored(
    existing_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = "\n# authored — must survive adopt\n"
    toml = existing_project / "crawfish.toml"
    toml.write_text(toml.read_text() + marker)
    _adopt_json(capsys, existing_project)
    assert toml.read_text().endswith(marker)


def test_exported_subagent_carries_no_secret(
    existing_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Export invariant: the .claude/agents file holds no credential value."""
    _adopt_json(capsys, existing_project)
    agent = (existing_project / ".claude" / "agents" / "triage-bot.md").read_text()
    # an env-var name may appear as a reference, but never a credential-shaped value
    from crawfish.code.lint import secret_shaped_findings

    assert secret_shaped_findings(agent) == []


def test_adopt_namespaces_are_disjoint(
    existing_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Export (.claude/agents) and any plugin (.claude/plugins/crawfish) never overlap."""
    _adopt_json(capsys, existing_project)
    agents = existing_project / ".claude" / "agents"
    plugins = existing_project / ".claude" / "plugins"
    assert agents.is_dir()
    # the agents namespace never contains a plugin dir and vice-versa
    if plugins.exists():
        assert not (agents / "plugins").exists()
        assert not (plugins / "agents").exists()


def test_not_a_project_is_usage_exit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """not_a_project: PROCESS exit is the CRA-243 usage family (2); granular 9 in detail.exit."""
    empty = tmp_path / "empty"
    empty.mkdir()
    rc, payload = _adopt_json(capsys, empty)
    assert rc == 2  # closed 0-4 table
    assert payload["detail"]["exit"] == 9  # type: ignore[index]
    assert payload["detail"]["reason"] == "not_a_project"  # type: ignore[index]


def test_adopt_no_export_flag(existing_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_code(["adopt", str(existing_project), "--no-export"])
    capsys.readouterr()
    assert rc == 0
    # --no-export skips the per-Definition subagent files
    assert not (existing_project / ".claude" / "agents" / "triage-bot.md").exists()
