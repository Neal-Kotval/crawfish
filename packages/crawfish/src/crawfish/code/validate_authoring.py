"""CRA-265 — the authoring validation eval.

The authoring playbook's value is that an agent who follows it produces a Definition that
``load_definition``s clean and passes the assembly gate. This module is the regression that
proves the skills + golden example actually compose: it loads the machine-checkable spec
(``docs/specs/craw-code/authoring/authoring-spec.toml``) + the golden project it names, then
runs a **positive** corpus (the golden — and any playbook-derived positive fixture — must
load jailed, pass the assembly gate, lint clean, and run green on the mock) and a **negative**
corpus (a fluid→static-sink wiring, an inline secret, an unknown tool binding) that must be
**rejected by the real checks** — not merely asserted in prose.

Determinism: the jailed compile uses ``SandboxPolicy(kind="fake")`` and the mock run uses a
record-shaped responder; no live model call, no network. The eval is a pure library function
(:func:`validate_authoring`) returning the ``craw.code.validate.v1`` body so a test (or a
later CLI verb) can drive it without this module owning argparse wiring.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from crawfish.code import SCHEMA_VERSIONS

if TYPE_CHECKING:
    from crawfish.runtime.base import AgentRuntime
    from crawfish.store.base import Store

__all__ = [
    "VERB_NAME",
    "VALIDATE_SCHEMA",
    "NegativeCase",
    "validate_authoring",
    "load_authoring_spec",
    "register",
]

#: The ``craw code validate-authoring`` verb name (spec CRA-265).
VERB_NAME = "validate-authoring"

VALIDATE_SCHEMA = "craw.code.validate.v1"

# Register the schema in the negotiated table without editing ``code/__init__.py`` (same
# ``setdefault`` self-registration pattern m2core used for ``code.init`` / ``code.new``).
SCHEMA_VERSIONS.setdefault("code.validate", (1, 0))  # type: ignore[attr-defined]

#: A record-shaped mock reply so a typed-record output (the golden's ``Triage``) validates
#: under the mock — the determinism harness, never a live call.
_TRIAGE_REPLY = json.dumps({"category": "bug", "severity": "high", "summary": "a summary"})


def load_authoring_spec(spec_path: str | Path) -> dict[str, object]:
    """Parse the machine-checkable authoring spec TOML (the single source of truth)."""
    return tomllib.loads(Path(spec_path).read_text())


class NegativeCase:
    """One negative corpus fixture: a spine-violating directory + the gate that must reject it.

    ``builder`` writes the hostile Definition under a tmp dir and returns its path; ``gate`` is
    the symbolic check expected to reject it (``"assembly_gate"`` / ``"secret_shaped_lint"`` /
    ``"load"``); ``code`` is the expected rejection type name.
    """

    __slots__ = ("id", "gate", "code", "builder")

    def __init__(self, id: str, gate: str, code: str, builder) -> None:  # type: ignore[no-untyped-def]
        self.id = id
        self.gate = gate
        self.code = code
        self.builder = builder


def _check_positive(project_dir: Path, *, store: Store, runtime: AgentRuntime) -> dict[str, object]:
    """Run the full positive pipeline over one authored project (all real checks).

    load jailed → assembly gate → secret-shaped lint → mock ``craw test``. Returns a
    per-fixture verdict row; ``ok`` is True only when every stage passes. A stage that
    *fails* (a compile/jail error, an assembly-gate rejection, a red fixture) is recorded on
    the row — never re-raised — so a regressed golden yields ``ok=False`` (verdict fail / the
    verb's expected-failure exit), not a traceback.
    """
    import asyncio

    from crawfish.alg3 import FluidToStaticSinkError
    from crawfish.build import assert_build_safe
    from crawfish.code.lint import lint_tree
    from crawfish.definition.compiler import DefinitionLoadError
    from crawfish.definition.jailed import load_definition_jailed
    from crawfish.jail import SandboxPolicy
    from crawfish.testing import run_fixtures

    row: dict[str, object] = {"id": project_dir.name}
    # 1) jailed compile (CRA-267) — agent-authored code confined, fail-closed.
    try:
        compiled = load_definition_jailed(
            project_dir, store=store, org_id="local", policy=SandboxPolicy(kind="fake")
        )
    except DefinitionLoadError as exc:
        row["loads"] = False
        row["error"] = type(exc).__name__
        row["ok"] = False
        return row
    definition = compiled.definition
    row["loads"] = True
    # 2) assembly gate (ALG-3) — no fluid→static-sink wiring.
    try:
        assert_build_safe([definition])
        row["assembly_gate"] = "pass"
    except FluidToStaticSinkError:
        row["assembly_gate"] = "rejected"
        row["ok"] = False
        return row
    # 3) secret-shaped lint — no inline credential in the tree.
    row["lint"] = "fail" if lint_tree(project_dir) else "clean"
    # 4) mock craw test — every fixture runs green (no live call).
    fixtures = project_dir / "fixtures"
    if fixtures.is_dir():
        results = asyncio.run(run_fixtures(fixtures, definition, runtime))
        row["test"] = "green" if all(r.passed for r in results) else "red"
    else:
        row["test"] = "green"  # no fixtures ⇒ nothing to fail
    row["ok"] = row["assembly_gate"] == "pass" and row["lint"] == "clean" and row["test"] == "green"
    return row


def _check_negative(case: NegativeCase, tmp_root: Path, *, store: Store) -> dict[str, object]:
    """Drive one negative fixture through the REAL gate that must reject it.

    Returns a verdict row recording which gate rejected it and the rejection type name.
    ``rejected`` is True only when the expected gate actually raised/flagged.
    """
    from crawfish.alg3 import FluidToStaticSinkError
    from crawfish.build import assert_build_safe
    from crawfish.code.lint import lint_tree
    from crawfish.definition.compiler import DefinitionLoadError, load_definition
    from crawfish.definition.jailed import load_definition_jailed
    from crawfish.jail import SandboxPolicy

    project = case.builder(tmp_root)
    row: dict[str, object] = {"id": case.id, "expected_gate": case.gate}

    if case.gate == "secret_shaped_lint":
        findings = lint_tree(project)
        row["rejected_by"] = "secret_shaped_lint" if findings else None
        row["rejected"] = bool(findings)
        return row

    if case.gate == "load":
        try:
            load_definition(project)
            row["rejected"] = False
            row["rejected_by"] = None
        except DefinitionLoadError as exc:
            row["rejected"] = True
            row["rejected_by"] = "load"
            row["code"] = type(exc).__name__
        return row

    # assembly_gate: compile jailed, then the ALG-3 gate must reject the fluid→sink wiring.
    try:
        compiled = load_definition_jailed(
            project, store=store, org_id="local", policy=SandboxPolicy(kind="fake")
        )
        assert_build_safe([compiled.definition])
        row["rejected"] = False
        row["rejected_by"] = None
    except FluidToStaticSinkError as exc:
        row["rejected"] = True
        row["rejected_by"] = "assembly_gate"
        row["code"] = type(exc).__name__
    except DefinitionLoadError as exc:
        # A jail Denial or compile failure is also a rejection (defense in depth).
        row["rejected"] = True
        row["rejected_by"] = "assembly_gate"
        row["code"] = type(exc).__name__
    return row


def validate_authoring(
    spec_path: str | Path,
    *,
    repo_root: str | Path,
    store: Store,
    runtime: AgentRuntime,
    negatives: list[NegativeCase] | None = None,
    tmp_root: Path | None = None,
) -> dict[str, object]:
    """Run the positive + negative authoring corpora and return the ``craw.code.validate.v1`` body.

    The positive corpus is the golden project the spec names (``golden=`` in the TOML); the
    negative corpus is ``negatives`` (default: the standard fluid→sink / inline-secret /
    unknown-tool triad from :func:`default_negatives`). ``verdict`` is ``"pass"`` iff every
    positive is ``ok`` and every negative is ``rejected`` by its expected gate.
    """
    spec = load_authoring_spec(spec_path)
    golden = Path(repo_root) / str(spec["golden"])
    cases = negatives if negatives is not None else default_negatives()
    work = tmp_root or (golden.parent / ".validate-tmp")
    work.mkdir(parents=True, exist_ok=True)

    positives = [_check_positive(golden, store=store, runtime=runtime)]
    negative_rows = [_check_negative(c, work, store=store) for c in cases]

    verdict = all(p.get("ok") for p in positives) and all(n.get("rejected") for n in negative_rows)
    return {
        "schema": VALIDATE_SCHEMA,
        "positives": positives,
        "negatives": negative_rows,
        "verdict": "pass" if verdict else "fail",
    }


# ---------------------------------------------------------------------------
# The standard negative corpus — each is a spine violation the real checks reject.
# ---------------------------------------------------------------------------
def default_negatives() -> list[NegativeCase]:
    """The red-team triad: fluid→sink, inline secret, unknown tool binding."""
    return [
        NegativeCase(
            "fluid-to-sink", "assembly_gate", "FluidToStaticSinkError", _build_fluid_to_sink
        ),
        NegativeCase("inline-secret", "secret_shaped_lint", "inline_secret", _build_inline_secret),
        NegativeCase("unknown-tool", "load", "DefinitionLoadError", _build_unknown_tool),
    ]


def _write(project: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return project


def _build_fluid_to_sink(root: Path) -> Path:
    """A Definition whose consequential output is mis-declared FLUID — ALG-3 must reject it."""
    return _write(
        root / "fluid-to-sink",
        {
            "instructions.md": "You triage a ticket.\n",
            "definition.py": (
                "from crawfish.core import Flow, Parameter\n"
                "inputs = [Parameter(name='ticket_body', type='str', flow=Flow.FLUID)]\n"
                # consequential output mis-declared FLUID — the injection path ALG-3 rejects.
                "outputs = [Parameter(name='triage', type='str', flow=Flow.FLUID)]\n"
            ),
        },
    )


def _build_inline_secret(root: Path) -> Path:
    """An mcp/*.py with an inline credential literal — the secret-shaped lint must flag it."""
    return _write(
        root / "inline-secret",
        {
            "instructions.md": "You triage a ticket.\n",
            "definition.py": (
                "from crawfish.core import Flow, Parameter\n"
                "inputs = [Parameter(name='project', type='str', flow=Flow.STATIC)]\n"
                "outputs = [Parameter(name='triage', type='str', flow=Flow.STATIC)]\n"
            ),
            # An inline GitHub PAT literal assigned to a secret-named var — the wrong shape.
            "mcp/github.py": (
                "from crawfish.definition.types import MCPConnection\n"
                'github = MCPConnection(name="github", '
                'auth="ghp_0123456789abcdef0123456789abcdef0123")\n'
            ),
        },
    )


def _build_unknown_tool(root: Path) -> Path:
    """An agent binding a tool that does not exist — load must fail with DefinitionLoadError."""
    return _write(
        root / "unknown-tool",
        {
            "instructions.md": "---\ntools: [does_not_exist]\n---\nYou triage a ticket.\n",
            "definition.py": (
                "from crawfish.core import Flow, Parameter\n"
                "inputs = [Parameter(name='project', type='str', flow=Flow.STATIC)]\n"
                "outputs = [Parameter(name='triage', type='str', flow=Flow.STATIC)]\n"
            ),
        },
    )


def triage_responder() -> Callable[[object], str]:
    """A record-shaped mock responder for the golden's typed ``Triage`` output."""
    return lambda _request: _TRIAGE_REPLY


# ---------------------------------------------------------------------------
# The self-registering CLI verb (CRA-265 / CRA-243).
# ---------------------------------------------------------------------------
#: The repo root that ships the authoring spec + golden (this package's grandparent tree).
#: ``…/packages/crawfish/src/crawfish/code/validate_authoring.py`` → up 5 → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_SPEC = _REPO_ROOT / "docs" / "specs" / "craw-code" / "authoring" / "authoring-spec.toml"


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code validate-authoring`` on the ``code`` subparser group.

    Self-registering via the pkgutil discovery in ``code/cli.py`` — no edit to
    ``cli.py`` / ``__init__.py`` (each verb is a new file with a ``register`` hook).
    """
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(
        VERB_NAME, help="validate the authoring playbook against the golden + red-team corpus"
    )
    p.add_argument("--spec", default=str(_DEFAULT_SPEC), help="authoring-spec.toml path")
    p.add_argument(
        "--repo-root",
        default=None,
        help="repo root the spec's golden path is relative to (default: spec ancestor)",
    )
    add_common_args(p)
    p.set_defaults(func=_cmd_validate)


def _cmd_validate(args: argparse.Namespace) -> int:
    """``craw code validate-authoring [--json]`` — run the eval; emit ``craw.code.validate.v1``.

    Exit mapping (CRA-265 onto the CRA-243 closed table):

    * ``verdict == "pass"`` → ``EXIT_OK`` (0);
    * a **positive** that failed to load / clear a stage → ``EXIT_EXPECTED_FAILURE`` (1)
      (granular spec exit 1 in ``detail.exit``);
    * a **negative** the gate unexpectedly let through → ``EXIT_SECURITY`` (4): a spine check
      that should have rejected but didn't is a security failure (granular spec exit 7 in
      ``detail.exit``).
    """
    import tempfile

    from crawfish.code import (
        EXIT_EXPECTED_FAILURE,
        EXIT_OK,
        ErrorCode,
        emit_error,
        emit_json,
    )
    from crawfish.manage import store_for_dir
    from crawfish.runtime.mock import MockRuntime

    as_json: bool = getattr(args, "as_json", False)
    org: str = getattr(args, "org", "local")
    spec_path = Path(args.spec)
    # The golden path in the spec is relative to the repo root; default to the spec's
    # ancestor (…/docs/specs/craw-code/authoring/spec.toml → up 4 → repo root).
    repo_root = Path(args.repo_root) if args.repo_root else spec_path.resolve().parents[4]

    # A throwaway per-run Store through the protocol factory (never a concrete backend).
    with tempfile.TemporaryDirectory() as work_dir:
        (Path(work_dir) / ".crawfish").mkdir(parents=True, exist_ok=True)
        store = store_for_dir(work_dir)
        try:
            body = validate_authoring(
                spec_path,
                repo_root=repo_root,
                store=store,
                runtime=MockRuntime(responder=triage_responder()),
                tmp_root=Path(work_dir) / "corpus",
            )
        finally:
            store.close()

    positives = cast("list[dict[str, object]]", body.get("positives", []))
    negatives = cast("list[dict[str, object]]", body.get("negatives", []))
    # A positive that failed to clear every stage (loaded but a gate/test failed).
    positive_failed = any(not p.get("ok") for p in positives)
    # A negative the expected gate unexpectedly let through (a security failure).
    negative_leaked = any(not n.get("rejected") for n in negatives)

    if negative_leaked:
        # A spine check that should have rejected but didn't is a SECURITY failure: the closed
        # table maps it to EXIT_SECURITY (4); the granular spec exit 7 rides in detail.exit.
        return emit_error(
            ErrorCode.FLUID_TO_STATIC_SINK,
            remediation=(
                "a spine-violating fixture was NOT rejected by its gate; the authoring "
                "enforcement has regressed — investigate the assembly gate / lint / compiler"
            ),
            detail={"exit": 7, "verdict": "fail", "negatives": negatives},
            as_json=as_json,
        )
    if positive_failed:
        # A positive that failed to load / clear a stage is an expected-failure (regression
        # gate tripped) → EXIT_EXPECTED_FAILURE (1). Emit the verdict body, not an error
        # envelope, so the caller still gets the per-stage detail.
        if as_json:
            emit_json("code.validate", body, org=org)
        else:
            _print_human(body)
        return EXIT_EXPECTED_FAILURE

    if as_json:
        emit_json("code.validate", body, org=org)
    else:
        _print_human(body)
    return EXIT_OK if body.get("verdict") == "pass" else EXIT_EXPECTED_FAILURE


def _print_human(body: dict[str, object]) -> None:
    """A terse human verdict summary (the non-``--json`` path)."""
    positives = cast("list[dict[str, object]]", body.get("positives", []))
    negatives = cast("list[dict[str, object]]", body.get("negatives", []))
    print(f"verdict: {body.get('verdict')}")
    for p in positives:
        print(
            f"  positive {p['id']}: loads={p.get('loads')} gate={p.get('assembly_gate')} "
            f"lint={p.get('lint')} test={p.get('test')}"
        )
    for n in negatives:
        print(f"  negative {n['id']}: rejected_by={n.get('rejected_by')}")
