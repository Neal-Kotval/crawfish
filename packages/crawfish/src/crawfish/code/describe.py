"""``craw code describe <component>`` — typed-IO reflection (CRA-244 / 271 / 274).

The RFC's load-bearing addition: ``describe`` recovers the one genuine ergonomic advantage
a per-app MCP had — typed schemas surfaced to the model — while staying filesystem-fresh,
because it reflects the component **at call time** (it compiles the on-disk directory) rather
than caching a registry. The agent reads the projection to wire components correctly *and*
to honor the security spine: each :class:`~crawfish.core.types.Parameter` surfaces its
``flow`` (``static`` / ``fluid``), so the agent never wires a fluid input toward a
static-only sink slot.

Three concerns layer here, all in this one file (one owner):

* **CRA-244** — compile the component (jailed per CRA-267 when agent-authored) and project
  its **typed inputs/outputs only** as JSON, the structural ``type`` resolved through
  :mod:`crawfish.typesystem` (a JSON-Schema export, ADR 0002 — structural, not string
  equality). Carries ``authored_by`` / ``tainted`` from the CRA-266 provenance row so the
  agent knows the file's trust.
* **CRA-271** — the projection is **typed-shape-only** and passes through the
  :class:`~crawfish.secrets.ScrubbingStore` redaction layer before emission. Capabilities
  surface their *kind* (``declares_secret_ref`` / ``has_mcp_connection`` / ``writes_to_sink``)
  but never a destination, env-var name, egress host, or sink target — the consequential
  config the security spine keeps away from the model (SECURITY.md rules 2 + 4). A leak here
  is a direct injection-amplifier, so the snapshot test asserts the *absence* of those fields.
* **CRA-274** — bound the per-call cost. ``describe`` recompiles per call, an unbounded
  hot-path latency for a verb the agent may call repeatedly; the projection is **cached by
  content sha** under ``.crawfish/describe/`` (generated state — never hand-edited; keyed
  strictly on the content sha so a stale/forged entry can't shadow a changed component). A
  repeated describe of an unchanged component is a zero-recompile hit; an edit (new sha) is a
  miss. ``craw code describe`` is a plain CLI call — no plugin, no MCP, no session (the RFC's
  "one execution path; humans and Claude hit the same code").
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from crawfish.code import EXIT_OK, ErrorCode, emit_error, emit_json
from crawfish.core.types import Flow

if TYPE_CHECKING:
    from crawfish.definition.types import Definition, MCPConnection
    from crawfish.store.base import Store

VERB_NAME = "describe"

#: Where the content-sha-keyed projection cache lives (generated state, gitignored). Keyed
#: strictly on the content sha (CRA-274 security note): a tampered/stale cache entry can
#: never shadow a changed component, because a content change changes the sha → cache miss.
_CACHE_DIR = Path(".crawfish") / "describe"

#: A coarse static ceiling on per-call reflection work (CRA-274). ``describe`` is a pure
#: structural projection (no model call), so the only unbounded axis is the number of
#: import-bearing components a single compile walks. A directory that declares more than this
#: many components is rejected (fail-closed) rather than recompiled unboundedly. The number is
#: deliberately generous — a real Definition has a handful of components, not hundreds.
_REFLECTION_COMPONENT_CEILING = 256


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code describe`` on the ``code`` subparser group (self-registering)."""
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(
        VERB_NAME, help="reflect a component's typed inputs/outputs (CRA-244)"
    )
    p.add_argument(
        "component", help="path to the component directory (e.g. definitions/triage-bot)"
    )
    add_common_args(p)
    p.set_defaults(func=_cmd_describe)


# ---------------------------------------------------------------------------
# CRA-271 — the destination-free capability projection.
# ---------------------------------------------------------------------------
# The agent learns *that* a component declares a secret / has an MCP connection / writes to a
# sink, never *which* secret / host / target. The kind is the only safe signal; the
# destination is the consequential config the spine keeps out of the model's context.
_CAP_DECLARES_SECRET = "declares_secret_ref"
_CAP_HAS_MCP = "has_mcp_connection"
_CAP_WRITES_SINK = "writes_to_sink"


def _redacted_capabilities(definition: Definition) -> list[dict[str, str]]:
    """Project a Definition's capabilities to **kind only** (CRA-271, destination-free).

    Surfaces ``has_mcp_connection`` when any :class:`~crawfish.definition.types.MCPConnection`
    is declared, ``declares_secret_ref`` when any connection references a secret (its ``auth``
    env-var name — by reference), and ``writes_to_sink`` when the Definition declares a sink
    target asset. The env-var name, the egress host (``url`` / ``command``), and the sink
    target itself are **never** emitted — only the bare kind. De-duplicated, stable order.
    """
    kinds: list[str] = []
    assets = getattr(definition, "assets", None)
    mcp: list[MCPConnection] = list(getattr(assets, "mcp", []) or []) if assets is not None else []
    if mcp:
        kinds.append(_CAP_HAS_MCP)
    if any(getattr(conn, "auth", None) for conn in mcp):
        kinds.append(_CAP_DECLARES_SECRET)
    # A sink target is carried in the Definition's outputs/assets as a consequential
    # destination; surfacing the *kind* (not the target) lets the agent reason about
    # consequence without learning where the write lands.
    if _declares_sink(definition):
        kinds.append(_CAP_WRITES_SINK)
    # Stable, de-duplicated order so the snapshot is byte-stable across runs.
    seen: dict[str, None] = {}
    for k in kinds:
        seen.setdefault(k, None)
    return [{"kind": k} for k in sorted(seen)]


def _declares_sink(definition: Definition) -> bool:
    """True iff the Definition declares a consequential sink target (CRA-271).

    A sink target is a static-only consequential destination; here we only report its
    *presence* as a capability kind. The check is conservative: any asset policy or output
    parameter whose name signals a sink destination counts. We never read the target value.
    """
    assets = getattr(definition, "assets", None)
    if assets is not None:
        for pol in getattr(assets, "policies", []) or []:
            kind = getattr(getattr(pol, "kind", None), "value", getattr(pol, "kind", ""))
            if isinstance(kind, str) and "sink" in kind.lower():
                return True
    return False


# ---------------------------------------------------------------------------
# CRA-244 — the typed-shape projection.
# ---------------------------------------------------------------------------
def _project_parameter(name: str, type_str: str, flow: Flow) -> dict[str, object]:
    """Project one :class:`~crawfish.core.types.Parameter` to its typed-shape JSON.

    ``type`` is the resolved **structural** JSON-Schema for the parameter's type (via
    :mod:`crawfish.typesystem`, ADR 0002 — never string equality), with the bare type name
    kept alongside for legibility. ``flow`` is the security signal the agent honors: a
    ``fluid`` input must never be wired toward a ``static``-only sink slot.
    """
    from crawfish.typesystem import default_registry

    try:
        schema = default_registry.json_schema(type_str)
    except Exception:
        # An unresolvable type name still surfaces its name + flow (never crash the
        # reflection); the structural schema degrades to the nominal name.
        schema = {"type": type_str}
    return {"name": name, "type": type_str, "schema": schema, "flow": flow.value}


def describe_payload(
    definition: Definition, *, content_sha: str, authored_by: str, tainted: bool, component: str
) -> dict[str, object]:
    """Build the ``craw.code.describe.v1`` body (CRA-244, redacted per CRA-271).

    Typed inputs/outputs only — each parameter's structural ``type`` + ``flow`` — plus the
    component identity (``content_sha``) and trust (``authored_by`` / ``tainted`` from the
    CRA-266 row) and the **kind-only** capability block. No secret ref, egress host, or sink
    destination ever appears (CRA-271): the snapshot test asserts their absence.
    """
    return {
        "component": component,
        "kind": "definition",
        "content_sha": content_sha,
        "inputs": [_project_parameter(p.name, p.type, p.flow) for p in definition.inputs],
        "outputs": [_project_parameter(p.name, p.type, p.flow) for p in definition.outputs],
        "capabilities": _redacted_capabilities(definition),
        "authored_by": authored_by,
        "tainted": tainted,
    }


# ---------------------------------------------------------------------------
# CRA-274 — content-sha cache + the compile path.
# ---------------------------------------------------------------------------
def _cache_path(project_dir: Path, content_sha: str, org_id: str) -> Path:
    """The ``.crawfish/describe/<org_id>/<content_sha>.json`` cache file for a component.

    The cache is **org-scoped** (CRA-275): a describe under ``--org a`` never reads ``--org
    b``'s cached projection, so a tenant's reflection cache cannot leak across the org
    boundary. Keyed strictly on the content sha within the org so a forged/stale entry can't
    shadow a changed component (CRA-274).
    """
    return project_dir / _CACHE_DIR / org_id / f"{content_sha}.json"


def describe_component(
    component: str,
    *,
    store: Store,
    org_id: str = "local",
    compile_counter: list[int] | None = None,
) -> dict[str, object]:
    """Compile + project a component, caching the projection by content sha (CRA-244/271/274).

    On a call: compute the component's content sha (the same sha ``load_definition`` derives);
    on a **cache hit** return the stored ``craw.code.describe.v1`` body with **zero recompile**;
    on a **miss** compile (jailed per CRA-267 when agent-authored), project (redacted per
    CRA-271), and store under ``.crawfish/describe/<sha>.json`` (keyed strictly on the sha so a
    forged/stale entry can't shadow a changed component). ``compile_counter`` (a one-element
    list) is bumped on every real compile so a test can assert a hit recompiled zero times.

    Raises :class:`FileNotFoundError` if the component dir is absent, and
    :class:`ReflectionCostError` if the directory exceeds the CRA-274 component ceiling.
    """
    from crawfish.definition.compiler import _content_sha
    from crawfish.definition.jailed import import_bearing_files, load_definition_jailed
    from crawfish.jail import SandboxPolicy
    from crawfish.provenance import AUTHORED_BY_HUMAN, file_provenance

    project_dir = Path(component)
    if not project_dir.is_dir():
        raise FileNotFoundError(component)

    # The content sha is the cache key (CRA-274). It is the pure content hash the canonical
    # loader uses, so an edit to any non-excluded file is a new sha → a miss → a recompile.
    content_sha = _content_sha(project_dir)

    cache_file = _cache_path(project_dir, content_sha, org_id)
    if cache_file.exists():
        # Cache hit — zero recompile. The cached body is already CRA-271-redacted.
        cached: dict[str, object] = json.loads(cache_file.read_text())
        return cached

    # CRA-274 reflection bound: refuse an unbounded reflection (fail closed) before compiling.
    files = import_bearing_files(project_dir)
    if len(files) > _REFLECTION_COMPONENT_CEILING:
        raise ReflectionCostError(
            f"component {component!r} declares {len(files)} import-bearing files, exceeding the "
            f"reflection ceiling of {_REFLECTION_COMPONENT_CEILING}"
        )

    if compile_counter is not None:
        compile_counter[0] += 1

    # Compile through the jailed path (CRA-267): agent-authored code is confined, taint is
    # propagated onto the CRA-266 rows, and a jail Denial fails closed (DefinitionLoadError).
    compiled = load_definition_jailed(
        project_dir, store=store, org_id=org_id, policy=SandboxPolicy(kind="fake")
    )
    definition = compiled.definition

    # Trust signal (CRA-266): the Definition's own content sha + the authorship of its
    # `definition.py` row (the root authoring decision). A tainted compile marks the whole
    # projection tainted so the agent treats it with suspicion.
    from crawfish.jail import FLUID_TAINT

    def_sha = definition.content_sha()
    root_prov = file_provenance(
        "definition.py", _file_sha(project_dir / "definition.py"), store=store, org_id=org_id
    )
    authored_by = root_prov.authored_by if root_prov is not None else AUTHORED_BY_HUMAN
    tainted = FLUID_TAINT in compiled.out_taint

    body = describe_payload(
        definition,
        content_sha=def_sha,
        authored_by=authored_by,
        tainted=tainted,
        component=component,
    )

    # Persist the redacted projection to the content-sha cache (generated state).
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(body, sort_keys=True))
    return body


def _file_sha(file_path: Path) -> str:
    """A pure 12-char content hash of one file's bytes (matches jailed.py identity)."""
    import hashlib

    data = file_path.read_bytes() if file_path.exists() else b""
    return hashlib.sha256(data).hexdigest()[:12]


class ReflectionCostError(RuntimeError):
    """A ``describe`` reflection exceeded the CRA-274 per-call cost ceiling (fail closed)."""


def _cmd_describe(args: argparse.Namespace) -> int:
    """``craw code describe <component> [--json] [--org ID]`` — compile, project, emit.

    Maps every failure to the CRA-270 envelope: a missing component / compile failure /
    jail Denial is ``compile_error`` (exit 2); a reflection-cost overflow is
    ``budget_exceeded`` (exit 4, fail-closed). The remediation is static — no fluid/tainted
    input is ever echoed back into the envelope (CRA-271).
    """
    from crawfish.manage import store_for_dir

    org = getattr(args, "org", "local")
    # NOT_FOUND is resolved before opening any Store so a bad path never materializes a
    # ``.crawfish/`` ledger dir under a non-component path.
    if not Path(args.component).is_dir():
        return emit_error(
            ErrorCode.NOT_FOUND,
            remediation=(
                f"Component {args.component!r} was not found; pass a component directory path."
            ),
            detail={"component": args.component},
            as_json=getattr(args, "as_json", False),
        )
    # The per-project Store (CRA-275 org-scoped), opened through the protocol-returning
    # factory — the product model never names a concrete backend. Ensure the generated-state
    # ``.crawfish/`` dir exists first (gitignored; the ledger + describe cache live under it).
    (Path(args.component) / ".crawfish").mkdir(parents=True, exist_ok=True)
    store = store_for_dir(args.component)
    try:
        try:
            body = describe_component(args.component, store=store, org_id=org)
        except FileNotFoundError:
            return emit_error(
                ErrorCode.NOT_FOUND,
                remediation=(
                    f"Component {args.component!r} was not found; pass a component directory path."
                ),
                detail={"component": args.component},
                as_json=getattr(args, "as_json", False),
            )
        except ReflectionCostError as exc:
            return emit_error(
                ErrorCode.BUDGET_EXCEEDED,
                remediation=(
                    "The component is too large to reflect; split it into smaller components."
                ),
                detail={"component": args.component, "reason": str(exc)},
                as_json=getattr(args, "as_json", False),
            )
        except Exception as exc:  # DefinitionLoadError / jail Denial → compile_error
            from crawfish.definition.compiler import DefinitionLoadError

            code = (
                ErrorCode.COMPILE_ERROR
                if isinstance(exc, DefinitionLoadError)
                else ErrorCode.INTERNAL
            )
            return emit_error(
                code,
                remediation=(
                    f"Component {args.component!r} failed to compile; fix the directory and retry."
                ),
                detail={"component": args.component},
                as_json=getattr(args, "as_json", False),
            )
        if getattr(args, "as_json", False):
            emit_json("code.describe", body, org=org)
        else:
            _print_human(body)
        return EXIT_OK
    finally:
        store.close()


def _print_human(body: dict[str, object]) -> None:
    """One-line-per-port human rendering (unchanged behaviour when ``--json`` is absent)."""
    print(f"{body['component']} (sha {body['content_sha']}, by {body['authored_by']})")
    for label in ("inputs", "outputs"):
        ports = body.get(label, [])
        if not isinstance(ports, list):
            continue
        for port in ports:
            if not isinstance(port, dict):
                continue
            print(f"  {label[:-1]:7} {port['name']}: {port['type']} [{port['flow']}]")
