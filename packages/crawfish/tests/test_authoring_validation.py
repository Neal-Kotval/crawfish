"""CRA-265 — the authoring validation eval.

The behavioural proof that the authoring playbook teaches the *enforced* shape: an agent who
follows it produces a Definition that loads jailed clean, passes the assembly gate, lints
clean, and runs green on the mock — and that the red-team negatives (a fluid→static-sink
wiring, an inline secret, an unknown tool binding) are **rejected by the real checks**, not
merely asserted in prose.

Deterministic: jailed compile via ``SandboxPolicy(kind="fake")``, mock run with a
record-shaped responder. No live model call, no network.
"""

from __future__ import annotations

from pathlib import Path

from crawfish.code.validate_authoring import (
    VALIDATE_SCHEMA,
    default_negatives,
    triage_responder,
    validate_authoring,
)
from crawfish.runtime.mock import MockRuntime
from crawfish.store import SqliteStore

_REPO = Path(__file__).resolve().parents[3]
_SPEC = _REPO / "docs" / "specs" / "craw-code" / "authoring" / "authoring-spec.toml"


def _run(tmp_path: Path) -> dict:
    store = SqliteStore()
    try:
        return validate_authoring(
            _SPEC,
            repo_root=_REPO,
            store=store,
            runtime=MockRuntime(responder=triage_responder()),
            tmp_root=tmp_path,
        )
    finally:
        store.close()


def test_eval_verdict_passes(tmp_path: Path) -> None:
    """The whole eval passes: golden clean + every negative rejected."""
    body = _run(tmp_path)
    assert body["schema"] == VALIDATE_SCHEMA
    assert body["verdict"] == "pass", body


def test_golden_positive_clears_every_stage(tmp_path: Path) -> None:
    """The golden loads jailed, passes the assembly gate + lint, and runs green on the mock."""
    body = _run(tmp_path)
    positives = body["positives"]
    assert len(positives) == 1
    row = positives[0]
    assert row["id"] == "craw-code-golden"
    assert row["loads"] is True
    assert row["assembly_gate"] == "pass"
    assert row["lint"] == "clean"
    assert row["test"] == "green"
    assert row["ok"] is True


def test_every_negative_is_rejected_by_the_real_gate(tmp_path: Path) -> None:
    """Each red-team fixture is rejected by its expected gate with the expected rejection."""
    body = _run(tmp_path)
    negatives = {n["id"]: n for n in body["negatives"]}

    # fluid→static-sink: the assembly gate (ALG-3) must raise FluidToStaticSinkError.
    fts = negatives["fluid-to-sink"]
    assert fts["rejected"] is True
    assert fts["rejected_by"] == "assembly_gate"
    assert fts["code"] == "FluidToStaticSinkError"

    # inline secret: the secret-shaped lint must flag it.
    sec = negatives["inline-secret"]
    assert sec["rejected"] is True
    assert sec["rejected_by"] == "secret_shaped_lint"

    # unknown tool binding: load must fail with DefinitionLoadError.
    unk = negatives["unknown-tool"]
    assert unk["rejected"] is True
    assert unk["rejected_by"] == "load"
    assert unk["code"] == "DefinitionLoadError"


def test_negatives_are_not_just_text_assertions(tmp_path: Path) -> None:
    """Sanity: the standard corpus is the three independent gates (no overlap, real rejections)."""
    cases = default_negatives()
    gates = {c.gate for c in cases}
    assert gates == {"assembly_gate", "secret_shaped_lint", "load"}
    # Each builder actually writes a directory that the gate then rejects (driven in the
    # eval above) — the gates are the real ALG-3 / lint / compiler, not a string match.
    assert {c.id for c in cases} == {"fluid-to-sink", "inline-secret", "unknown-tool"}


# ---------------------------------------------------------------------------
# The self-registering CLI verb (CRA-265 / CRA-243).
# ---------------------------------------------------------------------------
def _run_verb(argv: list[str]) -> tuple[int, str, str]:
    """Drive ``craw code <argv>`` through the registry; capture (exit, stdout, stderr)."""
    import contextlib
    import io

    from crawfish.code.cli import run_code

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = run_code(argv)
    return rc, out.getvalue(), err.getvalue()


def test_verb_is_self_registered() -> None:
    """``validate-authoring`` self-registers via the pkgutil discovery (no cli.py edit)."""
    from crawfish.code.validate_authoring import VERB_NAME, register

    assert VERB_NAME == "validate-authoring"
    assert callable(register)


def test_verb_runs_over_golden_exit_zero() -> None:
    """``craw code validate-authoring --json`` over the golden → exit 0, craw.code.validate.v1."""
    import json

    rc, out, _ = _run_verb(["validate-authoring", "--json"])
    assert rc == 0, out
    env = json.loads(out)
    assert env["schema"] == "craw.code.validate.v1"
    assert env["schema_version"] == {"major": 1, "minor": 0}
    assert env["verdict"] == "pass"
    assert all(p["ok"] for p in env["positives"])
    assert all(n["rejected"] for n in env["negatives"])


def test_verb_human_path_runs() -> None:
    """The non-``--json`` path prints a verdict summary and exits 0."""
    rc, out, _ = _run_verb(["validate-authoring"])
    assert rc == 0
    assert "verdict: pass" in out


def test_verb_positive_failure_is_nonzero(tmp_path: Path) -> None:
    """A spec whose golden FAILS to clear a stage → non-zero exit (positive regression).

    Point ``--spec`` at a temp spec whose ``golden`` is a project with a consequential output
    mis-declared FLUID — the assembly gate rejects it, so the positive does not clear and the
    verb exits non-zero (CRA-243 expected-failure family).
    """
    import json

    # A broken "golden": a fluid-output Definition the assembly gate will reject.
    broken = tmp_path / "broken-golden"
    broken.mkdir()
    (broken / "instructions.md").write_text("You triage a ticket.\n")
    (broken / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket_body', type='str', flow=Flow.FLUID)]\n"
        "outputs = [Parameter(name='triage', type='str', flow=Flow.FLUID)]\n"
    )
    spec = tmp_path / "spec.toml"
    spec.write_text('version = 1\ngolden = "broken-golden"\n[[file]]\nkind = "definition.py"\n')

    rc, out, err = _run_verb(
        ["validate-authoring", "--json", "--spec", str(spec), "--repo-root", str(tmp_path)]
    )
    assert rc != 0
    # The verdict is fail (a positive that didn't clear the assembly gate). The body carries
    # the per-stage detail (emitted on stdout for a positive regression, exit 1).
    payload = json.loads(out) if out.strip() else json.loads(err)
    assert payload.get("verdict") == "fail" or payload.get("detail", {}).get("verdict") == "fail"


def test_verb_negative_leak_is_security_exit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A negative the gate unexpectedly let through → EXIT_SECURITY (4), spec exit 7 in detail.

    Drive ``_cmd_validate`` with a patched eval that reports a negative as NOT rejected (a
    regression of the enforcement). The verb must surface it as a security failure.
    """
    import argparse

    from crawfish.code import validate_authoring as mod

    leaked = {
        "schema": "craw.code.validate.v1",
        "positives": [{"id": "golden", "ok": True}],
        "negatives": [{"id": "fluid-to-sink", "rejected": False, "rejected_by": None}],
        "verdict": "fail",
    }
    monkeypatch.setattr(mod, "validate_authoring", lambda *a, **k: leaked)

    args = argparse.Namespace(as_json=True, org="local", spec=str(_SPEC), repo_root=str(_REPO))
    import contextlib
    import io

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = mod._cmd_validate(args)
    assert rc == 4  # EXIT_SECURITY
    import json

    env = json.loads(err.getvalue())
    assert env["detail"]["exit"] == 7  # granular spec exit rides in detail
