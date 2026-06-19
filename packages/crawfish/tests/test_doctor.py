"""CRA-157 acceptance: configurable structure + craw doctor.

A project can relocate unit folders via ``[project.paths]`` and discovery still
resolves them; ``craw doctor`` reports structure health and points at misplacements.
"""

from __future__ import annotations

from pathlib import Path

from crawfish.config import ProjectPaths, load_manifest
from crawfish.discovery import Registry
from crawfish.doctor import diagnose


def _def_dir(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "instructions.md").write_text("# agent\n")


def test_paths_override_parsed_from_manifest(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text(
        "[project]\nname='p'\n[project.paths]\ndefinitions='agents'\nobservers='watch'\n"
    )
    paths = load_manifest(tmp_path).paths
    assert paths.definitions == "agents"
    assert paths.observers == "watch"
    assert paths.sources == "sources"  # unspecified keeps default


def test_discovery_follows_relocated_folder(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text("[project]\n[project.paths]\ndefinitions='agents'\n")
    _def_dir(tmp_path / "agents" / "triage")
    reg = Registry.discover(tmp_path)
    assert reg.get("definition", "triage") is not None
    # the default folder is no longer scanned
    _def_dir(tmp_path / "definitions" / "ignored")
    reg2 = Registry.discover(tmp_path)
    assert reg2.get("definition", "ignored") is None


def test_observers_discovered_as_directory_packages(tmp_path: Path) -> None:
    _def_dir(tmp_path / "observers" / "quality")
    reg = Registry.discover(tmp_path)
    assert reg.get("observer", "quality") is not None


def test_doctor_reports_present_layout(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text("[project]\nname='p'\n")
    _def_dir(tmp_path / "definitions" / "triage")
    report = diagnose(tmp_path)
    assert report.ok
    assert any("crawfish.toml present" in f.message for f in report.findings)


def test_doctor_flags_misplaced_definition(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text("[project]\n")
    _def_dir(tmp_path / "sources" / "looks_like_def")  # a definition under sources/
    report = diagnose(tmp_path)
    assert not report.ok
    assert any("looks like a Definition" in f.message for f in report.findings)


def test_doctor_flags_unignored_generated_state(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text("[project]\n")
    (tmp_path / ".crawfish").mkdir()
    report = diagnose(tmp_path)
    assert any(f.level == "warn" and "gitignored" in f.message for f in report.findings)


def test_doctor_flags_missing_override_target(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text("[project]\n[project.paths]\ndefinitions='nowhere'\n")
    report = diagnose(tmp_path)
    assert not report.ok
    assert any("does not exist" in f.message for f in report.findings)


def test_as_discovery_map_covers_unit_kinds() -> None:
    m = ProjectPaths().as_discovery_map()
    assert set(m) == {"source", "sink", "definition", "observer", "tool", "policy"}
