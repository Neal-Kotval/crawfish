"""CRA-272 — run the assembly gate (assert_build_safe) inside the run path.

``assert_build_safe`` runs the ALG-3 fluid→static-sink check and fails closed before any
image is produced — but today it fires at *build* time, not in the edit→run loop where
``craw code`` iterates. :func:`crawfish.build.assert_run_safe` wires the same gate into the
**run path**: compile (jailed per CRA-267), then run the assembly gate over the compiled
Definition before any run. A fluid→static-sink wiring fails closed with
``code='fluid_to_static_sink'`` (``retryable=false``, exit 4) **before any model call**; a
safe pipeline passes. No model calls (FakeJail compile; the gate is pure).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crawfish.alg3 import FluidToStaticSinkError
from crawfish.build import assert_run_safe
from crawfish.code import CODE_EXIT, EXIT_SECURITY, SECURITY_CODES, ErrorCode
from crawfish.store import SqliteStore


def _safe_project(tmp_path: Path) -> Path:
    """A pipeline whose outputs are all STATIC — the assembly gate passes."""
    root = tmp_path / "safe"
    root.mkdir(parents=True)
    (root / "instructions.md").write_text("triage\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
    )
    return root


def _unsafe_project(tmp_path: Path) -> Path:
    """A pipeline that wires a fluid value onto the egress surface (a FLUID output).

    A consequential output declared ``Flow.FLUID`` is the fluid→static-sink wiring the gate
    rejects: ALG-3 cannot prove it is non-consequential content vs. a fluid-fed target slot,
    so it fails closed.
    """
    root = tmp_path / "unsafe"
    root.mkdir(parents=True)
    (root / "instructions.md").write_text("triage\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        # A FLUID output on the egress surface — the poisoned-ticket → sink wiring.
        "outputs = [Parameter(name='sink_target', type='str', flow=Flow.FLUID)]\n"
    )
    return root


def test_safe_pipeline_passes(tmp_path: Path) -> None:
    """A static-output pipeline passes the run-path assembly gate and returns the Definition."""
    root = _safe_project(tmp_path)
    store = SqliteStore()
    try:
        defn = assert_run_safe(root, store=store)
    finally:
        store.close()
    assert [p.name for p in defn.outputs] == ["label"]


def test_unsafe_pipeline_fails_closed(tmp_path: Path) -> None:
    """A fluid→static-sink wiring fails closed at run time (FluidToStaticSinkError)."""
    root = _unsafe_project(tmp_path)
    store = SqliteStore()
    try:
        with pytest.raises(FluidToStaticSinkError):
            assert_run_safe(root, store=store)
    finally:
        store.close()


def test_fluid_to_static_sink_is_non_retryable_exit_4() -> None:
    """The CRA-270 mapping: fluid_to_static_sink → exit 4, non-retryable (fail closed)."""
    assert CODE_EXIT[ErrorCode.FLUID_TO_STATIC_SINK] == EXIT_SECURITY
    assert ErrorCode.FLUID_TO_STATIC_SINK in SECURITY_CODES


def test_gate_fires_before_any_run(tmp_path: Path) -> None:
    """The gate is a precondition: it raises before any runtime/model call is constructed.

    We assert by construction — ``assert_run_safe`` only compiles (FakeJail) and runs the
    pure ALG-3 check; there is no runtime in the call path, so a rejection cannot have fired
    a model call. The unsafe project raising before returning a Definition is the proof.
    """
    root = _unsafe_project(tmp_path)
    store = SqliteStore()
    try:
        raised = False
        try:
            assert_run_safe(root, store=store)
        except FluidToStaticSinkError:
            raised = True
        assert raised
    finally:
        store.close()
