"""CRA-279 acceptance: ``craw code init`` is idempotent + re-entrant (``--upgrade``).

Deterministic: tmp dirs, ``run_code``, no network/model. Re-running init creates nothing,
preserves the ledger byte-for-byte, refuses a tampered ``.crawfish/`` (dirty_init, exit 2),
and ``--upgrade`` re-pins the plugin / reconciles new folders without rewriting authored files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code


def _init_json(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, dict[str, object]]:
    rc = run_code(["init", *args, "--json"])
    cap = capsys.readouterr()
    text = cap.out.strip() or cap.err.strip()
    payload: dict[str, object] = json.loads(text.splitlines()[-1]) if text else {}
    return rc, payload


def test_reinit_creates_nothing_and_preserves_authored_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = tmp_path / "app"
    _init_json(capsys, str(app))
    # a user edit to an authored file must survive a re-init untouched
    marker = "\n# user edit — must survive re-init\n"
    toml = app / "crawfish.toml"
    toml.write_text(toml.read_text() + marker)

    rc, payload = _init_json(capsys, str(app))
    assert rc == 0
    assert payload["scaffolded"] == []  # nothing newly created
    assert "crawfish.toml" in payload["skipped_existing"]  # type: ignore[operator]
    assert toml.read_text().endswith(marker)
    ledger = payload["ledger"]
    assert isinstance(ledger, dict)
    assert ledger["preserved"] is True and ledger["started"] is False


def test_ledger_rows_unchanged_after_reinit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rows present before a re-init are present and unchanged after (idempotent)."""
    app = tmp_path / "app"
    _init_json(capsys, str(app))

    from crawfish.manage import store_for_dir
    from crawfish.provenance import FILE_PROVENANCE_RECORD_KIND

    def _rows() -> list[dict[str, object]]:
        store = store_for_dir(str(app))
        try:
            return store.list_records(FILE_PROVENANCE_RECORD_KIND, org_id="local")
        finally:
            getattr(store, "close", lambda: None)()

    before = _rows()
    _init_json(capsys, str(app))  # re-init over unchanged content
    after = _rows()
    # same number of rows (re-init wrote no new provenance row for unchanged content)
    assert len(before) == len(after)
    assert {r["content_sha"] for r in before} == {r["content_sha"] for r in after}  # type: ignore[index]


def test_tampered_ledger_is_dirty_init_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = tmp_path / "app"
    _init_json(capsys, str(app))
    # an authored unit hiding inside generated state is the tamper signal
    sneaky = app / ".crawfish" / "definitions" / "sneaky"
    sneaky.mkdir(parents=True)
    (sneaky / "instructions.md").write_text("---\nrole: lead\n---\nx\n")

    rc, payload = _init_json(capsys, str(app))
    assert rc == 2
    assert payload["code"] == "jail_violation"
    assert payload["retryable"] is False
    assert payload["detail"]["reason"] == "dirty_init"  # type: ignore[index]


def test_dirty_init_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A dirty_init refusal is fail-closed before any write — no new scaffold files."""
    app = tmp_path / "app"
    _init_json(capsys, str(app))
    # remove an authored file, then tamper; the refusal must NOT recreate the removed file
    removed = app / "README.md"
    removed.unlink()
    (app / ".crawfish" / "sources").mkdir(parents=True)
    (app / ".crawfish" / "sources" / "x.py").write_text("def x():\n    pass\n")

    rc, _ = _init_json(capsys, str(app))
    assert rc == 2
    assert not removed.exists()  # the refusal wrote nothing


def test_upgrade_reconciles_without_rewriting_authored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = tmp_path / "app"
    _init_json(capsys, str(app))
    marker = "\n# authored, must survive --upgrade\n"
    toml = app / "crawfish.toml"
    toml.write_text(toml.read_text() + marker)

    rc, payload = _init_json(capsys, str(app), "--upgrade")
    assert rc == 0
    assert payload["scaffolded"] == []  # authored files reconciled, never rewritten
    assert toml.read_text().endswith(marker)
    ledger = payload["ledger"]
    assert isinstance(ledger, dict)
    assert ledger["preserved"] is True
