"""CRA-239 / SEC-2 — operator-level prompt-injection red-team.

The *behavioural* twin of ALG-7's *static* taint conformance suite. ALG-7 proves
``tainted`` survives every boundary; this proves a concrete injection attempt against
each new fluid surface (Refine feedback, Router/Classifier labels, Verifier/Quorum
verdicts, the learned-guard correction corpus, Rag/Wiki retrieval, generated
artifacts) is **refused by a spine control** — offline, no model call.

A green run is the CI gate: every injection in the corpus is blocked by construction
(fluid stays data; ALG-3 rejects fluid→sink; the F-4 corpus gate quarantines a
fluid-tainted correction; the CL-2 precision gate fails closed; an eval-mode Wiki
refuses mutation). A regression that lets any injection through fails the suite.
"""

from __future__ import annotations

import pytest

from crawfish.testing import (
    RedTeamAttack,
    RedTeamResult,
    assert_all_attacks_blocked,
    redteam_attacks,
    run_redteam,
)

# Every new fluid surface the epic introduced must carry >=1 injection attempt.
_EXPECTED_SURFACES = {
    "refine",
    "router",
    "rag",
    "guard_corpus",
    "generated_artifact",
    "verifier",
}


def test_corpus_covers_every_new_fluid_surface() -> None:
    """Acceptance: each new operator/fluid surface has at least one injection payload."""
    surfaces = {a.surface for a in redteam_attacks()}
    missing = _EXPECTED_SURFACES - surfaces
    assert not missing, f"missing red-team coverage for {missing}"


def test_corpus_is_nonempty_and_well_formed() -> None:
    attacks = redteam_attacks()
    assert attacks, "red-team corpus is empty"
    for a in attacks:
        assert isinstance(a, RedTeamAttack)
        assert a.payload and a.intent and a.control, f"under-specified attack {a.name!r}"


@pytest.mark.parametrize("attack", redteam_attacks(), ids=lambda a: a.name)
def test_each_injection_is_blocked(attack: RedTeamAttack) -> None:
    """Every individual injection attempt is refused by its named spine control."""
    (result,) = run_redteam([attack])
    assert isinstance(result, RedTeamResult)
    assert result.blocked, f"injection NOT blocked on {attack.name}: {result.how}"
    # The refusal is concrete (auditable), not a bare boolean.
    assert result.how


def test_whole_corpus_blocked_is_the_ci_gate() -> None:
    """The CI gate: the full corpus runs and every attempt is blocked."""
    results = assert_all_attacks_blocked()
    assert len(results) == len(redteam_attacks())
    assert all(r.blocked for r in results)


def test_deterministic_offline() -> None:
    """Re-running the corpus yields the identical verdicts (no clock, no model call)."""
    a = [(r.attack.name, r.blocked) for r in run_redteam()]
    b = [(r.attack.name, r.blocked) for r in run_redteam()]
    assert a == b
