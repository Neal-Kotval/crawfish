"""CRA-179 — Sandboxed pipelines: the ``Jail`` abstraction (ADR 0016).

Deterministic unit tests run against :class:`FakeJail` — no real sandbox spawns, no
kernel/OS dependency, no live anything (same record-replay discipline as the suite).
They assert the security spine: folder-escape and undeclared-egress are DENIED and
AUDITED (``JAIL_VIOLATION``), ``allow_paths`` rejects a FLUID value, taint re-tags
across the boundary, and the child rehydrates ``default_registry``.

Real-backend (``bwrap`` / ``sandbox-exec``) integration tests are
``@pytest.mark.integration``, capability-probed, and auto-skip where the primitive is
absent — so ``pytest -q`` stays green everywhere.
"""

from __future__ import annotations

import sys

import pytest

from crawfish.core.types import Flow
from crawfish.emission import EmissionKind, read_emissions
from crawfish.jail import (
    BwrapJail,
    Denial,
    DenialKind,
    FakeJail,
    Jail,
    JailPath,
    NoJail,
    PathMode,
    SandboxPolicy,
    SeatbeltJail,
    StaticOnlyError,
    UnsupportedPlatformError,
    _Probe,
    emit_denials,
    registry_descriptors,
    rehydrate_registry,
    select_jail,
)
from crawfish.store import SqliteStore
from crawfish.typesystem import TypeRegistry, default_registry

ALLOWED = "/work/project"


def _program(probe: _Probe):
    return lambda cmd: probe


# -- folder escape ---------------------------------------------------------------


def test_read_inside_allow_paths_is_permitted() -> None:
    jail = FakeJail(_program(_Probe(reads=[f"{ALLOWED}/data.csv"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED, PathMode.RO)])
    assert res.denied == ()
    assert res.exit_code == 0


def test_read_outside_allow_paths_is_denied() -> None:
    jail = FakeJail(_program(_Probe(reads=["/etc/passwd"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED, PathMode.RO)])
    assert len(res.denied) == 1
    assert res.denied[0].kind is DenialKind.FOLDER_ESCAPE
    assert res.denied[0].attempt == "/etc/passwd"
    assert res.exit_code != 0  # an escape makes the child's output untrustworthy


def test_write_to_readonly_path_is_denied() -> None:
    # path is allowed for read but not write -> write is a folder escape.
    jail = FakeJail(_program(_Probe(writes=[f"{ALLOWED}/out.txt"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED, PathMode.RO)])
    assert [d.kind for d in res.denied] == [DenialKind.FOLDER_ESCAPE]


def test_write_to_rw_path_is_permitted() -> None:
    jail = FakeJail(_program(_Probe(writes=[f"{ALLOWED}/out.txt"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED, PathMode.RW)])
    assert res.denied == ()


# -- undeclared egress -----------------------------------------------------------


def test_egress_denied_by_default() -> None:
    jail = FakeJail(_program(_Probe(connects=["evil.example.com:443"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED)])  # allow_net defaults False
    assert len(res.denied) == 1
    assert res.denied[0].kind is DenialKind.UNDECLARED_EGRESS
    assert res.denied[0].attempt == "evil.example.com:443"


def test_egress_permitted_when_explicitly_allowed() -> None:
    jail = FakeJail(_program(_Probe(connects=["api.allowed.com:443"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED)], allow_net=True)
    assert all(d.kind is not DenialKind.UNDECLARED_EGRESS for d in res.denied)


# -- allow_paths / allow_net are STATIC-only -------------------------------------


def test_fluid_allow_path_is_rejected() -> None:
    fluid = JailPath("/secret", PathMode.RO, flow=Flow.FLUID)
    with pytest.raises(StaticOnlyError):
        FakeJail().run(["node"], allow_paths=[fluid])


def test_static_allow_path_is_accepted() -> None:
    static = JailPath(ALLOWED, PathMode.RO, flow=Flow.STATIC)
    res = FakeJail().run(["node"], allow_paths=[static])
    assert res.denied == ()


def test_fluid_path_rejected_before_any_execution() -> None:
    # even NoJail (which actually spawns) must reject a fluid path up front.
    fluid = JailPath("/secret", flow=Flow.FLUID)
    with pytest.raises(StaticOnlyError):
        NoJail().run([sys.executable, "-c", "pass"], allow_paths=[fluid])


# -- audit: every denial -> a JAIL_VIOLATION emission ----------------------------


def test_denial_emits_jail_violation(tmp_path) -> None:
    store = SqliteStore(tmp_path / "ledger.db")
    jail = FakeJail(_program(_Probe(reads=["/etc/shadow"], connects=["exfil.io:443"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED)])
    assert len(res.denied) == 2

    written = emit_denials(store, res, run_id="run-1", node_id="bad-node", ts=1.0)
    assert len(written) == 2
    for e in written:
        assert e.kind is EmissionKind.JAIL_VIOLATION
        assert e.is_valid()  # carries required attrs: attempt, severity
        assert "attempt" in e.attrs and "severity" in e.attrs
        assert e.tainted is True

    rows = read_emissions(store, "run-1")
    kinds = {r.kind for r in rows}
    assert EmissionKind.JAIL_VIOLATION in kinds
    attempts = {r.attrs["attempt"] for r in rows if r.kind is EmissionKind.JAIL_VIOLATION}
    assert attempts == {"/etc/shadow", "exfil.io:443"}


def test_clean_run_emits_no_violations(tmp_path) -> None:
    store = SqliteStore(tmp_path / "ledger.db")
    res = FakeJail(_program(_Probe(reads=[f"{ALLOWED}/ok.txt"]))).run(
        ["node"], allow_paths=[JailPath(ALLOWED)]
    )
    assert emit_denials(store, res, run_id="run-2") == []


# -- taint re-tag across the boundary --------------------------------------------


def test_input_taint_flows_out() -> None:
    res = FakeJail().run(["node"], allow_paths=[JailPath(ALLOWED)], taint=frozenset({"fluid"}))
    assert "fluid" in res.out_taint


def test_child_touching_network_re_tags_output_tainted() -> None:
    # a child that hit the network produces tainted output even if input was clean.
    jail = FakeJail(_program(_Probe(connects=["api.allowed.com:443"])))
    res = jail.run(["node"], allow_paths=[JailPath(ALLOWED)], allow_net=True, taint=frozenset())
    assert "fluid" in res.out_taint  # tool/network result stays tainted


def test_clean_child_with_clean_input_stays_untainted() -> None:
    res = FakeJail(_program(_Probe(reads=[f"{ALLOWED}/ok.txt"]))).run(
        ["node"], allow_paths=[JailPath(ALLOWED)], taint=frozenset()
    )
    assert res.out_taint == frozenset()


def test_denial_taints_output() -> None:
    res = FakeJail(_program(_Probe(reads=["/etc/passwd"]))).run(
        ["node"], allow_paths=[JailPath(ALLOWED)], taint=frozenset()
    )
    assert "fluid" in res.out_taint  # reaching for untrusted scope taints the result


# -- type-registry rehydration across the boundary -------------------------------


def test_registry_rehydration_round_trips() -> None:
    parent = TypeRegistry()
    parent.register_record("PR", {"title": "str", "number": "int"})
    descriptors = registry_descriptors(parent)

    child = TypeRegistry()
    rehydrate_registry(descriptors, child)
    # structural compatibility holds across the boundary (CRA-188 AC).
    assert child.is_registered("PR")
    assert child.is_compatible("PR", "PR")
    assert child.is_compatible("PR", "Optional[PR]")


def test_default_registry_descriptors_serialize() -> None:
    # the process-global registry serializes to JSON-safe descriptors.
    descriptors = registry_descriptors(default_registry)
    assert isinstance(descriptors, list)
    for d in descriptors:
        assert isinstance(d, dict) and "name" in d and "kind" in d


# -- factory + backend selection -------------------------------------------------


def test_select_jail_pins_fake() -> None:
    assert select_jail(SandboxPolicy(kind="fake")).kind == "fake"


def test_select_jail_pins_nojail() -> None:
    assert select_jail(SandboxPolicy(kind="nojail")).kind == "nojail"


def test_select_jail_auto_picks_os_backend() -> None:
    jail = select_jail()
    if sys.platform.startswith("linux"):
        assert jail.kind == "bwrap"
    elif sys.platform == "darwin":
        assert jail.kind == "seatbelt"
    else:  # pragma: no cover - CI is linux/macos
        pytest.skip("no real backend on this platform")


def test_select_jail_raises_on_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(UnsupportedPlatformError):
        select_jail()


# -- backend-conformance: fake honest vs the real interface ----------------------


@pytest.mark.parametrize("jail", [FakeJail(), NoJail(), BwrapJail(), SeatbeltJail()])
def test_all_backends_share_the_contract(jail: Jail) -> None:
    # every backend is a Jail, exposes a kind tag, and enforces the static-only spine
    # *before* any execution — provable without spawning anything.
    assert isinstance(jail, Jail)
    assert jail.kind in {"fake", "nojail", "bwrap", "seatbelt"}
    with pytest.raises(StaticOnlyError):
        jail.run(["x"], allow_paths=[JailPath("/p", flow=Flow.FLUID)])


def test_seatbelt_profile_denies_network_by_default() -> None:
    prof = SeatbeltJail().profile([JailPath(ALLOWED, PathMode.RW)], allow_net=False)
    assert "(deny default)" in prof
    assert "(deny network*)" in prof
    assert f'(subpath "{ALLOWED}")' in prof


def test_seatbelt_profile_allows_network_when_granted() -> None:
    prof = SeatbeltJail().profile([JailPath(ALLOWED)], allow_net=True)
    assert "(allow network*)" in prof


def test_bwrap_wrap_unshares_net_by_default() -> None:
    argv = BwrapJail()._wrap(["node"], allow_paths=[JailPath(ALLOWED)], allow_net=False, cwd=None)
    assert "--unshare-net" in argv  # loopback-only: no egress path exists
    assert "--ro-bind" in argv


def test_bwrap_wrap_keeps_net_when_granted() -> None:
    argv = BwrapJail()._wrap(["node"], allow_paths=[JailPath(ALLOWED)], allow_net=True, cwd=None)
    assert "--unshare-net" not in argv


def test_denial_as_attrs_matches_required_schema() -> None:
    d = Denial(DenialKind.FOLDER_ESCAPE, "/etc/passwd")
    attrs = d.as_attrs()
    assert attrs["attempt"] == "/etc/passwd"
    assert attrs["severity"] == "high"


# -- real-sandbox integration (gated, auto-skip) ---------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not BwrapJail().available(), reason="bwrap unavailable")
def test_bwrap_blocks_folder_escape_for_real(tmp_path) -> None:  # pragma: no cover
    jail = BwrapJail()
    allowed = tmp_path / "work"
    allowed.mkdir()
    res = jail.run(
        [sys.executable, "-c", "open('/etc/shadow').read()"],
        allow_paths=[JailPath(str(allowed), PathMode.RW)],
    )
    assert res.exit_code != 0


@pytest.mark.integration
@pytest.mark.skipif(not SeatbeltJail().available(), reason="sandbox-exec unavailable")
def test_seatbelt_blocks_egress_for_real(tmp_path) -> None:  # pragma: no cover
    jail = SeatbeltJail()
    allowed = tmp_path / "work"
    allowed.mkdir()
    code = "import socket; socket.create_connection(('1.1.1.1', 80), timeout=2)"
    res = jail.run(
        [sys.executable, "-c", code],
        allow_paths=[JailPath(str(allowed), PathMode.RW)],
        allow_net=False,
    )
    assert res.exit_code != 0
