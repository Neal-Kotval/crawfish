"""``DefinitionStore`` — git for Definitions (CRA-225 / AL-DV2, CRA-226 / AL-DV3).

Composition (``with_*`` in :mod:`crawfish.derive`) gives content **hashes** but no
**names**. Git's ergonomic is a *mutable name pointer* into an *append-only, immutable,
content-addressed object store*. Crawfish already has the immutable side (a frozen
:class:`~crawfish.definition.types.Definition` is content-addressed by
:meth:`Definition.content_sha`); this module adds the name registry and the version log,
i.e. ``save`` / ``recall`` / ``log`` (AL-DV2) and ``modify`` / ``reset`` (AL-DV3).

The three storage planes (every row ``org_id``-scoped — a name in org A is invisible to
org B):

* **object store** — ``kind="definition_object"``, keyed by the content sha. Append-only and
  content-addressed: byte-identical Definitions collapse to one stored object (dedup). A
  re-``save`` of an already-stored sha is a no-op on the object (idempotent on sha).
* **name pointer** — ``kind="definition_name"``, keyed by ``name``. The **one mutable row**:
  a ``save`` overwrites it to point at the new sha (a git branch tip move). Everything else
  is append-only.
* **version log** — ``kind="definition_version"``, one append-only event per ``save`` keyed
  by a deterministic event id. Carries the ``parent_sha`` lineage edge. Byte-identical
  Definitions saved twice store the object **once** but record **two** pointer events.

Determinism (the whole module is pure data — **no model call, no wall clock**):

* The pointer move is the *sole* mutation; the object store is append-only + content-
  addressed; ``recall`` is pure and **never mints a new sha** (it reads a stored object).
* ``modify`` = ``recall → fn → save(parent=old_sha)`` routed through the same
  ``with_*``/``_refreeze`` content-hash law as composition, so the same start + a pure ``fn``
  yields the same resulting sha. ``reset`` mints **no** object — a pure pointer move (git
  checkout), reversible, and refuses a target unreachable from the name's log.

Security / versioning spine: ``save`` requires a **frozen** (eval-mode) Definition —
un-versioned mutation is impossible because the only way in is a sealed, content-hashed
artifact. ``modify`` is legal only in **train mode**: an eval-mode name is read-only and
``modify`` raises (AL-DV3). Reading is **data-only** — a recalled Definition is context, not
an instruction surface.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from pydantic import BaseModel

from crawfish.definition.types import Definition
from crawfish.store.base import Store
from crawfish.versioning.version import FrozenError

__all__ = [
    "DefinitionVersion",
    "DefinitionStore",
    "UnfrozenDefinitionError",
    "UnknownNameError",
    "UnreachableShaError",
    "modify",
    "reset",
]

# Store ``kind`` namespaces. Three planes, one object store + one mutable pointer plane +
# one append-only event log — all ``org_id``-scoped by the underlying :class:`Store`.
_OBJECT_KIND = "definition_object"
_NAME_KIND = "definition_name"
_VERSION_KIND = "definition_version"


class UnfrozenDefinitionError(ValueError):
    """``save`` was handed a Definition that is not frozen (eval-mode).

    Un-versioned mutation is forbidden: a name pointer may only ever point at a sealed,
    content-hashed artifact, so ``save`` rejects an unfrozen draft. Freeze (or re-freeze via
    a ``with_*`` derivation) first.
    """


class UnknownNameError(KeyError):
    """``recall`` / ``log`` / ``modify`` / ``reset`` referenced a name with no pointer.

    A name only exists once ``save`` has recorded a pointer for it in this ``org_id``; a name
    saved in another org is invisible (cross-tenant isolation).
    """


class UnreachableShaError(ValueError):
    """``reset`` was asked to move a name to a sha that is not in that name's log.

    ``reset`` is a git checkout: it may only rewind to a version actually recorded for the
    name (so the pointer never lands on content the lineage never produced).
    """


class DefinitionVersion(BaseModel):
    """One append-only point in a name's version log — the lineage edge (CRA-225).

    A ``save`` records exactly one of these. It mirrors the lineage shape of
    :class:`crawfish.learning.VersionRecord` (``sha`` + ``parent_sha`` + the frozen
    ``definition``) but is a distinct, **purely append-only** record: it carries no mutable
    ``active`` flag (the *name* row is the single mutable pointer here, not a per-version
    bit) and no eval ``scores`` (a name registry is not a tuner lineage). Keeping them
    separate avoids coupling a git-style pointer log to the LearningLoop's promotion state.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str  # the name this version was saved under
    sha: str  # the saved Definition's content sha (the object-store + lineage key)
    version: str  # the human-readable ``str(Version)`` (``major.minor-sha``)
    parent_sha: str | None = None  # the version this one was derived from (lineage edge)
    seq: int  # monotonically increasing per (org, name) — recording order


class DefinitionStore:
    """A Store-backed, append-only, org-scoped name→hash registry for Definitions.

    Git for Definitions: a mutable name pointer over an append-only, content-addressed object
    store. ``save`` moves the pointer (the only mutation) and appends a lineage event;
    ``recall`` resolves ``name`` (latest) or ``name@sha`` / a bare sha (a pinned historical
    version) by reading a stored object — it never mints a sha. Every row is ``org_id``-scoped
    via the underlying :class:`Store`, so a name in org A is invisible to org B.
    """

    def __init__(self, store: Store, *, org_id: str = "local") -> None:
        self.store = store
        self.org_id = org_id

    # -- object store (append-only, content-addressed, dedup) ---------------
    def _put_object(self, definition: Definition) -> str:
        """Store ``definition``'s frozen body under its content sha; return the sha.

        Content-addressed + idempotent: a byte-identical Definition collapses to the same sha
        and overwrites the same row with the same bytes (dedup — stored once however many
        times saved). The stored payload is the model dump; ``recall`` rebuilds the frozen
        artifact from it.
        """
        sha = definition.content_sha()
        # ``model_dump(mode="json")`` is JSON-safe; the object row is keyed by the sha, so a
        # re-put of the same content is a deterministic no-op (same key, same bytes).
        self.store.put_record(
            _OBJECT_KIND,
            sha,
            {"definition": definition.model_dump(mode="json")},
            org_id=self.org_id,
        )
        return sha

    def _get_object(self, sha: str) -> Definition | None:
        raw = self.store.get_record(_OBJECT_KIND, sha, org_id=self.org_id)
        if raw is None:
            return None
        body = raw["definition"]
        if not isinstance(body, dict):  # defensive: malformed row
            return None
        defn = Definition.model_validate(body)
        # A stored object is always a sealed artifact — re-seal the reconstructed instance so
        # the recalled Definition is frozen (eval-mode) exactly as it was saved.
        if not defn.frozen:
            defn.freeze()
        return defn

    # -- name pointer (the SOLE mutable plane) ------------------------------
    def _pointer(self, name: str) -> str | None:
        raw = self.store.get_record(_NAME_KIND, name, org_id=self.org_id)
        if raw is None:
            return None
        sha = raw.get("sha")
        return sha if isinstance(sha, str) else None

    def _move_pointer(self, name: str, sha: str) -> None:
        """Move the name pointer to ``sha`` — the one and only mutation in this module."""
        self.store.put_record(_NAME_KIND, name, {"sha": sha}, org_id=self.org_id)

    # -- version log (append-only lineage) ----------------------------------
    def _version_id(self, name: str, seq: int) -> str:
        """A deterministic, collision-free event id for the (name, seq) lineage event.

        Keyed on (org, name, seq) so two byte-identical Definitions saved under one name
        record two *distinct* pointer events (same sha, different seq) — the AC that dedup on
        the object plane must not dedup the pointer log.
        """
        blob = json.dumps({"org": self.org_id, "name": name, "seq": seq}, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def _append_version(self, rec: DefinitionVersion) -> None:
        self.store.put_record(
            _VERSION_KIND,
            self._version_id(rec.name, rec.seq),
            rec.model_dump(mode="json"),
            org_id=self.org_id,
        )

    def log(self, name: str) -> list[DefinitionVersion]:
        """The full append-only version lineage for ``name``, oldest → newest.

        Raises :class:`UnknownNameError` if ``name`` has no pointer in this org. The returned
        chain carries the ``parent_sha`` edges (each non-root version names the version it was
        derived from), ordered by recording ``seq``.
        """
        if self._pointer(name) is None:
            raise UnknownNameError(name)
        records = [
            DefinitionVersion.model_validate(r)
            for r in self.store.list_records(_VERSION_KIND, org_id=self.org_id)
        ]
        return sorted((r for r in records if r.name == name), key=lambda r: r.seq)

    def _next_seq(self, name: str) -> int:
        """The next recording sequence number for ``name`` (0 for the first save)."""
        records = [
            DefinitionVersion.model_validate(r)
            for r in self.store.list_records(_VERSION_KIND, org_id=self.org_id)
        ]
        seqs = [r.seq for r in records if r.name == name]
        return (max(seqs) + 1) if seqs else 0

    # -- the public verbs ---------------------------------------------------
    def save(self, name: str, definition: Definition, *, parent: str | None = None) -> str:
        """Record ``name → definition.content_sha`` and append a lineage event; return the sha.

        Requires a **frozen** (eval-mode) Definition — un-versioned mutation is impossible
        because only a sealed, content-hashed artifact may be saved (raises
        :class:`UnfrozenDefinitionError` otherwise). The object is stored content-addressed
        (dedup: byte-identical content stored once); the name pointer **moves** to the new sha
        (the sole mutation); a :class:`DefinitionVersion` event is appended with the
        ``parent`` lineage edge. Byte-identical Definitions saved twice store the object once
        but record two pointer events.

        ``parent`` is the prior sha this version derives from (the lineage edge);
        :func:`modify` passes the old sha so ``log`` reconstructs the chain.
        """
        if not definition.frozen:
            raise UnfrozenDefinitionError(
                f"save({name!r}) requires a frozen (eval-mode) Definition; freeze or re-freeze "
                "via a with_* derivation first"
            )
        sha = self._put_object(definition)
        seq = self._next_seq(name)
        self._append_version(
            DefinitionVersion(
                name=name,
                sha=sha,
                version=str(definition.version),
                parent_sha=parent,
                seq=seq,
            )
        )
        # The pointer move is recorded LAST: the object + lineage event exist before any name
        # resolves to the new sha, so a reader never sees a pointer to an absent object.
        self._move_pointer(name, sha)
        return sha

    def recall(self, name: str, *, sha: str | None = None) -> Definition:
        """Resolve a Definition by name (latest) or a pinned historical ``sha``. Pure.

        ``recall(name)`` returns the object the name pointer currently names (the latest
        saved version). ``recall(name, sha=...)`` returns that exact historical version — it
        stays recallable after the name pointer moves on (object store is append-only). A
        ``name@sha`` string is also accepted as ``name`` for ergonomics.

        Reading is **data-only** and **never mints a sha**: it reads a stored object and
        re-seals it frozen. Raises :class:`UnknownNameError` for an unknown name (or a bare
        sha / ``name@sha`` whose object is absent in this org).
        """
        # ``name@sha`` ergonomic: split a single-string pin into (name, sha).
        if sha is None and "@" in name:
            name, _, sha = name.partition("@")

        if sha is not None:
            # A pinned version: read the exact object. (Resolving by sha is name-independent —
            # the name only had to *have produced* it, which append-only history guarantees.)
            defn = self._get_object(sha)
            if defn is None:
                raise UnknownNameError(f"{name}@{sha}")
            return defn

        pointer = self._pointer(name)
        if pointer is None:
            # A bare sha passed positionally (no pointer of that literal name): try the object
            # store before giving up, so ``recall(some_sha)`` resolves a content-addressed pin.
            bare = self._get_object(name)
            if bare is not None:
                return bare
            raise UnknownNameError(name)
        defn = self._get_object(pointer)
        if defn is None:  # pragma: no cover - pointer always written after its object
            raise UnknownNameError(f"{name}@{pointer}")
        return defn

    def head(self, name: str) -> str:
        """The sha the name pointer currently names. Raises :class:`UnknownNameError`."""
        pointer = self._pointer(name)
        if pointer is None:
            raise UnknownNameError(name)
        return pointer


# == module-level verbs (AL-DV3) ============================================
# ``modify`` / ``reset`` are free functions taking the store first, matching the issue's
# ``modify(store, name, fn)`` / ``reset(store, name, to)`` shape. They compose the
# DefinitionStore verbs above; they own no new persistence law.


def modify(
    store: DefinitionStore,
    name: str,
    fn: Callable[[Definition], Definition],
) -> str:
    """Git-style branch-local edit: ``recall → fn → save(parent=old_sha)``. Returns new sha.

    ``fn`` composes via the ``with_*`` derivation operators (each returns a **new frozen**
    Definition), so the result is already sealed and content-hashed; ``modify`` saves it with
    the prior sha as the ``parent`` lineage edge. The pointer advances to the new content and
    the old sha stays recallable via ``recall(name, sha=old)`` (append-only history).

    **Train mode only**: a recalled, frozen (eval-mode) name is read-only, so an ``fn`` that
    tries to edit it in place raises :class:`~crawfish.versioning.version.FrozenError` — the
    AC that ``modify`` on an eval-mode name raises. Compose with ``with_*`` (copy-on-write)
    instead of mutating. Deterministic: the same start + a pure ``fn`` ⇒ the same resulting
    sha.

    Raises :class:`UnknownNameError` if ``name`` has no pointer; :class:`UnfrozenDefinitionError`
    if ``fn`` returns an unfrozen draft.
    """
    old_sha = store.head(name)
    current = store.recall(name)
    mutated = fn(current)
    if not mutated.frozen:
        raise UnfrozenDefinitionError(
            f"modify({name!r}): fn must return a frozen Definition (compose via with_*, which "
            "re-freezes); got an unfrozen draft"
        )
    return store.save(name, mutated, parent=old_sha)


def reset(store: DefinitionStore, name: str, to: str) -> str:
    """Git checkout: move the name pointer back to a prior recorded ``to`` sha. Returns it.

    A **pure pointer move** — it mints no content (no new object, no new lineage event), is
    reversible, and refuses a ``to`` that is not in ``log(name)`` (raises
    :class:`UnreachableShaError`). After ``reset``, ``recall(name)`` and the original
    ``recall(name, sha=to)`` return content-equal Definitions.

    Raises :class:`UnknownNameError` if ``name`` has no pointer.
    """
    reachable = {v.sha for v in store.log(name)}  # raises UnknownNameError if name is unknown
    if to not in reachable:
        raise UnreachableShaError(
            f"reset({name!r}, {to!r}): sha is not in the name's log (reachable: "
            f"{sorted(reachable)})"
        )
    store._move_pointer(name, to)
    return to


# ``FrozenError`` is re-exported in the module namespace for callers that catch the
# train-mode read-only error from ``modify`` without reaching into ``versioning``.
_ = FrozenError
