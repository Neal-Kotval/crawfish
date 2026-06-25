"""CRA-276 acceptance: the secret-shaped-literal lint (``craw code lint``).

Deterministic + pure (no network/model). Positive cases per shape class with the value
REDACTED in output; negative cases (env-var refs, .env.example); detector parity with the
ScrubbingStore redaction path; a hit fails closed with the remediation naming reference-by-name.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code
from crawfish.code.lint import REDACTED, secret_shaped_findings

# One literal per shape class the spec enumerates (kept obviously fake).
SHAPE_CASES = {
    "github_pat": 'token = "ghp_0123456789abcdefABCDEF0123"',
    "openai_key": 'api_key = "sk-0123456789abcdefABCDEF0123"',
    "aws_key": 'aws = "AKIA0123456789ABCDEF"',
    "generic_high_entropy": 'secret = "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MA=="',
}

CLEAN_CASES = {
    "env_var_reference": 'auth = "GITHUB_TOKEN"',
    "comment": "# set GITHUB_TOKEN in your .env (never inline)",
    "static_param": 'Parameter(name="project", type="str", flow=Flow.STATIC)',
}


@pytest.mark.parametrize("name", sorted(SHAPE_CASES))
def test_each_shape_class_is_flagged_redacted(name: str) -> None:
    findings = secret_shaped_findings(SHAPE_CASES[name])
    assert findings, f"{name} should be flagged"
    # the value is REDACTED — the raw literal is never echoed
    assert all(f["match_redacted"] == REDACTED for f in findings)
    raw_value = SHAPE_CASES[name].split('"')[1]
    assert raw_value not in json.dumps(findings)


@pytest.mark.parametrize("name", sorted(CLEAN_CASES))
def test_clean_cases_pass(name: str) -> None:
    assert secret_shaped_findings(CLEAN_CASES[name]) == []


def test_detector_parity_with_scrubbing_store() -> None:
    """A literal the lint flags is also redacted by the ScrubbingStore path (parity)."""
    from crawfish.secrets import redact

    literal = "ghp_0123456789abcdefABCDEF0123"
    assert secret_shaped_findings(f'token = "{literal}"')
    # the shared redaction path scrubs the same literal — they agree
    assert literal not in redact(literal)


def test_lint_verb_clean_tree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    app = tmp_path / "app"
    assert run_code(["init", str(app)]) == 0
    capsys.readouterr()
    rc = run_code(["lint", "--dir", str(app), "--json"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    payload = json.loads(out.splitlines()[-1])
    assert payload["verdict"] == "clean" and payload["findings"] == []


def test_lint_verb_fails_closed_on_inline_secret(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = tmp_path / "app"
    run_code(["init", str(app)])
    capsys.readouterr()
    (app / "tools").mkdir(exist_ok=True)
    (app / "tools" / "leak.py").write_text('token = "ghp_0123456789abcdefABCDEF0123"\n')

    rc = run_code(["lint", "--dir", str(app), "--json"])
    cap = capsys.readouterr()
    text = cap.out.strip() or cap.err.strip()
    payload = json.loads(text.splitlines()[-1])
    assert rc == 2  # usage family; spec exit 6 in detail
    assert payload["detail"]["exit"] == 6
    assert payload["detail"]["verdict"] == "fail"
    assert "ghp_0123456789abcdefABCDEF0123" not in json.dumps(payload)  # never echoed


def test_env_example_is_out_of_scope(tmp_path: Path) -> None:
    """.env.example documents references-only and is not scanned for inline secrets."""
    from crawfish.code.lint import lint_tree

    app = tmp_path / "app"
    app.mkdir()
    (app / ".env.example").write_text("# GITHUB_TOKEN=ghp_xxx (example, never real)\n")
    assert lint_tree(app) == []


def test_shipped_templates_pass_lint(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Every shipped scaffold/new template passes the lint (no inline credential)."""
    app = tmp_path / "app"
    run_code(["init", str(app)])
    for kind, name in [("mcp", "github"), ("tool", "fmt"), ("sink", "issues"), ("policy", "g")]:
        run_code(["new", kind, name, "--dir", str(app)])
    capsys.readouterr()
    assert run_code(["lint", "--dir", str(app)]) == 0
