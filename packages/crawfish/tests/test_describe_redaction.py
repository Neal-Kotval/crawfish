"""CRA-271 — redact secret refs & consequential config from ``craw code describe``.

``describe`` projects a component into the agent's context. If it surfaced secret references,
egress hosts, or sink destinations it would leak the consequential config the security spine
keeps away from the model (SECURITY.md rules 2 + 4). This pins the contract: ``describe``
surfaces capability **kind** only (``has_mcp_connection`` / ``declares_secret_ref``) — never
the env-var name, the egress host (``url`` / ``command``), or a sink target. The negative test
greps the serialized payload for the secret name + host and asserts their absence (a regression
re-introducing a leak fails CI). No model calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from crawfish.code.describe import describe_component
from crawfish.store import SqliteStore

_SECRET_REF = "SLACK_TOKEN"
_EGRESS_HOST = "https://hooks.slack.example.com/services/T000/B000/XXXX"


def _project_with_mcp(tmp_path: Path) -> Path:
    """A Definition dir whose ``mcp/notify.py`` declares an auth ref + an egress url."""
    root = tmp_path / "triage"
    (root / "mcp").mkdir(parents=True)
    (root / "instructions.md").write_text("You triage tickets.\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
    )
    (root / "mcp" / "notify.py").write_text(
        "from crawfish.definition.types import MCPConnection\n"
        f"slack = MCPConnection(name='slack', url={_EGRESS_HOST!r}, auth={_SECRET_REF!r},\n"
        "    tools=['post_message'])\n"
    )
    return root


def test_capabilities_surface_kind_only(tmp_path: Path) -> None:
    """``describe`` reports ``has_mcp_connection`` + ``declares_secret_ref`` — kinds, not values."""
    root = _project_with_mcp(tmp_path)
    store = SqliteStore()
    try:
        body = describe_component(str(root), store=store)
    finally:
        store.close()
    kinds = {c["kind"] for c in body["capabilities"]}  # type: ignore[union-attr]
    assert "has_mcp_connection" in kinds
    assert "declares_secret_ref" in kinds
    # No capability entry carries anything but the bare kind.
    for cap in body["capabilities"]:  # type: ignore[union-attr]
        assert set(cap.keys()) == {"kind"}


def test_no_secret_ref_or_egress_host_in_payload(tmp_path: Path) -> None:
    """The serialized payload contains neither the secret name nor the egress host (CRA-271)."""
    root = _project_with_mcp(tmp_path)
    store = SqliteStore()
    try:
        body = describe_component(str(root), store=store)
    finally:
        store.close()
    serialized = json.dumps(body, sort_keys=True)
    assert _SECRET_REF not in serialized
    assert _EGRESS_HOST not in serialized
    assert "slack" not in serialized  # the connection name (egress identity) is dropped too
