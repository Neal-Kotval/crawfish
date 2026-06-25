"""CRA-278 — authoring-tree advisory lock (read-during-edit consistency).

The self-generating loop edits a file while ``craw code sync``/``run`` compiles it. A
half-written ``definition.py`` compiles to the **wrong** content sha → a corrupt run
identity (§12.3): an unreviewed edit could ride a previously-signed sha. The fix is an
**advisory read/write lock** over the authored tree so a torn tree is *refused*, not
compiled.

* A **writer** (``craw code new``, an Edit) takes a short **exclusive** lease around the
  write+fsync.
* A **reader** (``sync``/``describe``/``map``) takes a **shared** lease around
  ``load_definition``. If it cannot acquire the shared lease — a write is in flight — it
  raises :class:`TreeBusy`, mapped to the spec's ``tree_busy`` (exit 8), rather than
  compiling a torn file.

The lock is keyed on ``(org_id, project_dir)`` and **Store-backed** (it survives the
process boundary and is tenancy-scoped: org A's lock never blocks org B). Because the
``Store`` protocol exposes no borrow/lease primitive (the spec's "verify name" resolved:
no such method exists on the protocol — see the spec correction in the spec file), the lease
state rides the protocol's ``kv_get``/``kv_set`` under a dedicated namespace, with the lock
record mirrored under ``.crawfish/locks/`` (generated state — excluded from the Definition
sha). Determinism: the lease primitive is driven directly (no real thread races), exactly as
the test plan requires.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from crawfish.core.ids import new_id

if TYPE_CHECKING:
    from collections.abc import Iterator

    from crawfish.store.base import Store

__all__ = ["TreeBusy", "TreeLock", "LockState"]

#: The kv namespace the lease state lives under (Store-backed, tenancy-scoped).
_LOCK_NAMESPACE = "craw_code_tree_lock"

#: Where the human-visible lock marker lives (generated state — never authored, excluded
#: from the Definition content sha via the compiler's ``.crawfish`` exclusion).
_LOCK_DIR = Path(".crawfish") / "locks"


class TreeBusy(RuntimeError):
    """Raised when a lease cannot be acquired because the tree is being written.

    Surfaced as the spec's ``tree_busy`` (granular code 8 in ``detail.exit``,
    ``retryable:true`` — a transient contention, safe to retry) with the PROCESS exit on the
    CRA-243 expected-failure family (1): a compile concurrent with an in-flight write returns
    this rather than compiling a torn (wrong-sha) Definition.
    """


@dataclass(frozen=True)
class LockState:
    """The current lease over a project tree (the persisted advisory record).

    ``mode`` is ``"write"`` (exclusive) or ``"read"`` (shared, with a holder count).
    ``token`` identifies the writer for release. ``readers`` counts active shared leases.
    An empty/absent state means the tree is free.
    """

    mode: str = ""  # "" | "read" | "write"
    token: str = ""
    readers: int = 0

    @property
    def free(self) -> bool:
        return self.mode == "" or (self.mode == "read" and self.readers == 0)


class TreeLock:
    """A Store-backed advisory read/write lock over one project tree (CRA-278).

    Keyed on ``(org_id, project_dir)``. The lease state is a single kv record (so it is
    atomic per Store write and tenancy-scoped); a mirror marker under ``.crawfish/locks/``
    makes a held lock visible to ``craw doctor``'s torn-tree check.
    """

    def __init__(self, store: Store, project_dir: str | Path, *, org_id: str = "local") -> None:
        self._store = store
        self._root = Path(project_dir)
        self._org_id = org_id
        self._key = str(self._root.resolve())

    # -- state read/write -----------------------------------------------------
    def _read(self) -> LockState:
        raw = self._store.kv_get(_LOCK_NAMESPACE, self._key, org_id=self._org_id)
        if not isinstance(raw, dict):
            return LockState()
        return LockState(
            mode=str(raw.get("mode", "")),
            token=str(raw.get("token", "")),
            readers=int(raw.get("readers", 0) or 0),
        )

    def _write(self, state: LockState) -> None:
        self._store.kv_set(
            _LOCK_NAMESPACE,
            self._key,
            {"mode": state.mode, "token": state.token, "readers": state.readers},
            org_id=self._org_id,
        )
        self._mirror(state)

    def _mirror(self, state: LockState) -> None:
        """Mirror the lock state under ``.crawfish/locks/`` (doctor's torn-tree signal)."""
        marker = self._root / _LOCK_DIR / "tree.lock"
        if state.free:
            marker.unlink(missing_ok=True)
            return
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{state.mode}:{state.token}:{state.readers}\n")

    # -- exclusive (writer) lease --------------------------------------------
    def acquire_write(self) -> str:
        """Take the exclusive write lease, or raise :class:`TreeBusy` if the tree is held.

        Returns the lease ``token`` used to release. A write lease is refused while any
        reader or another writer holds the tree (exclusive).
        """
        state = self._read()
        if not state.free:
            raise TreeBusy(f"tree {self._key!r} is busy ({state.mode} lease held)")
        token = new_id()
        self._write(LockState(mode="write", token=token, readers=0))
        return token

    def release_write(self, token: str) -> None:
        """Release the write lease identified by ``token`` (a no-op if not held by it)."""
        state = self._read()
        if state.mode == "write" and state.token == token:
            self._write(LockState())

    @contextmanager
    def write_lease(self) -> Iterator[None]:
        """Context manager around a writer's write+fsync (exclusive)."""
        token = self.acquire_write()
        try:
            yield
        finally:
            self.release_write(token)

    # -- shared (reader) lease ------------------------------------------------
    def acquire_read(self) -> None:
        """Take a shared read lease, or raise :class:`TreeBusy` if a writer holds the tree."""
        state = self._read()
        if state.mode == "write":
            raise TreeBusy(f"tree {self._key!r} is busy (write lease in flight)")
        self._write(LockState(mode="read", token="", readers=state.readers + 1))

    def release_read(self) -> None:
        """Drop one shared read lease."""
        state = self._read()
        if state.mode == "read":
            remaining = max(0, state.readers - 1)
            if remaining:
                self._write(LockState(mode="read", token="", readers=remaining))
            else:
                self._write(LockState())

    @contextmanager
    def read_lease(self) -> Iterator[None]:
        """Context manager around a reader's ``load_definition`` (shared).

        Raises :class:`TreeBusy` (→ exit 8) if a write is in flight, so a torn tree is
        refused rather than compiled to a wrong sha.
        """
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()
