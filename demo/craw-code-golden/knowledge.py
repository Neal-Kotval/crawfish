"""Knowledge composition for the golden Definition (CRA-263 worked example).

Knowledge is attached by **composition**, not as a directory file: build a ``Wiki``, freeze
it, and summon it into the Definition with ``with_context``. The summoned pages reach the
agent as **tainted data** (never instructions) and are **pinned by content hash** — the body
never enters the export checksum. This module is pure (no model call); a test calls
:func:`build_specialized` and asserts the taint + the pin.
"""

from __future__ import annotations

from crawfish.derive import SummonMode, with_context
from crawfish.wiki import TrustTier, Wiki

if __debug__:  # keep the type importable without forcing a runtime dep at module import
    from crawfish.definition.types import Definition


def triage_rubric_wiki() -> Wiki:
    """A small, frozen first-party rubric Wiki — summoned tainted even though TRUSTED."""
    return Wiki().with_page(
        "triage-rubric",
        "P0 = outage; P1 = broken core flow, no workaround; P2 = degraded; P3 = cosmetic.",
        trust=TrustTier.TRUSTED,  # first-party curated; STILL summoned tainted (data)
    )


def build_specialized(base: Definition) -> Definition:
    """Return a new frozen Definition that summons the rubric Wiki read-only.

    ``with_context`` stores a pinned ``SummonRef`` (id + content sha + mode); the rubric body
    is never copied inline, so ``export().checksum`` moves only if the pinned version moves.
    """
    return with_context(base, triage_rubric_wiki(), mode=SummonMode.READONLY)
