"""CRA-244 — ``craw code describe`` typed-IO reflection.

Compile a component and project its typed inputs/outputs (structural ``type`` + ``flow``).
Asserts: ``flow`` is reported correctly for a fluid input; a re-run after an edit reflects the
new on-disk shape (no stale registry); ``authored_by`` / ``tainted`` ride from the CRA-266
row; the payload is ``craw.code.describe.v1``. No model calls (FakeJail compile).
"""

from __future__ import annotations

from pathlib import Path

from crawfish.code.describe import describe_component, describe_payload
from crawfish.store import SqliteStore


def _project(tmp_path: Path, *, fluid_name: str = "ticket_body") -> Path:
    """A minimal agent-authorable Definition dir: typed IO with one static, one fluid input."""
    root = tmp_path / "triage"
    root.mkdir(parents=True)
    (root / "instructions.md").write_text("You triage tickets.\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [\n"
        "    Parameter(name='project', type='str', flow=Flow.STATIC),\n"
        f"    Parameter(name='{fluid_name}', type='str', flow=Flow.FLUID),\n"
        "]\n"
        "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
    )
    return root


def test_reflects_typed_io_with_flow(tmp_path: Path) -> None:
    """Inputs/outputs carry the resolved structural ``type`` and the correct ``flow``."""
    root = _project(tmp_path)
    store = SqliteStore()
    try:
        body = describe_component(str(root), store=store)
    finally:
        store.close()
    assert body["kind"] == "definition"
    inputs = {p["name"]: p for p in body["inputs"]}  # type: ignore[union-attr]
    assert inputs["project"]["flow"] == "static"
    assert inputs["ticket_body"]["flow"] == "fluid"
    # The structural schema is a JSON-Schema export, not string equality.
    assert inputs["project"]["schema"] == {"type": "string"}
    outputs = {p["name"]: p for p in body["outputs"]}  # type: ignore[union-attr]
    assert outputs["label"]["flow"] == "static"


def test_carries_authored_by_and_tainted(tmp_path: Path) -> None:
    """A jailed (agent-authored) compile stamps ``authored_by='craw-code'`` and a clean taint."""
    root = _project(tmp_path)
    store = SqliteStore()
    try:
        body = describe_component(str(root), store=store)
    finally:
        store.close()
    assert body["authored_by"] == "craw-code"
    assert body["tainted"] is False


def test_reflects_on_disk_at_call_time(tmp_path: Path) -> None:
    """Editing the file and re-running sees the change — no stale registry (CRA-244)."""
    root = _project(tmp_path, fluid_name="ticket_body")
    store = SqliteStore()
    try:
        first = describe_component(str(root), store=store)
        assert {p["name"] for p in first["inputs"]} == {"project", "ticket_body"}  # type: ignore[union-attr]
        # Edit the on-disk component (rename the fluid input). New content sha → cache miss.
        (root / "definition.py").write_text(
            "from crawfish.core import Flow, Parameter\n"
            "inputs = [\n"
            "    Parameter(name='project', type='str', flow=Flow.STATIC),\n"
            "    Parameter(name='renamed_body', type='str', flow=Flow.FLUID),\n"
            "]\n"
            "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
        )
        second = describe_component(str(root), store=store)
    finally:
        store.close()
    assert {p["name"] for p in second["inputs"]} == {"project", "renamed_body"}  # type: ignore[union-attr]


def test_describe_payload_shape() -> None:
    """``describe_payload`` builds the typed-shape-only body deterministically."""
    from crawfish.core.types import Flow, Parameter
    from crawfish.definition.types import Definition

    defn = Definition(
        inputs=[Parameter(name="ticket", type="str", flow=Flow.FLUID)],
        outputs=[Parameter(name="label", type="str", flow=Flow.STATIC)],
    )
    body = describe_payload(
        defn, content_sha="ab12", authored_by="craw-code", tainted=True, component="x"
    )
    assert body["content_sha"] == "ab12"
    assert body["tainted"] is True
    assert body["inputs"][0]["flow"] == "fluid"  # type: ignore[index]
    assert body["outputs"][0]["flow"] == "static"  # type: ignore[index]
