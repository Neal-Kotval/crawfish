"""M5 — the thin MCP veneer over the ``craw code`` CLI.

Pins the veneer's load-bearing invariants:

* The surface is exactly **4 FIXED meta-tools** (``describe`` / ``author`` / ``operate`` /
  ``approve``), a closed ``(str, Enum)`` — not generated from input (ALG-3: untrusted data
  never decides *which* authority exists).
* Each tool maps a closed ``action`` set onto the right ``craw code <verb> --json`` argv and
  returns the CLI's envelope **verbatim** (re-scrubbed on egress). The veneer adds ``--json``
  and ``--org`` and nothing else — no execution logic, no new authority.
* The CLI is the **one execution path**: the veneer dispatches through the same in-process
  ``run_code`` a human's Bash call hits, so every CLI gate fires unchanged.
* The approve gate stays **fail-closed through the veneer**: ``approve``/``apply`` on a
  component with no recorded human approval returns the CLI's non-retryable ``no_approval``
  (exit 4). The veneer owns no Store and no approval record, so it **cannot auto-approve** —
  a red-team payload routing ``apply`` through the veneer cannot escalate past the gate.
* Secret values never leave through a tool result (egress scrub).

Deterministic: a fake :class:`CliRunner` for the marshalling/scrub assertions and a real
seeded project driven in-process for the fail-closed gate. No live model call, no network,
no spawned subprocess.
"""

from __future__ import annotations

from pathlib import Path

from crawfish.code.mcp import (
    META_TOOLS,
    MCPVeneer,
    MetaTool,
    ToolResult,
)


# ===========================================================================
# Fake CLI runner — records the argv and returns a canned (code, stdout, stderr).
# ---------------------------------------------------------------------------
class _FakeRunner:
    """Captures the argv the veneer builds and replays a scripted CLI result.

    Lets a test assert the exact ``craw code <verb> --json …`` the veneer would shell, and
    feed back a chosen envelope/exit code, with **no** real CLI, model, or process.
    """

    def __init__(self, *, code: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self._code = code
        self._stdout = stdout
        self._stderr = stderr

    def __call__(self, argv: list[str]) -> tuple[int, str, str]:
        self.calls.append(argv)
        return self._code, self._stdout, self._stderr


# -- the FIXED 4-tool surface --------------------------------------------------------------
def test_surface_is_exactly_four_fixed_tools() -> None:
    """The veneer advertises exactly the 4 fixed meta-tools — never more, never input-derived."""
    veneer = MCPVeneer(_FakeRunner())
    names = [t["name"] for t in veneer.list_tools()]
    assert names == ["describe", "author", "operate", "approve"]
    assert len(META_TOOLS) == 4
    assert {t.value for t in MetaTool} == {"describe", "author", "operate", "approve"}


def test_tool_descriptors_are_destination_free() -> None:
    """A descriptor surfaces tool/plane/actions only — no secret ref, host, or sink target."""
    veneer = MCPVeneer(_FakeRunner())
    blob = repr(veneer.list_tools()).lower()
    for forbidden in ("token", "secret", "http://", "https://", "env=", "auth_ref"):
        assert forbidden not in blob


# -- each tool maps its action onto the right CLI verb (verbatim args) ----------------------
def test_describe_tool_wraps_describe_verb() -> None:
    """``describe`` shells ``craw code describe <component> --json --org``."""
    runner = _FakeRunner(stdout='{"schema":"craw.code.describe.v1","component":"x"}')
    veneer = MCPVeneer(runner)
    veneer.call_tool("describe", args=["definitions/triage"])
    assert runner.calls == [["describe", "definitions/triage", "--json", "--org", "local"]]


def test_author_tool_wraps_authoring_verbs() -> None:
    """``author`` dispatches new/sync/validate onto the right CLI verbs (validate→authoring)."""
    runner = _FakeRunner(stdout="{}")
    veneer = MCPVeneer(runner)
    veneer.call_tool("author", action="new", args=["definitions/triage"])
    veneer.call_tool("author", action="sync", args=["definitions/triage"])
    veneer.call_tool("author", action="validate", args=["definitions/triage"])
    verbs = [c[0] for c in runner.calls]
    assert verbs == ["new", "sync", "validate-authoring"]


def test_operate_tool_is_read_or_propose_only() -> None:
    """``operate`` reaches estimate/optimize/review/diagnose — and never a consequential apply."""
    runner = _FakeRunner(stdout="{}")
    veneer = MCPVeneer(runner)
    for action in ("estimate", "optimize", "review", "diagnose"):
        veneer.call_tool("operate", action=action, args=["definitions/triage"])
    verbs = [c[0] for c in runner.calls]
    assert verbs == ["estimate", "optimize", "review", "diagnose"]
    assert "apply" not in verbs  # operate cannot promote — that is the approve gate's job


def test_org_is_threaded_verbatim() -> None:
    """The ``org`` argument threads to ``--org`` (tenancy), unchanged."""
    runner = _FakeRunner(stdout="{}")
    veneer = MCPVeneer(runner)
    veneer.call_tool("describe", args=["c"], org="acme")
    assert runner.calls[0][-2:] == ["--org", "acme"]


def test_envelope_returned_verbatim_with_exit_code() -> None:
    """A success envelope is parsed + returned with the closed CRA-243 exit code, verbatim."""
    runner = _FakeRunner(code=0, stdout='{"schema":"craw.code.estimate.v1","total_usd":0.12}')
    veneer = MCPVeneer(runner)
    result = veneer.call_tool("operate", action="estimate", args=["c"])
    assert isinstance(result, ToolResult)
    assert result.exit_code == 0
    assert result.is_error is False
    assert result.payload["total_usd"] == 0.12


# -- closed surface: unknown tool / action is a usage rejection (no guessed verb) -----------
def test_unknown_tool_is_rejected_without_running_cli() -> None:
    """An unknown meta-tool never reaches the CLI — the fixed surface is closed."""
    runner = _FakeRunner()
    veneer = MCPVeneer(runner)
    try:
        veneer.call_tool("exec", args=["rm", "-rf", "/"])
    except ValueError as exc:
        assert "exec" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected the closed surface to reject an unknown tool")
    assert runner.calls == []  # nothing was shelled


def test_unknown_action_is_usage_error_not_a_guessed_verb() -> None:
    """An action outside a tool's closed map is a usage error — the veneer never invents a verb."""
    runner = _FakeRunner()
    veneer = MCPVeneer(runner)
    result = veneer.call_tool("describe", action="exfiltrate", args=["c"])
    assert result.is_error is True
    assert result.exit_code == 2
    assert result.payload["code"] == "usage"
    assert runner.calls == []  # never reached the CLI


# -- egress scrub: a secret value cannot leave through a tool result -----------------------
def test_secret_values_are_scrubbed_on_egress() -> None:
    """Even if a secret somehow reached stdout, the veneer redacts it before returning it."""
    leaked = '{"schema":"craw.code.describe.v1","note":"token sk-ABCDEF1234567890abcdef"}'
    runner = _FakeRunner(code=0, stdout=leaked)
    veneer = MCPVeneer(runner)
    result = veneer.call_tool("describe", args=["c"])
    assert "sk-ABCDEF1234567890abcdef" not in repr(result.payload)


# ===========================================================================
# End-to-end against the real CLI: the approve gate stays fail-closed.
# ---------------------------------------------------------------------------
def _component(tmp_path: Path) -> Path:
    """A minimal compilable component (FakeJail compile path — no model call)."""
    root = tmp_path / "triage"
    (root / "agents").mkdir(parents=True)
    (root / "instructions.md").write_text("triage\n")
    (root / "definition.py").write_text(
        "from crawfish.core import Flow, Parameter\n"
        "inputs = [Parameter(name='ticket', type='str', flow=Flow.FLUID)]\n"
        "outputs = [Parameter(name='label', type='str', flow=Flow.STATIC)]\n"
        "lead = 'lead'\n"
    )
    (root / "agents" / "lead.md").write_text(
        "---\nrole: lead\nmodel: claude-haiku-4-5\ntemperature: 0.2\n---\nTriage it.\n"
    )
    (root / "crawfish.toml").write_text("[project]\nname = 'triage'\n")
    (root / ".crawfish").mkdir(parents=True, exist_ok=True)
    return root


def test_describe_through_real_cli_returns_typed_surface(tmp_path: Path) -> None:
    """The default in-process runner reaches the real ``describe`` verb (one execution path)."""
    comp = _component(tmp_path)
    veneer = MCPVeneer()  # default in-process runner — the same path a human's Bash call hits
    result = veneer.call_tool("describe", args=[str(comp)])
    assert result.exit_code == 0
    assert result.payload["schema"] == "craw.code.describe.v1"
    # the security-relevant flow signal survives the round-trip
    inputs = result.payload["inputs"]
    assert isinstance(inputs, list)
    assert any(p.get("flow") == "fluid" for p in inputs)


def test_apply_without_recorded_approval_fails_closed_through_veneer(tmp_path: Path) -> None:
    """RED-TEAM: routing ``apply`` through the veneer on an UNapproved candidate cannot escalate.

    The veneer can ``propose`` (stage a candidate) but ``apply`` reads only the CLI's own
    recorded ``code_approval`` decision — which the veneer has no path to write. So an apply
    with no human approval returns the CLI's non-retryable ``no_approval`` (exit 4), unchanged:
    the veneer adds no authority and cannot auto-approve.
    """
    comp = _component(tmp_path)
    veneer = MCPVeneer()  # real CLI path

    # propose stages a candidate — and surfaces its pending (unapproved) sha.
    proposed = veneer.call_tool("approve", action="propose", args=[str(comp)])
    assert proposed.exit_code == 0
    sha = proposed.payload["candidate_sha"]
    assert proposed.payload["approval"] == "pending"  # fail-closed: no human decision yet

    # apply with NO recorded approval → the gate's non-retryable security rejection (exit 4).
    applied = veneer.call_tool("approve", action="apply", args=[str(comp), str(sha)])
    assert applied.exit_code == 4  # EXIT_SECURITY — non-retryable, fail-closed
    assert applied.is_error is True
    assert applied.payload["code"] == "no_approval"
    assert applied.payload["retryable"] is False


def test_veneer_owns_no_approval_authority(tmp_path: Path) -> None:
    """The veneer exposes no path to record an approval — so it can never satisfy the gate itself.

    The 4 fixed tools map only to propose/apply/reject; none records a human approve decision.
    This is the structural reason the veneer cannot auto-approve.
    """
    from crawfish.code.mcp import _TOOL_VERBS

    approve_verbs = set(_TOOL_VERBS[MetaTool.APPROVE].values())
    assert approve_verbs == {"propose", "apply", "reject"}
    # no tool reaches a decision-recording verb (only the human CLI `code_approval` row does)
    all_verbs = {v for verbs in _TOOL_VERBS.values() for v in verbs.values()}
    assert not (all_verbs & {"grant", "record_decision"})
