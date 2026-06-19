"""CRA-113/CRA-118 acceptance: init scaffolds a working project; CLI commands run."""

from __future__ import annotations

from pathlib import Path

from crawfish.cli import main
from crawfish.definition import Definition
from crawfish.scaffold import scaffold_project


def test_scaffold_creates_compilable_definition(tmp_path: Path) -> None:
    root = scaffold_project(str(tmp_path / "app"))
    assert (root / "crawfish.toml").exists()
    assert (root / ".gitignore").exists()
    # the shipped hero example compiles
    d = Definition.from_package(str(root / "definitions" / "triage-bot"))
    assert d.id == "triage-bot"
    assert {a.role for a in d.team.agents} == {"lead", "classifier", "summarizer"}


def test_init_then_list_freeze_build_test(tmp_path: Path) -> None:
    app = str(tmp_path / "app")
    assert main(["init", app]) == 0

    assert main(["list", "--dir", app]) == 0
    assert main(["freeze", "--dir", app]) == 0
    assert (Path(app) / "crawfish.lock").exists()

    assert main(["build", "--dir", app]) == 0
    assert (Path(app) / "Containerfile").exists()

    # the scaffolded fixture runs green against the bundled Definition
    rc = main(["test", f"{app}/definitions/triage-bot", "--fixtures", f"{app}/fixtures"])
    assert rc == 0


def test_install_requires_consent(tmp_path: Path) -> None:
    app = str(tmp_path / "app")
    main(["init", app])
    # without --yes: declines (non-zero); with --yes: consents
    assert main(["install", app]) == 1
    assert main(["install", app, "--yes"]) == 0


def test_version_and_help() -> None:
    assert main([]) == 0  # prints help, no command
