"""Tests for container build generation (CRA-115)."""

from __future__ import annotations

from pathlib import Path

from crawfish.build import (
    generate_containerfile,
    plan_build,
    write_containerfile,
)
from crawfish.config import ProjectManifest


def test_generate_containerfile_contains_base_install_and_run() -> None:
    manifest = ProjectManifest(name="acme", version="1.2.3")
    text = generate_containerfile(manifest, python_version="3.11")
    assert "FROM python:3.11-slim" in text
    assert "pip install --no-cache-dir ." in text
    assert 'ENTRYPOINT ["craw", "run"]' in text


def test_generate_containerfile_is_deterministic() -> None:
    manifest = ProjectManifest(name="acme", version="1.2.3")
    assert generate_containerfile(manifest) == generate_containerfile(manifest)


def test_generate_containerfile_omits_lock_when_absent() -> None:
    manifest = ProjectManifest(name="acme", version="1.2.3")
    with_lock = generate_containerfile(manifest, lock_present=True)
    without_lock = generate_containerfile(manifest, lock_present=False)
    assert "crawfish.lock" in with_lock
    assert "crawfish.lock" not in without_lock


def test_plan_build_derives_image_name_from_manifest() -> None:
    manifest = ProjectManifest(name="acme", version="1.2.3")
    plan = plan_build(manifest)
    assert plan.image == "acme:1.2.3"
    assert plan.base_image == "python:3.11-slim"
    assert plan.steps


def test_write_containerfile_writes_file(tmp_path: Path) -> None:
    manifest = ProjectManifest(name="acme", version="1.2.3")
    dest = tmp_path / "Containerfile"
    out = write_containerfile(manifest, dest)
    assert out == dest
    assert out.exists()
    assert 'ENTRYPOINT ["craw", "run"]' in out.read_text()


def test_write_containerfile_to_directory(tmp_path: Path) -> None:
    manifest = ProjectManifest(name="acme", version="1.2.3")
    out = write_containerfile(manifest, tmp_path)
    assert out == tmp_path / "Containerfile"
    assert out.exists()
