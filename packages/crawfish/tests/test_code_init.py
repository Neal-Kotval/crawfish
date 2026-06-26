"""CRA-245 acceptance: ``craw code init`` scaffolds + starts the ledger, no model/secret.

All deterministic: tmp dirs, ``run_code`` (no top-level CLI), no network, no live model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code


def _init_json(capsys: pytest.CaptureFixture[str], *args: str) -> dict[str, object]:
    rc = run_code(["init", *args, "--json"])
    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    payload: dict[str, object] = json.loads(out)
    return payload


def test_init_writes_canonical_tree_and_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = tmp_path / "app"
    payload = _init_json(capsys, str(app), "--name", "my-app")

    # canonical seven-ish folders + crawfish.toml + the secrets-by-reference template
    assert (app / "crawfish.toml").exists()
    assert (app / ".env.example").exists()
    assert (app / "definitions" / "triage-bot" / "definition.py").exists()
    assert (app / "sources").is_dir() and (app / "sinks").is_dir()

    # the ledger is opened under .crawfish/ (generated state)
    assert (app / ".crawfish").is_dir()
    assert payload["ledger"] == {"started": True, "preserved": False, "path": ".crawfish/"}
    assert payload["project"] == "my-app"
    assert "crawfish.toml" in payload["scaffolded"]  # type: ignore[operator]


def test_init_records_provenance_row(tmp_path: Path) -> None:
    """An init provenance row is recorded through the Store protocol (generated_by tag)."""
    app = tmp_path / "app"
    assert run_code(["init", str(app)]) == 0

    from crawfish.manage import store_for_dir
    from crawfish.provenance import FILE_PROVENANCE_RECORD_KIND

    store = store_for_dir(str(app))
    try:
        rows = store.list_records(FILE_PROVENANCE_RECORD_KIND, org_id="local")
    finally:
        getattr(store, "close", lambda: None)()
    assert any(r.get("authored_by") == "craw-code-init" for r in rows)


def test_init_no_concrete_store_import_in_code_pkg() -> None:
    """The verb reaches the Store through the protocol/factory, never a backend import.

    Grep guard (acceptance): no ``code/`` module names ``SqliteStore`` directly.
    """
    code_dir = Path(__file__).resolve().parents[1] / "src" / "crawfish" / "code"
    for py in code_dir.glob("*.py"):
        text = py.read_text()
        assert "SqliteStore" not in text, f"{py.name} must not import a concrete Store backend"


def test_init_makes_no_live_call_and_resolves_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No network/model and no secret resolution occurs (resolve_secret never called)."""
    import crawfish.secrets as secrets

    calls: list[object] = []
    orig = secrets.resolve_secret
    monkeypatch.setattr(secrets, "resolve_secret", lambda *a, **k: calls.append(a) or orig(*a, **k))
    assert run_code(["init", str(tmp_path / "app")]) == 0
    assert calls == []


def test_init_no_plugin_flag_skips_plugin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _init_json(capsys, str(tmp_path / "app"), "--no-plugin")
    plugin = payload["plugin"]
    assert isinstance(plugin, dict)
    assert plugin.get("installed") is False
    # no plugin tree under .claude when skipped
    assert not (tmp_path / "app" / ".claude" / "plugins" / "crawfish").exists()


def test_init_reconciles_existing_without_clobber(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Re-running init creates nothing new and lists skipped_existing (reconcile-first)."""
    app = tmp_path / "app"
    _init_json(capsys, str(app))
    # tamper a marker into an authored file; a reconcile re-run must not overwrite it
    marker = "# user edit\n"
    toml = app / "crawfish.toml"
    toml.write_text(toml.read_text() + marker)

    payload = _init_json(capsys, str(app))
    assert payload["scaffolded"] == []  # nothing newly created
    assert "crawfish.toml" in payload["skipped_existing"]  # type: ignore[operator]
    assert toml.read_text().endswith(marker)  # the user edit survived
