"""CRA-131: manifest parsing + profile resolution (dev→command, prod→managed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crawfish.config import load_manifest


def test_defaults_when_no_manifest(tmp_path: Path) -> None:
    m = load_manifest(tmp_path)
    assert m.resolve_profile("dev").runtime == "command"
    assert m.resolve_profile("prod").runtime == "managed"


def test_manifest_overrides(tmp_path: Path) -> None:
    (tmp_path / "crawfish.toml").write_text(
        """
[project]
name = "triage-bot"
default_profile = "dev"

[profiles.dev]
runtime = "command"

[profiles.staging]
runtime = "client"
"""
    )
    m = load_manifest(tmp_path)
    assert m.name == "triage-bot"
    assert m.resolve_profile().runtime == "command"  # default_profile
    assert m.resolve_profile("staging").runtime == "client"


def test_unknown_profile_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        load_manifest(tmp_path).resolve_profile("nope")
