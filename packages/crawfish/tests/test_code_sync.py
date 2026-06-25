"""CRA-247 acceptance: ``craw code sync`` reconciles the tree with discovery + doctor.

Deterministic: tmp dirs, ``run_code``, no network/model. Covers a clean tree, misplaced
drift, a DefinitionLoadError finding (exit 1, not a crash), the assembly-gate precondition
(a fluid->static-sink wiring → exit 4, non-retryable), and .crawfish/ tamper (exit 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code


def _sync_json(capsys: pytest.CaptureFixture[str], app: Path) -> tuple[int, dict[str, object]]:
    rc = run_code(["sync", "--dir", str(app), "--json"])
    cap = capsys.readouterr()
    # success payloads go to stdout; the craw.error.v1 envelope goes to stderr.
    text = cap.out.strip() or cap.err.strip()
    payload: dict[str, object] = json.loads(text.splitlines()[-1]) if text else {}
    return rc, payload


@pytest.fixture
def app(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "app"
    assert run_code(["init", str(root)]) == 0
    capsys.readouterr()
    return root


def test_clean_tree_syncs(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, payload = _sync_json(capsys, app)
    assert rc == 0
    comps = payload["components"]
    assert isinstance(comps, dict)
    assert "triage-bot" in comps["definitions"]  # type: ignore[index]
    gate = payload["assembly_gate"]
    assert isinstance(gate, dict)
    assert "triage-bot" in gate["checked"] and gate["rejected"] == []  # type: ignore[index]
    assert payload["ledger"] == "clean"


def test_misplaced_definition_is_drift(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # a Definition-shaped dir sitting under sources/ is misplacement drift
    bad = app / "sources" / "looks-like-def"
    bad.mkdir(parents=True)
    (bad / "instructions.md").write_text("---\nrole: lead\n---\nx\n")
    rc, payload = _sync_json(capsys, app)
    assert rc == 1  # drift/warnings
    drift = payload["drift"]
    assert isinstance(drift, list)
    assert any(d["kind"] == "misplaced" for d in drift)


def test_definition_load_error_is_a_finding_not_a_crash(
    app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = app / "definitions" / "broken"
    bad.mkdir(parents=True)
    # bind an unknown tool -> DefinitionLoadError at load
    (bad / "instructions.md").write_text("---\nrole: lead\ntools: [nope]\n---\nx\n")
    rc, payload = _sync_json(capsys, app)
    assert rc == 1
    errors = payload["load_errors"]
    assert isinstance(errors, list)
    assert any(
        e["component"] == "definitions/broken" and e["code"] == "DefinitionLoadError"
        for e in errors
    )


def test_assembly_gate_rejects_fluid_to_sink_wiring(
    app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Red-team: a Definition with a FLUID consequential-egress output fails closed (exit 4)."""
    bad = app / "definitions" / "exfil"
    bad.mkdir(parents=True)
    (bad / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        'inputs = [Parameter(name="ticket_body", type="str")]\n'
        'outputs = [Parameter(name="reply", type="str", flow=Flow.FLUID)]\n'
        'lead = "lead"\n'
    )
    (bad / "instructions.md").write_text("---\nrole: lead\n---\nx\n")
    rc, payload = _sync_json(capsys, app)
    assert rc == 4  # security rejection
    assert payload["code"] == "fluid_to_static_sink"
    assert payload["retryable"] is False
    # the remediation is static — it never echoes a fluid value back to the agent
    assert "ticket_body" not in payload["remediation"]  # type: ignore[operator]


def test_crawfish_tamper_is_exit_2(app: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An authored unit hiding inside .crawfish/ is the tamper / generated-boundary breach."""
    hidden = app / ".crawfish" / "definitions" / "sneaky"
    hidden.mkdir(parents=True)
    (hidden / "instructions.md").write_text("x\n")
    rc, payload = _sync_json(capsys, app)
    assert rc == 2
    assert payload["ledger"] == "dirty"


def test_sync_no_concrete_store_import() -> None:
    """sync (and its siblings) reach the Store via protocol only — grep guard."""
    code_dir = Path(__file__).resolve().parents[1] / "src" / "crawfish" / "code"
    assert "SqliteStore" not in (code_dir / "sync.py").read_text()
