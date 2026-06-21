"""Secrets v1 + hardening.

Credentials are held **by reference** (an env-var name), never by value: a node
receives only the secrets it declares (least privilege — the embryonic capability
manifest), the value never reaches stored config, an Output, logs, or the prompt.
Transcripts/telemetry are **scrubbed before the Store write** (:class:`ScrubbingStore`).
A package's declared capabilities are surfaced at install time for consent.

Known v1 tradeoff (see SECURITY.md): a local CommandRuntime can read ``.env`` in its
sandbox; closed later by egress-mediated injection. Out-of-process host-side execution
+ taint propagation are the runtime half of this hardening.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from crawfish.core.ids import new_id
from crawfish.core.types import Flow, JSONValue
from crawfish.store.base import Store

if TYPE_CHECKING:
    from crawfish.core.types import Parameter

__all__ = [
    "resolve_secret",
    "load_env",
    "SecretManager",
    "redact",
    "redact_obj",
    "ScrubbingStore",
    "read_capabilities",
    "Capabilities",
    "Grant",
    # CRA-178 — secret schema + sidecar broker (egress-mediated injection)
    "SecretRequest",
    "LeaseHandle",
    "LeaseDenied",
    "Outbound",
    "EgressTransport",
    "PendingApproval",
    "ApprovalQueue",
    "AutoApprovalQueue",
    "QueuedApprovalQueue",
    "SecretBroker",
    "brokered_mcp_config",
]

# Heuristic patterns for common credentials/PII, scrubbed even if not in the env map.
_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{12,}"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # email (PII)
]
_REDACTED = "***REDACTED***"


def resolve_secret(ref: str | None, env: Mapping[str, str] | None = None) -> str | None:
    """Resolve a secret reference (env-var name) to its value, or None if unset."""
    if not ref:
        return None
    if env is not None:
        return env.get(ref)
    import os

    return os.environ.get(ref)


def load_env(path: str | Path = ".env") -> dict[str, str]:
    """Parse a gitignored ``.env`` (KEY=VALUE lines). Values are never logged."""
    p = Path(path)
    if not p.exists():
        return {}
    env: dict[str, str] = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


class SecretManager:
    """Maps nodes to the secrets they declare and resolves them least-privilege."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env) if env is not None else load_env()
        self._declared: dict[str, set[str]] = {}

    def declare(self, node_id: str, refs: Iterable[str]) -> None:
        self._declared.setdefault(node_id, set()).update(r for r in refs if r)

    def for_node(self, node_id: str) -> dict[str, str]:
        """Return only the secrets this node declared (and that exist)."""
        return {
            ref: self._env[ref] for ref in self._declared.get(node_id, set()) if ref in self._env
        }

    @property
    def values(self) -> list[str]:
        """All known secret values (for scrubbing)."""
        return [v for v in self._env.values() if v]


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Replace known secret values and credential/PII patterns with a marker."""
    out = text
    for s in secrets:
        if s:
            out = out.replace(s, _REDACTED)
    for pat in _PATTERNS:
        out = pat.sub(_REDACTED, out)
    return out


def redact_obj(obj: JSONValue, secrets: Iterable[str] = ()) -> JSONValue:
    """Recursively redact strings inside a JSON-serializable structure."""
    secrets = list(secrets)
    if isinstance(obj, str):
        return redact(obj, secrets)
    if isinstance(obj, dict):
        return {k: redact_obj(v, secrets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v, secrets) for v in obj]
    return obj


class ScrubbingStore:
    """A ``Store`` wrapper that redacts secrets/PII before any write.

    Wrap a backing Store so transcripts, outputs, and telemetry are redacted on the
    way in — the persisted ledger never contains a raw credential.
    """

    def __init__(self, inner: Store, secrets: Iterable[str] = ()) -> None:
        self._inner = inner
        self._secrets = list(secrets)

    def _redact_dict(self, data: dict[str, JSONValue]) -> dict[str, JSONValue]:
        return {k: redact_obj(v, self._secrets) for k, v in data.items()}

    def put_record(
        self, kind: str, id: str, data: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None:
        self._inner.put_record(kind, id, self._redact_dict(data), org_id=org_id)

    def get_record(
        self, kind: str, id: str, *, org_id: str = "local"
    ) -> dict[str, JSONValue] | None:
        return self._inner.get_record(kind, id, org_id=org_id)

    def list_records(self, kind: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]:
        return self._inner.list_records(kind, org_id=org_id)

    def delete_record(self, kind: str, id: str, *, org_id: str = "local") -> None:
        self._inner.delete_record(kind, id, org_id=org_id)

    def kv_get(self, namespace: str, key: str, *, org_id: str = "local") -> JSONValue | None:
        return self._inner.kv_get(namespace, key, org_id=org_id)

    def kv_set(self, namespace: str, key: str, value: JSONValue, *, org_id: str = "local") -> None:
        self._inner.kv_set(namespace, key, redact_obj(value, self._secrets), org_id=org_id)

    def claim_idempotency(self, key: str, *, org_id: str = "local") -> bool:
        return self._inner.claim_idempotency(key, org_id=org_id)

    def append_event(
        self, run_id: str, event: dict[str, JSONValue], *, org_id: str = "local"
    ) -> None:
        self._inner.append_event(run_id, self._redact_dict(event), org_id=org_id)

    def events(self, run_id: str, *, org_id: str = "local") -> list[dict[str, JSONValue]]:
        return self._inner.events(run_id, org_id=org_id)

    def close(self) -> None:
        self._inner.close()


class Capabilities:
    """What a package/unit declares it needs (the consent surface)."""

    def __init__(
        self, *, secrets: list[str] | None = None, egress: list[str] | None = None
    ) -> None:
        self.secrets = secrets or []
        self.egress = egress or []

    def summary(self) -> str:
        parts = []
        if self.secrets:
            parts.append(f"secrets: {', '.join(self.secrets)}")
        if self.egress:
            parts.append(f"network egress: {', '.join(self.egress)}")
        return "; ".join(parts) if parts else "no special capabilities"


@dataclass(frozen=True)
class Grant:
    """A recorded, consented capability grant for an installed package.

    The persisted record that an install-time consent (CRA-180) produces: which
    secrets and egress destinations the user approved for ``package``. The broker
    (CRA-178) and the jail (CRA-179) consume this shape to enforce least privilege;
    CRA-180 owns the grant *manifest* (creation/storage). Frozen + content-stable.
    """

    package: str
    secrets: tuple[str, ...] = ()
    egress: tuple[str, ...] = ()
    granted_at: float = 0.0  # epoch seconds; set at consent time
    grant_id: str = field(default_factory=new_id)

    def permits_secret(self, ref: str) -> bool:
        """True if this grant covers secret reference ``ref``."""
        return ref in self.secrets

    def permits_egress(self, destination: str) -> bool:
        """True if this grant covers network egress to ``destination``."""
        return destination in self.egress


def read_capabilities(project_dir: str | Path) -> Capabilities:
    """Read a package's declared capabilities from ``crawfish.toml [capabilities]``."""
    path = Path(project_dir) / "crawfish.toml"
    if not path.exists():
        return Capabilities()
    data = tomllib.loads(path.read_text()).get("capabilities", {})
    return Capabilities(secrets=list(data.get("secrets", [])), egress=list(data.get("egress", [])))


# ---------------------------------------------------------------------------
# CRA-178 — secret schema + sidecar broker (egress-mediated injection)
#
# Threat closed (SECURITY.md v1 gap): secrets today are env-var REFERENCES that the
# resolver hands to a subprocess the agent controls (``.env`` in the jail,
# ``build_mcp_config`` env). A prompt-injected agent can therefore read the credential
# VALUE. This broker makes the value structurally unreachable by the agent/jailed child:
#
#   * The broker runs in the TRUSTED orchestrator (never the jailed child).
#   * The child receives only a :class:`LeaseHandle` (an opaque reference) — never a
#     value, and never the env-var name with its value attached.
#   * Injection happens at the EGRESS boundary, inside the broker: when a declared,
#     consented egress call is made, the broker attaches the credential to the outbound
#     request via an injectable :class:`EgressTransport`. The value is materialized for
#     the duration of one outbound call and is never returned to the child.
#
# Every lease is gated by a :class:`Grant` (CRA-184 — the consented capabilities) and
# audited via an ``EmissionKind.SECRET_LEASE`` emission carrying the REFERENCE, never
# the value. The ledger (``ScrubbingStore``) never contains a raw credential.
# ---------------------------------------------------------------------------


class LeaseDenied(RuntimeError):
    """A secret lease was refused: not granted, wrong destination, fluid, or rejected.

    A leak-equivalent failure mode is *granting* a value the agent shouldn't have, so
    every denial path raises this rather than silently degrading.
    """


@dataclass(frozen=True)
class SecretRequest:
    """A typed declaration of which secret a node needs and where it may be sent.

    The **schema** half of CRA-178: a node declares, by reference, the secret it needs
    (``ref`` — an env-var name, never a value) scoped to a single egress ``destination``
    (a host). Both are STATIC-only (the prompt-injection spine): a FLUID value can never
    name a secret or a destination. Pass :class:`~crawfish.core.types.Parameter`-like
    flows via :meth:`from_parameters` to have the broker enforce that at lease time.
    """

    node_id: str
    ref: str
    destination: str
    # Provenance of ``ref``/``destination`` — STATIC unless derived from a fluid input.
    # A FLUID provenance is rejected at lease time (a fluid value can never name a
    # secret or a destination — SECURITY.md).
    ref_flow: Flow = Flow.STATIC
    destination_flow: Flow = Flow.STATIC

    @classmethod
    def from_parameters(
        cls,
        node_id: str,
        *,
        ref: str,
        destination: str,
        ref_param: Parameter | None = None,
        destination_param: Parameter | None = None,
    ) -> SecretRequest:
        """Build a request, lifting STATIC/FLUID provenance off the source Parameters."""
        return cls(
            node_id=node_id,
            ref=ref,
            destination=destination,
            ref_flow=ref_param.flow if ref_param is not None else Flow.STATIC,
            destination_flow=(
                destination_param.flow if destination_param is not None else Flow.STATIC
            ),
        )


@dataclass(frozen=True)
class LeaseHandle:
    """The opaque reference a node/jailed child receives in place of a secret value.

    Carries the REFERENCE and the scoped destination so the child can route an outbound
    call, plus a random ``lease_id`` the broker maps back to the held value. **It never
    carries the value.** Frozen so a child can't tamper with its scope.
    """

    lease_id: str
    ref: str
    destination: str
    node_id: str

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"LeaseHandle(ref={self.ref!r}, destination={self.destination!r})"


@dataclass(frozen=True)
class Outbound:
    """An outbound request the child wants the broker to make on its behalf.

    The child builds this with a :class:`LeaseHandle` (not a value); the broker injects
    the credential into ``headers``/``env`` at egress and hands it to the transport. The
    child never sees the resulting credentialed request.
    """

    host: str
    method: str = "GET"
    path: str = "/"
    headers: Mapping[str, str] = field(default_factory=dict)
    body: JSONValue = None


@runtime_checkable
class EgressTransport(Protocol):
    """The injectable network seam. The broker calls this AFTER attaching credentials.

    Real deployments supply an httpx/requests-backed transport; tests supply a fake that
    records what it received (so a test can assert the credential reached the wire but
    never reached the child). Determinism: tests inject a fake — no real network.
    """

    def send(self, request: Outbound) -> JSONValue: ...


@dataclass(frozen=True)
class PendingApproval:
    """A consequential lease/egress awaiting human (or policy) approval.

    Detached deploys (ADR 0009) have no stdin to prompt on; the broker enqueues this
    instead and blocks the lease until an out-of-band approver resolves it.
    """

    approval_id: str
    node_id: str
    ref: str
    destination: str


@runtime_checkable
class ApprovalQueue(Protocol):
    """Out-of-band approval hook for consequential leases (the detached-deploy answer).

    ``request`` is called by the broker before injecting; it returns ``True`` to permit.
    A stdin-free queue implementation lets an operator approve via the console/API.
    """

    def request(self, pending: PendingApproval) -> bool: ...


class AutoApprovalQueue:
    """Default: auto-approve every lease (local/interactive trust loop). No prompts."""

    def request(self, pending: PendingApproval) -> bool:  # noqa: D102
        return True


class QueuedApprovalQueue:
    """A stdin-free approval queue for detached deploys (ADR 0009).

    The broker enqueues a :class:`PendingApproval`; an out-of-band approver calls
    :meth:`resolve`. Until resolved, :meth:`request` returns the configured default
    (``deny`` by default — fail-closed). This is the hook a console/API approval UI
    drives; the broker never blocks on stdin.
    """

    def __init__(self, *, default: bool = False) -> None:
        self._default = default
        # Keyed by approval_id for the operator-facing queue...
        self._pending: dict[str, PendingApproval] = {}
        # ...but decisions are keyed by the (node, ref, destination) identity so a
        # decision survives a lease retry (each retry mints a fresh approval_id).
        self._decisions: dict[tuple[str, str, str], bool] = {}

    @staticmethod
    def _identity(p: PendingApproval) -> tuple[str, str, str]:
        return (p.node_id, p.ref, p.destination)

    def request(self, pending: PendingApproval) -> bool:  # noqa: D102
        decision = self._decisions.get(self._identity(pending))
        if decision is not None:
            return decision
        self._pending[pending.approval_id] = pending
        return self._default

    def pending(self) -> list[PendingApproval]:
        """Leases currently awaiting an out-of-band decision."""
        return list(self._pending.values())

    def resolve(self, approval_id: str, *, approve: bool) -> None:
        """Record an out-of-band decision for a queued approval (by its identity)."""
        pending = self._pending.pop(approval_id, None)
        if pending is not None:
            self._decisions[self._identity(pending)] = approve


class SecretBroker:
    """Holds secret VALUES out-of-band; injects them only at the egress boundary.

    Lives in the trusted orchestrator. A node calls :meth:`lease` to exchange a
    :class:`SecretRequest` (matched against its :class:`Grant`) for a :class:`LeaseHandle`
    — an opaque reference, never a value. The node hands the handle back via
    :meth:`send`, and the broker attaches the credential to the outbound request and
    calls the injected :class:`EgressTransport`. **The value never crosses to the child.**

    Determinism: the value source is an injected mapping (a fake secret store in tests);
    the transport is injected; no clock is read unless the caller stamps ``ts``.
    """

    def __init__(
        self,
        *,
        secret_values: Mapping[str, str],
        transport: EgressTransport,
        store: Store | None = None,
        approvals: ApprovalQueue | None = None,
        run_id: str = "broker",
        org_id: str = "local",
    ) -> None:
        # The out-of-band value table. Held only here, in the trusted orchestrator.
        self._values = dict(secret_values)
        self._transport = transport
        self._store = store
        self._approvals = approvals or AutoApprovalQueue()
        self._run_id = run_id
        self._org_id = org_id
        # lease_id -> (ref, destination) so we can re-materialize at egress without ever
        # handing the value back to the child.
        self._leases: dict[str, tuple[str, str]] = {}

    @property
    def secret_values(self) -> list[str]:
        """All held values (for wiring a :class:`ScrubbingStore`). Never logged."""
        return [v for v in self._values.values() if v]

    def lease(self, request: SecretRequest, grant: Grant) -> LeaseHandle:
        """Exchange a :class:`SecretRequest` for an opaque :class:`LeaseHandle`.

        Enforces, in order (all denials raise :class:`LeaseDenied`):
          1. STATIC-only — a FLUID ref or destination can never name a secret/target.
          2. The :class:`Grant` permits the secret ``ref``.
          3. The :class:`Grant` permits egress to ``destination``.
          4. The value actually exists (an unset ref is a misconfiguration, not a leak).
          5. The approval queue permits the (consequential) lease.

        On success: records the lease, emits a ``SECRET_LEASE`` audit emission carrying
        the REFERENCE (never the value), and returns a handle. The value stays in the
        broker; it is *never* returned, env-injected, or prompted.
        """
        # 1. Static-only spine: a fluid value can never name a secret or a destination.
        if request.ref_flow is Flow.FLUID:
            raise LeaseDenied(
                f"secret ref {request.ref!r} is FLUID; secret references are STATIC-only "
                "(a fluid/untrusted value can never name a secret — SECURITY.md)"
            )
        if request.destination_flow is Flow.FLUID:
            raise LeaseDenied(
                f"egress destination {request.destination!r} is FLUID; destinations are "
                "STATIC-only (a fluid value can never name an egress target — SECURITY.md)"
            )
        # 2. Granted secret?
        if not grant.permits_secret(request.ref):
            raise LeaseDenied(
                f"node {request.node_id!r} was not granted secret {request.ref!r} "
                f"(grant {grant.grant_id} covers {list(grant.secrets)})"
            )
        # 3. Granted destination?
        if not grant.permits_egress(request.destination):
            raise LeaseDenied(
                f"node {request.node_id!r} may not egress to {request.destination!r} "
                f"(grant {grant.grant_id} covers {list(grant.egress)})"
            )
        # 4. Value present?
        if request.ref not in self._values:
            raise LeaseDenied(f"secret {request.ref!r} is not configured in the broker value store")
        # 5. Out-of-band approval (detached deploys: queue, never stdin).
        pending = PendingApproval(
            approval_id=new_id(),
            node_id=request.node_id,
            ref=request.ref,
            destination=request.destination,
        )
        if not self._approvals.request(pending):
            raise LeaseDenied(
                f"lease of {request.ref!r} for {request.destination!r} was not approved"
            )

        handle = LeaseHandle(
            lease_id=new_id(),
            ref=request.ref,
            destination=request.destination,
            node_id=request.node_id,
        )
        self._leases[handle.lease_id] = (request.ref, request.destination)
        self._audit_lease(handle)
        return handle

    def send(
        self, handle: LeaseHandle, request: Outbound, *, header: str | None = None
    ) -> JSONValue:
        """Make a credentialed outbound call on the child's behalf — value never returned.

        Re-materializes the value from the held table (keyed by ``lease_id``), attaches
        it to the outbound request (an ``Authorization``/``header`` field), enforces that
        the call goes only to the leased ``destination``, and hands the credentialed
        request to the injected transport. The transport's response is returned to the
        child; the credential is not.
        """
        scope = self._leases.get(handle.lease_id)
        if scope is None:
            raise LeaseDenied("unknown or revoked lease handle")
        ref, destination = scope
        if request.host != destination:
            raise LeaseDenied(
                f"lease is scoped to {destination!r}; refusing egress to {request.host!r}"
            )
        value = self._values[ref]
        # Injection happens HERE, in the trusted broker, at the egress boundary.
        injected_headers = dict(request.headers)
        injected_headers[header or "Authorization"] = f"Bearer {value}"
        credentialed = Outbound(
            host=request.host,
            method=request.method,
            path=request.path,
            headers=injected_headers,
            body=request.body,
        )
        return self._transport.send(credentialed)

    def revoke(self, handle: LeaseHandle) -> None:
        """Invalidate a lease handle so it can no longer drive egress."""
        self._leases.pop(handle.lease_id, None)

    def _audit_lease(self, handle: LeaseHandle) -> None:
        """Emit a ``SECRET_LEASE`` emission carrying the REFERENCE, never the value."""
        if self._store is None:
            return
        # Imported lazily to avoid an import cycle (emission has no secrets dep, but
        # secrets is the lower-level module).
        from crawfish.emission import Emission, EmissionKind, emit

        e = Emission(
            kind=EmissionKind.SECRET_LEASE,
            run_id=self._run_id,
            org_id=self._org_id,
            node_id=handle.node_id,
            attrs={
                "ref": handle.ref,  # the REFERENCE — never the value
                "node_id": handle.node_id,
                "destination": handle.destination,
            },
        )
        emit(self._store, e, org_id=self._org_id)


@runtime_checkable
class _MCPConnLike(Protocol):
    """The duck-typed shape ``brokered_mcp_config`` reads off an MCP connection.

    Declared here (rather than importing the Definition type) so ``secrets.py`` stays a
    low-level module with no upward dependency on the Definition layer.
    """

    name: str
    command: list[str] | None
    url: str | None
    auth: str | None


def brokered_mcp_config(
    connections: Iterable[_MCPConnLike],
    broker: SecretBroker,
    grant: Grant,
    *,
    destination_for: Mapping[str, str] | None = None,
) -> tuple[dict[str, object], dict[str, LeaseHandle]]:
    """Build an MCP config whose credential channel is BROKERED, not env-injected.

    ``build_mcp_config`` (runtime/mcp.py) injects each server's secret VALUE into a
    subprocess ``env`` the agent reads — the exact leak this issue closes. This builder
    instead leases each connection's secret through the broker (gated by ``grant``,
    STATIC-only, audited) and writes only the resulting reference name into the config,
    NEVER the value. The returned handle map lets the trusted orchestrator broker the
    real call at egress.

    ``connections`` items are duck-typed (``.name``, ``.command``, ``.url``, ``.auth``)
    to avoid importing the Definition types here. ``destination_for`` maps a connection
    name to its egress host (defaults to the connection name).
    """
    destination_for = destination_for or {}
    servers: dict[str, object] = {}
    handles: dict[str, LeaseHandle] = {}
    for conn in connections:
        name = conn.name
        command = conn.command
        url = conn.url
        auth = conn.auth
        server: dict[str, object] = {}
        if command:
            server["command"] = command[0]
            server["args"] = list(command[1:])
        if url:
            server["url"] = url
        if auth:
            destination = destination_for.get(name, name)
            handle = broker.lease(
                SecretRequest(node_id=name, ref=auth, destination=destination),
                grant,
            )
            handles[name] = handle
            # Only the REFERENCE name lands in the config the agent can read — never the
            # value. The credential is attached by the broker at egress instead.
            server["auth_ref"] = auth
            server["brokered"] = True
        servers[name] = server
    return {"mcpServers": servers}, handles
