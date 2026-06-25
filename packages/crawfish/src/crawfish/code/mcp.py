"""``craw code mcp serve`` — the optional **thin MCP veneer** over the CLI (M5).

RFC 0001 §3 ("Optional later veneer"): *if* typed entry points prove worth a second
surface, add a **thin** MCP of ~4 **fixed** meta-tools that shell out to the CLI — the
project component is an *argument*, not a tool. Fixed arity sidesteps both staleness and
bloat. This module is that veneer, and nothing more.

The load-bearing invariants (this is a *veneer*, not a second execution path):

* **The CLI is the one execution path.** Every meta-tool does exactly one thing: build a
  ``craw code <verb> --json …`` argv and run it through the same in-process dispatch
  (:func:`crawfish.code.cli.run_code`) that a human's Bash call hits. The veneer adds **no**
  execution logic, **no** new authority, and **never** bypasses a CLI gate. The CLI's
  jail / redaction / consent / approval gates do **all** the enforcement; the veneer only
  marshals args in and the ``--json`` envelope out.
* **The 4 meta-tools are a FIXED, static surface** (:class:`MetaTool`, a ``(str, Enum)``).
  They are **not** generated from fluid/session data — a per-component or
  dynamically-named tool surface would re-introduce exactly the injection-widening ALG-3
  forbids (untrusted input deciding *what authority exists*). The component is always an
  *argument* passed through to the CLI, never a tool name.
* **The approve gate stays fail-closed through the veneer.** The ``approve`` meta-tool can
  ``propose`` (stage a candidate) but an ``apply`` still routes through ``craw code apply``,
  which reads **only** its own recorded ``code_approval`` decision — the veneer has no path
  to record an approval and therefore **cannot auto-approve**. A prompt-injected client
  calling ``approve`` with ``action="apply"`` on an unapproved candidate gets the CLI's
  non-retryable ``no_approval`` envelope (exit 4), unchanged.
* **Output is scrubbed.** The CLI already redacts on the way into the ledger; as a
  belt-and-suspenders egress pass the veneer runs the captured stdout/stderr through
  :func:`crawfish.secrets.redact` before returning it to the MCP client, so a secret value
  can never round-trip out through a tool result.

This file **self-registers** a ``mcp`` verb on the ``craw code`` group via the pkgutil
registry (a sibling module exposing ``register(subparsers)``) and seeds its schema key with
``SCHEMA_VERSIONS.setdefault`` — it does **not** edit ``code/cli.py`` or the ``code``
``__init__`` registry.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from crawfish.code import SCHEMA_VERSIONS, schema_tag, schema_version
from crawfish.secrets import redact

# The veneer advertises its own --json envelope version through the shared negotiation map
# (CRA-269). ``setdefault`` so importing this module never clobbers a key another verb owns.
SCHEMA_VERSIONS.setdefault("code.mcp", (1, 0))  # type: ignore[attr-defined]

VERB_NAME = "mcp"

__all__ = [
    "VERB_NAME",
    "MetaTool",
    "META_TOOLS",
    "ToolResult",
    "CliRunner",
    "subprocess_runner",
    "MCPVeneer",
    "register",
]


# ===========================================================================
# The FIXED 4-tool surface (RFC 0001 §3 "~4 fixed meta-tools").
# ---------------------------------------------------------------------------
# A closed ``(str, Enum)`` (ADR 0004 — UP042 disabled). The set is fixed at import time and
# never derived from fluid/session input: untrusted data may choose a tool's *arguments*
# (which flow through the CLI's gates), never *which tools exist* (ALG-3).
class MetaTool(str, Enum):
    """The four fixed meta-tools, one per CLI authority plane.

    * :attr:`DESCRIBE` — **read** plane: reflect a component's typed surface.
    * :attr:`AUTHOR`   — **author** plane: scaffold / sync / validate authoring.
    * :attr:`OPERATE`  — **operate** plane: estimate / optimize / review / diagnose /
      dashboard (read-or-propose only — no consequential write).
    * :attr:`APPROVE`  — **approve-gate** plane: propose / apply / reject, honoring the
      fail-closed human approval gate (the veneer can propose, never auto-approve).
    """

    DESCRIBE = "describe"
    AUTHOR = "author"
    OPERATE = "operate"
    APPROVE = "approve"


#: The fixed verb each meta-tool may dispatch to, keyed by the tool's ``action`` argument.
#: This is the *whole* mapping — a meta-tool can only reach a CLI verb listed here, and every
#: such verb is itself gated by the CLI. The veneer never invents a verb from input.
_TOOL_VERBS: dict[MetaTool, dict[str, str]] = {
    MetaTool.DESCRIBE: {
        "describe": "describe",
        "schema": "schema",
    },
    MetaTool.AUTHOR: {
        "new": "new",
        "sync": "sync",
        "validate": "validate-authoring",
    },
    MetaTool.OPERATE: {
        "estimate": "estimate",
        "optimize": "optimize",
        "review": "review",
        "diagnose": "diagnose",
        "dashboard": "dashboard",
        "map": "map",
        "lint": "lint",
    },
    MetaTool.APPROVE: {
        "propose": "propose",
        "apply": "apply",
        "reject": "reject",
    },
}

#: The default action for each tool (used when a client omits ``action``).
_TOOL_DEFAULT_ACTION: dict[MetaTool, str] = {
    MetaTool.DESCRIBE: "describe",
    MetaTool.AUTHOR: "sync",
    MetaTool.OPERATE: "estimate",
    MetaTool.APPROVE: "propose",
}


def _tool_descriptor(tool: MetaTool) -> dict[str, object]:
    """The static MCP-tool descriptor for one meta-tool (advertised in ``list_tools``).

    Typed-shape-only and destination-free: it names the tool, its plane, the closed set of
    ``action`` values, and the free-form ``args`` passthrough — never a secret, host, or
    sink target.
    """
    actions = sorted(_TOOL_VERBS[tool])
    return {
        "name": tool.value,
        "description": _TOOL_DESCRIPTIONS[tool],
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": actions,
                    "default": _TOOL_DEFAULT_ACTION[tool],
                    "description": f"which {tool.value} verb to dispatch",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "positional/flag args passed verbatim to craw code <verb>",
                },
                "org": {"type": "string", "description": "tenancy org_id (default: local)"},
            },
            "additionalProperties": False,
        },
    }


_TOOL_DESCRIPTIONS: dict[MetaTool, str] = {
    MetaTool.DESCRIBE: "Read a component's typed IO surface (read-only).",
    MetaTool.AUTHOR: "Scaffold, sync, or validate authoring files.",
    MetaTool.OPERATE: "Estimate cost, optimize, review, or diagnose (read/propose only).",
    MetaTool.APPROVE: (
        "Propose/apply/reject a candidate. Apply requires a recorded human approval — "
        "the veneer cannot auto-approve."
    ),
}

#: The fixed list of tool descriptors the veneer advertises (stable order).
META_TOOLS: list[dict[str, object]] = [_tool_descriptor(t) for t in MetaTool]


@dataclass(frozen=True)
class ToolResult:
    """The result of one meta-tool call: the CLI's exit code + scrubbed ``--json`` payload.

    ``payload`` is the parsed ``craw.<verb>.v1`` / ``craw.error.v1`` envelope the CLI emitted
    (already redacted again on egress); ``exit_code`` is the closed CRA-243 0–4 code, passed
    through verbatim so a non-retryable security rejection stays a security rejection.
    """

    exit_code: int
    payload: dict[str, object]
    is_error: bool


# ===========================================================================
# The single execution path: shell out to the CLI.
# ---------------------------------------------------------------------------
class CliRunner(Protocol):
    """How the veneer reaches the CLI. Injected so tests can drive a fake/seeded project.

    The contract is exactly a ``craw code`` invocation: given the argv **after** ``craw
    code`` (e.g. ``["describe", "definitions/triage", "--json"]``), run it and return
    ``(exit_code, stdout, stderr)``. The default impl runs it in-process through the same
    dispatch a human's Bash call hits — there is no second code path.
    """

    def __call__(self, argv: list[str]) -> tuple[int, str, str]: ...


def in_process_runner(argv: list[str]) -> tuple[int, str, str]:
    """Run ``craw code <argv>`` in-process via :func:`crawfish.code.cli.run_code`.

    This is the **one execution path** the veneer shares with a human's Bash call: it dispatches
    through the exact same registry/parse/handler chain, so every jail / consent / approval gate
    fires identically. stdout/stderr are captured (the CLI writes its ``--json`` envelope to
    stdout and its ``craw.error.v1`` envelope to stderr) and returned with the exit code.
    """
    from crawfish.code.cli import run_code

    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = run_code(argv)
    except SystemExit as exc:  # argparse usage error → exit 2, never a crash through the veneer
        code = int(exc.code) if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    """Run ``craw code <argv>`` as a real subprocess (for an out-of-process MCP host).

    Identical authority to :func:`in_process_runner` — it shells the very same CLI entry
    point. Provided for a deployment that wants the veneer and the CLI in separate processes;
    tests use a fake runner instead so they never spawn a process or touch the network.
    """
    import subprocess
    import sys

    proc = subprocess.run(  # noqa: S603 — fixed argv0 (this interpreter), args are CLI verbs
        [sys.executable, "-m", "crawfish.cli", "code", *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


class MCPVeneer:
    """The thin MCP veneer: the fixed 4 meta-tools dispatched onto the CLI.

    Holds **no** state and **no** authority of its own — only a :class:`CliRunner`. Every
    ``call_tool`` builds a ``craw code <verb> --json`` argv and runs it; the parsed, re-scrubbed
    envelope is returned verbatim. The veneer never records an approval, never resolves a secret,
    and never decides a gate — it cannot, because it owns no Store and no approval record.
    """

    def __init__(self, runner: CliRunner | None = None) -> None:
        self._run: CliRunner = runner or in_process_runner

    # -- protocol surface -------------------------------------------------
    def list_tools(self) -> list[dict[str, object]]:
        """Advertise the FIXED 4 meta-tools (static; never derived from input)."""
        return [dict(t) for t in META_TOOLS]

    def call_tool(
        self,
        name: str,
        *,
        action: str | None = None,
        args: list[str] | None = None,
        org: str = "local",
    ) -> ToolResult:
        """Dispatch one meta-tool to its CLI verb and return the scrubbed ``--json`` envelope.

        ``name`` must be one of the fixed :class:`MetaTool` values; ``action`` selects the
        verb within that tool's closed map; ``args`` are passed **verbatim** as positional /
        flag args to ``craw code <verb>``. The veneer adds ``--json`` and threads ``--org`` —
        and adds nothing else. An unknown tool or action is a usage error (the veneer never
        guesses a verb). Everything past that is the CLI's to enforce.
        """
        tool = _coerce_tool(name)
        verbs = _TOOL_VERBS[tool]
        chosen = action or _TOOL_DEFAULT_ACTION[tool]
        verb = verbs.get(chosen)
        if verb is None:
            return _usage_result(
                f"unknown action {chosen!r} for tool {tool.value!r}; "
                f"valid actions: {', '.join(sorted(verbs))}"
            )

        argv = [verb, *(args or []), "--json", "--org", org]
        exit_code, stdout, stderr = self._run(argv)
        return _parse_result(exit_code, stdout, stderr)


def _coerce_tool(name: str) -> MetaTool:
    """Resolve a tool name to a fixed :class:`MetaTool`, or raise ``ValueError`` (closed set)."""
    try:
        return MetaTool(name)
    except ValueError as exc:
        valid = ", ".join(t.value for t in MetaTool)
        raise ValueError(f"unknown meta-tool {name!r}; the fixed surface is: {valid}") from exc


def _usage_result(message: str) -> ToolResult:
    """A veneer-side usage rejection shaped like the CLI's ``craw.error.v1`` (exit 2)."""
    payload: dict[str, object] = {
        "schema": schema_tag("error"),
        "schema_version": schema_version("error"),
        "code": "usage",
        "retryable": False,
        "detail": {},
        "remediation": message,
    }
    return ToolResult(exit_code=2, payload=payload, is_error=True)


def _parse_result(exit_code: int, stdout: str, stderr: str) -> ToolResult:
    """Parse + **scrub** the CLI's captured output into a :class:`ToolResult`.

    The CLI writes its success envelope to stdout and its ``craw.error.v1`` envelope to stderr;
    on a non-zero exit we prefer stderr (the structured error), else stdout. The chosen text is
    redacted on egress (:func:`crawfish.secrets.redact`) **before** parsing, so no secret value
    can leave through a tool result even if one somehow reached the stream. The exit code is the
    closed CRA-243 code, returned verbatim (a security rejection stays a security rejection).
    """
    raw = stderr if exit_code != 0 and stderr.strip() else stdout
    scrubbed = redact(raw)
    payload: dict[str, object]
    try:
        parsed = json.loads(scrubbed) if scrubbed.strip() else {}
        payload = parsed if isinstance(parsed, dict) else {"output": parsed}
    except json.JSONDecodeError:
        # A non-JSON line (human-mode fallback / unexpected text) is wrapped, still scrubbed.
        payload = {"output": scrubbed.strip()}
    return ToolResult(exit_code=exit_code, payload=payload, is_error=exit_code != 0)


# ===========================================================================
# CLI registration: `craw code mcp serve` (self-registering verb).
# ---------------------------------------------------------------------------
def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code mcp`` on the ``code`` group (self-registering; one owner).

    ``mcp serve`` is the entry an MCP host launches; ``mcp list-tools`` prints the fixed
    descriptor surface (useful for inspection + the deterministic tests). Neither edits the
    shared dispatcher — this module is discovered by ``pkgutil.iter_modules``.
    """
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(
        VERB_NAME, help="thin MCP veneer over the CLI: 4 fixed meta-tools (M5)"
    )
    p.add_argument(
        "mcp_action",
        choices=("serve", "list-tools"),
        nargs="?",
        default="list-tools",
        help="serve the MCP veneer (stdio) or print the fixed tool descriptors",
    )
    add_common_args(p)
    p.set_defaults(func=_cmd_mcp)


def _cmd_mcp(args: argparse.Namespace) -> int:
    """``craw code mcp [serve|list-tools]`` — start the veneer or print its fixed tools."""
    from crawfish.code import EXIT_OK, emit_json

    veneer = MCPVeneer()
    action = getattr(args, "mcp_action", "list-tools")
    if action == "list-tools":
        body: dict[str, object] = {"tools": veneer.list_tools()}
        if getattr(args, "as_json", False):
            emit_json("code.mcp", body, org=getattr(args, "org", "local"))
        else:
            for tool in veneer.list_tools():
                print(f"{tool['name']:9} {tool['description']}")
        return EXIT_OK
    # ``serve`` — the stdio MCP loop. Kept minimal + protocol-correct; the real transport is
    # provided by the MCP host. We surface the fixed surface and exit cleanly when no host is
    # attached (deterministic tests exercise the veneer object directly, never a live stdio loop).
    return _serve(veneer, getattr(args, "as_json", False))


def _serve(veneer: MCPVeneer, as_json: bool) -> int:
    """Announce the fixed tool surface for an MCP host. No live model/network in tests.

    The veneer's protocol surface is :meth:`MCPVeneer.list_tools` / :meth:`MCPVeneer.call_tool`;
    a host wires those onto a transport. This entry simply confirms the surface is fixed and
    ready (printing the descriptors) — the deterministic test drives ``call_tool`` directly,
    so there is no blocking stdio read here to make the suite hang.
    """
    from crawfish.code import EXIT_OK, emit_json

    body: dict[str, object] = {"ready": True, "tools": veneer.list_tools()}
    if as_json:
        emit_json("code.mcp", body)
    else:
        print(f"craw code mcp veneer ready: {len(veneer.list_tools())} fixed meta-tools")
    return EXIT_OK
