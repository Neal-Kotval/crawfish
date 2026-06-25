"""CRA-277 acceptance: agent-added MCP/secret capabilities re-enter the consent gate.

Deterministic: tmp dirs, ``run_code``, no stdin (consent via the injectable deciders / the
``--yes`` flag). A new MCP triggers a re-gate; the non-interactive default fails closed
(``consent_required``, exit 4, non-retryable); ``--yes`` records the grant (references-only);
an already-covered artifact needs no re-consent; tenancy isolates a grant per org.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code


def _def_with_mcp(root: Path, name: str = "withmcp") -> Path:
    """Author a Definition declaring an MCPConnection (a new egress + secret reference)."""
    d = root / "definitions" / name
    (d / "mcp").mkdir(parents=True)
    (d / "instructions.md").write_text("---\nrole: lead\n---\nlead\n")
    (d / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        'inputs = [Parameter(name="project", type="str", flow=Flow.STATIC)]\n'
        'outputs = [Parameter(name="o", type="str", flow=Flow.STATIC)]\n'
        'lead = "lead"\n'
    )
    (d / "mcp" / "github.py").write_text(
        "from crawfish.definition.types import MCPConnection\n"
        'github = MCPConnection(name="github", auth="GITHUB_TOKEN", tools=[])\n'
    )
    return d


@pytest.fixture
def app(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "app"
    assert run_code(["init", str(root)]) == 0
    capsys.readouterr()
    return root


def test_new_mcp_triggers_regate_fail_closed(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A non-interactive sync over a Definition with a new MCP fails closed (exit 4)."""
    _def_with_mcp(app)
    rc = run_code(["sync", "--dir", str(app), "--json"])
    cap = capsys.readouterr()
    payload = json.loads((cap.out.strip() or cap.err.strip()).splitlines()[-1])
    assert rc == 4
    assert payload["code"] == "consent_required"
    assert payload["retryable"] is False


def test_grant_yes_records_grant_then_sync_passes(
    app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d = _def_with_mcp(app)
    assert run_code(["sync", "--dir", str(app)]) == 4  # fail closed first
    capsys.readouterr()

    rc = run_code(["grant", str(d), "--yes", "--json"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    payload = json.loads(out.splitlines()[-1])
    # the consent surface shows secrets by REFERENCE name only, never a value
    caps = payload["new_capabilities"]
    assert caps["secrets"] == ["GITHUB_TOKEN"] and caps["egress"] == ["github"]

    # now the prior grant covers it — sync no longer re-prompts
    assert run_code(["sync", "--dir", str(app)]) == 0


def test_no_new_capability_no_consent(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A Definition declaring nothing new needs no re-consent (the scaffold triage-bot)."""
    # the bare scaffold (no MCP) syncs clean — no consent prompt
    assert run_code(["sync", "--dir", str(app)]) == 0


def test_grant_is_tenancy_scoped(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A grant recorded in org A does not satisfy the re-gate in org B (tenancy isolation)."""
    d = _def_with_mcp(app)
    assert run_code(["grant", str(d), "--yes", "--org", "a"]) == 0
    capsys.readouterr()
    # org b has no grant — its sync still fails closed
    assert run_code(["sync", "--dir", str(app), "--org", "b"]) == 4
    # org a, which granted, passes
    assert run_code(["sync", "--dir", str(app), "--org", "a"]) == 0


def test_grant_uses_no_concrete_store_import() -> None:
    """consent.py reaches the Store via the protocol/factory — grep guard."""
    code_dir = Path(__file__).resolve().parents[1] / "src" / "crawfish" / "code"
    assert "SqliteStore" not in (code_dir / "consent.py").read_text()
