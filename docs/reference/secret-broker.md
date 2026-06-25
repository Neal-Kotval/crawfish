# Secret broker

How a consequential secret reaches the network without ever reaching the agent or its
prompt. The broker holds credential values in the trusted orchestrator, hands the agent only
an opaque lease, and attaches the real value to an outbound call at the egress boundary.
These live in `crawfish.secrets` alongside the resolution and consent side documented in
[secrets and consent](secrets-and-consent.md).

**Symbols on this page:** `Grant` · `SecretRequest` · `LeaseHandle` · `LeaseDenied` ·
`Outbound` · `EgressTransport` · `PendingApproval` · `ApprovalQueue` ·
`AutoApprovalQueue` · `QueuedApprovalQueue` · `SecretBroker` · `brokered_mcp_config`

A node sometimes needs a *secret*, a credential like a GitHub token, to make a call out to
the network. The danger is that if the agent ever holds that value, a prompt-injected agent
(one tricked by untrusted input into following hidden instructions) can exfiltrate it. The
broker removes the value from the agent's reach entirely.

## The three pieces

- A *grant* (`Grant`) is the user's recorded consent: this package may use these secrets,
  sending them only to these destinations. It is written once at install time (see
  [secrets and consent](secrets-and-consent.md)), and the broker reads it to decide what to
  allow.
- A node asks for a secret with a *secret request* (`SecretRequest`): node `X` needs secret
  `GITHUB_TOKEN`, scoped to host `api.github.com`. It names the secret by *reference* (an
  environment-variable name), never by value.
- If the request is permitted, the broker returns a *lease* (`LeaseHandle`): an opaque token
  the node carries in place of the value. The lease holds the reference and the destination
  so the call can be routed, plus a random id the broker maps back to the held value. A
  refused request raises `LeaseDenied`.

When the node is ready to make its call, it builds an *outbound* request (`Outbound`) with a
host, method, path, headers, and body, and hands it back to the broker with its lease. The
broker, running in the trusted orchestrator, looks up the real value, attaches it to the
request, and sends it through an *egress transport* (`EgressTransport`), the injectable
network seam (*egress* is outbound network traffic). The credentialed request goes to the
wire. The value is never returned to the node.

!!! warning "The lease never carries the value"

    A `LeaseHandle` holds only the reference, the destination, and a random `lease_id` the
    broker maps back to the held value, never the value itself. The handle's `__repr__` omits
    `lease_id` and shows only the reference and destination, so a leaked log line carries no
    usable token. Every request and response shape here is a frozen dataclass, so a child
    cannot widen its own scope after the fact.

## Why the value is unreachable

The v1 secrets design ([secrets and consent](secrets-and-consent.md)) hands a credential
reference to a subprocess the agent controls: the resolver puts the value in the jailed
child's `.env` or its MCP server `env`. A prompt-injected agent in that child can read the
value. [SECURITY.md](../architecture/SECURITY.md) flags this as the v1 gap.

The broker closes it by inverting where injection happens:

- The broker runs in the trusted orchestrator, never the jailed child.
- The child receives only a `LeaseHandle`: an opaque reference, never a value, and never the
  env-var name with its value attached.
- Injection happens at the egress boundary, inside the broker. When the child asks the
  broker to make an outbound call, the broker materialises the value, attaches it to that
  one request, and discards it. The value is alive for one call and is never handed back.

## The lease lifecycle

`SecretBroker.lease` runs five checks in order, and every failure raises `LeaseDenied`.
There is no silent degradation, because the dangerous failure mode is granting a value the
agent should not have:

1. **Static-only.** A `SecretRequest` whose `ref_flow` or `destination_flow` is `Flow.FLUID`
   is rejected. **Fluid** means untrusted, per-item session data, the prompt-injection
   boundary. A fluid value can never name a secret or a destination, so an injected agent
   cannot redirect a credential to its own server.
2. **Granted secret?** The `Grant` must permit `request.ref`.
3. **Granted destination?** The `Grant` must permit egress to `request.destination`.
4. **Value present?** The reference must exist in the broker's value table. An unset ref is a
   misconfiguration, not a leak, but it still denies.
5. **Approved?** The `ApprovalQueue` must permit the lease.

On success the broker records the lease, emits a `SECRET_LEASE` audit emission carrying the
reference (never the value), and returns the handle. `SecretBroker.send` then re-materialises
the value by `lease_id`, refuses any `Outbound` whose `host` differs from the leased
destination, attaches the credential as a `Bearer` token under `Authorization` (or a
caller-named header), and calls the transport. `SecretBroker.revoke` drops a handle so it can
no longer drive egress.

Because the value table lives only in the broker, the ledger never sees a credential. Wire a
[`ScrubbingStore`](secrets-and-consent.md) from `broker.secret_values` and even an accidental
log of a held value is redacted before the Store write.

!!! warning "A fluid value can never name a secret or destination"

    Check one is static-only: a `SecretRequest` whose `ref_flow` or `destination_flow` is
    `Flow.FLUID` is rejected before anything else. Fluid means untrusted, per-item session
    data, the prompt-injection boundary. So an injected agent cannot name a secret it was not
    granted, nor redirect a granted credential to its own server.

## Approval queues and the detached deploy

A local interactive run trusts the operator at the terminal, so `AutoApprovalQueue` approves
every lease without a prompt. A detached deploy has no stdin to prompt on, and blocking the
broker on a console read would hang it. `QueuedApprovalQueue` solves this: `request` enqueues
a `PendingApproval` and returns its configured `default` (`False`, fail-closed) until an
out-of-band approver calls `resolve`.

The queue keys decisions by the `(node_id, ref, destination)` identity, not by
`approval_id`. A lease retry mints a fresh `approval_id` each time, so keying decisions by
identity lets a single human approval survive retries. Once an operator approves that node,
secret, and destination triple, later `request` calls for the same triple return the recorded
decision immediately. `pending()` lists what is still awaiting a decision, the data a console
or API approval UI renders.

## `brokered_mcp_config` versus env injection

The ordinary `build_mcp_config` (in `runtime/mcp.py`) writes each MCP server's secret value
into a subprocess `env` the agent reads, the exact leak the broker closes.
`brokered_mcp_config` instead leases each connection's `auth` reference through the broker
(gated by the `Grant`, static-only, audited) and writes only the reference name (`auth_ref`)
plus a `brokered: True` marker into the config, never the value. It returns the config and a
map of connection name to `LeaseHandle`, so the trusted orchestrator can broker the real call
at egress. Connections are duck-typed (`.name`, `.command`, `.url`, `.auth`) to keep
`secrets.py` a low-level module with no upward dependency on the Definition layer.

## Example

A broker with `AutoApprovalQueue` issues a lease for a granted request, injects the
credential only at egress, denies an ungranted secret, and a `QueuedApprovalQueue` holds
a pending approval for a human. Pure and in-memory: a fake transport, a fake secret table,
no network.

```python
from crawfish.secrets import (
    SecretBroker, SecretRequest, LeaseDenied, Grant,
    AutoApprovalQueue, QueuedApprovalQueue, PendingApproval, Outbound,
)

class RecordingTransport:
    def __init__(self): self.sent = []
    def send(self, request):
        self.sent.append(request)
        return {"status": 200}

# Consent: this package may use GITHUB_TOKEN, egressing only to api.github.com.
grant = Grant(package="triage-bot", secrets=("GITHUB_TOKEN",), egress=("api.github.com",))

transport = RecordingTransport()
broker = SecretBroker(
    secret_values={"GITHUB_TOKEN": "ghp_realsecretvalue"},
    transport=transport,
    approvals=AutoApprovalQueue(),
)

# A granted request -> an opaque LeaseHandle (the value is not inside it).
req = SecretRequest(node_id="poster", ref="GITHUB_TOKEN", destination="api.github.com")
handle = broker.lease(req, grant)
print("handle:", handle)
print("value in handle?", "ghp_" in repr(handle))

# The broker injects the credential only at egress; the child never sees it.
broker.send(handle, Outbound(host="api.github.com", path="/issues"))
sent_auth = transport.sent[0].headers["Authorization"]
print("wire carried credential:", sent_auth == "Bearer ghp_realsecretvalue")

# An ungranted secret is refused -> LeaseDenied (caught).
try:
    broker.lease(SecretRequest(node_id="poster", ref="STRIPE_KEY",
                               destination="api.github.com"), grant)
except LeaseDenied as e:
    print("denied (ungranted secret):", str(e).startswith("node 'poster' was not granted"))

# A queued approval holds the lease for a human; request() returns the deny default.
queue = QueuedApprovalQueue()  # default=False -> fail-closed
p = PendingApproval(approval_id="a1", node_id="poster",
                    ref="GITHUB_TOKEN", destination="api.github.com")
print("queued default decision:", queue.request(p))
print("pending count:", len(queue.pending()))
queue.resolve("a1", approve=True)
print("after resolve:", queue.request(p))
```

??? success "▶ Output"

    ```text
    handle: LeaseHandle(ref='GITHUB_TOKEN', destination='api.github.com')
    value in handle? False
    wire carried credential: True
    denied (ungranted secret): True
    queued default decision: False
    pending count: 1
    after resolve: True
    ```

## API reference

### `Grant`

`@dataclass(frozen=True) class Grant`: a recorded, consented capability grant for an
installed package. The broker reads it to enforce least privilege. (Creating and storing
grants belongs to the consent side; see [secrets and consent](secrets-and-consent.md).)

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `package` | `str` | — (required) | The package the grant covers. |
| `secrets` | `tuple[str, ...]` | `()` | Secret references (env-var names) the user approved. |
| `egress` | `tuple[str, ...]` | `()` | Egress destinations (hosts) the user approved. |
| `granted_at` | `float` | `0.0` | Epoch seconds, set at consent time. |
| `grant_id` | `str` | `new_id()` | Opaque id, defaulted per instance. |

Methods: `permits_secret(ref) -> bool` (True if `ref in secrets`),
`permits_egress(destination) -> bool` (True if `destination in egress`).

### `SecretRequest`

`@dataclass(frozen=True) class SecretRequest`: a node's typed declaration of which secret it
needs and where it may be sent.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `node_id` | `str` | — (required) | The node asking for the lease. |
| `ref` | `str` | — (required) | The secret reference (env-var name), never a value. |
| `destination` | `str` | — (required) | The single egress host this secret may reach. |
| `ref_flow` | `Flow` | `Flow.STATIC` | Provenance of `ref`; `Flow.FLUID` is denied at lease time. |
| `destination_flow` | `Flow` | `Flow.STATIC` | Provenance of `destination`; `Flow.FLUID` is denied at lease time. |

```python
@classmethod
def from_parameters(
    cls,
    node_id: str,
    *,
    ref: str,
    destination: str,
    ref_param: Parameter | None = None,
    destination_param: Parameter | None = None,
) -> SecretRequest
```

Builds a request, lifting `ref_flow`/`destination_flow` off the source
[`Parameter`](core-types.md)s (each defaults to `Flow.STATIC` when its param is `None`).

### `LeaseHandle`

`@dataclass(frozen=True) class LeaseHandle`: the opaque reference a node receives in place of
a secret value. **Never carries the value.**

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `lease_id` | `str` | — (required) | Random id the broker maps back to the held value. |
| `ref` | `str` | — (required) | The leased secret reference. |
| `destination` | `str` | — (required) | The host this lease is scoped to. |
| `node_id` | `str` | — (required) | The node the lease was issued to. |

`__repr__` shows only `ref` and `destination` (not `lease_id`).

### `LeaseDenied`

`class LeaseDenied(RuntimeError)`: raised whenever a lease is refused (not granted, wrong
destination, fluid provenance, unset value, or rejected by the approval queue). Also raised
by `SecretBroker.send` for an unknown or revoked handle, or a host outside the lease scope.

### `Outbound`

`@dataclass(frozen=True) class Outbound`: an outbound request the child wants the broker to
make on its behalf.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `host` | `str` | — (required) | Target host; must match the lease destination. |
| `method` | `str` | `"GET"` | HTTP method. |
| `path` | `str` | `"/"` | Request path. |
| `headers` | `Mapping[str, str]` | `{}` | Caller headers; the broker adds the credential header. |
| `body` | `JSONValue` | `None` | Request body. |

### `EgressTransport`

`@runtime_checkable class EgressTransport(Protocol)`: the injectable network seam.

```python
def send(self, request: Outbound) -> JSONValue: ...
```

The broker calls `send` **after** attaching the credential. Real deployments supply an
httpx/requests-backed transport; tests supply a fake that records what it received.

### `PendingApproval`

`@dataclass(frozen=True) class PendingApproval`: a consequential lease awaiting a human (or
policy) decision.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `approval_id` | `str` | — (required) | Id for the operator-facing queue entry. |
| `node_id` | `str` | — (required) | The requesting node. |
| `ref` | `str` | — (required) | The secret reference awaiting approval. |
| `destination` | `str` | — (required) | The egress host awaiting approval. |

### `ApprovalQueue`

`@runtime_checkable class ApprovalQueue(Protocol)`: the out-of-band approval hook.

```python
def request(self, pending: PendingApproval) -> bool: ...
```

The broker calls `request` before injecting; `True` permits the lease.

### `AutoApprovalQueue`

`class AutoApprovalQueue`: `request` always returns `True`. The default for the local,
interactive trust loop; no prompts.

### `QueuedApprovalQueue`

`class QueuedApprovalQueue`: a stdin-free queue for detached deploys.

```python
def __init__(self, *, default: bool = False) -> None
```

| Method | Signature | Behaviour |
| --- | --- | --- |
| `request` | `(pending: PendingApproval) -> bool` | Returns the recorded decision for the `(node_id, ref, destination)` identity if one exists; else enqueues `pending` and returns `default`. |
| `pending` | `() -> list[PendingApproval]` | Leases currently awaiting a decision. |
| `resolve` | `(approval_id: str, *, approve: bool) -> None` | Records an out-of-band decision (by the pending entry's identity). |

`default` is `False` (fail-closed), so an unresolved lease is denied.

### `SecretBroker`

`class SecretBroker`: holds secret values out-of-band; injects them only at egress.

```python
def __init__(
    self,
    *,
    secret_values: Mapping[str, str],
    transport: EgressTransport,
    store: Store | None = None,
    approvals: ApprovalQueue | None = None,
    run_id: str = "broker",
    org_id: str = "local",
) -> None
```

`approvals` defaults to `AutoApprovalQueue()`. If `store` is set, each lease emits a
`SECRET_LEASE` audit emission carrying the reference, never the value.

| Method | Signature | Behaviour |
| --- | --- | --- |
| `lease` | `(request: SecretRequest, grant: Grant) -> LeaseHandle` | Runs the five-check gate (static-only → granted secret → granted destination → value present → approved); records the lease and returns a handle, or raises `LeaseDenied`. |
| `send` | `(handle: LeaseHandle, request: Outbound, *, header: str \| None = None) -> JSONValue` | Re-materialises the value, refuses a host ≠ leased destination, attaches it as `Bearer` under `header` (default `Authorization`), and calls the transport. Returns the transport response; never the credential. |
| `revoke` | `(handle: LeaseHandle) -> None` | Invalidates a handle so it can no longer drive egress. |
| `secret_values` | property `-> list[str]` | All held values (for wiring a `ScrubbingStore`). Never logged. |

### `brokered_mcp_config`

```python
def brokered_mcp_config(
    connections: Iterable[_MCPConnLike],
    broker: SecretBroker,
    grant: Grant,
    *,
    destination_for: Mapping[str, str] | None = None,
) -> tuple[dict[str, object], dict[str, LeaseHandle]]
```

Builds an MCP server config whose credential channel is brokered, not env-injected. For
each connection with an `auth` reference, it leases that secret through `broker` (gated by
`grant`) and writes only `auth_ref` + `brokered: True` into the server entry, never the
value. `destination_for` maps a connection name to its egress host (defaults to the
connection name). Returns `({"mcpServers": {...}}, {name: LeaseHandle})`. Connection items
are duck-typed on `.name`, `.command`, `.url`, `.auth`.

## See also

- [Secrets and consent](secrets-and-consent.md): where a `Grant` comes from, plus
  declaration, scrubbing, and the install-time consent gate.
- [Sandbox and jail](sandbox-and-jail.md): the jailed child the broker keeps the value away
  from, and host-side egress control.
- [Core types](core-types.md): `Flow`, the static-versus-fluid distinction the lease gate
  rests on.
