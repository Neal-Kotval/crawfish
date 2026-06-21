"""CRA-178 — secret schema + sidecar broker (egress-mediated injection).

The load-bearing security property: the agent/jailed child NEVER receives a secret
value — only an opaque reference/handle. Injection happens in the trusted broker at the
egress boundary. These tests prove the value never appears in the child's inputs, an
Output, the ledger, or any emission, and that every lease is gated by a Grant, scoped
to a granted destination, STATIC-only, and audited.

Determinism: a fake in-memory transport and a fake secret-value table — no real network,
no real secrets, no live calls.
"""

from __future__ import annotations

import json

import pytest

from crawfish.core.types import Flow, Parameter
from crawfish.emission import EmissionKind, read_emissions
from crawfish.secrets import (
    AutoApprovalQueue,
    Grant,
    LeaseDenied,
    Outbound,
    PendingApproval,
    QueuedApprovalQueue,
    ScrubbingStore,
    SecretBroker,
    SecretRequest,
    brokered_mcp_config,
)
from crawfish.store import SqliteStore

SECRET_VALUE = "sk-supersecret-value-0123456789"
REF = "ACME_API_KEY"
DEST = "api.acme.com"
NODE = "sink.acme"


class FakeTransport:
    """Records exactly what reached the wire — so a test can assert the credential got
    there while never reaching the child."""

    def __init__(self) -> None:
        self.sent: list[Outbound] = []

    def send(self, request: Outbound) -> object:
        self.sent.append(request)
        return {"status": "ok"}


def _grant(*, secrets: tuple[str, ...] = (REF,), egress: tuple[str, ...] = (DEST,)) -> Grant:
    return Grant(package="acme", secrets=secrets, egress=egress)


def _broker(transport: FakeTransport, **kw: object) -> SecretBroker:
    return SecretBroker(secret_values={REF: SECRET_VALUE}, transport=transport, **kw)  # type: ignore[arg-type]


# -- THE key security test: value never reaches the child, only the wire ----------


def test_brokered_egress_attaches_credential_child_never_sees_value() -> None:
    transport = FakeTransport()
    broker = _broker(transport)
    grant = _grant()

    # The child leases by reference + destination — and gets back only a handle.
    handle = broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), grant)

    # The handle the child holds carries NO value.
    handle_blob = json.dumps(handle.__dict__)
    assert SECRET_VALUE not in handle_blob
    assert handle.ref == REF

    # The child builds an outbound request with the handle (never the value) and asks
    # the broker to send it.
    child_request = Outbound(host=DEST, method="POST", path="/v1/things", body={"x": 1})
    child_blob = json.dumps({"host": child_request.host, "body": child_request.body})
    assert SECRET_VALUE not in child_blob

    resp = broker.send(handle, child_request)
    assert resp == {"status": "ok"}

    # The credential DID reach the wire (injection happened in the broker at egress)...
    assert len(transport.sent) == 1
    assert transport.sent[0].headers["Authorization"] == f"Bearer {SECRET_VALUE}"
    # ...but never crossed back to the child: the response carries no value.
    assert SECRET_VALUE not in json.dumps(resp)


# -- Grant gates the lease --------------------------------------------------------


def test_cannot_lease_secret_not_granted() -> None:
    broker = _broker(FakeTransport())
    grant = _grant(secrets=())  # no secrets granted
    with pytest.raises(LeaseDenied, match="not granted"):
        broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), grant)


def test_lease_scoped_to_granted_destination_only() -> None:
    broker = _broker(FakeTransport())
    grant = _grant(egress=("other.example.com",))  # DEST not granted
    with pytest.raises(LeaseDenied, match="may not egress"):
        broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), grant)


def test_send_refuses_destination_outside_lease_scope() -> None:
    transport = FakeTransport()
    broker = _broker(transport)
    handle = broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), _grant())
    # Even with a valid handle, you cannot redirect the credentialed call elsewhere.
    with pytest.raises(LeaseDenied, match="scoped to"):
        broker.send(handle, Outbound(host="evil.example.com"))
    assert transport.sent == []


# -- STATIC-only spine: a fluid value can never name a secret/destination ----------


def test_fluid_secret_ref_is_rejected() -> None:
    broker = _broker(FakeTransport())
    req = SecretRequest(node_id=NODE, ref=REF, destination=DEST, ref_flow=Flow.FLUID)
    with pytest.raises(LeaseDenied, match="STATIC-only"):
        broker.lease(req, _grant())


def test_fluid_destination_is_rejected() -> None:
    broker = _broker(FakeTransport())
    req = SecretRequest(node_id=NODE, ref=REF, destination=DEST, destination_flow=Flow.FLUID)
    with pytest.raises(LeaseDenied, match="STATIC-only"):
        broker.lease(req, _grant())


def test_from_parameters_lifts_fluid_flow() -> None:
    broker = _broker(FakeTransport())
    fluid = Parameter(name="dest", type="str", flow=Flow.FLUID)
    req = SecretRequest.from_parameters(NODE, ref=REF, destination=DEST, destination_param=fluid)
    with pytest.raises(LeaseDenied, match="STATIC-only"):
        broker.lease(req, _grant())


# -- Audit: SECRET_LEASE emission carries the ref, never the value ----------------


def test_secret_lease_audit_emission_carries_ref_not_value() -> None:
    transport = FakeTransport()
    inner = SqliteStore()
    # Wrap in a ScrubbingStore primed with the broker's held values — belt and braces.
    store = ScrubbingStore(inner, secrets=[SECRET_VALUE])
    broker = _broker(transport, store=store, run_id="run-1")
    handle = broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), _grant())
    broker.send(handle, Outbound(host=DEST))

    emissions = read_emissions(inner, "run-1")
    leases = [e for e in emissions if e.kind is EmissionKind.SECRET_LEASE]
    assert len(leases) == 1
    e = leases[0]
    assert e.attrs["ref"] == REF
    assert e.attrs["node_id"] == NODE
    assert e.is_valid()  # required attrs present

    # The value appears NOWHERE in the ledger.
    ledger_blob = json.dumps([ev for ev in inner.events("run-1")])
    assert SECRET_VALUE not in ledger_blob


def test_value_never_in_ledger_via_scrubbing_store() -> None:
    inner = SqliteStore()
    store = ScrubbingStore(inner, secrets=[SECRET_VALUE])
    broker = _broker(FakeTransport(), store=store, run_id="run-2")
    broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), _grant())
    assert SECRET_VALUE not in json.dumps(inner.events("run-2"))


# -- Brokered MCP channel: no secret value in the agent-readable subprocess env -----


class _Conn:
    def __init__(self, name: str, auth: str | None) -> None:
        self.name = name
        self.command = ["mcp-acme"]
        self.url = None
        self.auth = auth


def test_mcp_channel_is_brokered_no_secret_in_subprocess_env() -> None:
    broker = _broker(FakeTransport())
    grant = _grant(secrets=(REF,), egress=(DEST,))
    conns = [_Conn("acme", REF)]
    config, handles = brokered_mcp_config(conns, broker, grant, destination_for={"acme": DEST})

    blob = json.dumps(config)
    # The value is NOT injected into any env the agent can read.
    assert SECRET_VALUE not in blob
    # The reference name is present (so the broker can match it), the value is not.
    server = config["mcpServers"]["acme"]
    assert server["brokered"] is True
    assert server["auth_ref"] == REF
    assert "env" not in server  # no value-bearing env at all
    # A real handle was issued for the orchestrator to broker the call.
    assert "acme" in handles and handles["acme"].ref == REF


def test_brokered_mcp_respects_grant() -> None:
    broker = _broker(FakeTransport())
    grant = _grant(secrets=())  # MCP secret not granted
    with pytest.raises(LeaseDenied):
        brokered_mcp_config([_Conn("acme", REF)], broker, grant, destination_for={"acme": DEST})


# -- Approval queue (detached deploys: ADR 0009 — no stdin) -----------------------


def test_queued_approval_blocks_until_resolved() -> None:
    transport = FakeTransport()
    queue = QueuedApprovalQueue(default=False)  # fail-closed
    broker = _broker(transport, approvals=queue)
    # First attempt: no decision yet -> denied, and enqueued for an operator.
    with pytest.raises(LeaseDenied, match="not approved"):
        broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), _grant())
    pending = queue.pending()
    assert len(pending) == 1
    assert isinstance(pending[0], PendingApproval)

    # Operator approves out-of-band, then the lease succeeds.
    queue.resolve(pending[0].approval_id, approve=True)
    handle = broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), _grant())
    assert handle.ref == REF


def test_auto_approval_is_default() -> None:
    assert AutoApprovalQueue().request(
        PendingApproval(approval_id="a", node_id=NODE, ref=REF, destination=DEST)
    )


def test_unset_secret_value_is_denied_not_leaked() -> None:
    broker = SecretBroker(secret_values={}, transport=FakeTransport())
    with pytest.raises(LeaseDenied, match="not configured"):
        broker.lease(SecretRequest(node_id=NODE, ref=REF, destination=DEST), _grant())
