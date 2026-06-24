"""CRA-225 / AL-DV2 (save/recall) + CRA-226 / AL-DV3 (modify/reset).

Git for Definitions: a mutable name pointer over an append-only, content-addressed object
store. These tests pin the acceptance criteria from both issues — pointer move, recall
latest + pinned, dedup-but-two-events, lineage chain, cross-org isolation, save-rejects-
unfrozen (AL-DV2); modify advances + records parent + leaves old recallable, reset checkout
(reachable-only, mints nothing), modify-on-eval-mode raises, determinism (AL-DV3).
"""

from __future__ import annotations

import pytest

from crawfish.definition.types import AgentSpec, Definition, TeamSpec
from crawfish.definition_store import (
    DefinitionStore,
    UnfrozenDefinitionError,
    UnknownNameError,
    UnreachableShaError,
    modify,
    reset,
)
from crawfish.derive import with_agent
from crawfish.store import SqliteStore
from crawfish.versioning.version import FrozenError


def _frozen(model: str = "fast", role: str = "lead") -> Definition:
    """A small frozen (eval-mode) Definition with a fresh content sha."""
    defn = Definition(team=TeamSpec(agents=[AgentSpec(role=role, model=model)]))
    defn.version.sha = defn.content_sha()
    defn.freeze()
    return defn


def _store(tmp_path, *, org_id: str = "local") -> DefinitionStore:
    return DefinitionStore(SqliteStore(str(tmp_path / "defs.db")), org_id=org_id)


# == AL-DV2: save / recall ==================================================
def test_save_then_recall_returns_same_sha(tmp_path) -> None:
    store = _store(tmp_path)
    d = _frozen()
    sha = store.save("extract", d)
    assert sha == d.content_sha()
    assert store.recall("extract").content_sha() == sha


def test_save_rejects_unfrozen_definition(tmp_path) -> None:
    store = _store(tmp_path)
    draft = Definition(team=TeamSpec(agents=[AgentSpec(role="lead")]))  # not frozen
    assert not draft.frozen
    with pytest.raises(UnfrozenDefinitionError):
        store.save("extract", draft)


def test_pointer_moves_old_sha_still_recallable_pinned(tmp_path) -> None:
    store = _store(tmp_path)
    v1 = _frozen(model="slow")
    old_sha = store.save("extract", v1)

    v2 = with_agent(v1, AgentSpec(role="critic", model="fast"))
    new_sha = store.save("extract", v2, parent=old_sha)
    assert new_sha != old_sha

    # latest follows the pointer; the old version stays pinned-recallable after the move.
    assert store.recall("extract").content_sha() == new_sha
    assert store.recall("extract", sha=old_sha).content_sha() == old_sha
    # the ``name@sha`` ergonomic resolves the same historical pointer.
    assert store.recall(f"extract@{old_sha}").content_sha() == old_sha


def test_byte_identical_dedup_but_two_pointer_events(tmp_path) -> None:
    store = _store(tmp_path)
    d = _frozen()
    sha1 = store.save("a", d)
    sha2 = store.save("a", d)  # byte-identical content saved again
    assert sha1 == sha2  # dedup: one object, one sha

    # but TWO distinct pointer events recorded in the log.
    events = store.log("a")
    assert len(events) == 2
    assert [e.sha for e in events] == [sha1, sha2]
    assert [e.seq for e in events] == [0, 1]


def test_log_returns_correct_parent_sha_chain(tmp_path) -> None:
    store = _store(tmp_path)
    v1 = _frozen(model="slow")
    s1 = store.save("p", v1)
    v2 = with_agent(v1, AgentSpec(role="b", model="fast"))
    s2 = store.save("p", v2, parent=s1)
    v3 = with_agent(v2, AgentSpec(role="c", model="mid"))
    s3 = store.save("p", v3, parent=s2)

    chain = store.log("p")
    assert [v.sha for v in chain] == [s1, s2, s3]
    assert [v.parent_sha for v in chain] == [None, s1, s2]


def test_recall_never_mints_a_new_sha(tmp_path) -> None:
    store = _store(tmp_path)
    d = _frozen()
    sha = store.save("extract", d)
    # repeated recall is pure: same sha, frozen, no new object minted.
    for _ in range(3):
        got = store.recall("extract")
        assert got.content_sha() == sha
        assert got.frozen


def test_cross_org_isolation(tmp_path) -> None:
    backend = SqliteStore(str(tmp_path / "shared.db"))
    org_a = DefinitionStore(backend, org_id="org_a")
    org_b = DefinitionStore(backend, org_id="org_b")
    org_a.save("extract", _frozen())
    # the name in org A is invisible to org B.
    with pytest.raises(UnknownNameError):
        org_b.recall("extract")
    with pytest.raises(UnknownNameError):
        org_b.log("extract")


def test_recall_unknown_name_raises(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(UnknownNameError):
        store.recall("nope")


def test_recall_bare_sha_resolves_content_addressed(tmp_path) -> None:
    store = _store(tmp_path)
    d = _frozen()
    sha = store.save("extract", d)
    # a bare sha (not a name) resolves via the content-addressed object store.
    assert store.recall(sha).content_sha() == sha


# == AL-DV3: modify / reset =================================================
def test_modify_advances_pointer_records_parent_old_recallable(tmp_path) -> None:
    store = _store(tmp_path)
    old = store.save("extract", _frozen(model="slow"))

    new = modify(store, "extract", lambda d: with_agent(d, AgentSpec(role="critic")))
    assert new != old
    assert store.head("extract") == new  # pointer advanced

    chain = store.log("extract")
    assert chain[-1].sha == new
    assert chain[-1].parent_sha == old  # lineage edge recorded
    # the old sha is still recallable via @sha (append-only).
    assert store.recall("extract", sha=old).content_sha() == old


def test_modify_on_eval_mode_in_place_edit_raises(tmp_path) -> None:
    store = _store(tmp_path)
    store.save("extract", _frozen())

    def _mutate_in_place(d: Definition) -> Definition:
        d.injected_prompts = []  # an in-place write on a frozen, eval-mode Definition
        return d

    with pytest.raises(FrozenError):
        modify(store, "extract", _mutate_in_place)


def test_modify_unknown_name_raises(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(UnknownNameError):
        modify(store, "nope", lambda d: d)


def test_modify_is_deterministic(tmp_path) -> None:
    # same start + pure fn ⇒ same resulting sha (across two independent stores).
    def run(tp) -> str:
        tp.mkdir(parents=True, exist_ok=True)
        store = DefinitionStore(SqliteStore(str(tp / "d.db")))
        store.save("x", _frozen(model="slow"))
        return modify(store, "x", lambda d: with_agent(d, AgentSpec(role="critic", model="fast")))

    a = run(tmp_path / "a")
    b = run(tmp_path / "b")
    assert a == b


def test_reset_checkout_mints_nothing_rewinds_pointer(tmp_path) -> None:
    store = _store(tmp_path)
    s1 = store.save("extract", _frozen(model="slow"))
    s2 = modify(store, "extract", lambda d: with_agent(d, AgentSpec(role="critic")))
    assert store.head("extract") == s2

    log_before = store.log("extract")
    back = reset(store, "extract", s1)
    assert back == s1
    assert store.head("extract") == s1
    # reset mints no object and no lineage event.
    assert store.log("extract") == log_before
    # recall(name) and the original @s1 are content-equal after reset.
    assert store.recall("extract").content_sha() == store.recall("extract", sha=s1).content_sha()


def test_reset_refuses_unreachable_sha(tmp_path) -> None:
    store = _store(tmp_path)
    store.save("extract", _frozen(model="slow"))
    # a sha that was never recorded for this name is unreachable.
    other = _frozen(model="totally-different").content_sha()
    with pytest.raises(UnreachableShaError):
        reset(store, "extract", other)


def test_reset_unknown_name_raises(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(UnknownNameError):
        reset(store, "nope", "deadbeef")
