"""CRA-257 — the golden worked-example Definition.

``demo/craw-code-golden`` is the complete, idiomatic reference Definition the agent
pattern-matches against and the validation eval (CRA-265) loads. These tests pin that it is
**gate-clean against the real pipeline**:

* it compiles through the jailed path (CRA-267) clean, with correct per-file provenance;
* it exercises every Definition file kind (typed IO, team, tools, mcp, policies, skills);
* its consequential ``triage`` output is ``Flow.STATIC`` so the assembly gate
  (``assert_build_safe`` → ALG-3) discharges it — the exact precondition ``craw code sync``
  runs;
* ``craw code describe`` projects its typed IO + capability *kinds* (never a destination);
* it runs green under the mock (``craw test`` semantics) with a typed-record responder;
* the knowledge composition (``with_context``) summons tainted, pinned-by-hash knowledge.

Deterministic: FakeJail compile, MockRuntime — no live model call.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from crawfish.build import assert_build_safe
from crawfish.code.describe import describe_component
from crawfish.core.types import Flow
from crawfish.definition.compiler import load_definition
from crawfish.definition.jailed import import_bearing_files, load_definition_jailed
from crawfish.jail import FLUID_TAINT, SandboxPolicy
from crawfish.runtime.mock import MockRuntime
from crawfish.store import SqliteStore
from crawfish.testing import run_fixtures

_REPO = Path(__file__).resolve().parents[3]
_GOLDEN = _REPO / "demo" / "craw-code-golden"


def test_golden_compiles_clean() -> None:
    """``load_definition`` compiles the golden with no ``DefinitionLoadError``."""
    defn = load_definition(_GOLDEN)
    assert defn.id == "craw-code-golden"
    roles = [a.role for a in defn.team.agents]
    assert roles == ["lead", "classifier", "summarizer"]
    assert defn.team.lead == "lead"


def test_golden_exercises_every_file_kind() -> None:
    """Every Definition file kind is present in the compiled assets/team."""
    defn = load_definition(_GOLDEN)
    # typed IO (definition.py)
    assert defn.inputs and defn.outputs
    # team (instructions.md + agents/*.md)
    assert {a.role for a in defn.team.agents} == {"lead", "classifier", "summarizer"}
    # tools/*.py — bound on the lead by filename stem
    assert "normalize_ticket" in defn.agent("lead").tools
    # mcp/*.py — MCPConnection with auth by reference + a tools allowlist
    assert [m.name for m in defn.assets.mcp] == ["github"]
    assert defn.assets.mcp[0].auth == "GITHUB_TOKEN"
    assert defn.assets.mcp[0].tools == ["create_issue", "search_issues"]
    # policies/*.py — a module-level Policy bound on the classifier
    assert [p.name for p in defn.assets.policies] == ["spend_guard"]
    assert "spend_guard" in defn.agent("classifier").policies
    # skills/*.md
    assert "triage-rubric.md" in defn.assets.skills


def test_golden_flow_tags() -> None:
    """At least one static and one fluid input; the consequential output is static."""
    defn = load_definition(_GOLDEN)
    inputs = {p.name: p.flow for p in defn.inputs}
    assert inputs["project"] is Flow.STATIC
    assert inputs["ticket_body"] is Flow.FLUID
    outputs = {p.name: p.flow for p in defn.outputs}
    # The consequential output is STATIC so ALG-3 can discharge it (build-gate clean).
    assert outputs["triage"] is Flow.STATIC


def test_golden_mcp_auth_is_by_reference() -> None:
    """MCP auth is an env-var NAME (a reference), never an inline credential."""
    defn = load_definition(_GOLDEN)
    auth = defn.assets.mcp[0].auth
    assert auth == "GITHUB_TOKEN"
    # Reference-only: an env-var-name shape, not a token literal (no ``ghp_``/``sk-`` prefix).
    assert auth is not None and auth.isupper()
    assert not auth.startswith(("ghp_", "sk-", "AKIA"))


def test_golden_passes_assembly_gate() -> None:
    """The assembly gate (the ``craw code sync`` precondition) discharges — no fluid→sink."""
    defn = load_definition(_GOLDEN)
    assert_build_safe([defn])  # raises FluidToStaticSinkError on any unsafe wiring


def test_golden_jailed_compile_clean_with_provenance() -> None:
    """The golden compiles jailed (CRA-267) clean, untainted, one row per import-bearing file."""
    store = SqliteStore()
    try:
        result = load_definition_jailed(
            _GOLDEN, store=store, org_id="local", policy=SandboxPolicy(kind="fake")
        )
    finally:
        store.close()
    assert FLUID_TAINT not in result.out_taint  # a clean compile is not tainted
    files = set(import_bearing_files(_GOLDEN))
    assert files == {
        "definition.py",
        "tools/normalize_ticket.py",
        "mcp/github.py",
        "policies/spend_guard.py",
    }
    rows = {r.component_path: r for r in result.provenance}
    assert set(rows) == files
    for row in rows.values():
        assert row.authored_by == "craw-code"
        assert row.source_tainted is False


def test_golden_describe_projects_kinds_only() -> None:
    """``craw code describe`` surfaces typed IO + capability KINDS, never a destination."""
    store = SqliteStore()
    try:
        body = describe_component(str(_GOLDEN), store=store)
    finally:
        store.close()
    kinds = {c["kind"] for c in body["capabilities"]}  # type: ignore[union-attr,index]
    assert "has_mcp_connection" in kinds
    assert "declares_secret_ref" in kinds
    # CRA-271: no destination, env-var name, egress host, or sink target ever leaks.
    blob = repr(body)
    assert "GITHUB_TOKEN" not in blob
    assert "modelcontextprotocol" not in blob
    outputs = {p["name"]: p["flow"] for p in body["outputs"]}  # type: ignore[union-attr,index]
    assert outputs["triage"] == "static"


def test_golden_runs_green_under_mock() -> None:
    """``craw test`` semantics: every fixture runs cleanly under the mock (no live call).

    The typed ``Triage`` record output needs a record-shaped response, so the harness drives
    the mock with a deterministic ``Triage`` JSON responder (exactly as the demo does).
    """
    import json

    defn = load_definition(_GOLDEN)
    triage_json = json.dumps({"category": "bug", "severity": "high", "summary": "summary line"})
    runtime = MockRuntime(responder=lambda _r: triage_json)
    results = asyncio.run(run_fixtures(_GOLDEN / "fixtures", defn, runtime))
    assert results, "expected at least one fixture"
    assert all(r.passed for r in results), [(r.name, r.error) for r in results if not r.passed]


def _load_knowledge_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("_golden_knowledge", _GOLDEN / "knowledge.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_golden_knowledge_is_tainted_and_pinned() -> None:
    """The Wiki page is summoned tainted; ``with_context`` pins by content sha (body excluded)."""
    mod = _load_knowledge_module()
    wiki = mod.triage_rubric_wiki()
    page = wiki.page("triage-rubric")
    assert page is not None and page.tainted is True  # tainted even though TRUSTED

    base = load_definition(_GOLDEN)
    specialized = mod.build_specialized(base)
    # A pinned SummonRef was added; the body is not embedded (pinned by content sha).
    assert len(specialized.dependencies) == len(base.dependencies) + 1
    ref = specialized.dependencies[-1]
    assert ref.id.startswith("summon:") and wiki.content_sha() in ref.version
    # export().checksum moves iff the pinned summon version moves (body never inlined).
    assert base.export().checksum != specialized.export().checksum
