"""CRA-246 acceptance: ``craw code new <kind> <name>`` scaffolds to the canonical folder.

Deterministic: tmp dirs, ``run_code``, no network/model. One case per kind asserts the
destination + content; plus overwrite refusal, [project.paths] relocation, provenance
stamping, the static/fluid spine in the templates, and the post-write secret-shaped lint.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code

KINDS_TO_FILE = {
    "tool": "tools/fmt.py",
    "policy": "policies/guard.py",
    "source": "sources/tickets.py",
    "sink": "sinks/issues.py",
    "mcp": "mcp/github.py",
    "pipeline": "pipelines/main.py",
    "definition": "definitions/triage/definition.py",
    "observer": "observers/watch/instructions.md",
}
NAME = {
    "tool": "fmt",
    "policy": "guard",
    "source": "tickets",
    "sink": "issues",
    "mcp": "github",
    "pipeline": "main",
    "definition": "triage",
    "observer": "watch",
}


def _new_json(
    capsys: pytest.CaptureFixture[str], app: Path, kind: str, name: str, *extra: str
) -> dict[str, object]:
    rc = run_code(["new", kind, name, "--dir", str(app), "--json", *extra])
    cap = capsys.readouterr()
    # success payloads go to stdout; the craw.error.v1 envelope goes to stderr.
    text = cap.out.strip() or cap.err.strip()
    payload: dict[str, object] = json.loads(text.splitlines()[-1]) if text else {}
    payload["_rc"] = rc
    return payload


@pytest.fixture
def app(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "app"
    assert run_code(["init", str(root)]) == 0
    capsys.readouterr()  # drain init output
    return root


@pytest.mark.parametrize("kind", sorted(KINDS_TO_FILE))
def test_each_kind_emits_to_canonical_folder(
    app: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    payload = _new_json(capsys, app, kind, NAME[kind])
    assert payload["_rc"] == 0
    assert (app / KINDS_TO_FILE[kind]).exists()
    assert payload["lint"] == {"secret_shaped": "clean"}


def test_mcp_template_uses_reference_auth(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _new_json(capsys, app, "mcp", "github")
    body = (app / "mcp" / "github.py").read_text()
    assert 'auth="GITHUB_TOKEN"' in body  # reference by env-var NAME, never a value


def test_definition_template_marks_static_and_fluid(
    app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _new_json(capsys, app, "definition", "triage")
    body = (app / "definitions" / "triage" / "definition.py").read_text()
    assert "flow=Flow.STATIC" in body  # a deliberate static (consequential) Parameter
    assert 'Parameter(name="ticket_body", type="str")' in body  # default-fluid (untrusted)


def test_new_definition_passes_sync(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A freshly new-ed Definition loads clean AND passes the sync assembly gate."""
    _new_json(capsys, app, "definition", "triage")
    capsys.readouterr()
    assert run_code(["sync", "--dir", str(app)]) == 0


def test_new_policy_compiles_via_load_definition(
    app: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A freshly new-ed POLICY actually compiles (regression: CRA-246 / Policy shape).

    The compiler imports ``<def>/policies/*.py`` and collects module-level ``Policy``
    instances. The template must therefore emit a valid ``Policy`` — ``Policy`` has no
    ``description`` field and *requires* ``kind: PolicyKind`` — so a new-ed policy placed in
    a Definition's policies/ dir must ``load_definition`` clean and bind to an agent.
    """
    from crawfish.core import Policy, PolicyKind
    from crawfish.definition import load_definition

    # 1) the project-level policy the verb authors compiles when imported the loader's way.
    _new_json(capsys, app, "policy", "guard")
    import importlib.util

    spec = importlib.util.spec_from_file_location("_t_policy", app / "policies" / "guard.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pol = mod.guard
    assert isinstance(pol, Policy)
    assert pol.kind is PolicyKind.GUARDRAIL  # the required field is present + valid

    # 2) the same template, placed inside a Definition's policies/ dir and bound to the lead,
    #    load_definitions clean (the exact compiler import path, end to end).
    d = tmp_path / "withpolicy"
    (d / "policies").mkdir(parents=True)
    (app / "policies" / "guard.py").rename(d / "policies" / "guard.py")
    (d / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        'inputs = [Parameter(name="p", type="str", flow=Flow.STATIC)]\n'
        'outputs = [Parameter(name="o", type="str", flow=Flow.STATIC)]\nlead = "lead"\n'
    )
    (d / "instructions.md").write_text("---\nrole: lead\npolicies: [guard]\n---\nlead\n")
    defn = load_definition(d)  # raises DefinitionLoadError if the policy is malformed
    assert any("guard" in a.policies for a in defn.team.agents)


def test_overwrite_refused_then_forced(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _new_json(capsys, app, "mcp", "github")
    dup = _new_json(capsys, app, "mcp", "github")
    assert dup["_rc"] == 2  # refused (spec exit 5, mapped to the usage family)
    assert dup["detail"]["exit"] == 5  # type: ignore[index]
    forced = _new_json(capsys, app, "mcp", "github", "--force")
    assert forced["_rc"] == 0


def test_paths_override_relocates_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = tmp_path / "app"
    assert run_code(["init", str(app)]) == 0
    capsys.readouterr()
    # relocate tools/ via [project.paths]
    toml = app / "crawfish.toml"
    toml.write_text(toml.read_text() + '\n[project.paths]\ntools = "lib/tools"\n')
    payload = _new_json(capsys, app, "tool", "fmt")
    assert payload["_rc"] == 0
    assert (app / "lib" / "tools" / "fmt.py").exists()
    assert not (app / "tools" / "fmt.py").exists()


def test_new_stamps_agent_provenance(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _new_json(capsys, app, "tool", "fmt")
    from crawfish.manage import store_for_dir
    from crawfish.provenance import FILE_PROVENANCE_RECORD_KIND

    store = store_for_dir(str(app))
    try:
        rows = store.list_records(FILE_PROVENANCE_RECORD_KIND, org_id="local")
    finally:
        getattr(store, "close", lambda: None)()
    authored = [r for r in rows if r.get("authored_by") == "craw-code-new"]
    assert authored, "new-authored file must carry craw-code-new provenance"
    # a template draws on no fluid input -> never tainted
    assert all(r.get("source_tainted") is False for r in authored)


def test_secret_shaped_lint_blocks_inline_credential(
    app: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a template ever emitted an inline secret, the post-write lint fails closed (exit 6)."""
    import crawfish.code.new as new_mod

    # Force a poisoned template (the negative the lint must catch) without shipping one.
    monkeypatch.setattr(
        new_mod,
        "_render_template",
        lambda kind, name: {f"{name}.py": 'token = "ghp_0123456789abcdefABCDEF0123"\n'},
    )
    payload = _new_json(capsys, app, "tool", "leak")
    assert payload["_rc"] == 2  # usage family; spec exit 6 in detail
    assert payload["detail"]["exit"] == 6  # type: ignore[index]
    findings = payload["detail"]["findings"]  # type: ignore[index]
    assert findings and all(f["match_redacted"] == "***REDACTED***" for f in findings)
    # the raw secret is NEVER echoed back
    assert "ghp_0123456789abcdefABCDEF0123" not in json.dumps(payload)
