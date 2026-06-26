"""UNFILED-MAP acceptance: ``craw code map`` — the project discovery graph.

Deterministic: tmp dirs, ``run_code``, no network/model. Asserts flow-tagged typed IO,
consequential-sink redaction (no destination/secret leak), the dot format, content-sha
cache hit, two-org isolation, and that no concrete Store backend is imported.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code


def _map_json(
    capsys: pytest.CaptureFixture[str], app: Path, org: str = "local"
) -> dict[str, object]:
    rc = run_code(["map", "--dir", str(app), "--org", org, "--json"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    return json.loads(out.splitlines()[-1])


@pytest.fixture
def app(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "app"
    assert run_code(["init", str(root)]) == 0
    capsys.readouterr()
    return root


def test_map_emits_flow_tagged_definition_io(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = _map_json(capsys, app)
    nodes = body["nodes"]
    assert isinstance(nodes, list)
    triage = next(n for n in nodes if n.get("id") == "triage-bot")
    flows = {p["name"]: p["flow"] for p in triage["inputs"]}
    assert flows["project"] == "static" and flows["ticket_body"] == "fluid"


def test_consequential_sink_is_redacted(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A sink surfaces as consequential with a static-only target kind — never a destination."""
    run_code(["new", "sink", "github-issues", "--dir", str(app)])
    capsys.readouterr()
    body = _map_json(capsys, app)
    sink = next(n for n in body["nodes"] if n.get("kind") == "sink")  # type: ignore[union-attr]
    assert sink["consequential"] is True
    assert sink["target_kind"] == "static"
    # no resolved destination key is ever present
    assert "target" not in sink and "url" not in sink and "auth" not in sink


def test_map_never_leaks_mcp_secret_or_url(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Red-team: a Definition with auth + an egress host renders no secret/URL in the map."""
    d = app / "definitions" / "withmcp"
    (d / "mcp").mkdir(parents=True)
    (d / "instructions.md").write_text("---\nrole: lead\n---\nx\n")
    (d / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        'inputs = [Parameter(name="p", type="str", flow=Flow.STATIC)]\n'
        'outputs = [Parameter(name="o", type="str", flow=Flow.STATIC)]\nlead = "lead"\n'
    )
    (d / "mcp" / "x.py").write_text(
        "from crawfish.definition.types import MCPConnection\n"
        'x = MCPConnection(name="internal", auth="AWS_SECRET_KEY", '
        'command=["curl", "https://internal.host"], tools=[])\n'
    )
    body = _map_json(capsys, app)
    blob = json.dumps(body)
    assert "AWS_SECRET_KEY" not in blob  # the secret ref name never appears
    assert "internal.host" not in blob  # the egress host never appears


def test_dot_format(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_code(["map", "--dir", str(app), "--format", "dot"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("digraph crawfish {")
    assert "definition:triage-bot" in out


def test_cache_hit_on_unchanged_sha(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _map_json(capsys, app)
    cache_dir = app / ".crawfish" / "map" / "local"
    assert cache_dir.is_dir()
    cached = list(cache_dir.glob("*.json"))
    assert len(cached) == 1
    # a second map of the unchanged tree reads the same cached sha (no new cache file)
    _map_json(capsys, app)
    assert list(cache_dir.glob("*.json")) == cached


def test_two_org_isolation(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _map_json(capsys, app, org="a")
    _map_json(capsys, app, org="b")
    assert (app / ".crawfish" / "map" / "a").is_dir()
    assert (app / ".crawfish" / "map" / "b").is_dir()


def test_map_no_concrete_store_import() -> None:
    code_dir = Path(__file__).resolve().parents[1] / "src" / "crawfish" / "code"
    assert "SqliteStore" not in (code_dir / "map.py").read_text()
