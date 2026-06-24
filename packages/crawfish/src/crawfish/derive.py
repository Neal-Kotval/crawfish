"""Shared copy-on-write derivation over a frozen :class:`~crawfish.definition.types.Definition`.

The single, load-bearing content-hash path of Milestone 6 (CRA-223 / DV-0). The Tuner's
content-hash primitives (``_content_sha`` / ``_refreeze`` / ``_with_agents``) once lived
private to :mod:`crawfish.tuner`, but the public Definition-as-variable API (AL-DV1/2/3),
``state_dict`` (AL-T2), and the property algebra all need the **same** content-hash path —
two implementations would drift, a determinism hazard. They are extracted here so the
Tuner and the public API share one law, and :mod:`crawfish.tuner` re-exports the same
function objects (a pure relocation: behaviour-preserving, byte-identical hashing).

Low-dep on purpose (the same lesson as :mod:`crawfish.tune`): only ``pydantic`` /
``hashlib`` / ``json`` plus the Definition types. **No** eval / metrics / batch / runtime
import, so ``crawfish.definition.types`` could import these helpers without a cycle and so
``import crawfish.tuner`` stays cheap.

Copy-on-write contract (CRA-224 / AL-DV1): each ``with_*`` method returns a **new frozen**
Definition (deep, unfrozen ``model_copy`` → structural edit → :func:`refreeze` → a fresh
``Version.sha``); the receiver is **never** mutated. Composing versions the agent (the sha
changes); two structurally-identical compositions collapse to the same sha (idempotent),
any knob diff diverges it. Determinism is pure structural transform — no model call, no
I/O, no wall clock. Security: a ``with_context`` summon enters identity by a **pinned
snapshot hash** (reference-not-embed, no mutable content embedded); consequential knobs
(model / policies / Sink targets) stay static author config, never fluid-derived, and
un-versioned mutation is impossible because every edit copies-then-seals.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from crawfish.core.types import Parameter, Policy
from crawfish.definition.types import AgentSpec, Definition, DefinitionRef
from crawfish.versioning.version import Version

__all__ = [
    "content_sha",
    "refreeze",
    "with_agents",
    "SummonMode",
    "SkillRef",
    "SummonRef",
    "Summonable",
    "with_agent",
    "with_skill",
    "with_context",
    "with_inputs",
    "with_policy",
    # legacy private aliases kept for in-tree callers that imported the underscored names
    "_content_sha",
    "_refreeze",
    "_with_agents",
]


# -- the single content-hash path -------------------------------------------
def content_sha(definition: Definition) -> str:
    """A deterministic content hash over the Definition's knob-bearing payload.

    Delegates to the **canonical** :meth:`Definition.content_sha` (ADR 0017 / F-5), the
    single source of hash truth: it drops the volatile ``version`` and identity ``id``,
    folds in the tunable decode knobs (hash-neutral when None) and a non-empty tune-spec.
    Two structurally identical Definitions collapse to one sha; any knob change diverges —
    which gives each derivation a distinct version (and, for the Tuner, a distinct cassette
    key on replay). Callers do not re-implement the law.
    """
    return definition.content_sha()


def refreeze(base: Definition, mutated: Definition) -> Definition:
    """Return a frozen copy of ``mutated`` carrying a fresh content-hash version.

    A frozen artifact rejects mutation, so derivation never edits in place: each result is
    a new, sealed Definition. The new ``version.sha`` is the content hash, so a result that
    differs from ``base`` in any knob gets a distinct version (and therefore a distinct
    cassette key — no replay collision); an identical result re-hashes to the same sha
    (idempotent). ``base`` is untouched: ``model_copy(deep=True)`` mints a fresh, unfrozen
    ``Version`` object we seal without reaching back into ``base``.
    """
    sha = content_sha(mutated)
    version = Version(major=base.version.major, minor=base.version.minor, sha=sha)
    candidate = mutated.model_copy(update={"version": version}, deep=True)
    candidate.freeze()
    return candidate


def with_agents(base: Definition, agents: Sequence[AgentSpec]) -> Definition:
    """A deep, *unfrozen* copy of ``base`` with its team agents replaced.

    Returns an **unfrozen** draft (fresh ``Version``) — the caller re-seals via
    :func:`refreeze`. The receiver is never mutated.
    """
    team = base.team.model_copy(update={"agents": list(agents)}, deep=True)
    return base.model_copy(update={"team": team, "version": Version()}, deep=True)


# Backwards-compatible private aliases (the names the Tuner used pre-extraction). Same
# function objects — ``crawfish.tuner._refreeze is crawfish.derive.refreeze`` — so no
# second hashing path exists in the tree.
_content_sha = content_sha
_refreeze = refreeze
_with_agents = with_agents


# == CRA-224 — copy-on-write Definition composition (AL-DV1) =================
class SummonMode(str, Enum):
    """How a summoned context unit is carried into a Definition.

    ``READONLY`` is the default and the safe one until F-7 lands ``.readonly()`` /
    ``.mutable()`` narrowing: the summoned unit is reference-only context the agent may
    read, never an instruction surface and never mutated through this Definition.
    """

    READONLY = "readonly"
    MUTABLE = "mutable"


class SkillRef(BaseModel):
    """A versioned pin to a skill the Definition acquires (``with_skill``).

    A skill enters identity by **pinned version**, not embedded content: the ``id`` + the
    frozen ``version`` string fold into the content hash so the composed Definition versions
    when the skill version moves, without copying the skill's mutable body inline.
    """

    model_config = {"frozen": True}

    id: str
    version: str = "0.1"


class SummonRef(BaseModel):
    """A pinned, reference-only handle to a summoned context unit (``with_context``).

    ``{id, version, mode}``: the summoned unit enters the Definition's identity by its
    **pinned version snapshot** (``str(Version)`` at compose time), never by embedding its
    mutable body — so ``export().checksum`` moves iff the pinned version moves. ``mode`` is
    ``"readonly"`` until F-7 lands ``.mutable()`` narrowing; a read-only summon is context
    data the agent may read, never an instruction surface.
    """

    model_config = {"frozen": True}

    id: str
    version: str = "0.1"
    mode: str = SummonMode.READONLY.value


@runtime_checkable
class Summonable(Protocol):
    """A unit that can be summoned into a Definition as pinned, read-only context.

    The structural contract :meth:`Definition.with_context` accepts (ADR 0002 — structural
    typing, never ``isinstance`` on a concrete class): anything carrying an ``id`` and a
    ``version`` (a :class:`Freezable` Definition satisfies it, as does any artifact with the
    two attributes). Its pinned version is snapshotted at compose time — a *moving* pointer
    is ``recall`` (AL-DV2), not this.
    """

    @property
    def id(self) -> str: ...

    @property
    def version(self) -> Version: ...


# A pinned ref carries a stable identity prefix in the shared ``dependencies`` list so a
# skill pin and a summon pin never collide with an ordinary dependency id (and so the two
# kinds round-trip distinctly through ``export()``). The pin folds into ``content_dict``
# (and thus the sha) and into ``export().checksum`` exactly because ``dependencies`` does.
_SKILL_PREFIX = "skill:"
_SUMMON_PREFIX = "summon:"


def with_agent(base: Definition, agent: AgentSpec, *, replace: bool = False) -> Definition:
    """Copy-on-write: return a **new frozen** Definition with ``agent`` added to the team.

    ``replace=True`` swaps an existing agent of the same ``role`` (else appends). The
    receiver is never mutated; the result re-freezes to a fresh ``version.sha`` (the sha
    moves iff a knob actually changed). Composable.
    """
    existing = list(base.team.agents)
    if replace and any(a.role == agent.role for a in existing):
        agents = [agent if a.role == agent.role else a for a in existing]
    else:
        agents = [*existing, agent]
    return refreeze(base, with_agents(base, agents))


def with_skill(base: Definition, skill: SkillRef) -> Definition:
    """Copy-on-write: return a **new frozen** Definition that acquires ``skill`` (a version pin).

    The skill enters identity by its ``{id, version}`` pin folded into the shared
    ``dependencies`` list (reference-not-embed) — so the composed sha versions when the skill
    version moves, without copying the skill body inline. Receiver untouched.
    """
    ref = DefinitionRef(id=f"{_SKILL_PREFIX}{skill.id}", version=skill.version)
    mutated = base.model_copy(
        update={"dependencies": [*base.dependencies, ref], "version": Version()}, deep=True
    )
    return refreeze(base, mutated)


def with_context(
    base: Definition, obj: Summonable, *, mode: SummonMode = SummonMode.READONLY
) -> Definition:
    """Copy-on-write: return a **new frozen** Definition that summons ``obj`` as pinned context.

    Stores only a :class:`SummonRef` (``{id, version, mode}``) — the summoned unit's version
    is **snapshotted at compose time** (a moving pointer is ``recall``). ``export().checksum``
    therefore changes iff the pinned summon version changes. ``mode`` defaults ``readonly``
    until F-7 lands ``.mutable()`` narrowing; a read-only summon is context the agent reads,
    never an instruction surface (security boundary upheld). Receiver untouched.
    """
    ref = DefinitionRef(id=f"{_SUMMON_PREFIX}{obj.id}:{mode.value}", version=str(obj.version))
    mutated = base.model_copy(
        update={"dependencies": [*base.dependencies, ref], "version": Version()}, deep=True
    )
    return refreeze(base, mutated)


def with_inputs(base: Definition, *params: Parameter) -> Definition:
    """Copy-on-write: return a **new frozen** Definition with ``params`` appended to ``inputs``.

    The typed input surface widens; static/fluid taint on each :class:`Parameter` is carried
    through unchanged (this op never widens fluidity). Receiver untouched.
    """
    mutated = base.model_copy(
        update={"inputs": [*base.inputs, *params], "version": Version()}, deep=True
    )
    return refreeze(base, mutated)


def with_policy(base: Definition, policy: Policy) -> Definition:
    """Copy-on-write: return a **new frozen** Definition with ``policy`` added to its assets.

    A policy is **static** consequential config (never fluid-derived). It folds into the
    Definition's assets and thus the content sha. Receiver untouched.
    """
    assets = base.assets.model_copy(update={"policies": [*base.assets.policies, policy]}, deep=True)
    mutated = base.model_copy(update={"assets": assets, "version": Version()}, deep=True)
    return refreeze(base, mutated)
