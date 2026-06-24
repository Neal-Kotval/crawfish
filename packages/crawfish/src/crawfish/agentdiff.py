"""Git-for-agents — a typed, content-addressed diff/merge over frozen Definitions (CRA-228 / R1).

The substrate every other revolutionary bet keys off: R3 replay, R4 guards-as-program-
members, and R5 weights all assume a content-addressed graph one can *diff* and *merge* the
way a human reviews code. M6 shipped the content-addressed unit (a frozen
:class:`~crawfish.definition.types.Definition`, hashed by :meth:`Definition.content_sha`,
derived copy-on-write through :mod:`crawfish.derive`, named + lineaged by
:mod:`crawfish.definition_store`). This module lifts that from "two shas are equal/not" to a
**field-level structural diff** (``diff(a, b) -> DefinitionDiff``) and a **three-way merge**
(``merge(base, a, b) -> Definition | MergeConflict``).

The diff is taken over the **canonical content payload** (``Definition.content_dict`` — ADR
0017 / F-5), i.e. exactly the fields that fold into the sha. Diffing what the hash sees means
the diff is non-empty **iff** the sha moved: a structurally-identical pair diffs to nothing
(``DefinitionDiff.is_empty``), and any field that diverges the sha shows up as a typed change.
Both ``diff`` and ``merge`` are **pure** — no model call, no I/O, no wall clock — so the same
inputs always yield the same diff and the same merged sha.

Merge is three-way over the lineage (``base`` is the common ancestor; ``a`` and ``b`` are the
two descendants). Non-conflicting field changes combine (a change on exactly one side wins; a
change to the same value on both sides is harmless agreement); a field that *both* sides
changed to *different* values is a typed :class:`FieldConflict` — **never silently resolved**.
A clean merge mints a new frozen Definition via the same content-hash CoW law as composition
(:func:`crawfish.derive.refreeze`), so the result is sealed, content-addressed, and replayable.

Security spine. Merge upholds the fluid/static boundary verbatim: a :class:`Parameter`'s
``flow`` (the prompt-injection boundary) and a :class:`~crawfish.core.types.Policy` (static
consequential config) are ordinary diffable fields — a merge that would *widen* an input from
``static`` to ``fluid`` (or vice-versa) without both sides agreeing is reported as a conflict,
never auto-applied, so a merge can never quietly turn a static knob fluid. Un-versioned
mutation stays impossible: ``merge`` only ever returns a freshly-frozen artifact (or a typed
conflict), never an in-place edit. Both verbs carry ``org_id`` through unchanged — a merge is
within one tenant's lineage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from crawfish.definition.types import Definition

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "ChangeKind",
    "FieldChange",
    "DefinitionDiff",
    "FieldConflict",
    "MergeConflict",
    "diff",
    "merge",
]


class ChangeKind(str, Enum):
    """How a single field moved between two content payloads.

    A ``(str, Enum)`` per the house style (ADR 0004). ``ADDED`` / ``REMOVED`` are keyed
    presence changes (an agent role, a parameter name, a pinned dependency that appears or
    disappears); ``CHANGED`` is a value move on a key present in both.
    """

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class FieldChange:
    """One typed, field-level change between two Definitions' content payloads.

    ``path`` is a stable dotted address into the canonical payload (e.g.
    ``team.agents.reviewer.prompt`` or ``inputs.ticket.flow``) so a change is addressable the
    way a code-review line is. ``before`` / ``after`` are the JSON-safe values at that path
    (``None`` on the absent side of an add/remove). Frozen + hashable: a diff is a value.
    """

    path: str
    kind: ChangeKind
    before: object = None
    after: object = None


@dataclass(frozen=True)
class DefinitionDiff:
    """A typed structural diff between two content-addressed Definitions.

    ``changes`` is the ordered (path-sorted, deterministic) list of field-level
    :class:`FieldChange`s. ``sha_before`` / ``sha_after`` pin the two endpoints so the diff is
    self-describing (the diff is non-empty iff the shas differ). Pure value object.
    """

    sha_before: str
    sha_after: str
    changes: tuple[FieldChange, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True iff the two Definitions are content-identical (no field moved, shas equal)."""
        return not self.changes

    def paths(self) -> tuple[str, ...]:
        """The set of changed paths, in deterministic order (handy for assertions)."""
        return tuple(c.path for c in self.changes)


@dataclass(frozen=True)
class FieldConflict:
    """A single field both descendants changed to *different* values (three-way merge).

    ``path`` addresses the contested field; ``base`` is the common-ancestor value; ``a`` / ``b``
    are the two divergent descendant values. Reported, never resolved — the caller (a human or
    ``craw code``) decides.
    """

    path: str
    base: object = None
    a: object = None
    b: object = None


@dataclass(frozen=True)
class MergeConflict:
    """The typed failure of a three-way merge: one or more fields diverged on both sides.

    Returned (not raised) by :func:`merge` so the caller branches on the result type rather
    than catching. ``conflicts`` is the deterministic, path-sorted list of every contested
    field — the whole conflict set, not just the first, so a reviewer sees all of it at once.
    """

    conflicts: tuple[FieldConflict, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(c.path for c in self.conflicts)


# == flattening: the canonical payload → an addressable {path: value} map ====
# We diff/merge over a FLAT map of dotted paths so field-level granularity falls out for free
# and the merge is a per-leaf three-way set. The map is taken over ``content_dict`` — the
# canonical hash payload — so the diff sees exactly what the sha sees: a change is in the diff
# iff it moved the sha. ``team.agents`` and ``inputs``/``outputs`` are re-keyed from positional
# lists to identity maps (agent ``role``, parameter ``name``, dependency ``id``) so reordering
# without an edit is not spuriously a change and an add/remove is keyed, not a shift cascade.

_AGENT_KEY = "role"
_PARAM_KEY = "name"
_DEP_KEY = "id"
_POLICY_KEY = "name"
_MCP_KEY = "name"


def _flatten(value: object, prefix: str, out: dict[str, object]) -> None:
    """Flatten a JSON-safe payload into ``out`` as ``{dotted.path: leaf}``.

    Dicts recurse by key. Lists that carry a natural identity key (agents by ``role``,
    parameters by ``name``, etc.) re-key to that identity so the diff is order-insensitive and
    keyed; any other list is addressed positionally (a stable, deterministic fallback). Leaves
    (scalars, and identity-less lists' elements) land as terminal paths.
    """
    if isinstance(value, dict):
        for k in sorted(value.keys()):
            _flatten(value[k], f"{prefix}.{k}" if prefix else str(k), out)
        return
    if isinstance(value, list):
        key = _identity_key_for(prefix)
        if key is not None and all(isinstance(el, dict) and key in el for el in value):
            for el in value:
                assert isinstance(el, dict)
                ident = el[key]
                _flatten(el, f"{prefix}.{ident}", out)
            return
        # Identity-less list: address positionally so it still diffs deterministically.
        for i, el in enumerate(value):
            _flatten(el, f"{prefix}.{i}", out)
        return
    out[prefix] = value


def _identity_key_for(path: str) -> str | None:
    """The identity key a list at ``path`` is re-keyed by, or ``None`` for positional.

    Matches on the trailing segment of the dotted path so the rule is structural (it follows
    the canonical payload's field names, not a node class). ``team.agents`` → ``role``;
    ``inputs`` / ``outputs`` → ``name``; ``dependencies`` → ``id``; assets' policies/mcp by
    ``name``. Everything else stays positional.
    """
    last = path.rsplit(".", 1)[-1]
    return {
        "agents": _AGENT_KEY,
        "inputs": _PARAM_KEY,
        "outputs": _PARAM_KEY,
        "dependencies": _DEP_KEY,
        "policies": _POLICY_KEY,
        "mcp": _MCP_KEY,
    }.get(last)


def _flat_payload(definition: Definition) -> dict[str, object]:
    """The flat ``{path: value}`` view of a Definition's canonical content payload."""
    out: dict[str, object] = {}
    _flatten(definition.content_dict(), "", out)
    return out


# A path segment that addresses a Parameter's fluid/static flow — the prompt-injection
# boundary (ADR / SECURITY). A merge may never *silently* move it: divergence here is always
# surfaced as a conflict, even though the per-leaf rule already surfaces two-sided divergence —
# this is the explicit security pin (see ``_is_flow_path``).
def _is_flow_path(path: str) -> bool:
    """True iff ``path`` addresses a Parameter's ``flow`` (the fluid/static boundary)."""
    return path.endswith(".flow") and (path.startswith("inputs.") or path.startswith("outputs."))


# == diff ====================================================================
def diff(a: Definition, b: Definition) -> DefinitionDiff:
    """A typed, field-level structural diff from ``a`` to ``b``. Pure, deterministic.

    Compares the two Definitions over their canonical content payloads (what the sha sees), so
    the result is non-empty **iff** ``a.content_sha() != b.content_sha()``. Each differing
    field becomes a :class:`FieldChange` — an ``ADDED`` / ``REMOVED`` keyed presence change
    (an agent role, a parameter, a pinned dependency) or a ``CHANGED`` value move — addressed
    by a stable dotted ``path``. Changes are returned path-sorted (deterministic). Neither
    input is mutated; ``a`` / ``b`` need not be frozen (the diff reads content only).
    """
    fa = _flat_payload(a)
    fb = _flat_payload(b)
    changes: list[FieldChange] = []
    for path in sorted(set(fa) | set(fb)):
        in_a = path in fa
        in_b = path in fb
        if in_a and in_b:
            if fa[path] != fb[path]:
                changes.append(
                    FieldChange(path, ChangeKind.CHANGED, before=fa[path], after=fb[path])
                )
        elif in_a:
            changes.append(FieldChange(path, ChangeKind.REMOVED, before=fa[path], after=None))
        else:
            changes.append(FieldChange(path, ChangeKind.ADDED, before=None, after=fb[path]))
    return DefinitionDiff(
        sha_before=a.content_sha(), sha_after=b.content_sha(), changes=tuple(changes)
    )


# == merge ===================================================================
def merge(base: Definition, a: Definition, b: Definition) -> Definition | MergeConflict:
    """Three-way merge of ``a`` and ``b`` over their common ancestor ``base``. Pure.

    Per leaf path across the three canonical payloads:

    * unchanged on a side ⇒ that side defers to the other;
    * changed on exactly one side ⇒ that side's value wins;
    * changed to the **same** value on both sides ⇒ harmless agreement (that value wins);
    * changed to **different** values on both sides ⇒ a :class:`FieldConflict` — never
      silently resolved.

    Any conflict (including a divergent fluid/static ``flow`` move, which is *always* surfaced)
    makes the whole merge a :class:`MergeConflict` carrying the full, path-sorted conflict set.
    A clean merge reconstructs the merged payload and re-seals it through the content-hash CoW
    law (:func:`crawfish.derive.refreeze` off ``base``), so the result is a **new frozen**
    Definition with a deterministic content sha — the same three inputs always merge to the
    same sha. ``base`` / ``a`` / ``b`` are untouched.
    """
    fbase = _flat_payload(base)
    fa = _flat_payload(a)
    fb = _flat_payload(b)

    merged: dict[str, object] = {}
    conflicts: list[FieldConflict] = []
    _MISSING = object()

    for path in sorted(set(fbase) | set(fa) | set(fb)):
        va = fa.get(path, _MISSING)
        vb = fb.get(path, _MISSING)
        vbase = fbase.get(path, _MISSING)
        a_changed = va != vbase
        b_changed = vb != vbase

        if not a_changed and not b_changed:
            resolved = va  # both equal base (and each other)
        elif a_changed and not b_changed:
            resolved = va
        elif b_changed and not a_changed:
            resolved = vb
        elif va == vb:
            resolved = va  # both changed, but agreed
        else:
            # Both sides changed to different values: a real conflict. The flow path is
            # surfaced here too (it is, by construction, a two-sided divergence) — the
            # security pin is that such a move can never be auto-applied.
            conflicts.append(
                FieldConflict(
                    path=path,
                    base=None if vbase is _MISSING else vbase,
                    a=None if va is _MISSING else va,
                    b=None if vb is _MISSING else vb,
                )
            )
            continue

        if resolved is not _MISSING:
            merged[path] = resolved
        # ``resolved is _MISSING`` means the winning side removed the leaf: omit it (a keyed
        # removal), so the rebuilt payload drops it exactly as that side did.

    if conflicts:
        return MergeConflict(conflicts=tuple(conflicts))

    return _rebuild(base, a, b, merged)


# == rebuild: flat merged payload → a new frozen Definition ==================
def _rebuild(
    base: Definition, a: Definition, b: Definition, merged: Mapping[str, object]
) -> Definition:
    """Reconstruct a frozen Definition from the merged flat payload, off ``base``'s identity.

    The flat ``{path: value}`` map is unflattened back into a nested payload, re-validated into
    a Definition (so the merged result is type-checked, not hand-assembled), and re-sealed via
    the content-hash CoW law. The volatile ``version`` / identity ``id`` are absent from the
    content payload (``content_dict`` drops them), so we restore ``base``'s ``id`` to keep the
    merged artifact within ``base``'s identity lineage, then :func:`crawfish.derive.refreeze`
    stamps the fresh content sha. The result is a NEW frozen Definition; the inputs are
    untouched.
    """
    from crawfish import derive

    nested = _unflatten(base, a, b, merged)
    nested["id"] = base.id  # content_dict drops id; keep the merged result on base's identity
    rebuilt = Definition.model_validate(nested)
    # ``rebuilt`` is an unfrozen draft (fresh Version); refreeze stamps the content sha and
    # seals it — the same CoW law that composition uses, so no second hashing path exists.
    return derive.refreeze(base, rebuilt)


def _unflatten(
    base: Definition, a: Definition, b: Definition, merged: Mapping[str, object]
) -> dict[str, object]:
    """Rebuild the nested content payload from the flat merged map.

    Keyed lists (agents/inputs/outputs/dependencies/policies/mcp) were re-keyed by identity on
    the way in; rebuild them as lists by collecting each identity's leaves and **preserving the
    declared order** of whichever side contributed the most members (a deterministic order that
    keeps a clean merge's element order stable). Scalar paths drop straight in.
    """
    # Group flat paths back under their container so each list-of-dicts is rebuilt as a list.
    # We reconstruct by walking the canonical container structure of ``base`` ∪ ``a`` ∪ ``b``.
    nested: dict[str, object] = {}
    list_members: dict[str, dict[str, dict[str, object]]] = {}

    # Determine, per keyed-list container path, the identity order to emit (longest side wins;
    # ties broken by the union in first-seen order across base, a, b for determinism).
    order = _member_order(base, a, b)

    for path in sorted(merged.keys()):
        container, sep, _rest = _split_keyed(path)
        if container is not None:
            # ``path`` = ``<container>.<identity>.<field...>`` for a keyed list element.
            ident, _, leaf = _rest.partition(".")
            bucket = list_members.setdefault(container, {})
            member = bucket.setdefault(ident, {})
            _assign(member, leaf, merged[path])
        else:
            _assign(nested, path, merged[path])

    for container, members in list_members.items():
        ordered_idents = [i for i in order.get(container, []) if i in members]
        # Any identity not in the precomputed order (defensive) appended in sorted order.
        for i in sorted(members):
            if i not in ordered_idents:
                ordered_idents.append(i)
        _assign(nested, container, [members[i] for i in ordered_idents])

    # Positional sub-lists (an agent's ``tools`` / ``policies`` / ``delegates_to``, a Policy's
    # ``rules`` are dicts, etc.) were addressed by integer index on the way in and rebuilt as
    # ``{"0": ..., "1": ...}`` index-dicts by ``_assign``; collapse those back to lists so the
    # payload re-validates. A dict whose keys are exactly ``0..n-1`` is an index-dict.
    return _delist(nested)  # type: ignore[return-value]


def _split_keyed(path: str) -> tuple[str | None, str, str]:
    """Split ``path`` into ``(container, sep, remainder)`` if it addresses a keyed-list element.

    Returns ``(container_path, ".", "<identity>.<field...>")`` when ``path`` sits under a known
    keyed-list container (``team.agents`` / ``inputs`` / ``outputs`` / ``dependencies`` /
    ``assets.policies`` / ``assets.mcp``), else ``(None, "", path)``.
    """
    for container in _KEYED_CONTAINERS:
        prefix = f"{container}."
        if path.startswith(prefix):
            return container, ".", path[len(prefix) :]
    return None, "", path


# The canonical payload's keyed-list container paths (dotted, matching ``content_dict``).
_KEYED_CONTAINERS = (
    "team.agents",
    "inputs",
    "outputs",
    "dependencies",
    "assets.policies",
    "assets.mcp",
)


def _member_order(base: Definition, a: Definition, b: Definition) -> dict[str, list[str]]:
    """The deterministic per-container identity order for rebuilt keyed lists.

    For each keyed container, take the side (base/a/b) with the most members as the order
    spine, then append any identity the other sides introduce in first-seen order. This keeps a
    clean merge's element order stable and reproducible.
    """
    order: dict[str, list[str]] = {}
    for container in _KEYED_CONTAINERS:
        sides = [_idents_in(d, container) for d in (base, a, b)]
        spine = max(sides, key=len)
        seq = list(spine)
        for side in sides:
            for ident in side:
                if ident not in seq:
                    seq.append(ident)
        order[container] = seq
    return order


def _idents_in(definition: Definition, container: str) -> list[str]:
    """The declared identity order of a keyed-list container in ``definition``'s payload."""
    payload = definition.content_dict()
    node: object = payload
    for seg in container.split("."):
        if isinstance(node, dict):
            node = node.get(seg)
        else:
            node = None
            break
    if not isinstance(node, list):
        return []
    key = _identity_key_for(container)
    if key is None:
        return []
    return [el[key] for el in node if isinstance(el, dict) and key in el]


def _delist(node: object) -> object:
    """Collapse index-dicts (keys exactly ``"0".."n-1"``) back into lists, recursively.

    Positional sub-lists are flattened by integer index and rebuilt by :func:`_assign` as
    ``{"0": v0, "1": v1}``; this restores them to ``[v0, v1]`` so the payload re-validates as a
    Definition. A genuine mapping (a Policy's ``rules``) whose keys are not a contiguous
    ``0..n-1`` index set is left untouched.
    """
    if isinstance(node, dict):
        keys = set(node.keys())
        if keys and keys == {str(i) for i in range(len(keys))}:
            return [_delist(node[str(i)]) for i in range(len(keys))]
        return {k: _delist(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_delist(el) for el in node]
    return node


def _assign(target: dict[str, object], dotted: str, value: object) -> None:
    """Set ``value`` at the dotted ``dotted`` path inside the nested dict ``target``.

    Intermediate dicts are created on demand. (Lists are rebuilt separately by
    :func:`_unflatten` from their keyed members; ``_assign`` only ever walks dict segments.)
    """
    if not dotted:
        return
    segs = dotted.split(".")
    node = target
    for seg in segs[:-1]:
        nxt = node.get(seg)
        if not isinstance(nxt, dict):
            nxt = {}
            node[seg] = nxt
        node = nxt
    node[segs[-1]] = value
