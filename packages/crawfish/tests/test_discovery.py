"""CRA-113 acceptance: module discovery (entry points + local scan) + registry."""

from __future__ import annotations

import warnings
from pathlib import Path

from crawfish.discovery import Registry, UnitRef


def _project(tmp_path: Path) -> Path:
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "github.py").write_text("# a source\n")
    (tmp_path / "sources" / "_helper.py").write_text("# ignored (underscore)\n")
    d = tmp_path / "definitions" / "triage"
    d.mkdir(parents=True)
    (d / "instructions.md").write_text("triage\n")
    return tmp_path


def test_local_scan_finds_units(tmp_path: Path) -> None:
    reg = Registry.discover(_project(tmp_path))
    assert reg.get("source", "github") is not None
    assert reg.get("definition", "triage") is not None
    assert reg.get("source", "_helper") is None  # underscore files skipped


def test_of_kind(tmp_path: Path) -> None:
    reg = Registry.discover(_project(tmp_path))
    assert {r.name for r in reg.of_kind("source")} == {"github"}


def test_first_wins_and_warns() -> None:
    reg = Registry()
    assert reg.register(UnitRef("source", "x", "local:a", "a")) is True
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        kept = reg.register(UnitRef("source", "x", "local:b", "b"))
    assert kept is False  # first-wins
    assert reg.get("source", "x").target == "a"
    assert any("collision" in str(w.message) for w in caught)
