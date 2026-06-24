"""Dependency resolver + lockfile for summoned units (OPT-4 / CRA-222).

A Definition may *summon* other units by reference (``DefinitionRef.id`` at a version
constraint). Replay reproducibility demands that the **transitive closure** of those
references be pinned to a concrete ``(version, content-sha)`` solution — an unpinned
closure lets an un-versioned mutation silently enter a frozen run.

:func:`resolve` walks ``root.dependencies`` transitively, matches each
``DefinitionRef.version`` (an exact pin or a ``^``/``~`` range) against candidates drawn
from an **injected** :class:`CandidateSource`, picks the highest compatible version,
detects conflicts and cycles, and returns a :class:`Lockfile` pinning every transitive
ref to an exact version plus ``sha256:`` integrity. It is **pure and offline**: no model
call, no network, deterministic ordering (sort by ``(id, version)``) — identical inputs
yield an identical :meth:`Lockfile.closure_sha` across machines.

The :class:`Lockfile` round-trips to/from a plain JSON dict (``to_dict`` / ``from_dict``);
reading a lockfile is **data-only** and never executes unit code. ``closure_sha()`` is one
hash over the sorted pin set — a run embeds this *reference*, keeping run identity small
(vision §5 reference-by-version). Per spine discipline the recorded closure carries
``org_id`` (defaulted ``"local"``); the pins themselves are content-addressed and
org-agnostic.

SemVer comparison is a pure-Python comparator (no new third-party dependency, ADR
discipline). v1 supports exact pins and the ``^`` / ``~`` ranges only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from crawfish.definition.types import DefinitionRef

__all__ = [
    "SemVer",
    "Candidate",
    "CandidateSource",
    "InMemoryCandidateSource",
    "Pin",
    "Lockfile",
    "ResolutionError",
    "resolve",
    "read_lockfile",
    "write_lockfile",
    "LOCKFILE_VERSION",
]

# Bumped whenever the lockfile on-disk schema changes incompatibly.
LOCKFILE_VERSION = 1

# A version core is ``MAJOR.MINOR`` or ``MAJOR.MINOR.PATCH`` (a missing component is 0).
# A trailing ``-sha`` (as ``str(Version)`` renders) is captured but ignored for ordering;
# the content sha is the authoritative integrity anchor in the pin, not the label.
_VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9a-zA-Z]+))?$")
_CONSTRAINT_RE = re.compile(r"^([\^~]?)\s*(.+)$")


class ResolutionError(Exception):
    """An unsatisfiable or conflicting constraint set. Fails closed.

    Carries the offending ``id`` and (for conflicts) the two requirers, so the message
    names both sides of the conflict per the acceptance criteria.
    """


@dataclass(frozen=True, order=True)
class SemVer:
    """A ``MAJOR.MINOR.PATCH`` semantic version; the comparator the resolver orders by.

    Ordering is the dataclass field order (major, then minor, then patch) — exactly
    SemVer precedence for the v1 ``X.Y.Z`` subset. The optional content ``sha`` label is
    *not* part of identity or ordering (it is metadata on the rendered string); pin
    integrity lives in :class:`Pin`, not here.
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> SemVer:
        m = _VERSION_RE.match(text.strip())
        if m is None:
            raise ResolutionError(f"not a valid version: {text!r}")
        major = int(m.group(1))
        minor = int(m.group(2)) if m.group(2) is not None else 0
        patch = int(m.group(3)) if m.group(3) is not None else 0
        return cls(major, minor, patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def _satisfies(version: SemVer, op: str, base: SemVer) -> bool:
    """Does ``version`` satisfy the constraint ``op base``?

    * ``""``  exact: equal on (major, minor, patch).
    * ``"^"`` caret: same leading non-zero (``^1.2`` -> ``1.x >= 1.2``; ``^0.2`` ->
      ``0.2.x >= 0.2`` since 0.x treats minor as the breaking component).
    * ``"~"`` tilde: same major+minor (``~1.2`` -> ``1.2.x``).
    """
    if op == "":
        return version == base
    if version < base:
        return False
    if op == "~":
        return version.major == base.major and version.minor == base.minor
    if op == "^":
        if base.major > 0:
            return version.major == base.major
        # 0.x: the minor is the breaking axis; 0.0.z pins exact-ish on patch axis.
        if base.minor > 0:
            return version.major == 0 and version.minor == base.minor
        return version.major == 0 and version.minor == 0
    raise ResolutionError(f"unknown constraint operator: {op!r}")


@dataclass(frozen=True)
class _Constraint:
    """A parsed ``DefinitionRef.version`` constraint (operator + base version)."""

    op: str  # "" | "^" | "~"
    base: SemVer
    raw: str

    @classmethod
    def parse(cls, text: str) -> _Constraint:
        m = _CONSTRAINT_RE.match(text.strip())
        if m is None:
            raise ResolutionError(f"not a valid constraint: {text!r}")
        op, rest = m.group(1), m.group(2)
        return cls(op=op, base=SemVer.parse(rest), raw=text.strip())

    def matches(self, version: SemVer) -> bool:
        return _satisfies(version, self.op, self.base)


@dataclass(frozen=True)
class Candidate:
    """One concrete, available version of a summonable unit.

    ``content_sha`` is the unit's content hash (e.g. ``Definition.content_sha()``) — the
    integrity anchor the pin records. ``dependencies`` is *this* candidate's own summoned
    refs, so the resolver can walk the transitive closure offline.
    """

    id: str
    version: SemVer
    content_sha: str
    dependencies: tuple[DefinitionRef, ...] = ()


@runtime_checkable
class CandidateSource(Protocol):
    """Injected, offline source of resolvable candidates (the resolver never reads disk
    or the network itself — the registry/store is passed in).

    :meth:`candidates` returns every known version of ``unit_id``; the resolver picks the
    highest one satisfying the active constraint. An empty list means *unknown unit* and
    fails the resolve closed.
    """

    def candidates(self, unit_id: str) -> list[Candidate]: ...


@dataclass
class InMemoryCandidateSource:
    """A plain in-memory :class:`CandidateSource` — the default, and what tests inject.

    Pass a mapping of ``unit_id -> [Candidate, ...]``. Deterministic: candidates are
    returned highest-version-first regardless of insertion order.
    """

    by_id: dict[str, list[Candidate]] = field(default_factory=dict)

    def add(self, candidate: Candidate) -> None:
        self.by_id.setdefault(candidate.id, []).append(candidate)

    def candidates(self, unit_id: str) -> list[Candidate]:
        return sorted(self.by_id.get(unit_id, ()), key=lambda c: c.version, reverse=True)


@dataclass(frozen=True, order=True)
class Pin:
    """One resolved unit in a lockfile: its id pinned to an exact version + integrity.

    ``order=True`` (id, version, integrity) gives the deterministic closure ordering the
    ``closure_sha`` hashes over. ``integrity`` is ``"sha256:<content-sha>"``.
    """

    id: str
    version: str  # exact "MAJOR.MINOR.PATCH"
    integrity: str  # "sha256:<content_sha>"

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "version": self.version, "integrity": self.integrity}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Pin:
        return cls(id=str(d["id"]), version=str(d["version"]), integrity=str(d["integrity"]))


@dataclass
class Lockfile:
    """The pinned transitive closure of a resolve — reproducible and committable.

    ``pins`` is the full solution (including the root). ``closure_sha()`` is one sha256
    over the sorted pin set: a run embeds *this reference*, so run identity stays small
    and a single hash detects any drift in the closure. ``org_id`` scopes the recorded
    closure per the tenancy spine; it does **not** enter the pins (which are
    content-addressed and org-agnostic) so the same closure resolves identically across
    tenants.
    """

    root_id: str
    pins: list[Pin] = field(default_factory=list)
    org_id: str = "local"

    def sorted_pins(self) -> list[Pin]:
        # Sorted + de-duplicated by (id, version, integrity) — a unit summoned by two
        # parents at the same resolved version contributes one pin, deterministically.
        return sorted(set(self.pins))

    def closure_sha(self) -> str:
        """One sha256 over the sorted pin set — the small reference a run records.

        Independent of ``org_id`` and of pin ordering: identical inputs ⇒ identical
        ``closure_sha`` across machines (acceptance: reproducible resolution).
        """
        payload = [p.to_dict() for p in self.sorted_pins()]
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(blob).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "lockfile_version": LOCKFILE_VERSION,
            "root": self.root_id,
            "org_id": self.org_id,
            "closure_sha": self.closure_sha(),
            "pins": [p.to_dict() for p in self.sorted_pins()],
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> Lockfile:
        """Reconstruct a lockfile from its JSON dict — **data only**, no code executes.

        Validates the recorded ``closure_sha`` against the recomputed one so a hand-edited
        or corrupted lockfile fails closed rather than silently shifting a closure.
        """
        version = d.get("lockfile_version")
        if version != LOCKFILE_VERSION:
            raise ResolutionError(
                f"unsupported lockfile_version {version!r} (expected {LOCKFILE_VERSION})"
            )
        raw_pins = d.get("pins", [])
        if not isinstance(raw_pins, list):
            raise ResolutionError("lockfile 'pins' must be a list")
        pins = [Pin.from_dict(p) for p in raw_pins]
        lock = cls(root_id=str(d.get("root", "")), pins=pins, org_id=str(d.get("org_id", "local")))
        recorded = d.get("closure_sha")
        if recorded is not None and recorded != lock.closure_sha():
            raise ResolutionError(
                f"lockfile closure_sha mismatch: recorded {recorded!r} != computed "
                f"{lock.closure_sha()!r} (corrupted or hand-edited closure)"
            )
        return lock


def resolve(
    root: Candidate,
    source: CandidateSource,
    *,
    org_id: str = "local",
) -> Lockfile:
    """Resolve ``root``'s transitive summoned closure to a pinned :class:`Lockfile`.

    Pure and offline: ``source`` (an injected :class:`CandidateSource`) supplies every
    candidate; this function performs no IO, no model call, and no network access. For
    each ``DefinitionRef`` it parses the version constraint, selects the **highest**
    candidate version satisfying it, and recurses into that candidate's own dependencies.

    Determinism: dependencies are walked in sorted ``(id, version)`` order and the
    resulting pins are sorted in the lockfile, so identical inputs produce an identical
    ``closure_sha`` across machines.

    Fail-closed conditions, all raising :class:`ResolutionError`:

    * an unknown unit (no candidates),
    * no candidate satisfying a constraint,
    * a **conflict** — the same unit already pinned at a different version by another
      requirer (the message names both requirers),
    * a dependency **cycle**.
    """
    # id -> (resolved Candidate, requirer id) for conflict detection + memoization.
    resolved: dict[str, tuple[Candidate, str]] = {}
    on_path: set[str] = set()  # ids on the current DFS path -> cycle detection

    def visit(candidate: Candidate, requirer: str) -> None:
        resolved[candidate.id] = (candidate, requirer)
        on_path.add(candidate.id)
        # Deterministic walk order over this candidate's direct dependencies.
        for dep in sorted(candidate.dependencies, key=lambda r: (r.id, r.version)):
            chosen = _select(dep, source, requirer=candidate.id)
            if chosen.id in on_path:
                cycle = " -> ".join([*on_path, chosen.id])
                raise ResolutionError(f"dependency cycle involving {chosen.id!r}: {cycle}")
            prior = resolved.get(chosen.id)
            if prior is not None and prior[0].version != chosen.version:
                prior_cand, prior_requirer = prior
                raise ResolutionError(
                    f"version conflict for {chosen.id!r}: {prior_requirer!r} requires "
                    f"{prior_cand.version}, {candidate.id!r} requires {chosen.version} "
                    f"(constraint {dep.version!r})"
                )
            if prior is None:
                visit(chosen, requirer=candidate.id)
        on_path.discard(candidate.id)

    visit(root, requirer="<root>")

    pins = [
        Pin(id=c.id, version=str(c.version), integrity="sha256:" + c.content_sha)
        for c, _ in resolved.values()
    ]
    return Lockfile(root_id=root.id, pins=pins, org_id=org_id)


def _select(ref: DefinitionRef, source: CandidateSource, *, requirer: str) -> Candidate:
    """Pick the highest candidate of ``ref.id`` satisfying ``ref.version``. Fails closed."""
    constraint = _Constraint.parse(ref.version)
    candidates = source.candidates(ref.id)
    if not candidates:
        raise ResolutionError(
            f"unknown unit {ref.id!r} (required by {requirer!r}, constraint {ref.version!r})"
        )
    matching = [c for c in candidates if constraint.matches(c.version)]
    if not matching:
        available = ", ".join(str(c.version) for c in candidates)
        raise ResolutionError(
            f"no version of {ref.id!r} satisfies {ref.version!r} "
            f"(required by {requirer!r}; available: {available})"
        )
    return max(matching, key=lambda c: c.version)


# --------------------------------------------------------------------------- io
def write_lockfile(lockfile: Lockfile) -> str:
    """Serialize a lockfile to its canonical JSON text (deterministic, committable)."""
    return json.dumps(lockfile.to_dict(), indent=2, sort_keys=True) + "\n"


def read_lockfile(text: str) -> Lockfile:
    """Parse canonical lockfile JSON back into a :class:`Lockfile` — **data only**.

    Reading a lockfile never executes unit code; it only reconstructs the pin set and
    re-verifies the recorded ``closure_sha``.
    """
    return Lockfile.from_dict(json.loads(text))
