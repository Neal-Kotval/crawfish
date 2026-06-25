"""CRA-278 acceptance: the authoring-tree advisory lock (read-during-edit consistency).

Deterministic — the lease primitive is driven directly (no real thread races). A writer's
exclusive lease makes a concurrent reader (sync) fail closed with ``tree_busy`` (exit 8,
retryable); the lock is tenancy-scoped (org A's lock never blocks org B), Store-enforced
(survives a fresh Store handle), and its marker lives under ``.crawfish/locks/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawfish.code.cli import run_code
from crawfish.code.treelock import TreeBusy, TreeLock


@pytest.fixture
def app(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    assert run_code(["init", str(root)]) == 0
    return root


def _store(app: Path):  # type: ignore[no-untyped-def]
    from crawfish.manage import store_for_dir

    (app / ".crawfish").mkdir(exist_ok=True)
    return store_for_dir(str(app))


def test_writer_lease_blocks_a_concurrent_reader(
    app: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store(app)
    lock = TreeLock(store, app, org_id="local")
    token = lock.acquire_write()
    try:
        rc = run_code(["sync", "--dir", str(app), "--json"])
        cap = capsys.readouterr()
        payload = json.loads((cap.out.strip() or cap.err.strip()).splitlines()[-1])
        assert rc == 8
        assert payload["code"] == "tree_busy"
        assert payload["retryable"] is True
        assert payload["detail"]["exit"] == 8
    finally:
        lock.release_write(token)
        store.close()


def test_release_then_reacquire(app: Path) -> None:
    store = _store(app)
    lock = TreeLock(store, app, org_id="local")
    token = lock.acquire_write()
    lock.release_write(token)
    # after release the tree is free — sync compiles cleanly
    assert run_code(["sync", "--dir", str(app)]) == 0
    store.close()


def test_two_org_isolation(app: Path) -> None:
    """A write lease in org A never blocks org B (tenancy-scoped)."""
    store = _store(app)
    lock_a = TreeLock(store, app, org_id="a")
    token = lock_a.acquire_write()
    try:
        # org b is unaffected — it can take its own read lease
        lock_b = TreeLock(store, app, org_id="b")
        lock_b.acquire_read()  # does not raise
        lock_b.release_read()
        # and a writer in org a blocks a reader in org a
        with pytest.raises(TreeBusy):
            lock_a.acquire_read()
    finally:
        lock_a.release_write(token)
        store.close()


def test_lock_survives_a_fresh_store_handle(app: Path) -> None:
    """The lease is Store-enforced (survives the process boundary), not in-memory."""
    s1 = _store(app)
    lock1 = TreeLock(s1, app, org_id="local")
    token = lock1.acquire_write()
    s1.close()  # writer's process "exits" holding the lease

    # a fresh Store handle still sees the held write lease
    s2 = _store(app)
    lock2 = TreeLock(s2, app, org_id="local")
    with pytest.raises(TreeBusy):
        lock2.acquire_read()
    lock2.release_write(token)
    s2.close()


def test_lock_marker_lives_under_crawfish_locks(app: Path) -> None:
    store = _store(app)
    lock = TreeLock(store, app, org_id="local")
    token = lock.acquire_write()
    assert (app / ".crawfish" / "locks" / "tree.lock").exists()
    lock.release_write(token)
    # released — the marker is cleared (tree free)
    assert not (app / ".crawfish" / "locks" / "tree.lock").exists()
    store.close()
