"""CRA-274 — bound ``craw code describe`` reflection cost + standalone CLI contract.

``describe`` recompiles per call, an unbounded hot-path latency for a verb the agent may call
repeatedly. The projection is cached by **content sha** under ``.crawfish/describe/``. Pins:
a repeated describe of an unchanged component is a zero-recompile hit; an edit (new sha) is a
miss + recompile; the cache lands under ``.crawfish/`` (never the authored tree); a reflection
cost ceiling fails closed; and ``craw code describe`` runs **standalone** over Bash (no plugin,
no MCP, no session) — asserted by a bare subprocess invocation. No model calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from crawfish.code.describe import _REFLECTION_COMPONENT_CEILING, describe_component
from crawfish.store import SqliteStore


def _project(tmp_path: Path, *, out_name: str = "label") -> Path:
    root = tmp_path / "triage"
    root.mkdir(parents=True)
    (root / "instructions.md").write_text("You triage tickets.\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        f"outputs = [Parameter(name='{out_name}', type='str', flow=Flow.STATIC)]\n"
    )
    return root


def test_unchanged_component_is_a_cache_hit(tmp_path: Path) -> None:
    """Two describes of an unchanged component → the second recompiles zero times."""
    root = _project(tmp_path)
    store = SqliteStore()
    counter = [0]
    try:
        describe_component(str(root), store=store, compile_counter=counter)
        assert counter[0] == 1  # first call compiled
        describe_component(str(root), store=store, compile_counter=counter)
        assert counter[0] == 1  # second call was a hit — no recompile
    finally:
        store.close()


def test_edited_component_is_a_miss(tmp_path: Path) -> None:
    """An edit (new content sha) is a cache miss and recompiles (CRA-274)."""
    root = _project(tmp_path, out_name="label")
    store = SqliteStore()
    counter = [0]
    try:
        describe_component(str(root), store=store, compile_counter=counter)
        assert counter[0] == 1
        (root / "definition.py").write_text(
            "from crawfish.core import Flow, Parameter\n"
            "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
            "outputs = [Parameter(name='verdict', type='str', flow=Flow.STATIC)]\n"
        )
        body = describe_component(str(root), store=store, compile_counter=counter)
        assert counter[0] == 2  # the edit forced a recompile
    finally:
        store.close()
    assert {p["name"] for p in body["outputs"]} == {"verdict"}  # type: ignore[union-attr]


def test_cache_lives_under_dot_crawfish(tmp_path: Path) -> None:
    """The cache lands under ``.crawfish/describe/`` — never written into the authored tree."""
    root = _project(tmp_path)
    store = SqliteStore()
    try:
        describe_component(str(root), store=store)
    finally:
        store.close()
    cache_dir = root / ".crawfish" / "describe"
    assert cache_dir.is_dir()
    # The projection is content-sha-keyed under a per-org subdir (CRA-274 + CRA-275).
    assert list(cache_dir.rglob("*.json"))


def test_reflection_ceiling_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A component exceeding the reflection ceiling fails closed (ReflectionCostError)."""
    from crawfish.code import describe as describe_mod

    root = _project(tmp_path)
    # Force the ceiling below the single-file project so the bound trips deterministically.
    monkeypatch.setattr(describe_mod, "_REFLECTION_COMPONENT_CEILING", 0)
    store = SqliteStore()
    try:
        with pytest.raises(describe_mod.ReflectionCostError):
            describe_mod.describe_component(str(root), store=store)
    finally:
        store.close()
    assert _REFLECTION_COMPONENT_CEILING > 0  # the real ceiling is generous


def test_standalone_bare_subprocess(tmp_path: Path) -> None:
    """``craw code describe`` runs standalone over Bash — no plugin, no MCP, no session."""
    root = _project(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "crawfish.cli", "code", "describe", str(root), "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["schema"] == "craw.code.describe.v1"
    assert {p["name"] for p in payload["inputs"]} == {"ticket"}
