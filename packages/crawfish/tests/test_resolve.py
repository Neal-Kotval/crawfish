"""CRA-222 / OPT-4 — dependency resolver + lockfile acceptance tests.

Covers: deterministic transitive resolution, ``^``/``~``/exact range semantics, conflict
and cycle fail-closed, lockfile round-trip + closure-sha reproducibility/tamper-detection,
and that reading a lockfile is data-only.
"""

from __future__ import annotations

import pytest

from crawfish.definition.types import DefinitionRef
from crawfish.resolve import (
    Candidate,
    InMemoryCandidateSource,
    Lockfile,
    Pin,
    ResolutionError,
    SemVer,
    read_lockfile,
    resolve,
    write_lockfile,
)


def _cand(uid: str, ver: str, *, deps: list[DefinitionRef] | None = None, sha: str | None = None):
    return Candidate(
        id=uid,
        version=SemVer.parse(ver),
        content_sha=sha if sha is not None else f"{uid}-{ver}-sha",
        dependencies=tuple(deps or ()),
    )


# --------------------------------------------------------------------- semver
def test_semver_parse_and_order():
    assert SemVer.parse("1.2") == SemVer(1, 2, 0)
    assert SemVer.parse("1.2.3") == SemVer(1, 2, 3)
    assert SemVer.parse("0.1-abc123") == SemVer(0, 1, 0)  # trailing sha ignored
    assert SemVer.parse("1.2.0") < SemVer.parse("1.2.1") < SemVer.parse("1.3.0")
    with pytest.raises(ResolutionError):
        SemVer.parse("not-a-version")


# ----------------------------------------------------------------- range ops
def test_caret_picks_highest_in_major():
    src = InMemoryCandidateSource()
    for v in ("1.1.0", "1.2.0", "1.4.0", "2.0.0"):
        src.add(_cand("lib", v))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="^1.2")])
    lock = resolve(root, src)
    pin = next(p for p in lock.pins if p.id == "lib")
    assert pin.version == "1.4.0"  # highest 1.x >= 1.2, not 2.0.0


def test_tilde_picks_highest_in_minor():
    src = InMemoryCandidateSource()
    for v in ("1.2.1", "1.2.9", "1.3.0"):
        src.add(_cand("lib", v))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="~1.2")])
    lock = resolve(root, src)
    pin = next(p for p in lock.pins if p.id == "lib")
    assert pin.version == "1.2.9"  # highest 1.2.x, not 1.3.0


def test_exact_pin():
    src = InMemoryCandidateSource()
    for v in ("1.2.0", "1.2.1"):
        src.add(_cand("lib", v))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="1.2.0")])
    lock = resolve(root, src)
    pin = next(p for p in lock.pins if p.id == "lib")
    assert pin.version == "1.2.0"


def test_caret_zerox_minor_is_breaking():
    src = InMemoryCandidateSource()
    for v in ("0.2.1", "0.2.5", "0.3.0"):
        src.add(_cand("lib", v))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="^0.2")])
    lock = resolve(root, src)
    pin = next(p for p in lock.pins if p.id == "lib")
    assert pin.version == "0.2.5"  # 0.x: minor is the breaking axis


# ------------------------------------------------------------ transitive walk
def test_transitive_closure_pins_everything():
    src = InMemoryCandidateSource()
    src.add(_cand("c", "1.0.0"))
    src.add(_cand("b", "1.0.0", deps=[DefinitionRef(id="c", version="^1.0")]))
    root = _cand("a", "1.0.0", deps=[DefinitionRef(id="b", version="^1.0")])
    lock = resolve(root, src)
    ids = {p.id for p in lock.pins}
    assert ids == {"a", "b", "c"}
    for p in lock.pins:
        assert p.integrity.startswith("sha256:")


def test_diamond_same_version_is_one_pin():
    src = InMemoryCandidateSource()
    src.add(_cand("d", "1.0.0"))
    src.add(_cand("b", "1.0.0", deps=[DefinitionRef(id="d", version="^1.0")]))
    src.add(_cand("c", "1.0.0", deps=[DefinitionRef(id="d", version="^1.0")]))
    root = _cand(
        "a",
        "1.0.0",
        deps=[DefinitionRef(id="b", version="^1.0"), DefinitionRef(id="c", version="^1.0")],
    )
    lock = resolve(root, src)
    d_pins = [p for p in lock.pins if p.id == "d"]
    assert len(d_pins) == 1


# --------------------------------------------------------------- fail closed
def test_unknown_unit_fails_closed():
    root = _cand("a", "1.0.0", deps=[DefinitionRef(id="missing", version="^1.0")])
    with pytest.raises(ResolutionError, match="unknown unit 'missing'"):
        resolve(root, InMemoryCandidateSource())


def test_unsatisfiable_constraint_fails_closed():
    src = InMemoryCandidateSource()
    src.add(_cand("lib", "2.0.0"))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="^1.0")])
    with pytest.raises(ResolutionError, match="no version of 'lib'"):
        resolve(root, src)


def test_conflict_names_both_requirers():
    src = InMemoryCandidateSource()
    src.add(_cand("lib", "1.0.0"))
    src.add(_cand("lib", "2.0.0"))
    src.add(_cand("b", "1.0.0", deps=[DefinitionRef(id="lib", version="^1.0")]))
    src.add(_cand("c", "1.0.0", deps=[DefinitionRef(id="lib", version="^2.0")]))
    root = _cand(
        "a",
        "1.0.0",
        deps=[DefinitionRef(id="b", version="^1.0"), DefinitionRef(id="c", version="^1.0")],
    )
    with pytest.raises(ResolutionError) as ei:
        resolve(root, src)
    msg = str(ei.value)
    assert "lib" in msg and "'b'" in msg and "'c'" in msg


def test_cycle_fails_closed():
    src = InMemoryCandidateSource()
    src.add(_cand("b", "1.0.0", deps=[DefinitionRef(id="a", version="^1.0")]))
    src.add(_cand("a", "1.0.0", deps=[DefinitionRef(id="b", version="^1.0")]))
    root = _cand("a", "1.0.0", deps=[DefinitionRef(id="b", version="^1.0")])
    with pytest.raises(ResolutionError, match="cycle"):
        resolve(root, src)


# --------------------------------------------------------- determinism / hash
def test_closure_sha_independent_of_insertion_order():
    def build(order: list[str]) -> Lockfile:
        src = InMemoryCandidateSource()
        cands = {
            "b": _cand("b", "1.0.0", deps=[DefinitionRef(id="c", version="^1.0")]),
            "c": _cand("c", "1.0.0"),
        }
        for key in order:
            src.add(cands[key])
        root = _cand("a", "1.0.0", deps=[DefinitionRef(id="b", version="^1.0")])
        return resolve(root, src)

    assert build(["b", "c"]).closure_sha() == build(["c", "b"]).closure_sha()


def test_closure_sha_independent_of_org():
    src = InMemoryCandidateSource()
    src.add(_cand("lib", "1.0.0"))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="^1.0")])
    a = resolve(root, src, org_id="local")
    b = resolve(root, src, org_id="acme")
    assert a.closure_sha() == b.closure_sha()
    assert b.org_id == "acme"


def test_mutated_unit_gets_new_closure_sha():
    src1 = InMemoryCandidateSource()
    src1.add(_cand("lib", "1.0.0", sha="original"))
    src2 = InMemoryCandidateSource()
    src2.add(_cand("lib", "1.0.0", sha="mutated"))
    root = _cand("app", "1.0.0", deps=[DefinitionRef(id="lib", version="^1.0")])
    assert resolve(root, src1).closure_sha() != resolve(root, src2).closure_sha()


# -------------------------------------------------------------- round-trip io
def test_lockfile_round_trip():
    src = InMemoryCandidateSource()
    src.add(_cand("c", "1.2.3"))
    src.add(_cand("b", "1.0.0", deps=[DefinitionRef(id="c", version="^1.2")]))
    root = _cand("a", "1.0.0", deps=[DefinitionRef(id="b", version="^1.0")])
    lock = resolve(root, src, org_id="acme")
    restored = read_lockfile(write_lockfile(lock))
    assert restored.root_id == lock.root_id
    assert restored.org_id == "acme"
    assert restored.closure_sha() == lock.closure_sha()
    assert restored.sorted_pins() == lock.sorted_pins()


def test_tampered_lockfile_fails_closed():
    lock = Lockfile(root_id="a", pins=[Pin("a", "1.0.0", "sha256:x")])
    d = lock.to_dict()
    d["closure_sha"] = "sha256:deadbeef"  # corrupt the recorded reference
    with pytest.raises(ResolutionError, match="closure_sha mismatch"):
        Lockfile.from_dict(d)


def test_unsupported_lockfile_version_fails_closed():
    with pytest.raises(ResolutionError, match="unsupported lockfile_version"):
        Lockfile.from_dict({"lockfile_version": 999, "root": "a", "pins": []})
